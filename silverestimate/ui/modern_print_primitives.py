"""Shared visual primitives for Modern direct-painted print reports."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal, Protocol, Sequence, cast

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QFontMetricsF, QPaintDevice, QPainter, QPen
from PySide6.QtPrintSupport import QPrinter

from .print_format_spec import MODERN_ESTIMATE_FORMAT_SPEC

PrintAlignment = Literal["left", "center", "right"]

TEXT = QColor("#111827")
MUTED_TEXT = QColor("#4b5563")
BORDER = QColor("#6b7280")
GRID = QColor("#cbd5e1")
COLUMN_HEADER_BG = QColor("#e5e7eb")
SECTION_BG = QColor("#dbeafe")
TOTAL_BG = QColor("#f3f4f6")
ALTERNATE_ROW_BG = QColor("#f8fafc")
FINAL_BG = QColor("#1f2937")
WHITE = QColor("#ffffff")


class PrintColumn(Protocol):
    """Structural column contract shared by semantic report layouts."""

    @property
    def start_ratio(self) -> float: ...

    @property
    def width_ratio(self) -> float: ...

    @property
    def alignment(self) -> PrintAlignment: ...


@dataclass(frozen=True)
class ModernPrintStyle:
    base_font: QFont
    bold_font: QFont
    title_font: QFont
    section_font: QFont
    summary_font: QFont
    base_metrics: QFontMetricsF
    bold_metrics: QFontMetricsF
    title_metrics: QFontMetricsF
    section_metrics: QFontMetricsF
    summary_metrics: QFontMetricsF
    padding: float
    title_height: float
    metadata_height: float
    note_height: float
    header_gap: float
    section_header_height: float
    column_header_height: float
    row_height: float
    total_height: float
    section_gap: float
    metric_title_height: float
    metric_row_height: float
    summary_gap: float
    thin_pen: QPen
    border_pen: QPen
    strong_pen: QPen


def minimize_bottom_page_margin(printer: QPrinter) -> None:
    """Use the printer's minimum supported bottom margin for Modern reports."""

    page_layout = printer.pageLayout()
    unit = page_layout.units()
    margins = page_layout.margins(unit)
    margins.setBottom(page_layout.minimumMargins().bottom())
    printer.setPageMargins(margins, unit)


def build_modern_print_style(
    base_font: QFont,
    printer: QPaintDevice,
    resolution: int | None = None,
) -> ModernPrintStyle:
    """Build device-aware fonts, measurements, and pens for a report.

    ``resolution`` is needed only for a device that is not a printer.
    """

    bold_font = _font_variant(base_font, bold=True)
    title_font = _font_variant(base_font, point_delta=2.0, bold=True)
    section_font = _font_variant(base_font, point_delta=0.5, bold=True)
    summary_font = _font_variant(base_font, point_delta=1.0, bold=True)
    base_metrics = QFontMetricsF(base_font, printer)
    bold_metrics = QFontMetricsF(bold_font, printer)
    title_metrics = QFontMetricsF(title_font, printer)
    section_metrics = QFontMetricsF(section_font, printer)
    summary_metrics = QFontMetricsF(summary_font, printer)
    base_height = max(1.0, base_metrics.height())
    row_height = base_height * 1.55
    if resolution is None:
        resolution = int(cast(QPrinter, printer).resolution())
    resolution = max(72, resolution)
    return ModernPrintStyle(
        base_font=base_font,
        bold_font=bold_font,
        title_font=title_font,
        section_font=section_font,
        summary_font=summary_font,
        base_metrics=base_metrics,
        bold_metrics=bold_metrics,
        title_metrics=title_metrics,
        section_metrics=section_metrics,
        summary_metrics=summary_metrics,
        padding=max(2.0, base_metrics.horizontalAdvance(" ") * 0.65),
        title_height=title_metrics.height() * 1.35,
        metadata_height=bold_metrics.height() * 1.45,
        note_height=base_height * 1.35,
        header_gap=base_height * 0.45,
        section_header_height=section_metrics.height() * 1.45,
        column_header_height=bold_metrics.height() * 1.75,
        row_height=row_height,
        total_height=bold_metrics.height() * 1.65,
        section_gap=row_height * 2.0,
        metric_title_height=bold_metrics.height() * 1.45,
        metric_row_height=summary_metrics.height() * 2.65,
        summary_gap=base_height * 0.65,
        thin_pen=QPen(GRID, max(1.0, resolution / 300.0)),
        border_pen=QPen(BORDER, max(1.0, resolution / 180.0)),
        strong_pen=QPen(TEXT, max(1.0, resolution / 90.0)),
    )


