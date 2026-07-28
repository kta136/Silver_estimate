"""Direct QPainter rendering for Modern silver-bar reports."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QRectF
from PySide6.QtGui import QFont, QPainter
from PySide6.QtPrintSupport import QPrinter

from .modern_print_primitives import (
    ALTERNATE_ROW_BG,
    COLUMN_HEADER_BG,
    MUTED_TEXT,
    SECTION_BG,
    TEXT,
    TOTAL_BG,
    WHITE,
    ModernPrintStyle,
    build_modern_print_style,
    draw_table_row,
    draw_text,
    minimize_bottom_page_margin,
)
from .print_format_spec import MODERN_ESTIMATE_FORMAT_SPEC
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
    """Build and directly paint silver-bar inventory and list reports."""

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
        base_font = self._resolve_font(print_font)
        minimize_bottom_page_margin(printer)
        painter = QPainter()
        if not painter.begin(printer):
            raise RuntimeError("Could not initialize the silver-bar print painter.")

        try:
            painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
            page_rect = printer.pageRect(QPrinter.Unit.DevicePixel)
            page_width = max(1.0, float(page_rect.width()))
            page_height = max(1.0, float(page_rect.height()))
            style = build_modern_print_style(base_font, printer)
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
        point_size = (
            print_font.pointSizeF() if print_font is not None else spec.font_size
        )
        if point_size <= 0:
            point_size = spec.font_size
        font.setPointSizeF(max(1.0, point_size))
        return font


def _paginate(
    layout: SilverBarPrintLayout,
    style: ModernPrintStyle,
    page_height: float,
) -> tuple[_PrintPage, ...]:
    capacity = page_height - _header_height(layout, style)
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


def _header_height(
    layout: SilverBarPrintLayout,
    style: ModernPrintStyle,
) -> float:
    note_height = style.note_height if layout.note else 0.0
    return style.title_height + style.metadata_height + note_height + style.header_gap


def _paint_page(
    painter: QPainter,
    layout: SilverBarPrintLayout,
    page: _PrintPage,
    style: ModernPrintStyle,
    *,
    page_width: float,
) -> None:
    y = _draw_header(painter, layout, style, page_width)
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


def _draw_header(
    painter: QPainter,
    layout: SilverBarPrintLayout,
    style: ModernPrintStyle,
    page_width: float,
) -> float:
    y = 0.0
    title_rect = QRectF(0.0, y, page_width, style.title_height)
    draw_text(
        painter,
        title_rect,
        layout.title,
        font=style.title_font,
        metrics=style.title_metrics,
        alignment="center",
        padding=style.padding,
    )
    y += style.title_height

    metadata_width = page_width / 2.0
    draw_text(
        painter,
        QRectF(0.0, y, metadata_width, style.metadata_height),
        layout.left_metadata,
        font=style.bold_font,
        metrics=style.bold_metrics,
        alignment="left",
        padding=style.padding,
    )
    draw_text(
        painter,
        QRectF(metadata_width, y, page_width - metadata_width, style.metadata_height),
        layout.right_metadata,
        font=style.bold_font,
        metrics=style.bold_metrics,
        alignment="right",
        padding=style.padding,
    )
    y += style.metadata_height

    if layout.note:
        draw_text(
            painter,
            QRectF(0.0, y, page_width, style.note_height),
            f"Note: {layout.note}",
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


def _draw_table_header(  # noqa: PLR0913 - explicit page painting inputs
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
