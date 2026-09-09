"""Decimal arithmetic and presentation rules for estimates.

Newly calculated line weights use hundredths of a gram and amounts use paise.
Halfway values round away from zero. Loading a saved value does not quantize it.
"""

from collections.abc import Iterable
from decimal import ROUND_HALF_UP, Decimal, localcontext

WEIGHT_PLACES = 2
MONEY_PLACES = 2
PURITY_PLACES = 2


def decimal_value(value: float | int | str | Decimal) -> Decimal:
    number = Decimal(str(value))
    if not number.is_finite():
        raise ValueError("A finite number is required.")
    return number


def quantize(value: float | int | str | Decimal, places: int) -> Decimal:
    number = decimal_value(value)
    with localcontext() as context:
        context.prec = max(34, number.adjusted() + places + 3)
        rounded = number.quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_UP)
    return abs(rounded) if rounded.is_zero() else rounded


def rounded_value(value: float | int | str | Decimal, places: int) -> float:
    return float(quantize(value, places))


def fixed_decimal(value: float | int | str | Decimal, places: int) -> str:
    return format(quantize(value, places), f".{places}f")


def sum_values(values: Iterable[float]) -> float:
    """Add recorded values without imposing a new precision on historical rows."""
    return float(sum((decimal_value(value) for value in values), Decimal(0)))


def net_weight(gross: float, poly: float) -> float:
    return rounded_value(
        max(decimal_value(gross) - decimal_value(poly), Decimal(0)), WEIGHT_PLACES
    )


def fine_weight(weight: float, purity: float) -> float:
    return rounded_value(
        decimal_value(weight) * max(decimal_value(purity), Decimal(0)) / 100,
        WEIGHT_PLACES,
    )


def wage_amount(basis: float, rate: float) -> float:
    return rounded_value(decimal_value(basis) * decimal_value(rate), MONEY_PLACES)


def silver_value(weight: float, rate: float) -> float:
    return wage_amount(weight, rate) if rate > 0 else 0.0