def resolve_print_font(print_font: QFont | None) -> QFont:
    """Return the chosen print font, or the Modern format's own when unset."""
    spec = MODERN_ESTIMATE_FORMAT_SPEC
    font = QFont(print_font) if print_font is not None else QFont(spec.font_family)
    point_size = print_font.pointSizeF() if print_font is not None else spec.font_size
    if point_size <= 0:
        point_size = spec.font_size
    font.setPointSizeF(max(1.0, point_size))
    return font


def paint_report[PageT](
    printer: QPrinter,
    print_font: QFont | None,
    *,
    what: str,
    paginate: Callable[[ModernPrintStyle, float], Sequence[PageT]],
    paint_page: Callable[[QPainter, PageT, ModernPrintStyle, float], None],
) -> None:
    """Paint a report onto a preview, PDF, or printer device, page by page.

    ``paginate`` receives the style and the page height; ``paint_page``
    receives the painter, one page, the style and the page width.
    """
    base_font = resolve_print_font(print_font)
    painter = QPainter()
    if not painter.begin(printer):
        raise RuntimeError(f"Could not initialize the {what} print painter.")

    try:
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
        page_rect = printer.pageRect(QPrinter.Unit.DevicePixel)
        page_width = max(1.0, float(page_rect.width()))
        page_height = max(1.0, float(page_rect.height()))
        style = build_modern_print_style(base_font, printer)
        for page_index, page in enumerate(paginate(style, page_height), start=1):
            if page_index > 1 and not printer.newPage():
                raise RuntimeError("Could not create another print page.")
            paint_page(painter, page, style, page_width)
    finally:
        painter.end()


def report_header_height(style: ModernPrintStyle, *, has_note: bool) -> float:
    """Height of the title, the metadata line, the optional note and the gap."""
    note_height = style.note_height if has_note else 0.0
    return style.title_height + style.metadata_height + note_height + style.header_gap


def draw_report_header(
    painter: QPainter,
    style: ModernPrintStyle,
    page_width: float,
    *,
    title: str,
    title_alignment: PrintAlignment,
    left: str,
    right: str,
    note: str,
) -> float:
    """Draw the title, the two metadata halves and the note; return the next y."""
    y = 0.0
    draw_text(
        painter,
        QRectF(0.0, y, page_width, style.title_height),
        title,
        font=style.title_font,
        metrics=style.title_metrics,
        alignment=title_alignment,
        padding=style.padding,
    )
    y += style.title_height

    metadata_width = page_width / 2.0
    draw_text(
        painter,
        QRectF(0.0, y, metadata_width, style.metadata_height),
        left,
        font=style.bold_font,
        metrics=style.bold_metrics,
        alignment="left",
        padding=style.padding,
    )
    draw_text(
        painter,
        QRectF(metadata_width, y, page_width - metadata_width, style.metadata_height),
        right,
        font=style.bold_font,
        metrics=style.bold_metrics,
        alignment="right",
        padding=style.padding,
    )
    y += style.metadata_height

    if note:
        draw_text(
            painter,
            QRectF(0.0, y, page_width, style.note_height),
            f"Note: {note}",
            font=style.base_font,
            metrics=style.base_metrics,
            alignment="left",
            padding=style.padding,
            color=MUTED_TEXT,
        )
        y += style.note_height

    painter.setPen(style.strong_pen)
    painter.drawLine(0, int(y), int(page_width), int(y))
    return y + style.header_gap


def draw_table_row(
    painter: QPainter,
    columns: Sequence[PrintColumn],
    values: Sequence[str],
    style: ModernPrintStyle,
    *,
    page_width: float,
    y: float,
    height: float,
    font: QFont,
    metrics: QFontMetricsF,
    background: QColor,
    strong_border: bool = False,
    fit_to_width: bool = False,
    elide_columns: tuple[int, ...] = (),
) -> None:
    """Draw one grid-aligned table row."""

    row_rect = QRectF(0.0, y, page_width, height)
    painter.fillRect(row_rect, background)
    painter.setPen(style.border_pen if strong_border else style.thin_pen)
    painter.drawRect(row_rect)
    for column_index, (column, value, cell_rect) in enumerate(
        zip(
            columns,
            values,
            _column_rects(columns, page_width, y, height),
            strict=True,
        )
    ):
        draw_text(
            painter,
            cell_rect,
            value,
            font=font,
            metrics=metrics,
            alignment=column.alignment,
            padding=style.padding,
            fit_to_width=fit_to_width and column_index not in elide_columns,
        )

    painter.setPen(style.thin_pen)
    for divider_x in column_divider_positions(columns, page_width):
        painter.drawLine(
            int(divider_x),
            int(row_rect.top()),
            int(divider_x),
            int(row_rect.bottom()),
        )


