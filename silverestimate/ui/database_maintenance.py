"""Responsive modal bridge for exclusive live-database maintenance."""

from __future__ import annotations

import threading
from collections.abc import Callable
from typing import TYPE_CHECKING, TypeVar, cast

from PySide6.QtCore import QObject, Qt, Signal, Slot
from PySide6.QtWidgets import QWidget

from silverestimate.ui.maintenance_progress import MaintenanceProgressDialog

if TYPE_CHECKING:
    from silverestimate.persistence.database_manager import DatabaseManager
    from silverestimate.persistence.database_protocols import MainCommandsDatabase

ResultT = TypeVar("ResultT")


class _OwnerRelease(QObject):
    requested = Signal()

    def __init__(self, callback: Callable[[], None]) -> None:
        super().__init__()
        self._callback = callback
        self._released = threading.Event()
        self._error: Exception | None = None
        self.requested.connect(self._release, Qt.ConnectionType.QueuedConnection)

    def request(self) -> None:
        """Worker-side signal bridge; no UI objects or SQL connections touched."""
        self.requested.emit()
        self._released.wait()
        if self._error is not None:
            raise self._error

    @Slot()
    def _release(self) -> None:
        try:
            self._callback()
        except Exception as exc:
            self._error = exc
        finally:
            self._released.set()


def run_database_maintenance(
    database: MainCommandsDatabase,
    operation: Callable[[DatabaseManager], ResultT],
    title: str,
    parent: QWidget | None = None,
) -> ResultT:
    """Capture the database on the UI thread; return after its writer resumes."""
    job = database.create_maintenance_job()
    bridge = _OwnerRelease(job.release_owner)
    dialog = None
    try:
        dialog = MaintenanceProgressDialog(
            lambda: job.run(operation, bridge.request), title, parent
        )
        return cast(ResultT, dialog.run_operation())
    finally:
        try:
            job.resume_owner()
        finally:
            bridge.deleteLater()
            if dialog is not None:
                dialog.deleteLater()
