"""Domain models supporting estimate calculations."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable, Iterator


class EstimateLineCategory(Enum):
    """Enumeration of line item categories used in totals breakdown."""

    REGULAR = "regular"
    RETURN = "return"
    SILVER_BAR = "silver_bar"

    @classmethod
    def from_label(cls, value: str | None) -> "EstimateLineCategory":
        """Map UI text to the corresponding category."""
        normalized = (value or "").strip().lower()
        if not normalized:
            return cls.REGULAR

        # Accept both display labels ("Silver Bar", "Return") and stored enum values ("silver_bar", "return")
        normalized = normalized.replace("_", " ")

        if normalized in {"return", "return items"}:
            return cls.RETURN
        if normalized in {"silver bar", "silver bars"}:
            return cls.SILVER_BAR
        if normalized in {"no", "regular"}:
            return cls.REGULAR
        return cls.REGULAR

    def display_name(self) -> str:
        """Return the user-friendly display name for this category."""
        if self is self.RETURN:
            return "Return"
        if self is self.SILVER_BAR:
            return "Silver Bar"
        return "No"

    def is_regular(self) -> bool:
        return self is self.REGULAR

    def is_return(self) -> bool:
        return self is self.RETURN

    def is_silver_bar(self) -> bool:
        return self is self.SILVER_BAR


@dataclass(frozen=True)
class EstimateLine:
    """Represents a single row in the estimate grid."""

    code: str
    category: EstimateLineCategory
    gross: float = 0.0
    poly: float = 0.0
    net_weight: float = 0.0
    fine_weight: float = 0.0
    wage_amount: float = 0.0


@dataclass(frozen=True)
class CategoryTotals:
    """Aggregated totals for a line category."""

    gross: float = 0.0
    net: float = 0.0
    fine: float = 0.0
    wage: float = 0.0


@dataclass(frozen=True)
class TotalsResult:
    """Breakdown of overall, categorical, and derived totals."""

    overall_gross: float
    overall_poly: float

    regular: CategoryTotals
    returns: CategoryTotals
    silver_bars: CategoryTotals

    net_fine_core: float
    net_wage_core: float
    net_value_core: float

    net_fine: float
    net_wage: float
    net_value: float

    grand_total: float
    silver_rate: float
    last_balance_silver: float
    last_balance_amount: float


def iter_regular(lines: Iterable[EstimateLine]) -> Iterator[EstimateLine]:
    """Yield only the regular line items."""
    return (line for line in lines if line.category.is_regular())


def iter_returns(lines: Iterable[EstimateLine]) -> Iterator[EstimateLine]:
    """Yield only the return line items."""
    return (line for line in lines if line.category.is_return())


def iter_silver_bars(lines: Iterable[EstimateLine]) -> Iterator[EstimateLine]:
    """Yield only the silver-bar line items."""
    return (line for line in lines if line.category.is_silver_bar())

