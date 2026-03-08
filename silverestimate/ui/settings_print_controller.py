from __future__ import annotations

import logging
from dataclasses import dataclass

from PyQt5.QtPrintSupport import QPrinterInfo
from PyQt5.QtWidgets import QComboBox, QDoubleSpinBox, QSpinBox

from silverestimate.infrastructure.settings import SettingsStore

LOGGER = logging.getLogger(__name__)

DEFAULT_PRINT_MARGINS = (10, 2, 10, 2)
DEFAULT_PREVIEW_ZOOM = 1.25
DEFAULT_PAGE_SIZE = "A4"
DEFAULT_ORIENTATION = "Landscape"
DEFAULT_ESTIMATE_LAYOUT = "old"
PRINT_ORIENTATION_MIGRATION_KEY = "print/orientation_explicit"
SUPPORTED_PAGE_SIZES = ("A4", "A5", "Letter", "Legal", "Thermal 80mm")
SUPPORTED_ORIENTATIONS = ("Portrait", "Landscape")
SUPPORTED_ESTIMATE_LAYOUTS = ("old", "new", "thermal")


@dataclass(frozen=True)
class PrintSettingsState:
    margins: tuple[int, int, int, int] = DEFAULT_PRINT_MARGINS
    preview_zoom: float = DEFAULT_PREVIEW_ZOOM
    default_printer: str = ""
    page_size: str = DEFAULT_PAGE_SIZE
    orientation: str = DEFAULT_ORIENTATION
    estimate_layout: str = DEFAULT_ESTIMATE_LAYOUT


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
    estimate_layout_combo: QComboBox


