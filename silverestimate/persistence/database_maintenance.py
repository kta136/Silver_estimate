"""Exclusive live-database maintenance with separate owner and worker writers."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, TypeVar

from silverestimate.persistence.database_driver import SqlCipherConnectionBroker

if TYPE_CHECKING:
    from silverestimate.persistence.database_manager import DatabaseManager

ResultT = TypeVar("ResultT")


class DatabaseMaintenanceJob:
    """Reserve on the UI thread, run on a worker, resume on the UI thread.

    The worker opens its own session before requesting the UI writer's close.
    Keeping that second connection alive avoids a last-connection checkpoint
    on the UI thread. All checkpoints and heavy work finish on the worker.
    """

    def __init__(self, database: DatabaseManager) -> None:
        if database.conn is None or not database._session.is_owner():
            raise RuntimeError("Database maintenance requires the owner's live writer")
        if database.conn.in_transaction:
            raise RuntimeError(
                "Finish the current database transaction before maintenance"
            )
        self._database = database
        self._broker = database._broker
        self._broker.reserve_maintenance()
        self._worker_database: DatabaseManager | None = None
        self._started = False
        self._resumed = False

    def release_owner(self) -> None:
        """Called by a queued UI slot once the worker writer is ready."""
        database = self._database
        if not database._session.is_owner() or database.conn is None:
            raise RuntimeError("The database writer owner changed during maintenance")
        if database.conn.in_transaction:
            raise RuntimeError("A database transaction started during maintenance")
        # No explicit checkpoint: the worker connection keeps the WAL open.
        database.conn.close()
        database.conn = None
        database.cursor = None
        database._session.clear()

    def run(
        self,
        operation: Callable[[DatabaseManager], ResultT],
        release_owner: Callable[[], None],
    ) -> ResultT:
        if self._started or self._resumed:
            raise RuntimeError("Database maintenance jobs can only run once")
        self._started = True
        self._broker.drain_readers()
        original = self._database
        # Initialize a distinct manager without replaying startup recovery/scans.
        # Its writer is opened, used and closed exclusively on this worker.
        worker = type(original).__new__(type(original))
        worker._initialize_state(original.database_path, original._device_secret)
        worker.key = original.key
        worker.database_salt = original.database_salt
        worker.open_status = original.open_status
        worker._item_cache_controller = original._item_cache_controller
        worker._broker = SqlCipherConnectionBroker(
            worker.database_path,
            worker.key,
            database_salt=worker.database_salt,
            logger=worker.logger,
        )
        self._worker_database = worker
        try:
            worker.conn, worker.driver_identity = worker._broker.open_writer()
            worker._bind_connection()
            release_owner()
            try:
                result = operation(worker)
                if worker.conn is not None and worker.conn.in_transaction:
                    raise RuntimeError(
                        "Maintenance left an unfinished database transaction"
                    )
                return result
            except BaseException:
                if worker.conn is not None:
                    worker.conn.rollback()
                raise
        finally:
            try:
                worker.close()
            finally:
                if worker.conn is not None:
                    worker._discard_connection()

    def resume_owner(self) -> None:
        """After worker termination, restore the writer and unlock readers."""
        if self._resumed:
            raise RuntimeError("Database maintenance was already resumed")
        self._resumed = True
        original = self._database
        worker = self._worker_database
        if original.conn is None:
            if worker is not None:
                original.key = worker.key
                original.database_salt = worker.database_salt
                original.last_error = worker.last_error
                self._broker.replace_key(worker.key, database_salt=worker.database_salt)
            try:
                original.conn, original.driver_identity = self._broker.open_writer()
                original._bind_connection()
            except Exception as exc:
                original._discard_connection()
                # Keep readers blocked when the live writer cannot be recovered.
                raise RuntimeError(
                    "Could not reopen the database after maintenance. Restart the application."
                ) from exc
        self._broker.release_maintenance()
