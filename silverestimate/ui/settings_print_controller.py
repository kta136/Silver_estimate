from __future__ import annotations

import logging
from dataclasses import dataclass

from PyQt6.QtPrintSupport import QPrinterInfo
from PyQt6.QtWidgets import QComboBox, QDoubleSpinBox, QSpinBox

from silverestimate.infrastructure.settings import SettingsStore
from silverestimate.ui.print_format_spec import (
    DEFAULT_ESTIMATE_FORMAT,
    normalize_estimate_format,
)
from silverestimate.ui.print_page_settings import (
    DEFAULT_ORIENTATION,
    DEFAULT_PAGE_SIZE,
    DEFAULT_PRINT_MARGINS,
    PrintPageSettings,
    load_print_page_settings,
    save_print_page_settings,
    serialize_margins,
)
from silverestimate.ui.print_page_settings import (
    SUPPORTED_ORIENTATIONS as SUPPORTED_ORIENTATIONS,
)

LOGGER = logging.getLogger(__name__)

DEFAULT_PREVIEW_ZOOM = 1.25


@dataclass(frozen=True)
class PrintSettingsState:
    margins: tuple[int, int, int, int] = DEFAULT_PRINT_MARGINS
    preview_zoom: float = DEFAULT_PREVIEW_ZOOM
    default_printer: str = ""
    page_size: str = DEFAULT_PAGE_SIZE
    page_size_name: str = DEFAULT_PAGE_SIZE
    page_width_mm: float = 0.0
    page_height_mm: float = 0.0
    orientation: str = DEFAULT_ORIENTATION
    estimate_format: str = DEFAULT_ESTIMATE_FORMAT


@dataclass(frozen=True)
class PrintSettingsWidgets:
    margin_left_spin: QSpinBox
    margin_top_spin: QSpinBox
    margin_right_spin: QSpinBox
    margin_bottom_spin: QSpinBox
    preview_zoom_spin: QDoubleSpinBox
    printer_combo: QComboBox
    page_size_combo: QComboBox
    orientation_combo: QComboBox
    estimate_format_combo: QComboBox