class SettingsPrintController:
    """Owns print-settings persistence and widget synchronization."""

    def __init__(self, settings: SettingsStore):
        self._settings = settings

    def load_state(self) -> PrintSettingsState:
        margins = self._load_margins()
        preview_zoom = self._load_preview_zoom()
        default_printer = (
            self._settings.value("print/default_printer", "", type=str) or ""
        )
        page_size = self._validated_value(
            self._settings.value("print/page_size", DEFAULT_PAGE_SIZE, type=str),
            supported=SUPPORTED_PAGE_SIZES,
            default=DEFAULT_PAGE_SIZE,
            setting_name="print/page_size",
        )
        orientation = self._load_orientation()
        estimate_layout = self._validated_value(
            self._settings.value(
                "print/estimate_layout",
                DEFAULT_ESTIMATE_LAYOUT,
                type=str,
            ),
            supported=SUPPORTED_ESTIMATE_LAYOUTS,
            default=DEFAULT_ESTIMATE_LAYOUT,
            setting_name="print/estimate_layout",
        )
        return PrintSettingsState(
            margins=margins,
            preview_zoom=preview_zoom,
            default_printer=default_printer,
            page_size=page_size,
            orientation=orientation,
            estimate_layout=estimate_layout,
        )

    def load_to_ui(self, widgets: PrintSettingsWidgets) -> PrintSettingsState:
        state = self.load_state()
        widgets.margin_left_spin.setValue(state.margins[0])
        widgets.margin_top_spin.setValue(state.margins[1])
        widgets.margin_right_spin.setValue(state.margins[2])
        widgets.margin_bottom_spin.setValue(state.margins[3])
        widgets.preview_zoom_spin.setValue(state.preview_zoom)

        if state.default_printer:
            idx = widgets.printer_combo.findText(state.default_printer)
            if idx >= 0:
                widgets.printer_combo.setCurrentIndex(idx)

        idx_page_size = widgets.page_size_combo.findText(state.page_size)
        if idx_page_size >= 0:
            widgets.page_size_combo.setCurrentIndex(idx_page_size)

        idx_orientation = widgets.orientation_combo.findText(state.orientation)
        if idx_orientation >= 0:
            widgets.orientation_combo.setCurrentIndex(idx_orientation)

        idx_layout = widgets.estimate_layout_combo.findData(state.estimate_layout)
        if idx_layout >= 0:
            widgets.estimate_layout_combo.setCurrentIndex(idx_layout)
        return state

    def save_from_ui(self, widgets: PrintSettingsWidgets) -> PrintSettingsState:
        state = PrintSettingsState(
            margins=(
                widgets.margin_left_spin.value(),
                widgets.margin_top_spin.value(),
                widgets.margin_right_spin.value(),
                widgets.margin_bottom_spin.value(),
            ),
            preview_zoom=float(widgets.preview_zoom_spin.value()),
            default_printer=widgets.printer_combo.currentText().strip(),
            page_size=widgets.page_size_combo.currentText() or DEFAULT_PAGE_SIZE,
            orientation=widgets.orientation_combo.currentText() or DEFAULT_ORIENTATION,
            estimate_layout=widgets.estimate_layout_combo.currentData()
            or DEFAULT_ESTIMATE_LAYOUT,
        )
        self.save_state(state)
        return state

    def save_state(self, state: PrintSettingsState) -> None:
        self._settings.setValue(
            "print/margins",
            self.serialize_margins(state.margins),
        )
        self._settings.setValue("print/preview_zoom", float(state.preview_zoom))
        if state.default_printer:
            self._settings.setValue("print/default_printer", state.default_printer)
        self._settings.setValue("print/page_size", state.page_size)
        self._settings.setValue("print/orientation", state.orientation)
        self._settings.setValue(PRINT_ORIENTATION_MIGRATION_KEY, True)
        self._settings.setValue("print/estimate_layout", state.estimate_layout)

    def apply_defaults_to_ui(self, widgets: PrintSettingsWidgets) -> PrintSettingsState:
        state = PrintSettingsState()
        widgets.margin_left_spin.setValue(state.margins[0])
        widgets.margin_top_spin.setValue(state.margins[1])
        widgets.margin_right_spin.setValue(state.margins[2])
        widgets.margin_bottom_spin.setValue(state.margins[3])
        widgets.preview_zoom_spin.setValue(state.preview_zoom)

        idx_page_size = widgets.page_size_combo.findText(state.page_size)
        if idx_page_size >= 0:
            widgets.page_size_combo.setCurrentIndex(idx_page_size)

        idx_orientation = widgets.orientation_combo.findText(state.orientation)
        if idx_orientation >= 0:
            widgets.orientation_combo.setCurrentIndex(idx_orientation)

        idx_layout = widgets.estimate_layout_combo.findData(state.estimate_layout)
        if idx_layout >= 0:
            widgets.estimate_layout_combo.setCurrentIndex(idx_layout)
        return state

    def refresh_printer_list(self, combo: QComboBox) -> None:
        try:
            combo.clear()
            printers = QPrinterInfo.availablePrinters()
            names = [printer.printerName() for printer in printers] if printers else []
            combo.addItems(sorted(names, key=lambda value: value.lower()))
        except Exception as exc:
            LOGGER.warning("Failed to read printers: %s", exc)

    @staticmethod
    def serialize_margins(margins: tuple[int, int, int, int]) -> str:
        return ",".join(str(value) for value in margins)

    def _load_margins(self) -> tuple[int, int, int, int]:
        raw_value = self._settings.value(
            "print/margins",
            self.serialize_margins(DEFAULT_PRINT_MARGINS),
            type=str,
        )
        try:
            margins = tuple(int(part.strip()) for part in str(raw_value).split(","))
        except (TypeError, ValueError):
            LOGGER.warning("Invalid margin format in settings: %r", raw_value)
            return DEFAULT_PRINT_MARGINS
        if len(margins) != 4:
            LOGGER.warning("Margin setting not found or invalid format: %r", raw_value)
            return DEFAULT_PRINT_MARGINS
        return (
            max(0, margins[0]),
            max(0, margins[1]),
            max(0, margins[2]),
            max(0, margins[3]),
        )

    def _load_preview_zoom(self) -> float:
        raw_value = self._settings.value(
            "print/preview_zoom",
            DEFAULT_PREVIEW_ZOOM,
            type=float,
        )
        try:
            return float(raw_value)
        except (TypeError, ValueError):
            LOGGER.warning("Invalid preview zoom in settings: %r", raw_value)
            return DEFAULT_PREVIEW_ZOOM

    def _load_orientation(self) -> str:
        raw_value = self._settings.value("print/orientation", None, type=str)
        explicit = bool(
            self._settings.value(
                PRINT_ORIENTATION_MIGRATION_KEY,
                False,
                type=bool,
            )
        )
        if raw_value in SUPPORTED_ORIENTATIONS:
            if raw_value == "Portrait" and not explicit:
                LOGGER.info(
                    "Migrating legacy default print orientation from Portrait to Landscape."
                )
                self._settings.setValue("print/orientation", DEFAULT_ORIENTATION)
                return DEFAULT_ORIENTATION
            return str(raw_value)
        if raw_value is None:
            return DEFAULT_ORIENTATION
        LOGGER.warning(
            "Invalid %s setting value %r; using %s",
            "print/orientation",
            raw_value,
            DEFAULT_ORIENTATION,
        )
        return DEFAULT_ORIENTATION

    @staticmethod
    def _validated_value(
        value: str | None,
        *,
        supported: tuple[str, ...],
        default: str,
        setting_name: str,
    ) -> str:
        if value in supported:
            return value
        LOGGER.warning(
            "Invalid %s setting value %r; using %s",
            setting_name,
            value,
            default,
        )
        return default
