"""The only production database-driver boundary.

All application database connections are keyed before the first schema read.  The
standard-library sqlite3 module is intentionally not imported here.
"""

from __future__ import annotations

import logging
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator, Protocol, TypeAlias

try:
    from sqlcipher3 import dbapi2 as dbapi
except ImportError as exc:  # pragma: no cover - exercised by package smoke tests
    dbapi = None
    _IMPORT_ERROR: BaseException | None = exc
else:
    _IMPORT_ERROR = None


EXPECTED_SQLCIPHER_SERIES = "4.17."
EXPECTED_TEMP_STORE = "TEMP_STORE=2"
EXPECTED_THREADSAFE = "THREADSAFE=1"
DEFAULT_CACHE_KIB = 20_000


class DriverUnavailableError(RuntimeError):
    """The controlled SQLCipher runtime is missing or has the wrong build."""


class DatabaseAuthenticationError(RuntimeError):
    """The supplied raw key did not authenticate the encrypted database."""


class MaintenanceBusyError(RuntimeError):
    """A maintenance operation could not drain active readers."""


class CancelFlag(Protocol):
    def is_set(self) -> bool: ...


Connection: TypeAlias = Any
Cursor: TypeAlias = Any

if dbapi is not None:
    Row = dbapi.Row
    Error = dbapi.Error
    DatabaseError = dbapi.DatabaseError
    IntegrityError = dbapi.IntegrityError
    OperationalError = dbapi.OperationalError
else:  # Import-safe aliases allow startup to report a typed package failure.
    Row = Any
    Error = Exception
    DatabaseError = Exception
    IntegrityError = Exception
    OperationalError = Exception


@dataclass(frozen=True)
class DriverIdentity:
    sqlcipher_version: str
    sqlite_version: str
    crypto_provider: str
    compile_options: frozenset[str]


def require_driver() -> Any:
    if dbapi is None:
        raise DriverUnavailableError(
            "The controlled sqlcipher3 runtime is not installed"
        ) from _IMPORT_ERROR
    return dbapi


def _quote_raw_key(key: bytes) -> str:
    if len(key) != 32:
        raise ValueError("SQLCipher raw keys must contain exactly 32 bytes")
    return f"\"x'{key.hex()}'\""


def _pragma_scalar(connection: Connection, pragma: str) -> str:
    row = connection.execute(f"PRAGMA {pragma}").fetchone()
    if not row or row[0] is None:
        return ""
    return str(row[0])


def verify_driver(connection: Connection) -> DriverIdentity:
    """Fail closed when the loaded extension differs from the controlled build."""
    cipher_version = _pragma_scalar(connection, "cipher_version")
    sqlite_version = str(connection.execute("SELECT sqlite_version()").fetchone()[0])
    provider = _pragma_scalar(connection, "cipher_provider")
    status = _pragma_scalar(connection, "cipher_status")
    options = frozenset(
        str(row[0]) for row in connection.execute("PRAGMA compile_options")
    )
    errors: list[str] = []
    if not cipher_version:
        errors.append("codec/cipher_version unavailable")
    elif not cipher_version.startswith(EXPECTED_SQLCIPHER_SERIES):
        errors.append(
            f"SQLCipher {EXPECTED_SQLCIPHER_SERIES}x required; loaded {cipher_version}"
        )
    if status not in {"1", "true", "on"}:
        errors.append(f"cipher_status is not enabled ({status or 'missing'})")
    if EXPECTED_TEMP_STORE not in options:
        errors.append(f"missing {EXPECTED_TEMP_STORE}")
    if EXPECTED_THREADSAFE not in options:
        errors.append(f"missing {EXPECTED_THREADSAFE}")
    if not provider:
        errors.append("crypto provider unavailable")
    if errors:
        raise DriverUnavailableError("Invalid SQLCipher runtime: " + "; ".join(errors))
    return DriverIdentity(cipher_version, sqlite_version, provider, options)


def configure_connection(
    connection: Connection,
    *,
    raw_key: bytes,
    writer: bool,
    authenticate: bool = True,
) -> DriverIdentity:
    """Key, authenticate, and harden one connection in the required order."""
    connection.execute(f"PRAGMA key = {_quote_raw_key(raw_key)}")
    try:
        identity = verify_driver(connection)
        if authenticate:
            connection.execute("SELECT count(*) FROM sqlite_master").fetchone()
    except DatabaseError as exc:
        raise DatabaseAuthenticationError(
            "Wrong password or corrupt SQLCipher database"
        ) from exc
    connection.execute("PRAGMA foreign_keys = ON")
    if writer:
        connection.execute("PRAGMA journal_mode = WAL").fetchone()
        connection.execute("PRAGMA synchronous = NORMAL")
    else:
        connection.execute("PRAGMA query_only = ON")
    connection.execute("PRAGMA temp_store = MEMORY")
    connection.execute(f"PRAGMA cache_size = -{DEFAULT_CACHE_KIB}")
    connection.execute("PRAGMA mmap_size = 0")
    connection.row_factory = Row
    return identity


