"""Direct QPainter rendering for Modern silver-bar reports."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QRectF
from PySide6.QtGui import QFont, QPainter
from PySide6.QtPrintSupport import QPrinter

from .modern_print_primitives import (
    ALTERNATE_ROW_BG,
    COLUMN_HEADER_BG,
    SECTION_BG,
    TEXT,
    TOTAL_BG,
    WHITE,
    ModernPrintStyle,
    draw_report_header,
    draw_table_row,
    draw_text,
    minimize_bottom_page_margin,
    paint_report,
    report_header_height,
)
from .silver_bar_print_document import SilverBarPrintDocument
from .silver_bar_print_layout import (
    SilverBarPrintLayout,
    SilverBarPrintTableRow,
    build_silver_bar_print_layout,
)


@dataclass(frozen=True)
class _PrintPage:
    rows: tuple[SilverBarPrintTableRow, ...]
    include_total: bool
    continued: bool
    empty: bool = False


class SilverBarPrintRenderer:
    """Build and directly paint silver-bar list reports."""

    def build_layout(
        self,
        document: SilverBarPrintDocument,
    ) -> SilverBarPrintLayout:
        return build_silver_bar_print_layout(document)

    def paint(
        self,
        printer: QPrinter,
        document: SilverBarPrintDocument,
        *,
        print_font: QFont | None = None,
    ) -> SilverBarPrintLayout:
        layout = self.build_layout(document)
        minimize_bottom_page_margin(printer)
        paint_report(
            printer,
            print_font,
            what="silver-bar",
            paginate=lambda style, page_height: _paginate(layout, style, page_height),
            paint_page=lambda painter, page, style, page_width: _paint_page(
                painter, layout, page, style, page_width=page_width
            ),
        )
        return layout


def _paginate(
    layout: SilverBarPrintLayout,
    style: ModernPrintStyle,
    page_height: float,
) -> tuple[_PrintPage, ...]:
    capacity = page_height - report_header_height(style, has_note=bool(layout.note))
    capacity -= style.section_header_height + style.column_header_height
    if capacity <= 0:
        raise ValueError("The printable page height is too small for this report.")

    if not layout.rows:
        required = style.row_height + style.total_height
        if required > capacity:
            raise ValueError("The printable page is too small for this report.")
        return (_PrintPage((), include_total=True, continued=False, empty=True),)

    pages: list[_PrintPage] = []
    row_index = 0
    while row_index < len(layout.rows):
        remaining = len(layout.rows) - row_index
        finish_height = remaining * style.row_height + style.total_height
        if finish_height <= capacity:
            take = remaining
            include_total = True
        else:
            take = int(capacity // style.row_height)
            if take >= remaining:
                take = remaining - 1
            include_total = False

        if take <= 0:
            raise ValueError("The printable page is too small for report rows.")

        pages.append(
            _PrintPage(
                rows=layout.rows[row_index : row_index + take],
                include_total=include_total,
                continued=bool(pages),
            )
        )
        row_index += take

    return tuple(pages)


def _paint_page(
    painter: QPainter,
    layout: SilverBarPrintLayout,
    page: _PrintPage,
    style: ModernPrintStyle,
    *,
    page_width: float,
) -> None:
    y = draw_report_header(
        painter,
        style,
        page_width,
        title=layout.title,
        title_alignment="center",
        left=layout.left_metadata,
        right=layout.right_metadata,
        note=layout.note,
    )
    y = _draw_table_header(
        painter,
        layout,
        page,
        style,
        page_width=page_width,
        y=y,
    )

    if page.empty:
        y = _draw_empty_row(
            painter,
            layout.empty_message,
            style,
            page_width=page_width,
            y=y,
        )
    else:
        for row_index, row in enumerate(page.rows):
            draw_table_row(
                painter,
                layout.columns,
                row.values,
                style,
                page_width=page_width,
                y=y,
                height=style.row_height,
                font=style.base_font,
                metrics=style.base_metrics,
                background=ALTERNATE_ROW_BG if row_index % 2 else WHITE,
            )
            y += style.row_height

    if page.include_total:
        draw_table_row(
            painter,
            layout.columns,
            layout.total_row.values,
            style,
            page_width=page_width,
            y=y,
            height=style.total_height,
            font=style.bold_font,
            metrics=style.bold_metrics,
            background=TOTAL_BG,
            strong_border=True,
            fit_to_width=True,
        )


def _draw_table_header(
    painter: QPainter,
    layout: SilverBarPrintLayout,
    page: _PrintPage,
    style: ModernPrintStyle,
    *,
    page_width: float,
    y: float,
) -> float:
    section_title = (
        f"{layout.section_title} (continued)"
        if page.continued
        else layout.section_title
    )
    section_rect = QRectF(0.0, y, page_width, style.section_header_height)
    painter.fillRect(section_rect, SECTION_BG)
    painter.setPen(style.border_pen)
    painter.drawRect(section_rect)
    draw_text(
        painter,
        section_rect,
        section_title,
        font=style.section_font,
        metrics=style.section_metrics,
        alignment="center",
        padding=style.padding,
    )
    y += style.section_header_height

    draw_table_row(
        painter,
        layout.columns,
        tuple(f" {column.title} " for column in layout.columns),
        style,
        page_width=page_width,
        y=y,
        height=style.column_header_height,
        font=style.bold_font,
        metrics=style.bold_metrics,
        background=COLUMN_HEADER_BG,
        strong_border=True,
        fit_to_width=True,
    )
    return y + style.column_header_height


def _draw_empty_row(
    painter: QPainter,
    message: str,
    style: ModernPrintStyle,
    *,
    page_width: float,
    y: float,
) -> float:
    rect = QRectF(0.0, y, page_width, style.row_height)
    painter.fillRect(rect, WHITE)
    painter.setPen(style.thin_pen)
    painter.drawRect(rect)
    draw_text(
        painter,
        rect,
        message,
        font=style.base_font,
        metrics=style.base_metrics,
        alignment="center",
        padding=style.padding,
        color=TEXT,
    )
    return y + style.row_height


__all__ = [
    "SilverBarPrintLayout",
    "SilverBarPrintRenderer",
]
