"""Domain-level validation rules for item master records."""

from __future__ import annotations

import math
from dataclasses import dataclass

MIN_PURITY = 0.0
MIN_WAGE_RATE = 0.0
MAX_WAGE_RATE = 1_000_000.0
VALID_WAGE_TYPES = {"PC", "WT", "Q", "P"}
WAGE_TYPE_ALIASES = {"P": "PC"}


@dataclass(frozen=True)
class ValidatedItem:
    code: str
    name: str
    purity: float
    wage_type: str
    wage_rate: float
    tunch: str | None = None


class ItemValidationError(ValueError):
    """Raised when item domain constraints are violated."""


def validate_item(  # noqa: PLR0913 - stable public field-by-field validation API
    *,
    code: str,
    name: str,
    purity: float,
    wage_type: str,
    wage_rate: float,
    tunch: object = None,
) -> ValidatedItem:
    normalized_code = (code or "").strip().upper()
    normalized_name = (name or "").strip()
    normalized_type = (wage_type or "").strip().upper()
    normalized_type = WAGE_TYPE_ALIASES.get(normalized_type, normalized_type)

    if not normalized_code:
        raise ItemValidationError("Item code is required.")
    if not normalized_name:
        raise ItemValidationError("Item name is required.")
    if normalized_type not in VALID_WAGE_TYPES:
        raise ItemValidationError(
            f"Invalid wage type '{normalized_type}'. Use one of: "
            f"{', '.join(sorted(VALID_WAGE_TYPES))}."
        )

    purity_value = _finite_number(purity, "Purity")
    # Numeric Tunch/purity is a business multiplier and may exceed 100%.
    if purity_value < MIN_PURITY:
        raise ItemValidationError("Purity cannot be negative.")

    wage_rate_value = _finite_number(wage_rate, "Lbr")
    if wage_rate_value < MIN_WAGE_RATE:
        raise ItemValidationError("Lbr cannot be negative.")
    if wage_rate_value > MAX_WAGE_RATE:
        raise ItemValidationError(f"Lbr must be <= {MAX_WAGE_RATE:,.0f}.")

    tunch_value = str(tunch).strip() if tunch is not None else ""

    return ValidatedItem(
        code=normalized_code,
        name=normalized_name,
        purity=purity_value,
        wage_type=normalized_type,
        wage_rate=wage_rate_value,
        tunch=tunch_value or None,
    )


def _finite_number(value: float, label: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ItemValidationError(f"{label} must be a finite number.") from exc
    if not math.isfinite(number):
        raise ItemValidationError(f"{label} must be a finite number.")
    return number