class _ManagedReadConnection:
    """DB-API proxy that reliably unregisters a broker reader on close."""

    def __init__(self, broker: "SqlCipherConnectionBroker", connection: Connection):
        self._broker = broker
        self._connection = connection
        self._closed = False

    def __getattr__(self, name: str) -> Any:
        return getattr(self._connection, name)

    def __enter__(self) -> "_ManagedReadConnection":
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        self.close()

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        try:
            self._connection.close()
        finally:
            self._broker._reader_closed(self)


ReadConnection: TypeAlias = _ManagedReadConnection


class SqlCipherConnectionBroker:
    """Own the raw key and serialize live readers against maintenance work."""

    def __init__(
        self,
        database_path: str | Path,
        raw_key: bytes,
        *,
        logger: logging.Logger | None = None,
    ) -> None:
        self.database_path = str(database_path)
        self._raw_key = bytes(raw_key)
        self._logger = logger or logging.getLogger(__name__)
        self._condition = threading.Condition()
        self._maintenance = False
        self._readers: set[_ManagedReadConnection] = set()
        self._reader_interrupt = threading.Event()

    @property
    def raw_key(self) -> bytes:
        return self._raw_key

    def replace_key(self, raw_key: bytes) -> None:
        if len(raw_key) != 32:
            raise ValueError("SQLCipher key must be 32 bytes")
        self._raw_key = bytes(raw_key)

    def open_writer(self, *, create: bool = False) -> tuple[Connection, DriverIdentity]:
        driver = require_driver()
        path = Path(self.database_path)
        if not create and not path.is_file():
            raise FileNotFoundError(path)
        connection = driver.connect(self.database_path, timeout=15.0)
        try:
            identity = configure_connection(
                connection,
                raw_key=self._raw_key,
                writer=True,
                authenticate=not create,
            )
            if create:
                connection.execute("SELECT count(*) FROM sqlite_master").fetchone()
            return connection, identity
        except BaseException:
            connection.close()
            raise

    def open_read_connection(
        self, cancel_event: CancelFlag | None = None
    ) -> ReadConnection:
        with self._condition:
            if self._maintenance:
                raise MaintenanceBusyError("Database maintenance is in progress")
            driver = require_driver()
            connection = driver.connect(self.database_path, timeout=15.0)
            try:
                configure_connection(
                    connection, raw_key=self._raw_key, writer=False, authenticate=True
                )
            except BaseException:
                connection.close()
                raise
            managed = _ManagedReadConnection(self, connection)
            self._readers.add(managed)

        def _cancelled() -> int:
            return int(
                self._reader_interrupt.is_set()
                or (cancel_event is not None and cancel_event.is_set())
            )

        connection.set_progress_handler(_cancelled, 1_000)
        return managed

    def _reader_closed(self, reader: _ManagedReadConnection) -> None:
        with self._condition:
            self._readers.discard(reader)
            self._condition.notify_all()

    @contextmanager
    def maintenance(self, *, timeout_seconds: float = 15.0) -> Iterator[None]:
        """Block new readers, cancel active queries, and wait for them to drain."""
        deadline = time.monotonic() + timeout_seconds
        with self._condition:
            if self._maintenance:
                raise MaintenanceBusyError("Database maintenance is already active")
            self._maintenance = True
            self._reader_interrupt.set()
            while self._readers:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    self._maintenance = False
                    self._reader_interrupt.clear()
                    self._condition.notify_all()
                    raise MaintenanceBusyError(
                        f"Timed out draining {len(self._readers)} database reader(s)"
                    )
                self._condition.wait(min(remaining, 0.25))
        try:
            yield
        finally:
            with self._condition:
                self._reader_interrupt.clear()
                self._maintenance = False
                self._condition.notify_all()


def export_database(
    source: Connection,
    target_path: str | Path,
    target_key: bytes,
    *,
    schema: str = "silver_export",
) -> None:
    """Copy the open source into a different-key SQLCipher database."""
    target = str(Path(target_path).resolve()).replace("'", "''")
    source.execute(
        f"ATTACH DATABASE '{target}' AS {schema} KEY {_quote_raw_key(target_key)}"
    )
    try:
        source.execute(f"SELECT sqlcipher_export('{schema}')").fetchone()
    finally:
        source.execute(f"DETACH DATABASE {schema}")


__all__ = [
    "Connection",
    "Cursor",
    "DatabaseAuthenticationError",
    "DatabaseError",
    "DriverIdentity",
    "DriverUnavailableError",
    "Error",
    "IntegrityError",
    "MaintenanceBusyError",
    "OperationalError",
    "ReadConnection",
    "Row",
    "SqlCipherConnectionBroker",
    "configure_connection",
    "export_database",
    "require_driver",
    "verify_driver",
]
