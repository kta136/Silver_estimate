"""Formatting helpers for estimate-entry numeric table columns."""

from __future__ import annotations

from PySide6.QtCore import QLocale


def get_estimate_table_locale() -> QLocale:
    """Return the locale used for estimate-entry numeric formatting."""

    return QLocale(QLocale.Language.English, QLocale.Country.India)


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
