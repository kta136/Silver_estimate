"""Direct painter for the previous Modern/New layout, now named Classic."""

from __future__ import annotations

from dataclasses import dataclass
from math import floor

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QFont, QFontMetricsF, QPainter
from PySide6.QtPrintSupport import QPrinter

from .estimate_print_document import EstimatePrintDocument, EstimatePrintItem
from .print_format_spec import CLASSIC_ESTIMATE_FORMAT_SPEC

_SNO_WIDTH = 3
_NAME_WIDTH = 18
_TUNCH_WIDTH = 7
_GROSS_WIDTH = 9
_POLY_WIDTH = 9
_NET_WIDTH = 9
_PURITY_WIDTH = 8
_WAGE_RATE_WIDTH = 9
_PIECES_WIDTH = 9
_FINE_WIDTH = 9
_LABOUR_WIDTH = 9
_LINE_WIDTH = sum(
    (
        _SNO_WIDTH,
        _NAME_WIDTH,
        _GROSS_WIDTH,
        _POLY_WIDTH,
        _NET_WIDTH,
        _PURITY_WIDTH,
        _WAGE_RATE_WIDTH,
        _PIECES_WIDTH,
        _FINE_WIDTH,
        _LABOUR_WIDTH,
        9,
    )
)


@dataclass(frozen=True)
class ClassicEstimateLayout:
    """Stable fixed-width model of the application's previous Modern format."""

    lines: tuple[str, ...]

    def normalized_text(self) -> str:
        return "\n".join(line.rstrip() for line in self.lines)


@dataclass
class _Totals:
    fine: float = 0.0
    wage: float = 0.0
    gross: float = 0.0
    poly: float = 0.0
    net: float = 0.0


@dataclass(frozen=True)
class _SectionSpec:
    title: str | None
    items: tuple[EstimatePrintItem, ...]
    include_wage_rate: bool = True
    include_pieces: bool = True


@dataclass(frozen=True)
class _RowValues:
    sno: str = ""
    name: str = ""
    tunch: str | None = None
    gross: float | None = None
    poly: float | None = None
    net: float | None = None
    purity: float | None = None
    wage_rate: float | None = None
    pieces: float | None = None
    fine: float | None = None
    labour: float | None = None


def build_classic_estimate_layout(
    document: EstimatePrintDocument,
) -> ClassicEstimateLayout:
    """Build the former Modern/New fixed-width format from typed data."""
    header = document.header
    show_tunch = document.show_tunch
    line_width = _line_width(show_tunch)
    regular, bars, returns, returned_bars = _split_items(document.items)
    lines = [
        _title_line(header.note, line_width=line_width),
        _voucher_line(
            header.voucher_no,
            header.silver_rate,
            line_width=line_width,
        ),
    ]
    separator = "=" * line_width
    dash = "-" * line_width
    column_header = _column_header(show_tunch=show_tunch, line_width=line_width)
    lines.extend((separator, column_header, separator))

    totals: list[_Totals] = []
    sections = (
        _SectionSpec(None, regular),
        _SectionSpec("* * Silver Bars * *", bars, False, False),
        _SectionSpec("* * Return Goods * *", returns),
        _SectionSpec("* * Return Silver Bar * *", returned_bars, False, False),
    )
    populated = tuple(section for section in sections if section.items)
    for index, section in enumerate(populated):
        if index:
            lines.append("")
        totals.append(
            _append_section(
                lines,
                section,
                column_header=column_header,
                dash=dash,
                separator=separator,
                show_tunch=show_tunch,
                line_width=line_width,
            )
        )
    while len(totals) < 4:
        totals.append(_Totals())
    totals_by_section = {
        section.title: total for section, total in zip(populated, totals, strict=False)
    }
    regular_totals = totals_by_section.get(None, _Totals())
    bar_totals = totals_by_section.get("* * Silver Bars * *", _Totals())
    return_totals = totals_by_section.get("* * Return Goods * *", _Totals())
    returned_bar_totals = totals_by_section.get("* * Return Silver Bar * *", _Totals())

    last_silver = header.last_balance_silver
    last_amount = header.last_balance_amount
    if last_silver > 0 or last_amount > 0:
        balance = (
            f"Silver: {_grouped(last_silver, decimals=1)} g   "
            f"Amount: Rs. {_grouped(last_amount, decimals=1)}"
        )
        lines.extend(
            (
                "* * Last Balance * *".center(line_width),
                dash,
                balance.center(line_width),
                dash,
            )
        )

    net_fine = (
        regular_totals.fine
        - bar_totals.fine
        - return_totals.fine
        - returned_bar_totals.fine
        + (last_silver if last_silver > 0 else 0.0)
    )
    net_wage = (
        regular_totals.wage
        - bar_totals.wage
        - return_totals.wage
        - returned_bar_totals.wage
        + (last_amount if last_amount > 0 else 0.0)
    )
    silver_cost = net_fine * header.silver_rate
    total_cost = net_wage + silver_cost
    lines.extend(
        (
            "Final Silver & Amount".center(line_width),
            separator,
            _final_line(
                net_fine,
                net_wage,
                silver_cost,
                total_cost,
                include_cost=header.silver_rate > 0,
                line_width=line_width,
            ),
            separator,
        )
    )
    return ClassicEstimateLayout(tuple(lines))


