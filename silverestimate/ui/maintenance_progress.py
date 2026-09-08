"""Modal maintenance with a responsive event loop and worker-owned resources."""

from __future__ import annotations

from typing import Callable

from PySide6.QtCore import Qt, QThread, Slot
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import QDialog, QLabel, QProgressBar, QVBoxLayout, QWidget


class _MaintenanceThread(QThread):
    def __init__(self, operation: Callable[[], object], parent: QWidget) -> None:
        super().__init__(parent)
        self._operation: Callable[[], object] | None = operation
        self.result: object = None
        self.error: Exception | None = None

    def run(self) -> None:
        try:
            assert self._operation is not None
            self.result = self._operation()
        except Exception as exc:
            self.error = exc
        finally:
            # Release closures that may hold the backup password.
            self._operation = None


class MaintenanceProgressDialog(QDialog):
    """Prevent dismissal and conflicting UI actions until the worker has stopped.

    Cancellation is deliberately unavailable during startup upgrades, archive
    publication and restore staging. No QWidgets or caller-owned SQL connections may be used by the job.
    """

    def __init__(
        self,
        operation: Callable[[], object],
        title: str,
        parent: QWidget | None = None,
        *,
        message: str | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setWindowModality(Qt.WindowModality.ApplicationModal)
        self.setWindowFlag(Qt.WindowType.WindowCloseButtonHint, False)
        self.setMinimumWidth(420)
        layout = QVBoxLayout(self)
        label = QLabel(
            message
            or (
                "Processing and validating encrypted data.\n"
                "Please wait until this operation finishes."
            ),
            self,
        )
        layout.addWidget(label)
        progress = QProgressBar(self)
        progress.setRange(0, 0)
        layout.addWidget(progress)
        self._finished = False
        self._worker = _MaintenanceThread(operation, self)
        self._worker.finished.connect(self._complete)

    @Slot()
    def _complete(self) -> None:
        self._worker.wait()
        self._finished = True
        self.accept()

    def done(self, result: int) -> None:
        if self._finished:
            super().done(result)

    def closeEvent(self, event: QCloseEvent) -> None:
        if not self._finished:
            event.ignore()
        else:
            super().closeEvent(event)

    def run_operation(self) -> object:
        self._worker.start()
        self.exec()
        if self._worker.error is not None:
            raise self._worker.error
        return self._worker.result
