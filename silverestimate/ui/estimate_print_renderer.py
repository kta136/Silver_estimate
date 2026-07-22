"""Direct QPainter rendering for Classic and Modern estimate documents."""

from __future__ import annotations

from dataclasses import dataclass, field, replace

from PyQt6.QtCore import QRectF, Qt
from PyQt6.QtGui import QColor, QFont, QFontMetricsF, QPainter, QPen
from PyQt6.QtPrintSupport import QPrinter

from .estimate_classic_renderer import (
    ClassicEstimateLayout,
    build_classic_estimate_layout,
    paint_classic_estimate,
)
from .estimate_print_document import EstimatePrintDocument
from .estimate_print_layout import (
    EstimatePrintColumn,
    EstimatePrintMetric,
    EstimatePrintRow,
    EstimatePrintSection,
    ModernEstimateLayout,
    build_modern_estimate_layout,
)
from .print_format_spec import MODERN_ESTIMATE_FORMAT_SPEC, normalize_estimate_format

_TEXT = QColor("#111827")
_MUTED_TEXT = QColor("#4b5563")
_BORDER = QColor("#6b7280")
_GRID = QColor("#cbd5e1")
_COLUMN_HEADER_BG = QColor("#e5e7eb")
_SECTION_BG = QColor("#dbeafe")
_RETURN_SECTION_BG = QColor("#fee2e2")
_TOTAL_BG = QColor("#f3f4f6")
_ALTERNATE_ROW_BG = QColor("#f8fafc")
_FINAL_BG = QColor("#1f2937")
_WHITE = QColor("#ffffff")
_REGULAR_SECTION_GAP_ROWS = 2.0


@dataclass(frozen=True)
class _PaintStyle:
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


@dataclass(frozen=True)
class _SectionFragment:
    section: EstimatePrintSection
    rows: tuple[EstimatePrintRow, ...]
    include_total: bool
    continued: bool


@dataclass
class _MutablePage:
    fragments: list[_SectionFragment] = field(default_factory=list)
    include_summary: bool = False
    used_height: float = 0.0


@dataclass(frozen=True)
class _PrintPage:
    fragments: tuple[_SectionFragment, ...]
    include_summary: bool


class EstimatePrintRenderer:
    """Build and directly paint Classic or Modern estimate documents."""

    def build_classic_layout(
        self,
        document: EstimatePrintDocument,
    ) -> ClassicEstimateLayout:
        """Build the former Modern/New fixed-width model, now named Classic."""
        return build_classic_estimate_layout(document)

    def build_modern_layout(
        self,
        document: EstimatePrintDocument,
    ) -> ModernEstimateLayout:
        """Build a semantic, device-independent Modern estimate layout."""
        return build_modern_estimate_layout(document)

    def paint(
        self,
        printer: QPrinter,
        document: EstimatePrintDocument,
        *,
        print_font: QFont | None = None,
    ) -> ModernEstimateLayout | ClassicEstimateLayout:
        """Paint the selected estimate format onto preview, PDF, or printer devices."""
        if normalize_estimate_format(document.format_key) == "classic":
            return paint_classic_estimate(
                printer,
                document,
                print_font=print_font,
            )
        layout = self.build_modern_layout(document)
        base_font = self._resolve_font(print_font)
        painter = QPainter()
        if not painter.begin(printer):
            raise RuntimeError("Could not initialize the estimate print painter.")

        try:
            painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
            page_rect = printer.pageRect(QPrinter.Unit.DevicePixel)
            page_width = max(1.0, float(page_rect.width()))
            page_height = max(1.0, float(page_rect.height()))
            style = _build_style(base_font, printer)
            pages = _paginate(layout, style, page_height)

            for page_index, page in enumerate(pages, start=1):
                if page_index > 1 and not printer.newPage():
                    raise RuntimeError("Could not create another print page.")
                _paint_page(
                    painter,
                    layout,
                    page,
                    style,
                    page_width=page_width,
                )
        finally:
            painter.end()

        return layout

    @staticmethod
    def _resolve_font(print_font: QFont | None) -> QFont:
        spec = MODERN_ESTIMATE_FORMAT_SPEC
        font = QFont(print_font) if print_font is not None else QFont(spec.font_family)
        configured_size = getattr(print_font, "float_size", spec.font_size)
        try:
            point_size = float(configured_size)
        except TypeError, ValueError:
            point_size = spec.font_size
        font.setPointSizeF(max(1.0, point_size))
        return font