class SettingsPrintController:
    """Owns print-settings persistence and widget synchronization."""

    def __init__(self, settings: SettingsStore):
        self._settings = settings

    def load_state(self) -> PrintSettingsState:
        page_settings = load_print_page_settings(self._settings)
        preview_zoom = self._load_preview_zoom()
        raw_estimate_format = self._settings.value(
            "print/estimate_layout",
            DEFAULT_ESTIMATE_FORMAT,
            type=str,
        )
        estimate_format = normalize_estimate_format(raw_estimate_format)
        if str(raw_estimate_format or "").strip().lower() != estimate_format:
            self._settings.setValue("print/estimate_layout", estimate_format)
        return PrintSettingsState(
            margins=page_settings.margins,
            preview_zoom=preview_zoom,
            default_printer=page_settings.default_printer,
            page_size=page_settings.page_size,
            page_size_name=page_settings.page_size_name,
            page_width_mm=page_settings.page_width_mm,
            page_height_mm=page_settings.page_height_mm,
            orientation=page_settings.orientation,
            estimate_format=estimate_format,
        )

    def load_to_ui(self, widgets: PrintSettingsWidgets) -> PrintSettingsState:
        state = self.load_state()
        widgets.margin_left_spin.setValue(state.margins[0])
        widgets.margin_top_spin.setValue(state.margins[1])
        widgets.margin_right_spin.setValue(state.margins[2])
        widgets.margin_bottom_spin.setValue(state.margins[3])
        widgets.preview_zoom_spin.setValue(state.preview_zoom)

        idx_printer = widgets.printer_combo.findData(state.default_printer)
        if idx_printer >= 0:
            widgets.printer_combo.setCurrentIndex(idx_printer)
        elif widgets.printer_combo.count() > 0:
            widgets.printer_combo.setCurrentIndex(0)

        idx_page_size = widgets.page_size_combo.findText(state.page_size)
        if idx_page_size < 0 and state.page_width_mm > 0 and state.page_height_mm > 0:
            widgets.page_size_combo.addItem(
                state.page_size,
                {
                    "page_size_name": state.page_size_name,
                    "page_width_mm": state.page_width_mm,
                    "page_height_mm": state.page_height_mm,
                },
            )
            idx_page_size = widgets.page_size_combo.findText(state.page_size)
        if idx_page_size >= 0:
            widgets.page_size_combo.setCurrentIndex(idx_page_size)

        idx_orientation = widgets.orientation_combo.findText(state.orientation)
        if idx_orientation >= 0:
            widgets.orientation_combo.setCurrentIndex(idx_orientation)

        idx_format = widgets.estimate_format_combo.findData(state.estimate_format)
        if idx_format >= 0:
            widgets.estimate_format_combo.setCurrentIndex(idx_format)

        return state

    def save_from_ui(self, widgets: PrintSettingsWidgets) -> PrintSettingsState:
        printer_data = widgets.printer_combo.currentData()
        if printer_data is None:
            default_printer = widgets.printer_combo.currentText().strip()
            if default_printer == "System default":
                default_printer = ""
        else:
            default_printer = str(printer_data).strip()

        page_size = widgets.page_size_combo.currentText() or DEFAULT_PAGE_SIZE
        page_size_data = widgets.page_size_combo.currentData()
        page_size_name = page_size
        page_width_mm = 0.0
        page_height_mm = 0.0
        if isinstance(page_size_data, dict):
            page_size_name = str(page_size_data.get("page_size_name") or page_size)
            page_width_mm = float(page_size_data.get("page_width_mm") or 0.0)
            page_height_mm = float(page_size_data.get("page_height_mm") or 0.0)

        state = PrintSettingsState(
            margins=(
                widgets.margin_left_spin.value(),
                widgets.margin_top_spin.value(),
                widgets.margin_right_spin.value(),
                widgets.margin_bottom_spin.value(),
            ),
            preview_zoom=float(widgets.preview_zoom_spin.value()),
            default_printer=default_printer,
            page_size=page_size,
            page_size_name=page_size_name,
            page_width_mm=page_width_mm,
            page_height_mm=page_height_mm,
            orientation=widgets.orientation_combo.currentText() or DEFAULT_ORIENTATION,
            estimate_format=(
                widgets.estimate_format_combo.currentData() or DEFAULT_ESTIMATE_FORMAT
            ),
        )
        self.save_state(state)
        return state

    def save_state(self, state: PrintSettingsState) -> None:
        save_print_page_settings(
            self._settings,
            PrintPageSettings(
                margins=state.margins,
                default_printer=state.default_printer,
                page_size=state.page_size,
                page_size_name=state.page_size_name,
                page_width_mm=state.page_width_mm,
                page_height_mm=state.page_height_mm,
                orientation=state.orientation,
            ),
        )
        self._settings.setValue("print/preview_zoom", float(state.preview_zoom))
        self._settings.setValue("print/estimate_layout", state.estimate_format)

    def apply_defaults_to_ui(self, widgets: PrintSettingsWidgets) -> PrintSettingsState:
        state = PrintSettingsState()
        widgets.margin_left_spin.setValue(state.margins[0])
        widgets.margin_top_spin.setValue(state.margins[1])
        widgets.margin_right_spin.setValue(state.margins[2])
        widgets.margin_bottom_spin.setValue(state.margins[3])
        widgets.preview_zoom_spin.setValue(state.preview_zoom)
        idx_printer = widgets.printer_combo.findData("")
        if idx_printer >= 0:
            widgets.printer_combo.setCurrentIndex(idx_printer)

        idx_page_size = widgets.page_size_combo.findText(state.page_size)
        if idx_page_size >= 0:
            widgets.page_size_combo.setCurrentIndex(idx_page_size)

        idx_orientation = widgets.orientation_combo.findText(state.orientation)
        if idx_orientation >= 0:
            widgets.orientation_combo.setCurrentIndex(idx_orientation)

        idx_format = widgets.estimate_format_combo.findData(state.estimate_format)
        if idx_format >= 0:
            widgets.estimate_format_combo.setCurrentIndex(idx_format)

        return state

    def refresh_printer_list(self, combo: QComboBox) -> None:
        try:
            combo.clear()
            combo.addItem("System default", "")
            printers = QPrinterInfo.availablePrinters()
            names = [printer.printerName() for printer in printers] if printers else []
            for name in sorted(names, key=lambda value: value.lower()):
                combo.addItem(name, name)
        except Exception as exc:
            LOGGER.warning("Failed to read printers: %s", exc)

    @staticmethod
    def serialize_margins(margins: tuple[int, int, int, int]) -> str:
        return serialize_margins(margins)

    def _load_preview_zoom(self) -> float:
        raw_value = self._settings.value(
            "print/preview_zoom",
            DEFAULT_PREVIEW_ZOOM,
            type=float,
        )
        try:
            return float(raw_value)
        except TypeError, ValueError:
            LOGGER.warning("Invalid preview zoom in settings: %r", raw_value)
            return DEFAULT_PREVIEW_ZOOM
