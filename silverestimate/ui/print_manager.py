#!/usr/bin/env python
import logging

from PySide6.QtGui import QFont
from PySide6.QtPrintSupport import QPrinter

from silverestimate.infrastructure.settings import SettingsKey, get_app_settings
from silverestimate.services.settings_service import SettingsService

from .estimate_print_document import EstimatePrintDocument
from .estimate_print_renderer import EstimatePrintRenderer
from .print_format_spec import DEFAULT_ESTIMATE_FORMAT, normalize_estimate_format
from .print_page_settings import (
    PrintPageSettings,
    apply_print_page_settings_to_printer,
    load_print_page_settings,
)
from .print_payload_builder import (
    PrintDocument,
    PrintPayloadBuilder,
    PrintPreviewPayload,
)
from .print_preview_controller import PrintPreviewController
from .print_preview_output import PrintOutputOutcome, PrintOutputService
from .silver_bar_print_document import SilverBarListPrintDocument
from .silver_bar_print_renderer import SilverBarPrintRenderer

LOGGER = logging.getLogger(__name__)


class PrintManager:
    """Coordinate typed print payloads, preview, PDF export, and printing."""

    def __init__(self, db_manager, print_font=None):
        """Initialize the print manager, accepting an optional print font."""
        self.db_manager = db_manager
        if print_font is not None:
            self.print_font = print_font
        else:
            self.print_font = QFont("Arial", 8)

        self.printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        settings = get_app_settings()
        try:
            page_settings = load_print_page_settings(settings)
        except Exception as exc:
            LOGGER.debug("Failed to load print page preferences: %s", exc)
            page_settings = PrintPageSettings()
        apply_print_page_settings_to_printer(self.printer, page_settings)

        try:
            self.estimate_format = normalize_estimate_format(
                settings.get_text(
                    SettingsKey.PRINT_ESTIMATE_LAYOUT,
                    DEFAULT_ESTIMATE_FORMAT,
                )
            )
        except Exception as exc:
            LOGGER.debug("Failed to load estimate format preference: %s", exc)
            self.estimate_format = DEFAULT_ESTIMATE_FORMAT

        try:
            self.show_tunch = settings.get_bool(
                SettingsKey.PRINT_SHOW_TUNCH,
                False,
            )
        except Exception as exc:
            LOGGER.debug("Failed to load Tunch print preference: %s", exc)
            self.show_tunch = False

        self._estimate_renderer = EstimatePrintRenderer()
        self._payload_builder = PrintPayloadBuilder()
        self._preview_controller = PrintPreviewController(
            printer=self.printer,
            render_document=self._render_document,
            persist_estimate_format=self._set_estimate_format,
            persist_tunch_visibility=self._set_tunch_visibility,
            get_print_font=lambda: self.print_font,
            persist_print_font=self._set_print_font,
        )
        self._silver_bar_renderer = SilverBarPrintRenderer()

    def build_estimate_preview_payload(
        self,
        voucher_no,
        *,
        estimate_data=None,
    ) -> PrintPreviewPayload | None:
        """Build a typed estimate preview payload without opening UI widgets."""
        return self._payload_builder.build_estimate_preview_payload(
            voucher_no,
            fetch_estimate=lambda current_voucher: (
                self.db_manager.get_estimate_by_voucher(current_voucher)
            ),
            format_key=self.estimate_format,
            estimate_data=estimate_data,
            show_tunch=self.show_tunch,
        )

    def _set_estimate_format(self, format_key: str) -> None:
        self.estimate_format = normalize_estimate_format(format_key)

    def _set_tunch_visibility(self, visible: bool) -> None:
        self.show_tunch = bool(visible)

    def _set_print_font(self, font: QFont) -> None:
        """Apply and persist a preview-selected estimate print font."""
        size = font.pointSizeF()
        self.print_font.setFamily(font.family())
        self.print_font.setPointSizeF(max(1.0, size))
        self.print_font.setBold(font.bold())
        SettingsService().save_print_font(self.print_font)

    def show_preview(
        self,
        payload: PrintPreviewPayload,
        *,
        parent_widget=None,
    ) -> PrintOutputOutcome:
        """Open a prepared preview payload on the GUI thread."""
        return self._preview_controller.open_preview(
            payload, parent_widget=parent_widget
        )

    def quick_print(self, payload: PrintPreviewPayload) -> PrintOutputOutcome:
        """Print a prepared payload using the saved printer and page settings."""
        return PrintOutputService(
            printer=self.printer, render_document=self._render_document
        ).quick_print(payload)

    def build_silver_bar_list_preview_payload(
        self,
        list_info,
        bars_in_list,
    ) -> PrintPreviewPayload | None:
        """Build the print payload for a silver-bar list without opening UI widgets."""
        return self._payload_builder.build_silver_bar_list_preview_payload(
            list_info,
            bars_in_list,
        )

    def _render_document(self, printer: QPrinter, document: PrintDocument) -> None:
        """Render a typed estimate or silver-bar report."""
        if isinstance(document, EstimatePrintDocument):
            self._estimate_renderer.paint(
                printer,
                document,
                print_font=self.print_font,
            )
            return
        if isinstance(document, SilverBarListPrintDocument):
            self._silver_bar_renderer.paint(
                printer,
                document,
                print_font=self.print_font,
            )
            return
        raise TypeError(f"Unsupported print document: {type(document).__name__}")
