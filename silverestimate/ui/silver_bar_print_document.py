"""Typed input models for silver-bar inventory and list printing."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date
from typing import Any, cast

from .display_formatting import format_display_date


def _row_value(row: object, key: str, default: object) -> object:
    """Read dictionaries and sqlite3.Row values without membership checks."""

    try:
        value = cast(Any, row)[key]
    except KeyError, IndexError, TypeError:
        return default
    return default if value is None else value


def _number(value: object, *, field: str) -> float:
    if value in (None, ""):
        return 0.0
    try:
        return float(cast(Any, value))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} must be numeric") from exc


def _rows(value: object, *, field: str) -> Iterable[object]:
    if isinstance(value, str | bytes) or not isinstance(value, Iterable):
        raise TypeError(f"{field} must be an iterable of rows")
    return value


@dataclass(frozen=True)
class SilverBarPrintRow:
    bar_id: str
    estimate_voucher_no: str
    weight: float
    purity: float
    fine_weight: float
    date_added: str
    status: str

    @classmethod
    def from_row(cls, value: object, *, index: int) -> SilverBarPrintRow:
        return cls(
            bar_id=str(_row_value(value, "bar_id", "N/A")),
            estimate_voucher_no=str(_row_value(value, "estimate_voucher_no", "N/A")),
            weight=_number(
                _row_value(value, "weight", 0.0),
                field=f"bars[{index}].weight",
            ),
            purity=_number(
                _row_value(value, "purity", 0.0),
                field=f"bars[{index}].purity",
            ),
            fine_weight=_number(
                _row_value(value, "fine_weight", 0.0),
                field=f"bars[{index}].fine_weight",
            ),
            date_added=format_display_date(
                _row_value(value, "date_added", ""),
            ),
            status=str(_row_value(value, "status", "")),
        )


@dataclass(frozen=True)
class SilverBarInventoryPrintDocument:
    bars: tuple[SilverBarPrintRow, ...]
    status_filter: str
    print_date: str

    @classmethod
    def from_rows(
        cls,
        bars: object,
        *,
        status_filter: object = None,
        print_date: object = None,
    ) -> SilverBarInventoryPrintDocument:
        resolved_print_date = print_date if print_date is not None else date.today()
        return cls(
            bars=tuple(
                SilverBarPrintRow.from_row(row, index=index)
                for index, row in enumerate(_rows(bars, field="bars"))
            ),
            status_filter=str(status_filter or "All"),
            print_date=format_display_date(resolved_print_date),
        )


@dataclass(frozen=True)
class SilverBarListPrintDocument:
    list_identifier: str
    list_note: str
    bars: tuple[SilverBarPrintRow, ...]

    @classmethod
    def from_rows(
        cls,
        list_info: object,
        bars: object,
    ) -> SilverBarListPrintDocument:
        return cls(
            list_identifier=str(_row_value(list_info, "list_identifier", "N/A")),
            list_note=str(_row_value(list_info, "list_note", "")),
            bars=tuple(
                SilverBarPrintRow.from_row(row, index=index)
                for index, row in enumerate(_rows(bars, field="bars"))
            ),
        )


SilverBarPrintDocument = SilverBarInventoryPrintDocument | SilverBarListPrintDocument


__all__ = [
    "SilverBarInventoryPrintDocument",
    "SilverBarListPrintDocument",
    "SilverBarPrintDocument",
    "SilverBarPrintRow",
]