def _build_style(base_font: QFont, printer: QPrinter) -> _PaintStyle:
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
    resolution = max(72, int(printer.resolution()))
    return _PaintStyle(
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
        section_gap=row_height * _REGULAR_SECTION_GAP_ROWS,
        metric_title_height=bold_metrics.height() * 1.45,
        metric_row_height=summary_metrics.height() * 2.65,
        summary_gap=base_height * 0.65,
        thin_pen=QPen(_GRID, max(1.0, resolution / 300.0)),
        border_pen=QPen(_BORDER, max(1.0, resolution / 180.0)),
        strong_pen=QPen(_TEXT, max(1.0, resolution / 90.0)),
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


def _paginate(
    layout: ModernEstimateLayout,
    style: _PaintStyle,
    page_height: float,
) -> tuple[_PrintPage, ...]:
    capacity = page_height - _header_height(layout, style)
    if capacity <= 0:
        raise ValueError("The printable page height is too small for an estimate.")

    pages = [_MutablePage()]
    for section in layout.sections:
        _paginate_section(pages, section, style, capacity)

    summary_height = _summary_height(layout, style)
    if summary_height > capacity:
        raise ValueError("The printable page is too small for the estimate summary.")
    current = _place_summary(pages, style, capacity, summary_height)
    current.include_summary = True
    current.used_height += summary_height
    return tuple(
        _PrintPage(tuple(page.fragments), page.include_summary) for page in pages
    )


def _paginate_section(
    pages: list[_MutablePage],
    section: EstimatePrintSection,
    style: _PaintStyle,
    capacity: float,
) -> None:
    row_index = 0
    continued = False
    header_height = style.section_header_height + style.column_header_height
    rows = section.rows

    while row_index < len(rows):
        page = pages[-1]
        remaining_rows = len(rows) - row_index
        minimum_height = header_height + style.row_height
        if remaining_rows == 1:
            minimum_height += style.total_height
        if page.used_height and page.used_height + minimum_height > capacity:
            page = _new_page(pages)

        available = capacity - page.used_height - header_height
        finish_height = remaining_rows * style.row_height + style.total_height
        if available >= finish_height:
            take = remaining_rows
            include_total = True
        else:
            take = int(available // style.row_height)
            if take >= remaining_rows:
                take = remaining_rows - 1
            include_total = False

        if take <= 0:
            if page.used_height:
                _new_page(pages)
                continue
            raise ValueError(f"The printable page is too small for {section.title}.")

        fragment = _SectionFragment(
            section=section,
            rows=rows[row_index : row_index + take],
            include_total=include_total,
            continued=continued,
        )
        page.fragments.append(fragment)
        page.used_height += header_height + take * style.row_height
        row_index += take
        if include_total:
            page.used_height += style.total_height + _section_gap_height(
                section,
                style,
            )
            break
        _new_page(pages)
        continued = True


def _new_page(pages: list[_MutablePage]) -> _MutablePage:
    page = _MutablePage()
    pages.append(page)
    return page


def _place_summary(
    pages: list[_MutablePage],
    style: _PaintStyle,
    capacity: float,
    summary_height: float,
) -> _MutablePage:
    current = pages[-1]
    if not current.used_height or current.used_height + summary_height <= capacity:
        return current
    summary_page = _new_page(pages)
    _move_last_rows_to_summary_page(
        pages[-2],
        summary_page,
        style,
        capacity=capacity,
        summary_height=summary_height,
    )
    return summary_page


def _move_last_rows_to_summary_page(
    previous_page: _MutablePage,
    summary_page: _MutablePage,
    style: _PaintStyle,
    *,
    capacity: float,
    summary_height: float,
) -> None:
    if not previous_page.fragments:
        return
    fragment = previous_page.fragments[-1]
    if not fragment.include_total or not fragment.rows:
        return

    header_height = style.section_header_height + style.column_header_height
    section_gap = _section_gap_height(fragment.section, style)
    fixed_height = header_height + style.total_height + section_gap
    available_for_rows = capacity - summary_height - fixed_height
    max_rows = int(available_for_rows // style.row_height)
    if max_rows <= 0:
        return

    keep_count = 1 if len(previous_page.fragments) == 1 else 0
    movable_count = len(fragment.rows) - keep_count
    if movable_count <= 0:
        return
    desired_count = max(1, min(8, len(fragment.rows) // 3))
    move_count = min(max_rows, movable_count, desired_count)
    moved_rows = fragment.rows[-move_count:]
    remaining_rows = fragment.rows[:-move_count]

    if remaining_rows:
        previous_page.fragments[-1] = replace(
            fragment,
            rows=remaining_rows,
            include_total=False,
        )
        previous_page.used_height -= (
            move_count * style.row_height + style.total_height + section_gap
        )
    else:
        previous_page.fragments.pop()
        previous_page.used_height -= (
            header_height
            + move_count * style.row_height
            + style.total_height
            + section_gap
        )

    summary_page.fragments.append(
        replace(
            fragment,
            rows=moved_rows,
            include_total=True,
            continued=True,
        )
    )
    summary_page.used_height += fixed_height + move_count * style.row_height


def _header_height(layout: ModernEstimateLayout, style: _PaintStyle) -> float:
    note_height = style.note_height if layout.note else 0.0
    return style.title_height + style.metadata_height + note_height + style.header_gap


def _summary_height(layout: ModernEstimateLayout, style: _PaintStyle) -> float:
    height = style.metric_title_height + style.metric_row_height
    if layout.last_balance_metrics:
        height += (
            style.metric_title_height + style.metric_row_height + style.summary_gap
        )
    return height


def _paint_page(
    painter: QPainter,
    layout: ModernEstimateLayout,
    page: _PrintPage,
    style: _PaintStyle,
    *,
    page_width: float,
) -> None:
    y = _draw_header(painter, layout, style, page_width)
    for fragment in page.fragments:
        y = _draw_section_fragment(
            painter,
            fragment,
            style,
            page_width=page_width,
            y=y,
        )
    if page.include_summary:
        _draw_summary(painter, layout, style, page_width=page_width, y=y)


def _draw_header(
    painter: QPainter,
    layout: ModernEstimateLayout,
    style: _PaintStyle,
    page_width: float,
) -> float:
    y = 0.0
    title_rect = QRectF(0.0, y, page_width, style.title_height)
    _draw_text(
        painter,
        title_rect,
        "ESTIMATE SLIP ONLY",
        font=style.title_font,
        metrics=style.title_metrics,
        alignment="center",
        padding=style.padding,
    )
    y += style.title_height

    widths = (0.50, 0.50)
    labels = (
        f"Voucher: {layout.voucher_no}",
        f"Silver Rate: {layout.silver_rate}",
    )
    alignments = ("left", "right")
    x = 0.0
    for ratio, label, alignment in zip(widths, labels, alignments, strict=True):
        width = page_width * ratio
        _draw_text(
            painter,
            QRectF(x, y, width, style.metadata_height),
            label,
            font=style.bold_font,
            metrics=style.bold_metrics,
            alignment=alignment,
            padding=style.padding,
        )
        x += width
    y += style.metadata_height

    if layout.note:
        _draw_text(
            painter,
            QRectF(0.0, y, page_width, style.note_height),
            f"Note: {layout.note}",
            font=style.base_font,
            metrics=style.base_metrics,
            alignment="left",
            padding=style.padding,
            color=_MUTED_TEXT,
        )
        y += style.note_height

    painter.setPen(style.strong_pen)
    painter.drawLine(0, int(y), int(page_width), int(y))
    return y + style.header_gap


def _draw_section_fragment(
    painter: QPainter,
    fragment: _SectionFragment,
    style: _PaintStyle,
    *,
    page_width: float,
    y: float,
) -> float:
    section = fragment.section
    title = f"{section.title} (continued)" if fragment.continued else section.title
    section_rect = QRectF(0.0, y, page_width, style.section_header_height)
    painter.fillRect(
        section_rect,
        _RETURN_SECTION_BG if section.is_return else _SECTION_BG,
    )
    painter.setPen(style.border_pen)
    painter.drawRect(section_rect)
    _draw_text(
        painter,
        section_rect,
        title,
        font=style.section_font,
        metrics=style.section_metrics,
        alignment="center",
        padding=style.padding,
    )
    y += style.section_header_height

    _draw_table_row(
        painter,
        section.columns,
        tuple(column.title for column in section.columns),
        style,
        page_width=page_width,
        y=y,
        height=style.column_header_height,
        font=style.bold_font,
        metrics=style.bold_metrics,
        background=_COLUMN_HEADER_BG,
        strong_border=True,
        fit_to_width=True,
    )
    y += style.column_header_height

    for row_index, row in enumerate(fragment.rows):
        _draw_table_row(
            painter,
            section.columns,
            row.values,
            style,
            page_width=page_width,
            y=y,
            height=style.row_height,
            font=style.base_font,
            metrics=style.base_metrics,
            background=_ALTERNATE_ROW_BG if row_index % 2 else _WHITE,
        )
        y += style.row_height

    if fragment.include_total:
        _draw_table_row(
            painter,
            section.columns,
            section.total_row.values,
            style,
            page_width=page_width,
            y=y,
            height=style.total_height,
            font=style.bold_font,
            metrics=style.bold_metrics,
            background=_TOTAL_BG,
            strong_border=True,
        )
        y += style.total_height + _section_gap_height(section, style)
    return y


def _section_gap_height(
    section: EstimatePrintSection,
    style: _PaintStyle,
) -> float:
    return style.section_gap if section.key == "regular" else 0.0


def _draw_table_row(
    painter: QPainter,
    columns: tuple[EstimatePrintColumn, ...],
    values: tuple[str, ...],
    style: _PaintStyle,
    *,
    page_width: float,
    y: float,
    height: float,
    font: QFont,
    metrics: QFontMetricsF,
    background: QColor,
    strong_border: bool = False,
    fit_to_width: bool = False,
) -> None:
    row_rect = QRectF(0.0, y, page_width, height)
    painter.fillRect(row_rect, background)
    painter.setPen(style.border_pen if strong_border else style.thin_pen)
    painter.drawRect(row_rect)
    for column, value, cell_rect in zip(
        columns,
        values,
        _column_rects(columns, page_width, y, height),
        strict=True,
    ):
        _draw_text(
            painter,
            cell_rect,
            value,
            font=font,
            metrics=metrics,
            alignment=column.alignment,
            padding=style.padding,
            fit_to_width=fit_to_width,
        )

    painter.setPen(style.thin_pen)
    for divider_x in _column_divider_positions(columns, page_width):
        painter.drawLine(
            int(divider_x),
            int(row_rect.top()),
            int(divider_x),
            int(row_rect.bottom()),
        )


def _column_rects(
    columns: tuple[EstimatePrintColumn, ...],
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


def _column_divider_positions(
    columns: tuple[EstimatePrintColumn, ...],
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


def _draw_summary(
    painter: QPainter,
    layout: ModernEstimateLayout,
    style: _PaintStyle,
    *,
    page_width: float,
    y: float,
) -> float:
    if layout.last_balance_metrics:
        y = _draw_metric_block(
            painter,
            "LAST BALANCE",
            layout.last_balance_metrics,
            style,
            page_width=page_width,
            y=y,
            dark_title=False,
        )
        y += style.summary_gap
    return _draw_metric_block(
        painter,
        "FINAL SILVER & AMOUNT",
        layout.final_metrics,
        style,
        page_width=page_width,
        y=y,
        dark_title=True,
    )


def _draw_metric_block(
    painter: QPainter,
    title: str,
    metrics: tuple[EstimatePrintMetric, ...],
    style: _PaintStyle,
    *,
    page_width: float,
    y: float,
    dark_title: bool,
) -> float:
    title_rect = QRectF(0.0, y, page_width, style.metric_title_height)
    painter.fillRect(title_rect, _FINAL_BG if dark_title else _COLUMN_HEADER_BG)
    painter.setPen(style.border_pen)
    painter.drawRect(title_rect)
    _draw_text(
        painter,
        title_rect,
        title,
        font=style.bold_font,
        metrics=style.bold_metrics,
        alignment="center",
        padding=style.padding,
        color=_WHITE if dark_title else _TEXT,
    )
    y += style.metric_title_height

    metric_width = page_width / max(1, len(metrics))
    for index, metric in enumerate(metrics):
        rect = QRectF(
            metric_width * index,
            y,
            metric_width
            if index < len(metrics) - 1
            else page_width - metric_width * index,
            style.metric_row_height,
        )
        painter.fillRect(rect, _TOTAL_BG if metric.emphasis else _WHITE)
        painter.setPen(style.strong_pen if metric.emphasis else style.border_pen)
        painter.drawRect(rect)
        label_rect = QRectF(rect.x(), rect.y(), rect.width(), rect.height() * 0.42)
        value_rect = QRectF(
            rect.x(),
            rect.y() + rect.height() * 0.38,
            rect.width(),
            rect.height() * 0.62,
        )
        _draw_text(
            painter,
            label_rect,
            metric.label,
            font=style.base_font,
            metrics=style.base_metrics,
            alignment="center",
            padding=style.padding,
            color=_MUTED_TEXT,
        )
        _draw_text(
            painter,
            value_rect,
            metric.value,
            font=style.summary_font,
            metrics=style.summary_metrics,
            alignment="center",
            padding=style.padding,
        )
    return y + style.metric_row_height


def _draw_text(
    painter: QPainter,
    rect: QRectF,
    text: str,
    *,
    font: QFont,
    metrics: QFontMetricsF,
    alignment: str,
    padding: float,
    color: QColor = _TEXT,
    fit_to_width: bool = False,
) -> None:
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
    "ClassicEstimateLayout",
    "EstimatePrintRenderer",
    "ModernEstimateLayout",
]
