#!/usr/bin/env python
import logging
from typing import Callable

from PyQt5.QtCore import QLocale, QObject, QSizeF, pyqtSignal
from PyQt5.QtGui import QFont, QPageSize, QTextDocument
from PyQt5.QtPrintSupport import QPrinter
from PyQt5.QtWidgets import QMessageBox

from silverestimate.infrastructure.settings import get_app_settings

from .estimate_print_renderer import EstimatePrintRenderer
from .print_payload_builder import PrintPayloadBuilder, PrintPreviewPayload
from .print_preview_controller import PrintPreviewController
from .settings_print_controller import PRINT_ORIENTATION_MIGRATION_KEY
from .silver_bar_print_renderer import SilverBarPrintRenderer

LOGGER = logging.getLogger(__name__)

_SUPPORTED_PRINT_ORIENTATIONS = {"Portrait", "Landscape"}


class PrintPreviewBuildWorker(QObject):
    """Background worker that prepares preview payloads off the UI thread."""

    preview_ready = pyqtSignal(int, object)
    preview_error = pyqtSignal(int, str)
    finished = pyqtSignal(int)

    def __init__(
        self,
        request_id: int,
        build_preview: Callable[[], object],
    ) -> None:
        super().__init__()
        self._request_id = request_id
        self._build_preview = build_preview

    def run(self) -> None:
        try:
            payload = self._build_preview()
            self.preview_ready.emit(self._request_id, payload)
        except Exception as exc:
            self.preview_error.emit(self._request_id, str(exc))
        finally:
            self.finished.emit(self._request_id)


