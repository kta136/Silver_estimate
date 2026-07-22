"""Device-independent semantic layout for Modern estimate printing."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from .estimate_print_document import (
    EstimatePrintDocument,
    EstimatePrintHeader,
    EstimatePrintItem,
)

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

    @property
    def lines(self) -> tuple[str, ...]:
        """Stable textual projection retained for tests and diagnostics."""
        return tuple(self.normalized_text().splitlines())

    def normalized_text(self) -> str:
        lines = [
            "ESTIMATE SLIP ONLY",
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
            lines.extend(" | ".join(row.values) for row in section.rows)
            lines.append(" | ".join(section.total_row.values))

        if self.last_balance_metrics:
            lines.append("[LAST BALANCE]")
            lines.append(_metrics_text(self.last_balance_metrics))

        lines.append("[FINAL SILVER & AMOUNT]")
        lines.append(_metrics_text(self.final_metrics))
        return "\n".join(lines)


@dataclass(frozen=True)
class _SectionTotals:
    gross: float
    poly: float
    net: float
    fine: float
    wage: float


REGULAR_COLUMNS = (
    EstimatePrintColumn("sno", "SNo", 0.00, 0.04, "center"),
    EstimatePrintColumn("name", "Item Name", 0.04, 0.25, "left"),
    EstimatePrintColumn("gross", "Gross", 0.29, 0.10, "right"),
    EstimatePrintColumn("poly", "Poly", 0.39, 0.09, "right"),
    EstimatePrintColumn("net", "Net", 0.48, 0.10, "right"),
    EstimatePrintColumn("purity", "%", 0.58, 0.08, "right"),
    EstimatePrintColumn("wage_rate", "W. Rate", 0.66, 0.09, "right"),
    EstimatePrintColumn("pieces", "PCS", 0.75, 0.07, "right"),
    EstimatePrintColumn("fine", "Fine", 0.82, 0.10, "right"),
    EstimatePrintColumn("wage", "Lbr", 0.92, 0.08, "right"),
)

REGULAR_COLUMNS_WITH_TUNCH = (
    EstimatePrintColumn("sno", "SNo", 0.00, 0.04, "center"),
    EstimatePrintColumn("name", "Item Name", 0.04, 0.18, "left"),
    EstimatePrintColumn("tunch", "Tunch", 0.22, 0.07, "right"),
    *REGULAR_COLUMNS[2:],
)

SILVER_BAR_COLUMNS = (
    EstimatePrintColumn("sno", "SNo", 0.00, 0.04, "center"),
    EstimatePrintColumn("name", "Item Name", 0.04, 0.25, "left"),
    EstimatePrintColumn("gross", "Gross", 0.29, 0.10, "right"),
    EstimatePrintColumn("poly", "Poly", 0.39, 0.09, "right"),
    EstimatePrintColumn("net", "Net", 0.48, 0.10, "right"),
    EstimatePrintColumn("purity", "%", 0.58, 0.08, "right"),
    EstimatePrintColumn("fine", "Fine", 0.82, 0.10, "right"),
    EstimatePrintColumn("wage", "Lbr", 0.92, 0.08, "right"),
)

SILVER_BAR_COLUMNS_WITH_TUNCH = (
    EstimatePrintColumn("sno", "SNo", 0.00, 0.04, "center"),
    EstimatePrintColumn("name", "Item Name", 0.04, 0.18, "left"),
    EstimatePrintColumn("tunch", "Tunch", 0.22, 0.07, "right"),
    *SILVER_BAR_COLUMNS[2:],
)


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
                "silver_bars",
                "SILVER BARS",
                bars,
                is_bar=True,
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
    section = EstimatePrintSection(
        key=key,
        title=title,
        columns=columns,
        rows=rows,
        total_row=_total_row(
            totals,
            is_bar=is_bar,
            show_tunch=show_tunch,
        ),
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
    values: tuple[str, ...]
    leading: tuple[str, ...] = (
        str(index),
        item.item_name,
    )
    if show_tunch:
        leading += (_tunch(item.tunch),)
    common = leading + (
        _weight(item.gross),
        _weight(item.poly),
        _weight(item.net_wt),
        _decimal(item.purity, decimals=2),
    )
    if is_bar:
        values = common + (
            _weight(item.fine),
            _amount(item.wage, decimals=0),
        )
    else:
        values = common + (
            _decimal(item.wage_rate, decimals=2),
            _pieces(item.pieces),
            _weight(item.fine),
            _amount(item.wage, decimals=0),
        )
    return EstimatePrintRow(values)


def _total_row(
    totals: _SectionTotals,
    *,
    is_bar: bool,
    show_tunch: bool,
) -> EstimatePrintRow:
    values: tuple[str, ...]
    leading: tuple[str, ...] = (
        "",
        "TOTAL",
    )
    if show_tunch:
        leading += ("",)
    common = leading + (
        _weight(totals.gross),
        _weight(totals.poly),
        _weight(totals.net),
        "",
    )
    if is_bar:
        values = common + (
            _weight(totals.fine),
            _amount(totals.wage, decimals=0),
        )
    else:
        values = common + (
            "",
            "",
            _weight(totals.fine),
            _amount(totals.wage, decimals=0),
        )
    return EstimatePrintRow(values, is_total=True)


def _complete_layout(
    header: EstimatePrintHeader,
    sections: tuple[EstimatePrintSection, ...],
    totals_by_key: dict[str, _SectionTotals],
) -> ModernEstimateLayout:
    regular = totals_by_key.get("regular", _zero_totals())
    bars = totals_by_key.get("silver_bars", _zero_totals())
    returns = totals_by_key.get("return_goods", _zero_totals())
    returned_bars = totals_by_key.get("return_silver_bars", _zero_totals())

    net_fine = regular.fine - bars.fine - returns.fine - returned_bars.fine
    net_wage = regular.wage - bars.wage - returns.wage - returned_bars.wage
    if header.last_balance_silver > 0:
        net_fine += header.last_balance_silver
    if header.last_balance_amount > 0:
        net_wage += header.last_balance_amount
    silver_cost = net_fine * header.silver_rate
    total_cost = net_wage + silver_cost

    last_balance = _last_balance_metrics(header)
    final_metrics = [
        EstimatePrintMetric("Fine Silver", f"{_weight(net_fine)} g"),
        EstimatePrintMetric("Labour", f"Rs. {_amount(net_wage, decimals=0)}"),
    ]
    if header.silver_rate > 0:
        final_metrics.extend(
            (
                EstimatePrintMetric(
                    "Silver Cost",
                    f"Rs. {_amount(silver_cost, decimals=1)}",
                ),
                EstimatePrintMetric(
                    "Total",
                    f"Rs. {_amount(total_cost, decimals=1)}",
                    emphasis=True,
                ),
            )
        )
    return ModernEstimateLayout(
        voucher_no=header.voucher_no,
        silver_rate=_amount(header.silver_rate, decimals=2),
        note=header.note.strip(),
        sections=sections,
        last_balance_metrics=last_balance,
        final_metrics=tuple(final_metrics),
    )


def _last_balance_metrics(
    header: EstimatePrintHeader,
) -> tuple[EstimatePrintMetric, ...]:
    if header.last_balance_silver <= 0 and header.last_balance_amount <= 0:
        return ()
    return (
        EstimatePrintMetric(
            "Silver",
            f"{_weight(header.last_balance_silver)} g",
        ),
        EstimatePrintMetric(
            "Amount",
            f"Rs. {_amount(header.last_balance_amount, decimals=1)}",
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
        gross=sum(item.gross for item in items),
        poly=sum(item.poly for item in items),
        net=sum(item.net_wt for item in items),
        fine=sum(item.fine for item in items),
        wage=sum(item.wage for item in items),
    )


def _zero_totals() -> _SectionTotals:
    return _SectionTotals(0.0, 0.0, 0.0, 0.0, 0.0)


def _weight(value: float) -> str:
    return _decimal(value, decimals=2, grouped=True)


def _tunch(value: str | None) -> str:
    return str(value or "")


def _pieces(value: float) -> str:
    if float(value).is_integer():
        return _amount(value, decimals=0)
    return _amount(value, decimals=2)


def _amount(value: float, *, decimals: int) -> str:
    return _decimal(value, decimals=decimals, grouped=True)


def _decimal(
    value: float,
    *,
    decimals: int,
    grouped: bool = False,
) -> str:
    numeric = float(value)
    sign = "-" if numeric < 0 else ""
    integer, separator, fraction = f"{abs(numeric):.{decimals}f}".partition(".")
    if grouped:
        integer = _indian_group(integer)
    if decimals <= 0:
        return f"{sign}{integer}"
    return f"{sign}{integer}{separator}{fraction}"


def _indian_group(digits: str) -> str:
    if len(digits) <= 3:
        return digits
    last_three = digits[-3:]
    prefix = digits[:-3]
    groups = []
    while prefix:
        groups.append(prefix[-2:])
        prefix = prefix[:-2]
    return f"{','.join(reversed(groups))},{last_three}"


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