def paint_classic_estimate(
    printer: QPrinter,
    document: EstimatePrintDocument,
    *,
    print_font: QFont | None = None,
) -> ClassicEstimateLayout:
    """Paint Classic directly without an HTML or QTextDocument intermediary."""
    layout = build_classic_estimate_layout(document)
    font = _resolve_font(print_font)
    painter = QPainter()
    if not painter.begin(printer):
        raise RuntimeError("Could not initialize the Classic estimate painter.")
    try:
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
        page_rect = printer.pageRect(QPrinter.Unit.DevicePixel)
        page_width = max(1.0, float(page_rect.width()))
        page_height = max(1.0, float(page_rect.height()))
        font, metrics = _fit_font(
            font,
            printer,
            page_width,
            line_width=_line_width(document.show_tunch),
        )
        line_height = max(1.0, metrics.height() * 1.08)
        lines_per_page = max(1, floor(page_height / line_height))
        painter.setFont(font)
        for index, line in enumerate(layout.lines):
            page_line = index % lines_per_page
            if index and page_line == 0 and not printer.newPage():
                raise RuntimeError("Could not create another Classic estimate page.")
            painter.drawText(
                QRectF(0.0, page_line * line_height, page_width, line_height),
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                line,
            )
    finally:
        painter.end()
    return layout


def _resolve_font(print_font: QFont | None) -> QFont:
    spec = CLASSIC_ESTIMATE_FORMAT_SPEC
    point_size = print_font.pointSizeF() if print_font is not None else spec.font_size
    if point_size <= 0:
        point_size = spec.font_size
    font = QFont(spec.font_family)
    font.setPointSizeF(max(1.0, point_size))
    font.setBold(bool(print_font.bold()) if print_font is not None else False)
    return font


def _fit_font(
    font: QFont,
    printer: QPrinter,
    page_width: float,
    *,
    line_width: int,
) -> tuple[QFont, QFontMetricsF]:
    metrics = QFontMetricsF(font, printer)
    required = metrics.horizontalAdvance("M" * line_width)
    if required <= page_width or required <= 0:
        return font, metrics
    fitted = QFont(font)
    fitted.setPointSizeF(max(1.0, font.pointSizeF() * page_width / required))
    return fitted, QFontMetricsF(fitted, printer)


def _split_items(
    items: tuple[EstimatePrintItem, ...],
) -> tuple[
    tuple[EstimatePrintItem, ...],
    tuple[EstimatePrintItem, ...],
    tuple[EstimatePrintItem, ...],
    tuple[EstimatePrintItem, ...],
]:
    return (
        tuple(item for item in items if not item.is_return and not item.is_silver_bar),
        tuple(item for item in items if not item.is_return and item.is_silver_bar),
        tuple(item for item in items if item.is_return and not item.is_silver_bar),
        tuple(item for item in items if item.is_return and item.is_silver_bar),
    )


def _line_width(show_tunch: bool) -> int:
    return _LINE_WIDTH + (_TUNCH_WIDTH + 1 if show_tunch else 0)


def _title_line(note: str, *, line_width: int) -> str:
    title = "* * ESTIMATE SLIP ONLY * *"
    normalized_note = note.strip()
    if not normalized_note:
        return title.center(line_width)
    available = max(0, line_width - len(title) - 5)
    combined = f"{title}     {_truncate(normalized_note, available)}"
    return combined.center(line_width)[:line_width]


def _voucher_line(voucher_no: str, silver_rate: float, *, line_width: int) -> str:
    voucher = voucher_no.ljust(15)
    rate = f"S.Rate :{silver_rate:10.1f}"
    return f"{voucher}{' ' * max(1, line_width - len(voucher) - len(rate))}{rate}"


def _column_header(*, show_tunch: bool, line_width: int) -> str:
    parts = [
        "SNo".ljust(_SNO_WIDTH),
        "Item Name".ljust(_NAME_WIDTH),
    ]
    if show_tunch:
        parts.append("Tunch".ljust(_TUNCH_WIDTH))
    parts.extend(
        (
            "Gross".ljust(_GROSS_WIDTH),
            "Poly".ljust(_POLY_WIDTH),
            "Net".ljust(_NET_WIDTH),
            "%".ljust(_PURITY_WIDTH),
            "W Rate".ljust(_WAGE_RATE_WIDTH),
            "PCS".ljust(_PIECES_WIDTH),
            "Fine".ljust(_FINE_WIDTH),
            "Lbr".ljust(_LABOUR_WIDTH),
        )
    )
    return " ".join(parts)[:line_width]


