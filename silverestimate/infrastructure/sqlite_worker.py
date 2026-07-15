"""SQLite helpers for cooperative background requests."""

from __future__ import annotations

import sqlite3
import threading
from collections.abc import Iterator
from contextlib import contextmanager


@contextmanager
def cancellable_sqlite_connection(
    database_path: str,
    cancel_event: threading.Event,
    *,
    progress_opcodes: int = 1_000,
) -> Iterator[sqlite3.Connection]:
    """Open a worker-local SQLite connection with cooperative cancellation."""
    connection = sqlite3.connect(database_path)
    connection.row_factory = sqlite3.Row
    connection.set_progress_handler(
        lambda: 1 if cancel_event.is_set() else 0,
        max(1, int(progress_opcodes)),
    )
    try:
        yield connection
    finally:
        connection.set_progress_handler(None, 0)
        connection.close()
