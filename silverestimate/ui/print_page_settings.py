"""Shared print page preference handling for Qt printers."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from PyQt6.QtCore import QMarginsF, QSizeF
from PyQt6.QtGui import QPageLayout, QPageSize
from PyQt6.QtPrintSupport import QPrinter, QPrinterInfo

LOGGER = logging.getLogger(__name__)

DEFAULT_PRINT_MARGINS = (10, 2, 10, 2)
DEFAULT_PAGE_SIZE = "A4"
DEFAULT_ORIENTATION = "Landscape"
PRINT_ORIENTATION_MIGRATION_KEY = "print/orientation_explicit"
SUPPORTED_PAGE_SIZES = ("A4", "A5", "Letter", "Legal", "Thermal 80mm")
SUPPORTED_ORIENTATIONS = ("Portrait", "Landscape")
THERMAL_PAGE_WIDTH_MM = 79.5
THERMAL_PAGE_HEIGHT_MM = 200.0

_PAGE_SIZE_IDS = {
    "A4": QPageSize.PageSizeId.A4,
    "A5": QPageSize.PageSizeId.A5,
    "Letter": QPageSize.PageSizeId.Letter,
    "Letter / ANSI A": QPageSize.PageSizeId.Letter,
    "Legal": QPageSize.PageSizeId.Legal,
}
_PAGE_SIZE_LABELS_BY_ID = {
    QPageSize.PageSizeId.A4: "A4",
    QPageSize.PageSizeId.A5: "A5",
    QPageSize.PageSizeId.Letter: "Letter",
    QPageSize.PageSizeId.Legal: "Legal",
}


@dataclass(frozen=True)
class PrintPageSettings:
    """Normalized page settings persisted under the print/ namespace."""

    margins: tuple[int, int, int, int] = DEFAULT_PRINT_MARGINS
    default_printer: str = ""
    page_size: str = DEFAULT_PAGE_SIZE
    page_size_name: str = DEFAULT_PAGE_SIZE
    page_width_mm: float = 0.0
    page_height_mm: float = 0.0
    orientation: str = DEFAULT_ORIENTATION

    def to_qpage_size(self) -> QPageSize:
        if self.page_size == "Thermal 80mm":
            return QPageSize(
                QSizeF(
                    self.page_width_mm or THERMAL_PAGE_WIDTH_MM,
                    self.page_height_mm or THERMAL_PAGE_HEIGHT_MM,
                ),
                QPageSize.Unit.Millimeter,
                "Thermal 80mm",
            )
        if self.page_size in _PAGE_SIZE_IDS:
            return QPageSize(_PAGE_SIZE_IDS[self.page_size])
        if self.page_width_mm > 0 and self.page_height_mm > 0:
            return QPageSize(
                QSizeF(float(self.page_width_mm), float(self.page_height_mm)),
                QPageSize.Unit.Millimeter,
                self.page_size_name or self.page_size or "Custom",
            )
        return QPageSize(_PAGE_SIZE_IDS[DEFAULT_PAGE_SIZE])


def load_print_page_settings(settings) -> PrintPageSettings:
    """Load and normalize persisted printer page preferences."""
    page_size, page_size_name, width_mm, height_mm = _load_page_size(settings)
    return PrintPageSettings(
        margins=load_margins(settings),
        default_printer=_clean_text(
            settings.value("print/default_printer", "", type=str)
        ),
        page_size=page_size,
        page_size_name=page_size_name,
        page_width_mm=width_mm,
        page_height_mm=height_mm,
        orientation=load_orientation(settings),
    )


def save_print_page_settings(settings, state: PrintPageSettings) -> None:
    """Persist normalized page preferences, including clearing blank printers."""
    settings.setValue("print/margins", serialize_margins(state.margins))
    if state.default_printer:
        settings.setValue("print/default_printer", state.default_printer)
    else:
        _remove_setting(settings, "print/default_printer")

    page_size = _clean_text(state.page_size) or DEFAULT_PAGE_SIZE
    settings.setValue("print/page_size", page_size)
    settings.setValue("print/page_size_name", state.page_size_name or page_size)

    width_mm = float(state.page_width_mm or 0.0)
    height_mm = float(state.page_height_mm or 0.0)
    if page_size == "Thermal 80mm" and (width_mm <= 0 or height_mm <= 0):
        width_mm = THERMAL_PAGE_WIDTH_MM
        height_mm = THERMAL_PAGE_HEIGHT_MM

    if width_mm > 0 and height_mm > 0:
        settings.setValue("print/page_width_mm", width_mm)
        settings.setValue("print/page_height_mm", height_mm)
    else:
        _remove_setting(settings, "print/page_width_mm")
        _remove_setting(settings, "print/page_height_mm")

    orientation = (
        state.orientation
        if state.orientation in SUPPORTED_ORIENTATIONS
        else DEFAULT_ORIENTATION
    )
    settings.setValue("print/orientation", orientation)
    settings.setValue(PRINT_ORIENTATION_MIGRATION_KEY, True)


def apply_print_page_settings_to_printer(
    printer: QPrinter,
    state: PrintPageSettings,
    *,
    include_default_printer: bool = True,
) -> None:
    """Apply persisted page preferences to a QPrinter."""
    if include_default_printer and state.default_printer:
        printer.setPrinterName(state.default_printer)
    printer.setPageSize(state.to_qpage_size())
    printer.setPageOrientation(qt_orientation(state.orientation))
    printer.setPageMargins(
        QMarginsF(*[float(value) for value in state.margins]),
        QPageLayout.Unit.Millimeter,
    )


def save_printer_page_settings(
    settings,
    printer: QPrinter,
    *,
    clear_empty_default: bool = False,
) -> None:
    """Persist the page setup currently held by a QPrinter."""
    printer_name = _clean_text(printer.printerName())
    if printer_name:
        settings.setValue("print/default_printer", printer_name)
    elif clear_empty_default:
        _remove_setting(settings, "print/default_printer")

    orientation = orientation_name(printer.pageLayout().orientation())
    settings.setValue("print/orientation", orientation)
    settings.setValue(PRINT_ORIENTATION_MIGRATION_KEY, True)

    page_size = printer.pageLayout().pageSize()
    label = page_size_label(page_size)
    size_mm = page_size.size(QPageSize.Unit.Millimeter)
    settings.setValue("print/page_size", label)
    settings.setValue("print/page_size_name", page_size.name() or label)
    settings.setValue("print/page_width_mm", _round_mm(size_mm.width()))
    settings.setValue("print/page_height_mm", _round_mm(size_mm.height()))

    margins = printer.pageLayout().margins(QPageLayout.Unit.Millimeter)
    settings.setValue(
        "print/margins",
        serialize_margins(
            (
                max(0, int(round(margins.left()))),
                max(0, int(round(margins.top()))),
                max(0, int(round(margins.right()))),
                max(0, int(round(margins.bottom()))),
            )
        ),
    )


def copy_printer_page_layout(source: QPrinter, target: QPrinter) -> None:
    """Copy page size, orientation, and margins from one printer to another."""
    layout = source.pageLayout()
    target.setPageSize(layout.pageSize())
    target.setPageOrientation(layout.orientation())
    target.setPageMargins(
        layout.margins(QPageLayout.Unit.Millimeter),
        QPageLayout.Unit.Millimeter,
    )


def load_margins(settings) -> tuple[int, int, int, int]:
    raw_value = settings.value(
        "print/margins",
        serialize_margins(DEFAULT_PRINT_MARGINS),
        type=str,
    )
    try:
        if isinstance(raw_value, (list, tuple)):
            values = tuple(int(value) for value in raw_value)
        else:
            values = tuple(int(part.strip()) for part in str(raw_value).split(","))
        if len(values) != 4:
            raise ValueError("expected four margin values")
    except TypeError, ValueError:
        LOGGER.warning("Invalid margin format in settings: %r", raw_value)
        return DEFAULT_PRINT_MARGINS
    return (
        max(0, values[0]),
        max(0, values[1]),
        max(0, values[2]),
        max(0, values[3]),
    )


def serialize_margins(margins: tuple[int, int, int, int]) -> str:
    return ",".join(str(max(0, int(value))) for value in margins)


def load_orientation(settings) -> str:
    raw_value = settings.value("print/orientation", None, type=str)
    explicit = bool(
        settings.value(
            PRINT_ORIENTATION_MIGRATION_KEY,
            False,
            type=bool,
        )
    )
    if raw_value in SUPPORTED_ORIENTATIONS:
        if raw_value == "Portrait" and not explicit:
            LOGGER.info(
                "Migrating legacy print orientation from Portrait to Landscape."
            )
            settings.setValue("print/orientation", DEFAULT_ORIENTATION)
            return DEFAULT_ORIENTATION
        return str(raw_value)
    if raw_value is not None:
        LOGGER.warning(
            "Invalid print/orientation setting value %r; using %s",
            raw_value,
            DEFAULT_ORIENTATION,
        )
    return DEFAULT_ORIENTATION


def qt_orientation(orientation: str) -> QPageLayout.Orientation:
    return (
        QPageLayout.Orientation.Landscape
        if orientation == "Landscape"
        else QPageLayout.Orientation.Portrait
    )


def orientation_name(orientation: QPageLayout.Orientation) -> str:
    return (
        "Landscape" if orientation == QPageLayout.Orientation.Landscape else "Portrait"
    )


def page_size_label(page_size: QPageSize) -> str:
    try:
        page_id = page_size.id()
    except Exception:
        page_id = None
    if page_id in _PAGE_SIZE_LABELS_BY_ID:
        return _PAGE_SIZE_LABELS_BY_ID[page_id]
    raw_name = (page_size.name() or "").strip()
    lowered = raw_name.lower()
    if lowered.startswith("letter"):
        return "Letter"
    if "thermal" in lowered and "80" in lowered:
        return "Thermal 80mm"
    return raw_name or DEFAULT_PAGE_SIZE


def available_printer_names() -> set[str]:
    try:
        return {
            _clean_text(printer.printerName())
            for printer in QPrinterInfo.availablePrinters()
            if _clean_text(printer.printerName())
        }
    except Exception as exc:
        LOGGER.warning("Failed to read available printers: %s", exc)
        return set()


def default_printer_name() -> str:
    try:
        return _clean_text(QPrinterInfo.defaultPrinter().printerName())
    except Exception:
        return ""


def validate_quick_print_printer(printer: QPrinter) -> tuple[bool, str]:
    """Return whether quick print has a usable target printer."""
    names = available_printer_names()
    printer_name = _clean_text(printer.printerName())
    if not names:
        return (
            False,
            "No printers are available. Add or reconnect a printer, then try again.",
        )
    if printer_name and printer_name not in names:
        return (
            False,
            f"The selected printer '{printer_name}' is no longer available. "
            "Choose another printer before quick printing.",
        )
    if not printer_name:
        system_default = default_printer_name()
        if not system_default or system_default not in names:
            return (
                False,
                "No default printer is configured. Choose a printer before quick printing.",
            )
    return True, ""


def _load_page_size(settings) -> tuple[str, str, float, float]:
    raw_page_size = _clean_text(
        settings.value("print/page_size", DEFAULT_PAGE_SIZE, type=str)
    )
    raw_page_size = "Letter" if raw_page_size == "Letter / ANSI A" else raw_page_size
    custom_name = _clean_text(
        settings.value("print/page_size_name", raw_page_size, type=str)
    )
    width_mm = _coerce_positive_float(
        settings.value("print/page_width_mm", 0.0, type=float)
    )
    height_mm = _coerce_positive_float(
        settings.value("print/page_height_mm", 0.0, type=float)
    )

    if raw_page_size in _PAGE_SIZE_IDS:
        return raw_page_size, raw_page_size, 0.0, 0.0
    if raw_page_size == "Thermal 80mm":
        return (
            raw_page_size,
            custom_name or raw_page_size,
            width_mm or THERMAL_PAGE_WIDTH_MM,
            height_mm or THERMAL_PAGE_HEIGHT_MM,
        )
    if width_mm > 0 and height_mm > 0:
        label = custom_name or raw_page_size or "Custom"
        return label, label, width_mm, height_mm

    LOGGER.warning(
        "Invalid print/page_size setting value %r; using %s",
        raw_page_size,
        DEFAULT_PAGE_SIZE,
    )
    return DEFAULT_PAGE_SIZE, DEFAULT_PAGE_SIZE, 0.0, 0.0


def _coerce_positive_float(value) -> float:
    try:
        numeric = float(value)
    except TypeError, ValueError:
        return 0.0
    return numeric if numeric > 0 else 0.0


def _clean_text(value) -> str:
    return str(value or "").strip()


def _round_mm(value: float) -> float:
    return float(round(float(value), 3))


def _remove_setting(settings, key: str) -> None:
    remove = getattr(settings, "remove", None)
    if callable(remove):
        remove(key)
