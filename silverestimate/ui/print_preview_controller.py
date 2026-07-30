"""Composition root for the print-preview workspace."""

from __future__ import annotations

import logging
from typing import Callable

from PySide6.QtCore import QTimer
from PySide6.QtGui import QFont
from PySide6.QtPrintSupport import QPrinter

from .print_payload_builder import PrintDocument, PrintPreviewPayload
from .print_preview_dialog import PrintPreviewDialog
from .print_preview_navigation import PrintPreviewNavigationController
from .print_preview_output import (
    PrintOutputService,
    PrintPreviewOutputController,
)
from .print_preview_page_setup import PrintPreviewPageSetupController
from .print_preview_preferences import PrintPreviewPreferences
from .print_preview_session import PrintPreviewSession
from .print_preview_toolbar import PrintPreviewToolbarBuilder
from .window_sizing import resize_to_available_screen

LOGGER = logging.getLogger(__name__)


class PrintPreviewController:
    """Compose and run a print-preview session."""

    def __init__(  # noqa: PLR0913 - stable PrintManager construction API
        self,
        *,
        printer: QPrinter,
        render_document: Callable[[QPrinter, PrintDocument], None],
        persist_estimate_format: Callable[[str], None] | None = None,
        persist_tunch_visibility: Callable[[bool], None] | None = None,
        get_print_font: Callable[[], QFont] | None = None,
        persist_print_font: Callable[[QFont], None] | None = None,
    ) -> None:
        self._printer = printer
        self._preferences = PrintPreviewPreferences(
            persist_estimate_format=persist_estimate_format,
            persist_tunch_visibility=persist_tunch_visibility,
        )
        self._navigation = PrintPreviewNavigationController()
        self._page_setup = PrintPreviewPageSetupController(
            printer=printer,
            preferences=self._preferences,
        )
        output_service = PrintOutputService(
            printer=printer,
            render_document=render_document,
        )
        self._output_controller = PrintPreviewOutputController(
            service=output_service,
            preferences=self._preferences,
        )
        self._toolbar_builder = PrintPreviewToolbarBuilder(
            navigation=self._navigation,
            page_setup=self._page_setup,
            output=self._output_controller,
            get_print_font=get_print_font,
            persist_print_font=persist_print_font,
        )
        self._render_document = render_document

    def open_preview(
        self,
        payload: PrintPreviewPayload,
        *,
        parent_widget=None,
    ) -> None:
        """Open the custom preview window with persistent report controls."""
        preview = PrintPreviewDialog(self._printer, parent_widget)
        preview.setWindowTitle(payload.title)
        session = PrintPreviewSession(
            preview=preview,
            payload=payload,
            render_document=self._render_document,
        )
        session.bind_renderer()

        preview_widget = session.preview_widget
        self._preferences.apply_initial_zoom(preview_widget)
        self._navigation.install_ctrl_wheel_zoom(preview, preview_widget)
        try:
            self._toolbar_builder.build(session, parent_widget)
        except Exception as exc:
            LOGGER.warning("Could not augment preview toolbar: %s", exc, exc_info=True)

        resize_to_available_screen(
            preview,
            preferred_width=1280,
            preferred_height=820,
            margin=24,
        )
        preview.showMaximized()
        PrintPreviewSession.focus(preview, preview_widget)

        def refresh_and_focus() -> None:
            session.refresh()
            PrintPreviewSession.focus(preview, preview_widget)

        QTimer.singleShot(0, refresh_and_focus)
        preview.exec()
        self._preferences.save_zoom(preview_widget)
        self._preferences.save_preview_defaults(self._printer, session.payload)


__all__ = ["PrintPreviewController"]
