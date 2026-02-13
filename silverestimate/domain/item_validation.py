"""Domain-level validation rules for item master records."""

from __future__ import annotations

from dataclasses import dataclass

MIN_PURITY = 0.0
MAX_PURITY = 100.0
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


class ItemValidationError(ValueError):
    """Raised when item domain constraints are violated."""


def validate_item(
    *,
    code: str,
    name: str,
    purity: float,
    wage_type: str,
    wage_rate: float,
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

    purity_value = float(purity)
    if not (MIN_PURITY <= purity_value <= MAX_PURITY):
        raise ItemValidationError(
            f"Purity must be between {MIN_PURITY:.0f} and {MAX_PURITY:.0f}."
        )

    wage_rate_value = float(wage_rate)
    if wage_rate_value < MIN_WAGE_RATE:
        raise ItemValidationError("Wage rate cannot be negative.")
    if wage_rate_value > MAX_WAGE_RATE:
        raise ItemValidationError(f"Wage rate must be <= {MAX_WAGE_RATE:,.0f}.")

    return ValidatedItem(
        code=normalized_code,
        name=normalized_name,
        purity=purity_value,
        wage_type=normalized_type,
        wage_rate=wage_rate_value,
    )
