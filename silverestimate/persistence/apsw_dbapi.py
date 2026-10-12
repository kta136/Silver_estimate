"""The standard-library ``sqlite3`` interface over APSW.

``apsw-sqlite3mc`` supplies the encrypted SQLite engine, but APSW has its own API.
Repositories are written against ``sqlite3`` (unit tests hand them plain
``sqlite3`` connections), so this module reproduces the part of that interface the
application uses: rows, cursors, the exception hierarchy, and transactions that
open implicitly before a data change and end on ``commit()`` or ``rollback()``.
"""

from __future__ import annotations

import threading
from collections.abc import Callable, Iterable, Iterator, Mapping, Sequence
from itertools import islice
from pathlib import Path
from types import TracebackType
from typing import Any, Final, TypeAlias

import apsw

Bindings: TypeAlias = Sequence[Any] | Mapping[str, Any]
RowFactory: TypeAlias = Callable[["Cursor", tuple[Any, ...]], Any]


class Error(Exception):
    """Base class for every database error."""


class DatabaseError(Error):
    """The database rejected an operation or is not usable."""


class IntegrityError(DatabaseError):
    """A constraint was violated."""


class OperationalError(DatabaseError):
    """The statement failed for a reason outside the caller's data."""


class ProgrammingError(DatabaseError):
    """The connection or cursor was misused."""


_INTEGRITY: Final = (apsw.ConstraintError, apsw.MismatchError)
_PROGRAMMING: Final = (
    apsw.BindingsError,
    apsw.ConnectionClosedError,
    apsw.CursorClosedError,
    apsw.MisuseError,
    apsw.RangeError,
)
_OPERATIONAL: Final = (
    apsw.AbortError,
    apsw.BusyError,
    apsw.CantOpenError,
    apsw.EmptyError,
    apsw.FullError,
    apsw.IOError,
    apsw.InterruptError,
    apsw.LockedError,
    apsw.PermissionsError,
    apsw.ProtocolError,
    apsw.ReadOnlyError,
    apsw.SchemaChangeError,
    apsw.SQLError,
)
_DATA_CHANGES: Final = ("INSERT", "UPDATE", "DELETE", "REPLACE")
_DONE: Final = object()


def _translated(exc: apsw.Error) -> DatabaseError:
    """Map an APSW error onto the class ``sqlite3`` raises for the same result."""
    kind: type[DatabaseError]
    if isinstance(exc, _INTEGRITY):
        kind = IntegrityError
    elif isinstance(exc, _OPERATIONAL):
        kind = OperationalError
    elif isinstance(exc, _PROGRAMMING):
        kind = ProgrammingError
    else:
        kind = DatabaseError
    return kind(str(exc))


def _changes_data(sql: str) -> bool:
    return sql.lstrip()[:7].upper().startswith(_DATA_CHANGES)


class Row:
    """One result row, readable by position or by column name."""

    __slots__ = ("_names", "_values")

    def __init__(self, cursor: Cursor, values: tuple[Any, ...]) -> None:
        self._names = cursor._names
        self._values = values

    def keys(self) -> list[str]:
        return list(self._names)

    def __getitem__(self, key: int | slice | str) -> Any:
        if not isinstance(key, str):
            return self._values[key]
        try:
            return self._values[self._names.index(key)]
        except ValueError:
            folded = key.lower()
            for position, name in enumerate(self._names):
                if name.lower() == folded:
                    return self._values[position]
        raise IndexError("No item with that key")

    def __iter__(self) -> Iterator[Any]:
        return iter(self._values)

    def __len__(self) -> int:
        return len(self._values)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Row):
            return NotImplemented
        return self._names == other._names and self._values == other._values

    def __hash__(self) -> int:
        return hash((self._names, self._values))

    def __repr__(self) -> str:
        return f"<Row {dict(zip(self._names, self._values, strict=True))!r}>"


