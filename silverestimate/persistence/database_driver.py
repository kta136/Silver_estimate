"""The only production database-driver boundary.

All application database connections are keyed before the first schema read.  The
standard-library sqlite3 module is intentionally not imported here.
"""

from __future__ import annotations

import functools
import logging
import threading
import time
from collections.abc import Callable
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator, TypeAlias

try:
    from silverestimate.persistence import apsw_dbapi
except ImportError as exc:  # pragma: no cover - exercised by package smoke tests
    dbapi: Any = None
    _IMPORT_ERROR: BaseException | None = exc
else:
    dbapi = apsw_dbapi
    _IMPORT_ERROR = None


# SQLite3 Multiple Ciphers reads and writes the SQLCipher 4 file format.
EXPECTED_CIPHER = "sqlcipher"
EXPECTED_SQLCIPHER_FORMAT = 4
EXPECTED_TEMP_STORE = "TEMP_STORE=2"
EXPECTED_THREADSAFE = "THREADSAFE=1"
DEFAULT_CACHE_KIB = 20_000
SQLCIPHER_SALT_BYTES = 16


class DriverUnavailableError(RuntimeError):
    """The encrypted SQLite runtime is missing or is not encrypting as required."""


class DatabaseAuthenticationError(RuntimeError):
    """The supplied raw key did not authenticate the encrypted database."""


class MaintenanceBusyError(RuntimeError):
    """A maintenance operation could not drain active readers."""


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
    cipher_library: str
    sqlite_version: str
    compile_options: frozenset[str]


@functools.cache
def _cipher_library() -> str:
    """Name the cipher build, or fail when APSW was built without one.

    Plain APSW ignores the key pragmas and would create a plaintext database.
    """
    probe = dbapi.connect(":memory:")
    try:
        return str(probe.execute("SELECT sqlite3mc_version()").fetchone()[0])
    except dbapi.OperationalError as exc:
        raise DriverUnavailableError(
            "The installed APSW build has no SQLite3 Multiple Ciphers support"
        ) from exc
    finally:
        probe.close()


def require_driver() -> Any:
    if dbapi is None:
        raise DriverUnavailableError(
            "The apsw-sqlite3mc runtime is not installed"
        ) from _IMPORT_ERROR
    _cipher_library()
    return dbapi


def _quote_raw_key(key: bytes, database_salt: bytes | None = None) -> str:
    if len(key) != 32:
        raise ValueError("SQLCipher raw keys must contain exactly 32 bytes")
    if database_salt is not None and len(database_salt) != SQLCIPHER_SALT_BYTES:
        raise ValueError("SQLCipher database salts must contain exactly 16 bytes")
    payload = key if database_salt is None else key + database_salt
    return f"\"x'{payload.hex()}'\""


def _pragma_scalar(connection: Connection, pragma: str) -> str:
    row = connection.execute(f"PRAGMA {pragma}").fetchone()
    if not row or row[0] is None:
        return ""
    return str(row[0])


def verify_driver(connection: Connection) -> DriverIdentity:
    """Fail closed unless this keyed connection encrypts in the SQLCipher format."""
    cipher = _pragma_scalar(connection, "cipher")
    cipher_format = _pragma_scalar(connection, "legacy")
    # Only a connection with an attached codec reports a key salt.
    key_salt = connection.execute(
        "SELECT sqlite3mc_codec_data('cipher_salt')"
    ).fetchone()[0]
    sqlite_version = str(connection.execute("SELECT sqlite_version()").fetchone()[0])
    options = frozenset(
        str(row[0]) for row in connection.execute("PRAGMA compile_options")
    )
    errors: list[str] = []
    if cipher != EXPECTED_CIPHER or cipher_format != str(EXPECTED_SQLCIPHER_FORMAT):
        errors.append(
            f"SQLCipher format {EXPECTED_SQLCIPHER_FORMAT} required; "
            f"connection uses {cipher or 'no cipher'} format {cipher_format or '?'}"
        )
    if not key_salt:
        errors.append("encryption is not active")
    if EXPECTED_TEMP_STORE not in options:
        errors.append(f"missing {EXPECTED_TEMP_STORE}")
    if EXPECTED_THREADSAFE not in options:
        errors.append(f"missing {EXPECTED_THREADSAFE}")
    if errors:
        raise DriverUnavailableError("Invalid SQLCipher runtime: " + "; ".join(errors))
    return DriverIdentity(_cipher_library(), sqlite_version, options)


