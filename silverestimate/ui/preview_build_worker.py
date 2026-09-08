"""Reusable, latest-request-only preview preparation with GUI-owned delivery."""

from __future__ import annotations

import threading
from collections.abc import Callable
from dataclasses import dataclass
from typing import cast

from PySide6.QtCore import QObject, Qt, Slot
from PySide6.QtWidgets import QProgressDialog, QWidget
from shiboken6 import isValid

from silverestimate.infrastructure.latest_request_runner import (
    LatestRequestRunner,
    RequestCancelledError,
)

from .print_payload_builder import PrintPreviewPayload


@dataclass(frozen=True)
class _PreviewRequest:
    build: Callable[[], PrintPreviewPayload | None]


def _build_preview(
    request: _PreviewRequest, cancelled: threading.Event
) -> PrintPreviewPayload | None:
    if cancelled.is_set():
        raise RequestCancelledError
    payload = request.build()
    if cancelled.is_set():
        raise RequestCancelledError
    return payload


class PreviewBuildController(QObject):
    """Own one lazy worker, one pending replacement, progress and current callbacks.

    Builders use captured data and must not access GUI widgets or the main writer.
    Cancellation suppresses delivery; a running pure build finishes cooperatively.
    """

    def __init__(
        self,
        owner: QWidget,
        *,
        message: str = "Preparing print preview...",
        modal: bool = False,
    ) -> None:
        super().__init__(owner)
        self._owner = owner
        self._message = message
        self._modal = modal
        self._runner: (
            LatestRequestRunner[_PreviewRequest, PrintPreviewPayload | None] | None
        ) = None
        self._progress: QProgressDialog | None = None
        self._callbacks: (
            tuple[Callable[[PrintPreviewPayload], object], Callable[[str], object]]
            | None
        ) = None
        self._empty_message = ""
        self._closed = False
        owner.destroyed.connect(self._owner_destroyed)

    def start(
        self,
        build: Callable[[], PrintPreviewPayload | None],
        *,
        on_ready: Callable[[PrintPreviewPayload], object],
        on_error: Callable[[str], object],
        empty_message: str,
    ) -> None:
        if self._closed:
            return
        if self._runner is None:
            # No Qt parent: a build may outlive the closing screen. shutdown(0)
            # suppresses late delivery; the Python worker retains its runner until exit.
            self._runner = LatestRequestRunner(
                _build_preview, name="print-preview-builder"
            )
            self._runner.result.connect(self._ready)
            self._runner.failed.connect(self._failed)
            self._runner.settled.connect(self._settled)
        self._dispose_progress()
        self._callbacks = (on_ready, on_error)
        self._empty_message = empty_message
        progress = QProgressDialog(self._message, "", 0, 0, self._owner)
        progress.setCancelButton(None)
        progress.setWindowTitle("Print Preview")
        if self._modal:
            progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setMinimumDuration(0)
        progress.setAutoClose(False)
        progress.setAutoReset(False)
        self._progress = progress
        progress.show()
        self._runner.submit(_PreviewRequest(build))

    def _current(self, generation: int) -> bool:
        return (
            not self._closed
            and self._runner is not None
            and generation == self._runner.generation
        )

    @Slot(int, object)
    def _ready(self, generation: int, value: object) -> None:
        if not self._current(generation) or self._callbacks is None:
            return
        ready, error = self._callbacks
        self._callbacks = None
        self._dispose_progress()
        if value is None:
            error(self._empty_message)
            return
        try:
            ready(cast(PrintPreviewPayload, value))
        except Exception as exc:
            error(str(exc))

    @Slot(int, object)
    def _failed(self, generation: int, value: object) -> None:
        if not self._current(generation) or self._callbacks is None:
            return
        error = self._callbacks[1]
        self._callbacks = None
        self._dispose_progress()
        error(str(value))

    @Slot(int)
    def _settled(self, generation: int) -> None:
        if self._current(generation):
            self._dispose_progress()

    def _dispose_progress(self) -> None:
        progress = self._progress
        self._progress = None
        if progress is not None and isValid(progress):
            progress.close()
            progress.deleteLater()

    @Slot()
    def shutdown(self) -> None:
        self._closed = True
        self._callbacks = None
        if self._runner is not None:
            self._runner.shutdown(timeout=0)
        self._dispose_progress()

    @Slot()
    def _owner_destroyed(self) -> None:
        # Qt owns progress here; do not touch widgets during their destruction.
        self._closed = True
        self._callbacks = None
        self._progress = None
        if self._runner is not None:
            self._runner.shutdown(timeout=0)
