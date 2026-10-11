"""Direct QPainter rendering for Modern estimate documents."""

from __future__ import annotations

from dataclasses import dataclass, field, replace

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QImage, QPageLayout, QPainter
from PySide6.QtPrintSupport import QPrinter

from .estimate_print_document import EstimatePrintDocument
from .estimate_print_layout import (
    EstimatePrintMetric,
    EstimatePrintRow,
    EstimatePrintSection,
    ModernEstimateLayout,
    build_modern_estimate_layout,
)
from .modern_print_primitives import (
    ALTERNATE_ROW_BG as _ALTERNATE_ROW_BG,
)
from .modern_print_primitives import (
    FINAL_BG as _FINAL_BG,
)
from .modern_print_primitives import (
    MUTED_TEXT as _MUTED_TEXT,
)
from .modern_print_primitives import (
    TEXT as _TEXT,
)
from .modern_print_primitives import (
    WHITE as _WHITE,
)
from .modern_print_primitives import (
    ModernPrintStyle as _PaintStyle,
)
from .modern_print_primitives import (
    build_modern_print_style as _build_style,
)
from .modern_print_primitives import (
    draw_report_header as _draw_report_header,
)
from .modern_print_primitives import (
    draw_table_row as _draw_table_row,
)
from .modern_print_primitives import (
    draw_text as _draw_text,
)
from .modern_print_primitives import (
    paint_report as _paint_report,
)
from .modern_print_primitives import (
    report_header_height as _report_header_height,
)
from .modern_print_primitives import (
    resolve_print_font as _resolve_print_font,
)

_TOTAL_BG = QColor("#e0f2f3")
_COLUMN_HEADER_BG = QColor("#f4f5f6")


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
    """Build and directly paint Modern estimate documents."""

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
    ) -> ModernEstimateLayout:
        """Paint the selected estimate format onto preview, PDF, or printer devices."""
        layout = self.build_modern_layout(document)
        _paint_report(
            printer,
            print_font,
            what="estimate",
            paginate=lambda style, page_height: _paginate(layout, style, page_height),
            paint_page=lambda painter, page, style, page_width: _paint_page(
                painter, layout, page, style, page_width=page_width
            ),
        )
        return layout

    def paint_first_page_image(
        self,
        document: EstimatePrintDocument,
        page_layout: QPageLayout,
        *,
        print_font: QFont | None = None,
        longest_side: int = 1200,
    ) -> QImage:
        """Paint the first page straight onto an image, for on-screen samples."""
        layout = self.build_modern_layout(document)
        base_font = _resolve_print_font(print_font)
        page_points = page_layout.fullRectPoints()
        resolution = max(
            72,
            round(longest_side * 72 / max(page_points.width(), page_points.height())),
        )
        paint_rect = page_layout.paintRectPixels(resolution)
        image = QImage(
            page_layout.fullRectPixels(resolution).size(),
            QImage.Format.Format_ARGB32_Premultiplied,
        )
        dots_per_metre = round(resolution / 0.0254)
        image.setDotsPerMeterX(dots_per_metre)
        image.setDotsPerMeterY(dots_per_metre)
        image.fill(Qt.GlobalColor.white)
        painter = QPainter()
        if not painter.begin(image):
            raise RuntimeError("Could not initialize the estimate sample painter.")
        try:
            painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
            painter.translate(paint_rect.topLeft())
            style = _build_style(base_font, image, resolution)
            pages = _paginate(layout, style, max(1.0, float(paint_rect.height())))
            _paint_page(
                painter,
                layout,
                pages[0],
                style,
                page_width=max(1.0, float(paint_rect.width())),
            )
        finally:
            painter.end()
        return image


def _paginate(
    layout: ModernEstimateLayout,
    style: _PaintStyle,
    page_height: float,
) -> tuple[_PrintPage, ...]:
    capacity = page_height - _report_header_height(style, has_note=bool(layout.note))
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


def _summary_height(layout: ModernEstimateLayout, style: _PaintStyle) -> float:
    height = style.summary_gap + style.metric_title_height + style.metric_row_height
    if layout.last_balance_metrics:
        height += style.metadata_height + style.summary_gap
    return height


def _paint_page(
    painter: QPainter,
    layout: ModernEstimateLayout,
    page: _PrintPage,
    style: _PaintStyle,
    *,
    page_width: float,
) -> None:
    y = _draw_report_header(
        painter,
        style,
        page_width,
        title="ESTIMATE SLIP",
        title_alignment="left",
        left=f"Voucher: {layout.voucher_no}",
        right=f"Silver Rate: {layout.silver_rate}",
        note=layout.note,
    )
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
        _WHITE,
    )
    painter.setPen(style.border_pen)
    _draw_text(
        painter,
        section_rect,
        title,
        font=style.section_font,
        metrics=style.section_metrics,
        alignment="left",
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
            fit_to_width=True,
            elide_columns=tuple(
                i
                for i, column in enumerate(section.columns)
                if column.key in {"name", "tunch", "type"}
            ),
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
            fit_to_width=True,
        )
        y += style.total_height + _section_gap_height(section, style)
    return y


def _section_gap_height(
    section: EstimatePrintSection,
    style: _PaintStyle,
) -> float:
    return style.section_gap * 0.25


def _draw_summary(
    painter: QPainter,
    layout: ModernEstimateLayout,
    style: _PaintStyle,
    *,
    page_width: float,
    y: float,
) -> float:
    if layout.last_balance_metrics:
        disclosure = "Last balance included: " + "  ·  ".join(
            f"{metric.label}: {metric.value}" for metric in layout.last_balance_metrics
        )
        _draw_text(
            painter,
            QRectF(0, y, page_width, style.metadata_height),
            disclosure,
            font=style.base_font,
            metrics=style.base_metrics,
            alignment="left",
            padding=style.padding,
            color=_MUTED_TEXT,
            fit_to_width=True,
        )
        y += style.metadata_height + style.summary_gap
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
            fit_to_width=True,
        )
        _draw_text(
            painter,
            value_rect,
            metric.value,
            font=style.summary_font,
            metrics=style.summary_metrics,
            alignment="center",
            padding=style.padding,
            fit_to_width=True,
        )
    return y + style.metric_row_height


__all__ = [
    "EstimatePrintRenderer",
    "ModernEstimateLayout",
]
