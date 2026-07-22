"""SQLite helpers for cooperative background requests."""

from __future__ import annotations

import threading
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any, Callable


@contextmanager
def cancellable_sqlite_connection(
    connection_factory: Callable[[threading.Event | None], Any],
    cancel_event: threading.Event,
    *,
    progress_opcodes: int = 1_000,
) -> Iterator[Any]:
    """Open a worker-local keyed connection with cooperative cancellation."""
    del progress_opcodes
    connection = connection_factory(cancel_event)
    try:
        yield connection
    finally:
        connection.close()