class PrintManager:
    """Class to handle print functionality using manual formatting."""

    def __init__(self, db_manager, print_font=None):
        """Initialize the print manager, accepting an optional print font."""
        self.db_manager = db_manager
        # Store the custom print font if provided, otherwise use a default
        if print_font:
            self.print_font = print_font
        else:
            # Default font if none is provided via settings
            # Force Courier New for estimate slip, but use size/bold from settings
            default_size = 7.0  # Default size if setting unavailable
            font_size_int = int(round(getattr(print_font, "float_size", default_size)))
            is_bold = getattr(
                print_font, "bold", lambda: False
            )()  # Check if bold exists and call
            self.print_font = QFont("Courier New", font_size_int)
            self.print_font.setBold(is_bold)
            # Store float size for consistency if needed elsewhere, though not used directly here
            self.print_font.float_size = (
                float(font_size_int)
                if not hasattr(print_font, "float_size")
                else print_font.float_size
            )

        self.printer = QPrinter(QPrinter.HighResolution)
        # Load printer defaults
        settings = get_app_settings()
        # Default printer
        try:
            default_printer_name = settings.value("print/default_printer", "", type=str)
            if default_printer_name:
                self.printer.setPrinterName(default_printer_name)
        except Exception as exc:
            LOGGER.debug("Failed to load default printer preference: %s", exc)
        # Page size
        try:
            self._apply_page_size_preference(settings)
        except Exception as exc:
            LOGGER.debug("Failed to load page size preference: %s", exc)
            self.printer.setPageSize(QPageSize(QPageSize.A4))
        # Orientation
        try:
            orientation_name = self._load_orientation_preference(settings)
            self.printer.setOrientation(
                QPrinter.Landscape
                if orientation_name == "Landscape"
                else QPrinter.Portrait
            )
        except Exception as exc:
            LOGGER.debug("Failed to load printer orientation preference: %s", exc)
            self.printer.setOrientation(QPrinter.Landscape)

        try:
            layout_mode = settings.value("print/estimate_layout", "old", type=str)
            self.estimate_layout_mode = (layout_mode or "old").lower()
            if self.estimate_layout_mode not in {"old", "new", "thermal"}:
                self.estimate_layout_mode = "old"
        except Exception as exc:
            LOGGER.debug("Failed to load estimate layout preference: %s", exc)
            self.estimate_layout_mode = "old"
        # Load margin settings
        default_margins = "10,5,10,5"  # Default: 10mm L/R, 5mm T/B
        margins_str = settings.value(
            "print/margins", defaultValue=default_margins, type=str
        )
        try:
            margins = [int(m.strip()) for m in margins_str.split(",")]
            if len(margins) != 4:
                raise ValueError("Invalid margin format")
            # Ensure margins are non-negative
            margins = [max(0, m) for m in margins]
            import logging

            logging.getLogger(__name__).debug(f"Using margins (L,T,R,B): {margins} mm")
        except (ValueError, TypeError):
            import logging

            logging.getLogger(__name__).warning(
                f"Using default margins ({default_margins} mm) due to invalid setting '{margins_str}'"
            )
            margins = [10, 5, 10, 5]

        self.printer.setPageMargins(
            margins[0], margins[1], margins[2], margins[3], QPrinter.Millimeter
        )  # Left, Top, Right, Bottom
        import logging

        logging.getLogger(__name__).debug(
            f"Printer margins set to: L={margins[0]}, T={margins[1]}, R={margins[2]}, B={margins[3]}"
        )
        self._estimate_renderer = EstimatePrintRenderer(
            currency_formatter=self._format_currency_locale
        )
        self._payload_builder = PrintPayloadBuilder()
        self._preview_controller = PrintPreviewController(
            printer=self.printer,
            render_document=self._print_html,
            persist_estimate_layout=self._set_estimate_layout_mode,
        )
        self._silver_bar_renderer = SilverBarPrintRenderer()

    @staticmethod
    def _load_orientation_preference(settings) -> str:
        orientation_name = settings.value("print/orientation", None, type=str)
        explicit = bool(
            settings.value(
                PRINT_ORIENTATION_MIGRATION_KEY,
                False,
                type=bool,
            )
        )
        if orientation_name in _SUPPORTED_PRINT_ORIENTATIONS:
            if orientation_name == "Portrait" and not explicit:
                settings.setValue("print/orientation", "Landscape")
                return "Landscape"
            return str(orientation_name)
        return "Landscape"

    def _apply_page_size_preference(self, settings) -> None:
        page_size_name = settings.value("print/page_size", "A4", type=str)
        if page_size_name == "Thermal 80mm":
            thermal_size = QPageSize(
                QSizeF(79.5, 200), QPageSize.Millimeter, "Thermal 80mm"
            )
            self.printer.setPageSize(thermal_size)
            return

        size_map = {
            "A4": QPageSize.A4,
            "A5": QPageSize.A5,
            "Letter": QPageSize.Letter,
            "Letter / ANSI A": QPageSize.Letter,
            "Legal": QPageSize.Legal,
        }
        if page_size_name in size_map:
            self.printer.setPageSize(QPageSize(size_map[page_size_name]))
            return

        width_mm = settings.value("print/page_width_mm", 0.0, type=float)
        height_mm = settings.value("print/page_height_mm", 0.0, type=float)
        custom_name = settings.value("print/page_size_name", page_size_name, type=str)
        if float(width_mm) > 0 and float(height_mm) > 0:
            self.printer.setPageSize(
                QPageSize(
                    QSizeF(float(width_mm), float(height_mm)),
                    QPageSize.Millimeter,
                    custom_name or page_size_name or "Custom",
                )
            )
            return

        self.printer.setPageSize(QPageSize(QPageSize.A4))

    def _set_estimate_layout_mode(self, layout_mode: str) -> None:
        normalized = (layout_mode or "").strip().lower()
        if normalized in {"old", "new", "thermal"}:
            self.estimate_layout_mode = normalized

    def format_indian_rupees(self, number):
        """Formats a number into Indian Rupees notation (Lakhs, Crores)."""
        # Ensure number is integer after rounding
        num = int(round(number))
        s = str(num)
        n = len(s)
        if n <= 3:
            return s
        # Format the last three digits
        last_three = s[-3:]
        # Format the remaining digits in groups of two
        other_digits = s[:-3]
        if not other_digits:
            return last_three  # Handle cases like 123

        # Reverse the other_digits string for easier processing
        other_digits_rev = other_digits[::-1]
        formatted_other_rev = ""
        for i, digit in enumerate(other_digits_rev):
            formatted_other_rev += digit
            # Add comma after every second digit (except at the end)
            if (i + 1) % 2 == 0 and (i + 1) != len(other_digits_rev):
                formatted_other_rev += ","

        # Reverse the formatted string back
        formatted_other = formatted_other_rev[::-1]
        return formatted_other + "," + last_three

    def _format_currency_locale(self, number):
        """Format currency using system locale; fallback to Indian format with ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡Ãƒâ€šÃ‚Â¹."""
        try:
            locale = QLocale.system()
            return locale.toCurrencyString(float(round(number)))
        except Exception:
            return f"ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡Ãƒâ€šÃ‚Â¹ {self.format_indian_rupees(int(round(number)))}"

    def print_estimate(self, voucher_no, parent_widget=None):
        """Print an estimate using manual formatting and preview."""
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
        """Build the estimate preview HTML without opening UI widgets."""
        return self._payload_builder.build_estimate_preview_payload(
            voucher_no,
            layout_mode=self.estimate_layout_mode,
            fetch_estimate=lambda current_voucher: (
                self.db_manager.get_estimate_by_voucher(current_voucher)
            ),
            render_old=self._generate_estimate_old_format,
            render_new=self._generate_estimate_new_format,
            render_thermal=self._generate_estimate_thermal_format,
            estimate_data=estimate_data,
        )

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

    def _print_html(self, printer, html_content, table_mode=False):
        """Renders the HTML text (containing PRE or TABLE) to the printer."""
        document = QTextDocument()
        if table_mode:
            table_font = QFont("Arial", 8)
            document.setDefaultFont(table_font)
        else:
            # Estimate slip: Use the stored print_font settings
            font_size_int = int(
                round(getattr(self.print_font, "float_size", 7.0))
            )  # Default 7pt
            # Force Courier New for alignment, but use stored size/bold
            font_to_use = QFont("Courier New", font_size_int)
            is_bold = getattr(
                self.print_font, "bold", lambda: False
            )()  # Safely check bold
            font_to_use.setBold(is_bold)
            document.setDefaultFont(font_to_use)

        document.setHtml(html_content)
        document.setPageSize(printer.pageRect(QPrinter.Point).size())
        document.print_(printer)

    @staticmethod
    def _build_preformatted_html(content: str, *, line_height: float = 1.0) -> str:
        return EstimatePrintRenderer._build_preformatted_html(
            content,
            line_height=line_height,
        )

    def _generate_estimate_old_format(self, estimate_data):
        return self._estimate_renderer.generate_old_format(estimate_data)

    def _generate_estimate_new_format(self, estimate_data):
        return self._estimate_renderer.generate_new_format(estimate_data)

    def _generate_estimate_thermal_format(self, estimate_data):
        return self._estimate_renderer.generate_thermal_format(estimate_data)

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
