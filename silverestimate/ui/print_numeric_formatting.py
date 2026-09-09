"""Column-wide precision decisions for estimate printing."""

from collections.abc import Iterable

from silverestimate.domain.numeric_policy import quantize


def print_column_places(values: Iterable[float | None]) -> int:
    """Hide decimals only when every populated value rounds to a whole number."""
    for value in values:
        if value is None:
            continue
        rounded = quantize(value, 2)
        if rounded != rounded.to_integral_value():
            return 2
    return 0
