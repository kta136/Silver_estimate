"""Semantic layouts for Modern silver-bar print reports."""

from __future__ import annotations

from dataclasses import dataclass

from silverestimate.domain.numeric_policy import WEIGHT_PLACES

from .estimate_table_formatting import format_indian_number
from .modern_print_primitives import PrintAlignment
from .silver_bar_print_document import (
    SilverBarListPrintDocument,
    SilverBarPrintDocument,
    SilverBarPrintRow,
)


@dataclass(frozen=True)
class SilverBarPrintColumn:
    key: str
    title: str
    start_ratio: float
    width_ratio: float
    alignment: PrintAlignment


@dataclass(frozen=True)
class SilverBarPrintTableRow:
    values: tuple[str, ...]


@dataclass(frozen=True)
class SilverBarPrintLayout:
    title: str
    left_metadata: str
    right_metadata: str
    note: str
    section_title: str
    columns: tuple[SilverBarPrintColumn, ...]
    rows: tuple[SilverBarPrintTableRow, ...]
    total_row: SilverBarPrintTableRow
    empty_message: str

    @property
    def lines(self) -> tuple[str, ...]:
        return tuple(self.normalized_text().splitlines())

    def normalized_text(self) -> str:
        lines = [self.title, self.left_metadata]
        if self.right_metadata:
            lines[-1] += f" | {self.right_metadata}"
        if self.note:
            lines.append(f"Note: {self.note}")
        lines.extend(
            (
                f"[{self.section_title}]",
                " | ".join(column.title for column in self.columns),
            )
        )
        if self.rows:
            lines.extend(" | ".join(row.values).rstrip() for row in self.rows)
        else:
            lines.append(self.empty_message)
        lines.append(" | ".join(self.total_row.values).rstrip())
        return "\n".join(lines)


LIST_COLUMNS = (
    SilverBarPrintColumn("sno", "SNo", 0.00, 0.12, "center"),
    SilverBarPrintColumn("weight", "Weight (g)", 0.12, 0.30, "right"),
    SilverBarPrintColumn("purity", "Purity (%)", 0.42, 0.24, "right"),
    SilverBarPrintColumn("fine", "Fine Wt (g)", 0.66, 0.34, "right"),
)


def build_silver_bar_print_layout(
    document: SilverBarPrintDocument,
) -> SilverBarPrintLayout:
    if isinstance(document, SilverBarListPrintDocument):
        return _build_list_layout(document)
    raise TypeError(f"Unsupported silver-bar document: {type(document).__name__}")


def _build_list_layout(
    document: SilverBarListPrintDocument,
) -> SilverBarPrintLayout:
    rows = tuple(
        SilverBarPrintTableRow(
            (
                str(index),
                _weight(bar.weight),
                _purity(bar.purity),
                _weight(bar.fine_weight),
            )
        )
        for index, bar in enumerate(document.bars, start=1)
    )
    total_weight, total_fine = _totals(document.bars)
    return SilverBarPrintLayout(
        title="SILVER BAR LIST DETAILS",
        left_metadata=f"List ID: {document.list_identifier}",
        right_metadata="",
        note=document.list_note or "N/A",
        section_title="SILVER BARS",
        columns=LIST_COLUMNS,
        rows=rows,
        total_row=SilverBarPrintTableRow(
            (
                f"TOTAL ({len(rows)})",
                _weight(total_weight),
                "",
                _weight(total_fine),
            )
        ),
        empty_message="-- No bars assigned --",
    )


def _totals(bars: tuple[SilverBarPrintRow, ...]) -> tuple[float, float]:
    return (
        sum(bar.weight for bar in bars),
        sum(bar.fine_weight for bar in bars),
    )


def _weight(value: float) -> str:
    return format_indian_number(value, WEIGHT_PLACES)


def _purity(value: float) -> str:
    return format_indian_number(value, 2)


__all__ = [
    "LIST_COLUMNS",
    "SilverBarPrintColumn",
    "SilverBarPrintLayout",
    "SilverBarPrintTableRow",
    "build_silver_bar_print_layout",
]