def column_divider_positions(
    columns: Sequence[PrintColumn],
    page_width: float,
) -> tuple[float, ...]:
    """Return every internal column edge once, including edges around gaps."""

    ratios = {
        round(ratio, 10)
        for column in columns
        for ratio in (column.start_ratio, column.start_ratio + column.width_ratio)
        if 0.0 < ratio < 1.0
    }
    return tuple(page_width * ratio for ratio in sorted(ratios))


def draw_text(
    painter: QPainter,
    rect: QRectF,
    text: str,
    *,
    font: QFont,
    metrics: QFontMetricsF,
    alignment: PrintAlignment,
    padding: float,
    color: QColor = TEXT,
    fit_to_width: bool = False,
) -> None:
    """Draw one elided, vertically centered line of plain text."""

    inner = rect.adjusted(padding, 0.0, -padding, 0.0)
    available_width = max(0, int(inner.width()))
    value = str(text or "")
    draw_font = font
    draw_metrics = metrics
    if fit_to_width:
        draw_font, draw_metrics = _fit_font_to_width(
            painter,
            font,
            metrics,
            value,
            available_width,
        )
    rendered = draw_metrics.elidedText(
        value,
        Qt.TextElideMode.ElideRight,
        available_width,
    )
    horizontal = {
        "left": Qt.AlignmentFlag.AlignLeft,
        "center": Qt.AlignmentFlag.AlignHCenter,
        "right": Qt.AlignmentFlag.AlignRight,
    }.get(alignment, Qt.AlignmentFlag.AlignLeft)
    painter.setFont(draw_font)
    painter.setPen(color)
    painter.drawText(
        inner,
        horizontal | Qt.AlignmentFlag.AlignVCenter | Qt.TextFlag.TextSingleLine,
        rendered,
    )


def _font_variant(
    source: QFont,
    *,
    point_delta: float = 0.0,
    bold: bool = False,
) -> QFont:
    font = QFont(source)
    font.setPointSizeF(max(1.0, source.pointSizeF() + point_delta))
    font.setBold(bold)
    return font


def _column_rects(
    columns: Sequence[PrintColumn],
    page_width: float,
    y: float,
    height: float,
) -> tuple[QRectF, ...]:
    rects = []
    for column in columns:
        x = page_width * column.start_ratio
        end_ratio = column.start_ratio + column.width_ratio
        width = page_width - x if end_ratio >= 1.0 else page_width * column.width_ratio
        rects.append(QRectF(x, y, width, height))
    return tuple(rects)


def _fit_font_to_width(
    painter: QPainter,
    font: QFont,
    metrics: QFontMetricsF,
    text: str,
    available_width: int,
) -> tuple[QFont, QFontMetricsF]:
    """Shrink a single-line label just enough to preserve its complete text."""

    required_width = metrics.horizontalAdvance(text)
    point_size = font.pointSizeF()
    if (
        not text
        or available_width <= 0
        or required_width <= available_width
        or required_width <= 0.0
        or point_size <= 0.0
    ):
        return font, metrics

    fitted = QFont(font)
    target_width = max(1.0, available_width - 2.0)
    scale = max(0.01, target_width / required_width)
    fitted.setPointSizeF(max(1.0, point_size * scale * 0.95))
    device = painter.device()
    for _attempt in range(4):
        fitted_metrics = (
            QFontMetricsF(fitted, device)
            if device is not None
            else QFontMetricsF(fitted)
        )
        fitted_width = fitted_metrics.horizontalAdvance(text)
        if fitted_width <= target_width or fitted.pointSizeF() <= 1.0:
            break
        fitted.setPointSizeF(
            max(1.0, fitted.pointSizeF() * target_width / fitted_width * 0.95)
        )
    return fitted, fitted_metrics


__all__ = [
    "ALTERNATE_ROW_BG",
    "COLUMN_HEADER_BG",
    "FINAL_BG",
    "MUTED_TEXT",
    "ModernPrintStyle",
    "PrintAlignment",
    "PrintColumn",
    "SECTION_BG",
    "TEXT",
    "TOTAL_BG",
    "WHITE",
    "build_modern_print_style",
    "column_divider_positions",
    "draw_report_header",
    "draw_table_row",
    "draw_text",
    "minimize_bottom_page_margin",
    "paint_report",
    "report_header_height",
    "resolve_print_font",
]
