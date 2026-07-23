#!/usr/bin/env python
import logging

from PySide6.QtGui import QFont, QTextDocument
from PySide6.QtPrintSupport import QPrinter
from PySide6.QtWidgets import QMessageBox

from silverestimate.infrastructure.settings import get_app_settings
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
    HtmlPrintDocument,
    PrintDocument,
    PrintPayloadBuilder,
    PrintPreviewPayload,
)
from .print_preview_controller import PrintPreviewController
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
                settings.value(
                    "print/estimate_layout",
                    DEFAULT_ESTIMATE_FORMAT,
                    type=str,
                )
            )
        except Exception as exc:
            LOGGER.debug("Failed to load estimate format preference: %s", exc)
            self.estimate_format = DEFAULT_ESTIMATE_FORMAT

        try:
            self.show_tunch = bool(
                settings.value(
                    "print/show_tunch",
                    defaultValue=False,
                    type=bool,
                )
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

    def print_estimate(self, voucher_no, parent_widget=None):
        """Preview and print an estimate through the selected direct painter."""
        try:
            payload = self.build_estimate_preview_payload(voucher_no)
            if payload is None:
                QMessageBox.warning(
                    parent_widget, "Print Error", f"Estimate {voucher_no} not found."
                )
                return False
            self.show_preview(payload, parent_widget=parent_widget)
            return True
        except Exception as exc:
            LOGGER.exception("Failed to prepare estimate print preview: %s", exc)
            QMessageBox.critical(
                parent_widget,
                "Print Error",
                "Could not prepare the estimate print preview.\n\n"
                "Check the estimate data and print settings, then try again.",
            )
            return False

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
    ) -> None:
        """Open a prepared preview payload on the GUI thread."""
        self._preview_controller.open_preview(payload, parent_widget=parent_widget)

    def print_silver_bars(self, status_filter=None, parent_widget=None):
        """Prints the INVENTORY list of silver bars using preview."""
        payload = self.build_silver_bar_inventory_preview_payload(status_filter)
        if payload is None:
            status_msg = f" with status '{status_filter}'" if status_filter else ""
            QMessageBox.warning(
                parent_widget, "Print Error", f"No silver bars{status_msg} found."
            )
            return False

        try:
            self.show_preview(payload, parent_widget=parent_widget)
            return True

        except Exception as exc:
            LOGGER.exception(
                "Failed to prepare silver bar inventory print preview: %s",
                exc,
            )
            QMessageBox.critical(
                parent_widget,
                "Print Error",
                "Could not prepare the silver bar inventory preview.\n\n"
                "Check the selected printer and print settings, then try again.",
            )
            return False

    def build_silver_bar_inventory_preview_payload(
        self,
        status_filter=None,
    ) -> PrintPreviewPayload | None:
        """Build the inventory payload for silver bars without opening UI widgets."""
        return self._payload_builder.build_silver_bar_inventory_preview_payload(
            status_filter=status_filter,
            fetch_bars=lambda selected_status: self.db_manager.get_silver_bars(
                selected_status
            ),
            render_inventory=self._generate_silver_bars_html_table,
        )

    def print_silver_bar_list_details(
        self, list_info, bars_in_list, parent_widget=None
    ):
        """Generates and previews/prints details of a specific silver bar list."""
        try:
            payload = self.build_silver_bar_list_preview_payload(
                list_info, bars_in_list
            )
            if payload is None:
                QMessageBox.warning(
                    parent_widget, "Print Error", "List information is missing."
                )
                return False
            self.show_preview(payload, parent_widget=parent_widget)
            return True
        except Exception as exc:
            LOGGER.exception("Failed to prepare list print preview: %s", exc)
            QMessageBox.critical(
                parent_widget,
                "Print Error",
                "Could not prepare the list print preview.\n\n"
                "Check the list data and print settings, then try again.",
            )
            return False

    def build_silver_bar_list_preview_payload(
        self,
        list_info,
        bars_in_list,
    ) -> PrintPreviewPayload | None:
        """Build the print payload for a silver-bar list without opening UI widgets."""
        return self._payload_builder.build_silver_bar_list_preview_payload(
            list_info,
            bars_in_list,
            render_list_details=self._generate_list_details_html,
        )

    def _render_document(self, printer: QPrinter, document: PrintDocument) -> None:
        """Render a typed estimate or an HTML silver-bar report."""
        if isinstance(document, EstimatePrintDocument):
            self._estimate_renderer.paint(
                printer,
                document,
                print_font=self.print_font,
            )
            return
        if isinstance(document, HtmlPrintDocument):
            self._print_html(
                printer,
                document.html_content,
                table_mode=document.table_mode,
            )
            return
        raise TypeError(f"Unsupported print document: {type(document).__name__}")

    def _print_html(self, printer, html_content, table_mode=False):
        """Render silver-bar HTML reports to the printer."""
        document = QTextDocument()
        if table_mode:
            table_font = QFont("Arial", 8)
            document.setDefaultFont(table_font)
        else:
            # Estimate slip: Use the stored print_font settings
            font_size = self.print_font.pointSizeF()
            font_size_int = int(round(font_size if font_size > 0 else 7.0))
            # Force Courier New for alignment, but use stored size/bold
            font_to_use = QFont("Courier New", font_size_int)
            is_bold = getattr(
                self.print_font, "bold", lambda: False
            )()  # Safely check bold
            font_to_use.setBold(is_bold)
            document.setDefaultFont(font_to_use)

        document.setHtml(html_content)
        document.setPageSize(printer.pageRect(QPrinter.Unit.Point).size())
        document.print_(printer)

    def _generate_silver_bars_html_table(self, bars, status_filter=None):
        return self._silver_bar_renderer.generate_inventory_html_table(
            bars,
            status_filter=status_filter,
        )

    def _generate_list_details_html(self, list_info, bars_in_list):
        return self._silver_bar_renderer.generate_list_details_html(
            list_info,
            bars_in_list,
        )