class Cursor:
    def __init__(self, connection: Connection) -> None:
        self.connection = connection
        self.row_factory = connection.row_factory
        self.description: tuple[tuple[Any, ...], ...] | None = None
        self.lastrowid: int | None = None
        self.rowcount = -1
        try:
            self._native = connection._native.cursor()
        except apsw.Error as exc:
            raise _translated(exc) from exc
        self._names: tuple[str, ...] = ()
        # sqlite3 steps to the following row as it hands one out, which finishes a
        # statement on its last row; an unfinished one blocks checkpoints and DDL.
        self._ahead: Any = _DONE

    def execute(self, sql: str, parameters: Bindings = ()) -> Cursor:
        self.connection._check_thread()
        native = self.connection._native
        changes_data = _changes_data(sql)
        try:
            if changes_data and not native.in_transaction:
                native.execute("BEGIN")
            self._native.execute(sql, parameters)
            self._describe()
            self._ahead = next(self._native, _DONE)
        except apsw.Error as exc:
            self._ahead = _DONE
            raise _translated(exc) from exc
        if changes_data:
            self.rowcount = native.changes()
            self.lastrowid = native.last_insert_rowid()
        else:
            self.rowcount = -1
        return self

    def executemany(self, sql: str, seq_of_parameters: Iterable[Bindings]) -> Cursor:
        self.connection._check_thread()
        native = self.connection._native
        changes_data = _changes_data(sql)
        changed = 0
        self._ahead = _DONE
        self.description = None
        try:
            if changes_data and not native.in_transaction:
                native.execute("BEGIN")
            for parameters in seq_of_parameters:
                self._native.execute(sql, parameters)
                changed += native.changes()
        except apsw.Error as exc:
            raise _translated(exc) from exc
        self.rowcount = changed if changes_data else -1
        return self

    def _describe(self) -> None:
        try:
            columns = self._native.description
        except apsw.ExecutionCompleteError:
            # Already finished, so it produced no rows to describe.
            self.description = None
            return
        self._names = tuple(column[0] for column in columns)
        self.description = tuple((name, *(None,) * 6) for name in self._names)

    def __iter__(self) -> Iterator[Any]:
        return self

    def __next__(self) -> Any:
        self.connection._check_thread()
        row = self._ahead
        if row is _DONE:
            raise StopIteration
        try:
            self._ahead = next(self._native, _DONE)
        except apsw.Error as exc:
            self._ahead = _DONE
            raise _translated(exc) from exc
        return row if self.row_factory is None else self.row_factory(self, row)

    def fetchone(self) -> Any:
        return next(self, None)

    def fetchmany(self, size: int = 1) -> list[Any]:
        return list(islice(self, size))

    def fetchall(self) -> list[Any]:
        return list(self)

    def close(self) -> None:
        self.connection._check_thread()
        self._ahead = _DONE
        self._native.close(True)


class Connection:
    def __init__(self, native: apsw.Connection) -> None:
        self._native = native
        self._thread = threading.get_ident()
        self.row_factory: RowFactory | None = None

    def _check_thread(self) -> None:
        # APSW would serialise another thread's calls into this one's transaction.
        if threading.get_ident() != self._thread:
            raise ProgrammingError(
                "SQLite objects created in a thread can only be used in that same "
                f"thread. The object was created in thread id {self._thread} and "
                f"this is thread id {threading.get_ident()}."
            )

    def __enter__(self) -> Connection:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        if exc_type is None:
            self.commit()
        else:
            self.rollback()

    @property
    def in_transaction(self) -> bool:
        try:
            return self._native.in_transaction
        except apsw.Error as exc:
            raise _translated(exc) from exc

    @property
    def total_changes(self) -> int:
        return self._native.total_changes()

    def cursor(self) -> Cursor:
        self._check_thread()
        return Cursor(self)

    def execute(self, sql: str, parameters: Bindings = ()) -> Cursor:
        return Cursor(self).execute(sql, parameters)

    def executemany(self, sql: str, seq_of_parameters: Iterable[Bindings]) -> Cursor:
        return Cursor(self).executemany(sql, seq_of_parameters)

    def commit(self) -> None:
        self._end_transaction("COMMIT")

    def rollback(self) -> None:
        self._end_transaction("ROLLBACK")

    def _end_transaction(self, statement: str) -> None:
        self._check_thread()
        try:
            if self._native.in_transaction:
                self._native.execute(statement)
        except apsw.Error as exc:
            raise _translated(exc) from exc

    def create_function(
        self, name: str, narg: int, func: Callable[..., Any] | None
    ) -> None:
        self._native.create_scalar_function(name, func, narg)

    def set_progress_handler(
        self, progress_handler: Callable[[], Any] | None, n: int
    ) -> None:
        self._native.set_progress_handler(progress_handler, n)

    def set_trace_callback(self, trace_callback: Callable[[str], Any] | None) -> None:
        """Report each statement, with its bound values filled in, as it starts."""
        if trace_callback is None:
            self._native.exec_trace = None
            return

        def trace(cursor: apsw.Cursor, sql: str, bindings: Any) -> bool:
            trace_callback(cursor.expanded_sql)
            return True

        self._native.exec_trace = trace

    def backup(self, target: Connection) -> None:
        """Replace ``target``'s contents with a consistent copy of this database."""
        self._check_thread()
        try:
            with target._native.backup("main", self._native, "main") as copy:
                complete = copy.step(-1)
        except apsw.Error as exc:
            raise _translated(exc) from exc
        if not complete:
            raise OperationalError("The database copy did not complete")

    def close(self) -> None:
        self._check_thread()
        try:
            self._native.close()
        except apsw.Error as exc:
            raise _translated(exc) from exc


def connect(database: str | Path, timeout: float = 5.0) -> Connection:
    try:
        native = apsw.Connection(str(database))
        native.set_busy_timeout(int(timeout * 1000))
    except apsw.Error as exc:
        raise _translated(exc) from exc
    return Connection(native)
