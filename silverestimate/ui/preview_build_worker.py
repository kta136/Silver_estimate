"""Thread-safe worker and callback routing for print-preview preparation."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QObject, Signal, Slot


class PreviewBuildWorker(QObject):
    """Prepare a preview payload away from the GUI thread."""

    preview_ready = Signal(int, object)
    preview_error = Signal(int, str)
    finished = Signal(int)

    def __init__(
        self,
        request_id: int,
        build_preview: Callable[[], object],
    ) -> None:
        super().__init__()
        self._request_id = request_id
        self._build_preview = build_preview

    @Slot()
    def run(self) -> None:
        try:
            self.preview_ready.emit(self._request_id, self._build_preview())
        except Exception as exc:
            self.preview_error.emit(self._request_id, str(exc))
        finally:
            self.finished.emit(self._request_id)


class PreviewBuildCallbackRouter(QObject):
    """Marshal worker results to callbacks on this object's GUI thread."""

    def __init__(
        self,
        *,
        on_ready: Callable[[int, object], None],
        on_error: Callable[[int, str], None],
        on_finished: Callable[[int], None],
        parent: QObject,
    ) -> None:
        super().__init__(parent)
        self._on_ready = on_ready
        self._on_error = on_error
        self._on_finished = on_finished

    @Slot(int, object)
    def handle_ready(self, request_id: int, payload: object) -> None:
        self._on_ready(request_id, payload)

    @Slot(int, str)
    def handle_error(self, request_id: int, message: str) -> None:
        self._on_error(request_id, message)

    @Slot(int)
    def handle_finished(self, request_id: int) -> None:
        self._on_finished(request_id)


__all__ = ["PreviewBuildCallbackRouter", "PreviewBuildWorker"]
