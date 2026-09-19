"""Device-independent semantic layout for Modern estimate printing."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from silverestimate.domain.estimate_totals import calculate_grand_total
from silverestimate.domain.numeric_policy import (
    WEIGHT_PLACES,
    fixed_decimal,
    silver_value,
    sum_values,
)
from silverestimate.ui.estimate_table_formatting import format_indian_number

from .estimate_print_document import (
    EstimatePrintDocument,
    EstimatePrintHeader,
    EstimatePrintItem,
)
from .print_numeric_formatting import print_column_places

ColumnAlignment = Literal["left", "center", "right"]


@dataclass(frozen=True)
class EstimatePrintColumn:
    """One table column anchored to the shared printable-width grid."""

    key: str
    title: str
    start_ratio: float
    width_ratio: float
    alignment: ColumnAlignment


@dataclass(frozen=True)
class EstimatePrintRow:
    """Already-formatted cell values for one estimate row."""

    values: tuple[str, ...]
    is_total: bool = False


@dataclass(frozen=True)
class EstimatePrintSection:
    """A print section with its own useful columns and totals."""

    key: str
    title: str
    columns: tuple[EstimatePrintColumn, ...]
    rows: tuple[EstimatePrintRow, ...]
    total_row: EstimatePrintRow
    is_return: bool = False


@dataclass(frozen=True)
class EstimatePrintMetric:
    """A labeled value displayed in a summary block."""

    label: str
    value: str
    emphasis: bool = False


@dataclass(frozen=True)
class ModernEstimateLayout:
    """Complete semantic representation consumed by the direct painter."""

    voucher_no: str
    silver_rate: str
    note: str
    sections: tuple[EstimatePrintSection, ...]
    last_balance_metrics: tuple[EstimatePrintMetric, ...]
    final_metrics: tuple[EstimatePrintMetric, ...]
    fine_weight: str = ""
    has_rate: bool = False

    @property
    def lines(self) -> tuple[str, ...]:
        """Stable textual projection retained for tests and diagnostics."""
        return tuple(self.normalized_text().splitlines())

    def normalized_text(self) -> str:
        lines = [
            "ESTIMATE SLIP",
            f"Voucher: {self.voucher_no} | Silver Rate: {self.silver_rate}",
        ]
        if self.note:
            lines.append(f"Note: {self.note}")

        for section in self.sections:
            lines.extend(
                (
                    f"[{section.title}]",
                    " | ".join(column.title for column in section.columns),
                )
            )
            lines.extend(" | ".join(row.values).rstrip() for row in section.rows)
            lines.append(" | ".join(section.total_row.values).rstrip())

        if self.last_balance_metrics:
            lines.append("[LAST BALANCE]")
            lines.append(_metrics_text(self.last_balance_metrics))

        if self.has_rate:
            lines.append(f"Total Fine Weight (g): {self.fine_weight}")
        lines.append("[SUMMARY]")
        lines.append(_metrics_text(self.final_metrics))
        return "\n".join(lines)


@dataclass(frozen=True)
class _SectionTotals:
    gross: float
    poly: float
    net: float
    fine: float
    wage: float
    pieces: float = 0.0


def _columns(show_tunch: bool = False) -> tuple[EstimatePrintColumn, ...]:
    specs: list[tuple[str, str, int, ColumnAlignment]] = [
        ("sno", "#", 3, "center"),
        ("name", "Item Name", 24, "left"),
    ]
    if show_tunch:
        specs.append(("tunch", "Tunch", 6, "left"))
    specs.extend(
        [
            ("gross", "Gross (g)", 8, "right"),
            ("poly", "Poly (g)", 7, "right"),
            ("net", "Net Wt (g)", 8, "right"),
            ("purity", "Purity (%)", 7, "right"),
            ("wage_rate", "Lbr", 8, "right"),
            ("pieces", "Pieces", 5, "right"),
            ("wage", "Lbr Amt (₹)", 10, "right"),
            ("fine", "Fine Wt (g)", 8, "right"),
        ]
    )
    total = sum(spec[2] for spec in specs)
    result = []
    start = 0.0
    for key, title, width, alignment in specs:
        ratio = width / total
        result.append(EstimatePrintColumn(key, title, start, ratio, alignment))
        start += ratio
    return tuple(result)


REGULAR_COLUMNS = _columns()
REGULAR_COLUMNS_WITH_TUNCH = _columns(True)
SILVER_BAR_COLUMNS = REGULAR_COLUMNS
SILVER_BAR_COLUMNS_WITH_TUNCH = REGULAR_COLUMNS_WITH_TUNCH


def build_modern_estimate_layout(
    document: EstimatePrintDocument,
) -> ModernEstimateLayout:
    """Convert a typed estimate into sections and summary metrics."""
    regular, bars, returns, returned_bars = _split_items(document.items)
    sections_with_totals = tuple(
        result
        for result in (
            _build_section(
                "regular",
                "REGULAR GOODS",
                regular,
                show_tunch=document.show_tunch,
            ),
            _build_section(
                "return_goods",
                "RETURN GOODS",
                returns,
                is_return=True,
                show_tunch=document.show_tunch,
            ),
            _build_section(
                "silver_bars",
                "SILVER BARS",
                bars,
                is_bar=True,
                show_tunch=document.show_tunch,
            ),
            _build_section(
                "return_silver_bars",
                "RETURN SILVER BARS",
                returned_bars,
                is_bar=True,
                is_return=True,
                show_tunch=document.show_tunch,
            ),
        )
        if result is not None
    )
    sections = tuple(result[0] for result in sections_with_totals)
    totals_by_key = {result[0].key: result[1] for result in sections_with_totals}
    return _complete_layout(document.header, sections, totals_by_key)


def _build_section(  # noqa: PLR0913 - explicit semantic section inputs
    key: str,
    title: str,
    items: tuple[EstimatePrintItem, ...],
    *,
    is_bar: bool = False,
    is_return: bool = False,
    show_tunch: bool = False,
) -> tuple[EstimatePrintSection, _SectionTotals] | None:
    if not items:
        return None
    totals = _totals(items)
    columns: tuple[EstimatePrintColumn, ...]
    if show_tunch:
        columns = (
            SILVER_BAR_COLUMNS_WITH_TUNCH if is_bar else REGULAR_COLUMNS_WITH_TUNCH
        )
    else:
        columns = SILVER_BAR_COLUMNS if is_bar else REGULAR_COLUMNS
    rows = tuple(
        _item_row(
            item,
            index=index,
            is_bar=is_bar,
            show_tunch=show_tunch,
        )
        for index, item in enumerate(items, start=1)
    )
    total_row = _total_row(totals, is_bar=is_bar, show_tunch=show_tunch)
    numeric_fields = {
        "gross": "gross",
        "poly": "poly",
        "net": "net_wt",
        "purity": "purity",
        "wage_rate": "wage_rate",
        "pieces": "pieces",
        "wage": "wage",
        "fine": "fine",
    }
    places = {
        key: print_column_places(
            [getattr(item, field) for item in items] + [getattr(totals, key, None)]
        )
        for key, field in numeric_fields.items()
    }

    def format_row(row: EstimatePrintRow) -> EstimatePrintRow:
        values = tuple(
            value.removesuffix(".00") if places.get(column.key) == 0 else value
            for column, value in zip(columns, row.values, strict=True)
        )
        return EstimatePrintRow(values, is_total=row.is_total)

    section = EstimatePrintSection(
        key=key,
        title=title,
        columns=columns,
        rows=tuple(format_row(row) for row in rows),
        total_row=format_row(total_row),
        is_return=is_return,
    )
    return section, totals


def _item_row(
    item: EstimatePrintItem,
    *,
    index: int,
    is_bar: bool,
    show_tunch: bool,
) -> EstimatePrintRow:
    leading: tuple[str, ...] = (str(index), item.item_name)
    if show_tunch:
        leading += (_tunch(item.tunch),)
    return EstimatePrintRow(
        leading
        + (
            _weight(item.gross),
            _weight(item.poly),
            _weight(item.net_wt),
            _decimal(item.purity, decimals=2),
            _decimal(item.wage_rate, decimals=2),
            _pieces(item.pieces),
            _amount(item.wage, decimals=2),
            _weight(item.fine),
        )
    )


def _total_row(
    totals: _SectionTotals, *, is_bar: bool, show_tunch: bool
) -> EstimatePrintRow:
    leading = ("", "SUBTOTAL") + (("",) if show_tunch else ())
    return EstimatePrintRow(
        leading
        + (
            _weight(totals.gross),
            _weight(totals.poly),
            _weight(totals.net),
            "",
            "",
            _pieces(totals.pieces),
            _amount(totals.wage, decimals=2),
            _weight(totals.fine),
        ),
        is_total=True,
    )


def _complete_layout(
    header: EstimatePrintHeader,
    sections: tuple[EstimatePrintSection, ...],
    totals_by_key: dict[str, _SectionTotals],
) -> ModernEstimateLayout:
    regular = totals_by_key.get("regular", _zero_totals())
    bars = totals_by_key.get("silver_bars", _zero_totals())
    returns = totals_by_key.get("return_goods", _zero_totals())
    returned_bars = totals_by_key.get("return_silver_bars", _zero_totals())

    net_fine = sum_values(
        (
            regular.fine,
            -bars.fine,
            -returns.fine,
            -returned_bars.fine,
            header.last_balance_silver,
        )
    )
    net_wage = sum_values(
        (
            regular.wage,
            -bars.wage,
            -returns.wage,
            -returned_bars.wage,
            header.last_balance_amount,
        )
    )
    silver_cost = silver_value(net_fine, header.silver_rate)
    total_cost = calculate_grand_total(
        net_fine=net_fine, net_wage=net_wage, silver_rate=header.silver_rate
    )

    last_balance = _last_balance_metrics(header)
    final_metrics = [
        EstimatePrintMetric("Total Lbr Amt (₹)", _amount(net_wage, decimals=0))
    ]
    if header.silver_rate > 0:
        final_metrics.extend(
            (
                EstimatePrintMetric(
                    "Silver Value (₹)", _amount(silver_cost, decimals=0)
                ),
                EstimatePrintMetric(
                    "GRAND TOTAL (₹)", _amount(total_cost, decimals=0), emphasis=True
                ),
            )
        )
    else:
        final_metrics.append(
            EstimatePrintMetric("Silver (g)", _weight(net_fine), emphasis=True)
        )
    return ModernEstimateLayout(
        voucher_no=header.voucher_no,
        fine_weight=_weight(net_fine),
        has_rate=header.silver_rate > 0,
        silver_rate=_amount(header.silver_rate, decimals=2)
        if header.silver_rate > 0
        else "—",
        note=header.note.strip(),
        sections=sections,
        last_balance_metrics=last_balance,
        final_metrics=tuple(final_metrics),
    )


def _last_balance_metrics(
    header: EstimatePrintHeader,
) -> tuple[EstimatePrintMetric, ...]:
    if header.last_balance_silver == 0 and header.last_balance_amount == 0:
        return ()
    return (
        EstimatePrintMetric(
            "Silver",
            f"{_weight(header.last_balance_silver)} g",
        ),
        EstimatePrintMetric(
            "Amount",
            f"Rs. {_amount(header.last_balance_amount, decimals=2)}",
        ),
    )


def _split_items(
    items: tuple[EstimatePrintItem, ...],
) -> tuple[
    tuple[EstimatePrintItem, ...],
    tuple[EstimatePrintItem, ...],
    tuple[EstimatePrintItem, ...],
    tuple[EstimatePrintItem, ...],
]:
    regular = tuple(
        item for item in items if not item.is_return and not item.is_silver_bar
    )
    bars = tuple(item for item in items if not item.is_return and item.is_silver_bar)
    returns = tuple(item for item in items if item.is_return and not item.is_silver_bar)
    returned_bars = tuple(
        item for item in items if item.is_return and item.is_silver_bar
    )
    return regular, bars, returns, returned_bars


def _totals(items: tuple[EstimatePrintItem, ...]) -> _SectionTotals:
    return _SectionTotals(
        gross=sum_values(item.gross for item in items),
        poly=sum_values(item.poly for item in items),
        net=sum_values(item.net_wt for item in items),
        fine=sum_values(item.fine for item in items),
        wage=sum_values(item.wage for item in items),
        pieces=sum_values(item.pieces for item in items),
    )


def _zero_totals() -> _SectionTotals:
    return _SectionTotals(0.0, 0.0, 0.0, 0.0, 0.0)


def _weight(value: float) -> str:
    return _decimal(value, decimals=WEIGHT_PLACES, grouped=True)


def _tunch(value: str | None) -> str:
    return str(value or "")


def _pieces(value: float) -> str:
    return _amount(value, decimals=2)


def _amount(value: float, *, decimals: int) -> str:
    return _decimal(value, decimals=decimals, grouped=True)


def _decimal(
    value: float,
    *,
    decimals: int,
    grouped: bool = False,
) -> str:
    return (
        format_indian_number(value, decimals)
        if grouped
        else fixed_decimal(value, decimals)
    )


def _metrics_text(metrics: tuple[EstimatePrintMetric, ...]) -> str:
    return " | ".join(f"{metric.label}: {metric.value}" for metric in metrics)


__all__ = [
    "EstimatePrintColumn",
    "EstimatePrintMetric",
    "EstimatePrintRow",
    "EstimatePrintSection",
    "ModernEstimateLayout",
    "REGULAR_COLUMNS",
    "SILVER_BAR_COLUMNS",
    "build_modern_estimate_layout",
]
