"""Consistent user-facing date and currency formatting helpers."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from silverestimate.ui.estimate_table_formatting import format_indian_number


def format_display_date(value: Any) -> str:
    """Return a compact ``DD/MM/YYYY`` date while preserving unknown values."""

    if isinstance(value, datetime):
        return value.strftime("%d/%m/%Y")
    if isinstance(value, date):
        return value.strftime("%d/%m/%Y")

    text = str(value or "").strip()
    if not text:
        return ""
    candidate = text[:10]
    for pattern in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(candidate, pattern).strftime("%d/%m/%Y")
        except ValueError:
            continue
    return text


def format_rupees(value: Any, *, decimals: int = 2) -> str:
    """Return a rupee value with Indian digit grouping."""

    try:
        number = float(value or 0.0)
    except TypeError, ValueError:
        number = 0.0
    return f"₹ {format_indian_number(number, decimals)}"


__all__ = ["format_display_date", "format_rupees"]
