"""Mutable preview-session state around an immutable print payload."""

from __future__ import annotations

import contextlib
from typing import Callable

from PySide6.QtCore import Qt
from PySide6.QtPrintSupport import QPrinter, QPrintPreviewWidget
from PySide6.QtWidgets import QDialog

from .print_payload_builder import PrintDocument, PrintPreviewPayload
from .print_preview_dialog import PrintPreviewDialog


class PrintPreviewSession:
    """Own the active payload and preview refresh lifecycle."""

    def __init__(
        self,
        *,
        preview: PrintPreviewDialog,
        payload: PrintPreviewPayload,
        render_document: Callable[[QPrinter, PrintDocument], None],
    ) -> None:
        self.preview = preview
        self.payload = payload
        self._render_document = render_document

    @property
    def preview_widget(self) -> QPrintPreviewWidget:
        return self.preview.preview_widget

    def bind_renderer(self) -> None:
        """Render the current immutable payload whenever Qt requests a repaint."""
        self.preview_widget.paintRequested.connect(self.render)

    def render(self, printer: QPrinter) -> None:
        self._render_document(printer, self.payload.document)

    def refresh(self) -> None:
        self.preview_widget.updatePreview()

    def replace_payload(self, payload: PrintPreviewPayload) -> None:
        self.payload = payload
        self.preview.setWindowTitle(payload.title)
        self.refresh()

    def switch_format(self, format_key: object) -> bool:
        if not format_key or self.payload.format_factory is None:
            return False
        next_payload = self.payload.format_factory(str(format_key))
        if next_payload is None:
            return False
        self.replace_payload(next_payload)
        return True

    def switch_tunch_visibility(self, visible: bool) -> bool:
        if self.payload.tunch_visibility_factory is None:
            return False
        next_payload = self.payload.tunch_visibility_factory(bool(visible))
        if next_payload is None:
            return False
        self.replace_payload(next_payload)
        return True

    @staticmethod
    def focus(
        preview: QDialog,
        preview_widget: QPrintPreviewWidget | None,
    ) -> None:
        """Activate the preview and put keyboard focus on its document view."""
        try:
            preview.raise_()
            preview.activateWindow()
        except AttributeError, RuntimeError:
            return
        focus_target = preview_widget or preview
        with contextlib.suppress(AttributeError, RuntimeError):
            focus_target.setFocus(Qt.FocusReason.ActiveWindowFocusReason)


__all__ = ["PrintPreviewSession"]