def _apply_key(
    connection: Connection, raw_key: bytes, database_salt: bytes | None
) -> None:
    # The library's own default cipher is not SQLCipher, so select it first.
    connection.execute(f"PRAGMA cipher = '{EXPECTED_CIPHER}'")
    connection.execute(f"PRAGMA legacy = {EXPECTED_SQLCIPHER_FORMAT}")
    connection.execute(f"PRAGMA key = {_quote_raw_key(raw_key, database_salt)}")


def configure_connection(
    connection: Connection,
    *,
    raw_key: bytes,
    database_salt: bytes | None = None,
    writer: bool,
    authenticate: bool = True,
) -> DriverIdentity:
    """Key, authenticate, and harden one connection in the required order."""
    _apply_key(connection, raw_key, database_salt)
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
        # Flush each committed WAL transaction before reporting save success.
        connection.execute("PRAGMA synchronous = FULL")
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
ReadConnectionFactory: TypeAlias = Callable[[], ReadConnection]


class SqlCipherConnectionBroker:
    """Own the raw key and serialize live readers against maintenance work."""

    def __init__(
        self,
        database_path: str | Path,
        raw_key: bytes,
        *,
        database_salt: bytes | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        self.database_path = str(database_path)
        self._raw_key = bytes(raw_key)
        if database_salt is not None and len(database_salt) != SQLCIPHER_SALT_BYTES:
            raise ValueError("SQLCipher database salts must contain exactly 16 bytes")
        self._database_salt = (
            bytes(database_salt) if database_salt is not None else None
        )
        self._logger = logger or logging.getLogger(__name__)
        self._condition = threading.Condition()
        self._maintenance = False
        self._readers: set[_ManagedReadConnection] = set()
        self._reader_interrupt = threading.Event()

    @property
    def raw_key(self) -> bytes:
        return self._raw_key

    @property
    def database_salt(self) -> bytes | None:
        return self._database_salt

    def replace_key(
        self, raw_key: bytes, *, database_salt: bytes | None = None
    ) -> None:
        if len(raw_key) != 32:
            raise ValueError("SQLCipher key must be 32 bytes")
        if database_salt is not None and len(database_salt) != SQLCIPHER_SALT_BYTES:
            raise ValueError("SQLCipher database salts must contain exactly 16 bytes")
        self._raw_key = bytes(raw_key)
        self._database_salt = (
            bytes(database_salt) if database_salt is not None else None
        )

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
                database_salt=self._database_salt,
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
        self, cancel_event: threading.Event | None = None
    ) -> ReadConnection:
        with self._condition:
            if self._maintenance:
                raise MaintenanceBusyError("Database maintenance is in progress")
            driver = require_driver()
            connection = driver.connect(self.database_path, timeout=15.0)
            try:
                configure_connection(
                    connection,
                    raw_key=self._raw_key,
                    database_salt=self._database_salt,
                    writer=False,
                    authenticate=True,
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

    @property
    def maintenance_active(self) -> bool:
        with self._condition:
            return self._maintenance

    def reserve_maintenance(self) -> None:
        """Block new readers immediately; draining happens on the worker."""
        with self._condition:
            if self._maintenance:
                raise MaintenanceBusyError("Database maintenance is already active")
            self._maintenance = True
            self._reader_interrupt.set()

    def drain_readers(self, *, timeout_seconds: float = 15.0) -> None:
        deadline = time.monotonic() + timeout_seconds
        with self._condition:
            if not self._maintenance:
                raise MaintenanceBusyError("Database maintenance was not reserved")
            while self._readers:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise MaintenanceBusyError(
                        f"Timed out draining {len(self._readers)} database reader(s)"
                    )
                self._condition.wait(min(remaining, 0.25))

    def release_maintenance(self) -> None:
        with self._condition:
            self._reader_interrupt.clear()
            self._maintenance = False
            self._condition.notify_all()

    @contextmanager
    def maintenance(self, *, timeout_seconds: float = 15.0) -> Iterator[None]:
        """Block new readers, cancel active queries, and wait for them to drain."""
        self.reserve_maintenance()
        try:
            self.drain_readers(timeout_seconds=timeout_seconds)
            yield
        finally:
            self.release_maintenance()


def export_database(
    source: Connection,
    target_path: str | Path,
    target_key: bytes,
    *,
    target_salt: bytes | None = None,
) -> None:
    """Copy the open source into a different-key SQLCipher database."""
    target = require_driver().connect(Path(target_path).resolve())
    try:
        _apply_key(target, target_key, target_salt)
        source.backup(target)
    finally:
        target.close()


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
    "ReadConnectionFactory",
    "Row",
    "SQLCIPHER_SALT_BYTES",
    "SqlCipherConnectionBroker",
    "configure_connection",
    "export_database",
    "require_driver",
    "verify_driver",
]
