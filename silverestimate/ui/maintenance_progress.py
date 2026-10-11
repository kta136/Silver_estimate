"""Modal maintenance with a responsive event loop and worker-owned resources."""

from __future__ import annotations

from typing import Callable

from PySide6.QtCore import Qt, QThread, QTimer, Slot
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
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(8)
        # The window has no close button, so it says what is running and
        # that it will go away by itself.
        heading = QLabel(title, self)
        heading.setStyleSheet("font-weight: 700;")
        layout.addWidget(heading)
        label = QLabel(
            message
            or (
                "Working on the encrypted data and checking the result.\n"
                "This window closes by itself when it is done."
            ),
            self,
        )
        label.setWordWrap(True)
        layout.addWidget(label)
        progress = QProgressBar(self)
        progress.setRange(0, 0)
        progress.setTextVisible(False)
        layout.addWidget(progress)
        self._elapsed_label = QLabel("", self)
        self._elapsed_label.setStyleSheet("color: #526176;")
        layout.addWidget(self._elapsed_label)
        self._elapsed_seconds = 0
        self._elapsed_timer = QTimer(self)
        self._elapsed_timer.setInterval(1000)
        self._elapsed_timer.timeout.connect(self._tick)
        self._finished = False
        self._worker = _MaintenanceThread(operation, self)
        self._worker.finished.connect(self._complete)

    def _tick(self) -> None:
        self._elapsed_seconds += 1
        self._elapsed_label.setText(f"{self._elapsed_seconds} s")

    @Slot()
    def _complete(self) -> None:
        self._worker.wait()
        self._elapsed_timer.stop()
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
        self._elapsed_timer.start()
        self.exec()
        if self._worker.error is not None:
            raise self._worker.error
        return self._worker.result