def _append_section(  # noqa: PLR0913 - explicit fixed-width rendering context
    lines: list[str],
    section: _SectionSpec,
    *,
    column_header: str,
    dash: str,
    separator: str,
    show_tunch: bool,
    line_width: int,
) -> _Totals:
    if section.title:
        lines.extend((section.title.center(line_width), dash, column_header, dash))
    totals = _Totals()
    for index, item in enumerate(section.items, start=1):
        totals.fine += item.fine
        totals.wage += item.wage
        totals.gross += item.gross
        totals.poly += item.poly
        totals.net += item.net_wt
        lines.append(
            _row_line(
                _RowValues(
                    sno=str(index),
                    name=item.item_name,
                    tunch=item.tunch,
                    gross=item.gross,
                    poly=item.poly,
                    net=item.net_wt,
                    purity=item.purity,
                    wage_rate=(item.wage_rate if section.include_wage_rate else None),
                    pieces=item.pieces if section.include_pieces else None,
                    fine=item.fine,
                    labour=item.wage,
                ),
                show_tunch=show_tunch,
                line_width=line_width,
            )
        )
    lines.extend(
        (
            dash,
            _row_line(
                _RowValues(
                    name="TOTAL",
                    gross=totals.gross,
                    poly=totals.poly,
                    net=totals.net,
                    fine=totals.fine,
                    labour=totals.wage,
                ),
                show_tunch=show_tunch,
                line_width=line_width,
            ),
            separator,
        )
    )
    return totals


def _row_line(
    row: _RowValues,
    *,
    show_tunch: bool,
    line_width: int,
) -> str:
    parts = [
        str(row.sno or "")[:_SNO_WIDTH].ljust(_SNO_WIDTH),
        str(row.name or "")[:_NAME_WIDTH].ljust(_NAME_WIDTH),
    ]
    if show_tunch:
        parts.append(_text(row.tunch, _TUNCH_WIDTH))
    parts.extend(
        (
            _number(row.gross, _GROSS_WIDTH, decimals=2),
            _number(row.poly, _POLY_WIDTH, decimals=0),
            _number(row.net, _NET_WIDTH, decimals=2),
            _number(row.purity, _PURITY_WIDTH, decimals=2),
            _number(row.wage_rate, _WAGE_RATE_WIDTH, decimals=2),
            _number(row.pieces, _PIECES_WIDTH, decimals=0),
            _number(row.fine, _FINE_WIDTH, decimals=2),
            _number(row.labour, _LABOUR_WIDTH, decimals=0),
        )
    )
    return " ".join(parts)[:line_width]


def _number(value: float | None, width: int, *, decimals: int) -> str:
    if value is None:
        return " " * width
    text = str(int(round(value))) if decimals <= 0 else f"{value:.{decimals}f}"
    return text[:width].ljust(width)


def _text(value: str | None, width: int) -> str:
    return str(value or "")[:width].ljust(width)


def _final_line(  # noqa: PLR0913 - explicit fixed-width summary inputs
    net_fine: float,
    net_wage: float,
    silver_cost: float,
    total_cost: float,
    *,
    include_cost: bool,
    line_width: int,
) -> str:
    fine = f"{_grouped(net_fine, decimals=2)} gm"
    wage = _grouped(net_wage, decimals=0)
    prefix = f"{' ' * (_SNO_WIDTH + 1)}{fine.rjust(max(_FINE_WIDTH, len(fine)))} "
    if not include_cost:
        return f"{prefix}{('Rs. ' + _grouped(total_cost, decimals=1)).rjust(_LABOUR_WIDTH)}"[
            :line_width
        ]
    prefix += wage.rjust(max(_LABOUR_WIDTH, len(wage)))
    cost = ("S.Cost : Rs. " + _grouped(silver_cost, decimals=1)).rjust(22)
    total = ("Total: Rs. " + _grouped(total_cost, decimals=1)).rjust(18)
    spacing = max(1, line_width - len(prefix) - len(cost) - len(total) - 1)
    return f"{prefix}{' ' * spacing}{cost} {total}"[:line_width]


def _grouped(value: float, *, decimals: int) -> str:
    sign = "-" if value < 0 else ""
    integer, separator, fraction = f"{abs(value):.{decimals}f}".partition(".")
    if len(integer) > 3:
        suffix = integer[-3:]
        prefix = integer[:-3]
        groups = []
        while prefix:
            groups.append(prefix[-2:])
            prefix = prefix[:-2]
        integer = f"{','.join(reversed(groups))},{suffix}"
    if decimals <= 0:
        return f"{sign}{integer}"
    return f"{sign}{integer}{separator}{fraction}"


def _truncate(value: str, width: int) -> str:
    if width <= 0:
        return ""
    if len(value) <= width:
        return value
    return value[: max(0, width - 3)] + "..."


__all__ = [
    "ClassicEstimateLayout",
    "build_classic_estimate_layout",
    "paint_classic_estimate",
]
