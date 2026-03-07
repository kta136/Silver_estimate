"""Formatting helpers for estimate-entry numeric table columns."""

from __future__ import annotations

from PyQt5.QtCore import QLocale

from silverestimate.ui.estimate_entry_logic.constants import (
    COL_FINE_WT,
    COL_GROSS,
    COL_NET_WT,
    COL_PIECES,
    COL_POLY,
    COL_PURITY,
    COL_WAGE_AMT,
    COL_WAGE_RATE,
)

_DECIMAL_PLACES_BY_COLUMN = {
    COL_GROSS: 3,
    COL_POLY: 3,
    COL_NET_WT: 2,
    COL_PURITY: 2,
    COL_WAGE_RATE: 2,
    COL_FINE_WT: 2,
}
_INTEGER_COLUMNS = {COL_PIECES, COL_WAGE_AMT}
NUMERIC_COLUMNS = frozenset(_DECIMAL_PLACES_BY_COLUMN) | _INTEGER_COLUMNS


def get_estimate_table_locale() -> QLocale:
    """Return the locale used for estimate-entry numeric formatting."""

    return QLocale(QLocale.English, QLocale.India)


def _group_indian_digits(number_text: str, separator: str) -> str:
    if len(number_text) <= 3:
        return number_text

    last_three = number_text[-3:]
    remaining = number_text[:-3]
    groups: list[str] = []
    while len(remaining) > 2:
        groups.append(remaining[-2:])
        remaining = remaining[:-2]
    if remaining:
        groups.append(remaining)
    return separator.join(reversed(groups)) + separator + last_three


def format_indian_number(value, decimals: int, *, locale: QLocale | None = None) -> str:
    """Format a number using Indian digit grouping."""

    active_locale = locale or get_estimate_table_locale()
    separator = active_locale.groupSeparator() or ","
    decimal_point = active_locale.decimalPoint() or "."

    if decimals <= 0:
        whole_value = int(round(float(value or 0)))
        sign = "-" if whole_value < 0 else ""
        return sign + _group_indian_digits(str(abs(whole_value)), separator)

    fractional_value = float(value or 0.0)
    sign = "-" if fractional_value < 0 else ""
    fixed = f"{abs(fractional_value):.{decimals}f}"
    whole, fraction = fixed.split(".", 1)
    grouped = _group_indian_digits(whole, separator)
    return sign + grouped + decimal_point + fraction


def format_estimate_table_number(
    column: int, value, *, locale: QLocale | None = None
) -> str:
    """Format a numeric estimate-table value for display."""

    active_locale = locale or get_estimate_table_locale()

    if column in _INTEGER_COLUMNS:
        return format_indian_number(value, 0, locale=active_locale)

    decimals = _DECIMAL_PLACES_BY_COLUMN.get(column)
    if decimals is None:
        return str(value)
    return format_indian_number(value, decimals, locale=active_locale)
