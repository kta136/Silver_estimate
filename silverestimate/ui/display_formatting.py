"""Consistent user-facing date and currency formatting helpers."""

from __future__ import annotations

from datetime import UTC, date, datetime
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


def format_local_timestamp(stamp: Any) -> str:
    """Return a stored UTC timestamp as local ``DD/MM/YYYY HH:MM AM``, or ``""``.

    Timestamps are stored in UTC; people read them in their own time zone and
    in the date format used everywhere else in the app.
    """

    text = str(stamp or "").strip()
    if not text:
        return ""
    try:
        moment = datetime.fromisoformat(text)
    except ValueError:
        return text
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=UTC)
    return moment.astimezone().strftime("%d/%m/%Y %I:%M %p")


def count_label(count: int, singular: str, plural: str | None = None) -> str:
    """Return ``1 bar`` or ``3 bars``: the noun agrees with the count."""

    number = int(count)
    word = singular if number == 1 else (plural or f"{singular}s")
    return f"{number} {word}"


def format_rate(value: Any, *, decimals: int = 2) -> str:
    """Return a silver rate, or a dash when no rate was entered."""

    try:
        number = float(value or 0.0)
    except TypeError, ValueError:
        number = 0.0
    return format_rupees(number, decimals=decimals) if number > 0 else "—"


__all__ = [
    "count_label",
    "format_display_date",
    "format_local_timestamp",
    "format_rate",
    "format_rupees",
]
