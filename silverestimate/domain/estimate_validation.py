"""Numeric constraints shared by estimate preparation and database writes."""

from __future__ import annotations

import math
from collections.abc import Mapping
from typing import Any

SQLITE_MAX_INTEGER = 2**63 - 1


def finite_number(value: Any, label: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"{label} must be a finite number.") from exc
    if not math.isfinite(number):
        raise ValueError(f"{label} must be a finite number.")
    return number


def validate_estimate_item(
    item: Mapping[str, Any], *, allow_missing_code: bool = False
) -> None:
    if not allow_missing_code and not str(item.get("code") or "").strip():
        raise ValueError("Item code is required.")
    values = {}
    for field, label in (
        ("gross", "Gross weight"),
        ("poly", "Poly weight"),
        ("net_wt", "Net weight"),
        ("purity", "Purity"),
        ("wage_rate", "Lbr"),
        ("wage", "Lbr Amt"),
        ("fine", "Fine weight"),
    ):
        value = finite_number(item.get(field, 0), label)
        if value < 0:
            raise ValueError(f"{label} cannot be negative.")
        values[field] = value
    if values["poly"] > values["gross"]:
        raise ValueError("Poly weight cannot exceed gross weight.")
    pieces = item.get("pieces", 1)
    finite_number(pieces, "Pieces")
    count = int(pieces)
    if count != pieces or not 0 <= count <= SQLITE_MAX_INTEGER:
        raise ValueError(
            f"Pieces must be a whole number between 0 and {SQLITE_MAX_INTEGER}."
        )


def validate_estimate_totals(silver_rate: Any, totals: Mapping[str, Any]) -> None:
    if finite_number(silver_rate, "Silver rate") < 0:
        raise ValueError("Silver rate cannot be negative.")
    for field in (
        "total_gross",
        "total_net",
        "net_fine",
        "net_wage",
        "last_balance_silver",
        "last_balance_amount",
    ):
        finite_number(totals.get(field, 0), field.replace("_", " ").capitalize())


def validate_estimate(
    voucher_no: str,
    silver_rate: Any,
    items: list[dict],
    totals: Mapping[str, Any],
    *,
    missing_code_keys: set[str] | None = None,
) -> None:
    if not str(voucher_no or "").strip():
        raise ValueError("Voucher number is required.")
    validate_estimate_totals(silver_rate, totals)
    for index, item in enumerate(items, 1):
        try:
            validate_estimate_item(
                item,
                allow_missing_code=bool(
                    missing_code_keys and item.get("line_key") in missing_code_keys
                ),
            )
        except ValueError as exc:
            raise ValueError(f"Row {item.get('row_number') or index}: {exc}") from exc
