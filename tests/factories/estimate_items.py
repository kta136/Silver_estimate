from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict

try:
    from hypothesis import strategies as st
except ModuleNotFoundError:  # pragma: no cover - optional dependency
    st = None

_HYPOTHESIS_AVAILABLE = st is not None


def _build(base: Dict[str, Any], **overrides: Any) -> Dict[str, Any]:
    item = base.copy()
    item.update(overrides)
    return item


def _round_weight(value: float, places: int = 3) -> float:
    return round(float(value), places)


def regular_item(**overrides: Any) -> Dict[str, Any]:
    """Factory for a regular estimate item."""
    base = {
        "code": "REG001",
        "name": "Regular Item",
        "gross": 10.0,
        "poly": 0.0,
        "net_wt": 10.0,
        "purity": 92.5,
        "wage_rate": 10.0,
        "pieces": 1,
        "wage": 100.0,
        "fine": 9.25,
        "is_return": False,
        "is_silver_bar": False,
    }
    return _build(base, **overrides)


def return_item(**overrides: Any) -> Dict[str, Any]:
    """Factory for a return item."""
    base = {
        "code": "RET001",
        "name": "Return Item",
        "gross": 1.5,
        "poly": 0.3,
        "net_wt": 1.2,
        "purity": 80.0,
        "wage_rate": 0.0,
        "pieces": 1,
        "wage": 0.0,
        "fine": 0.96,
        "is_return": True,
        "is_silver_bar": False,
    }
    return _build(base, **overrides)


def silver_bar_item(**overrides: Any) -> Dict[str, Any]:
    """Factory for a silver bar item."""
    base = {
        "code": "BAR001",
        "name": "Silver Bar",
        "gross": 5.0,
        "poly": 0.0,
        "net_wt": 5.0,
        "purity": 99.9,
        "wage_rate": 0.0,
        "pieces": 1,
        "wage": 0.0,
        "fine": 4.995,
        "is_return": False,
        "is_silver_bar": True,
    }
    return _build(base, **overrides)


def estimate_totals(**overrides: Any) -> Dict[str, Any]:
    """Factory for estimate totals payload."""
    base = {
        "total_gross": 10.0,
        "total_net": 9.0,
        "net_fine": 8.325,
        "net_wage": 90.0,
        "note": "",
        "last_balance_silver": 0.0,
        "last_balance_amount": 0.0,
    }
    return _build(base, **overrides)


@dataclass
class FineCalculationCase:
    """Representative data for fine-weight calculations."""

    gross: float
    poly: float
    purity: float

    def __post_init__(self) -> None:
        self.gross = max(_round_weight(self.gross), 0.0)
        poly = max(_round_weight(self.poly), 0.0)
        self.poly = min(poly, self.gross)
        purity = round(float(self.purity), 3)
        self.purity = min(max(purity, 0.0), 100.0)

    @property
    def net_weight(self) -> float:
        return _round_weight(max(self.gross - self.poly, 0.0))

    @property
    def expected_fine(self) -> float:
        if self.purity <= 0.0:
            return 0.0
        return _round_weight(self.net_weight * (self.purity / 100.0))


@dataclass
class WageCalculationCase:
    """Representative data for wage calculations."""

    wage_type: str
    net_weight: float
    wage_rate: float
    pieces: int

    def __post_init__(self) -> None:
        wage_type = (self.wage_type or "WT").strip().upper()
        self.wage_type = "PC" if wage_type == "PC" else "WT"
        self.net_weight = _round_weight(max(self.net_weight, 0.0))
        self.wage_rate = round(max(float(self.wage_rate), 0.0), 2)
        self.pieces = int(max(self.pieces, 0))

    @property
    def code(self) -> str:
        return "PC001" if self.wage_type == "PC" else "WT001"

    @property
    def expected_wage(self) -> float:
        base = self.pieces * self.wage_rate if self.wage_type == "PC" else self.net_weight * self.wage_rate
        return round(base)


def fine_calculation_cases():
    """Hypothesis strategy producing realistic fine-weight scenarios."""
    if not _HYPOTHESIS_AVAILABLE:  # pragma: no cover - optional dependency
        raise RuntimeError("Hypothesis is not installed")

    weight = st.floats(min_value=0.0, max_value=250.0, allow_nan=False, allow_infinity=False)
    ratio = st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False)
    purity = st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False)

    return st.builds(
        lambda gross, r, pur: FineCalculationCase(gross=gross, poly=gross * r, purity=pur),
        gross=weight,
        r=ratio,
        pur=purity,
    )


def wage_calculation_cases():
    """Hypothesis strategy producing realistic wage scenarios."""
    if not _HYPOTHESIS_AVAILABLE:  # pragma: no cover - optional dependency
        raise RuntimeError("Hypothesis is not installed")

    wage_type = st.sampled_from(["WT", "PC"])
    net = st.floats(min_value=0.0, max_value=250.0, allow_nan=False, allow_infinity=False)
    rate = st.floats(min_value=0.0, max_value=500.0, allow_nan=False, allow_infinity=False)
    pieces = st.integers(min_value=0, max_value=25)

    return st.builds(
        WageCalculationCase,
        wage_type=wage_type,
        net_weight=net,
        wage_rate=rate,
        pieces=pieces,
    )


__all__ = [
    "regular_item",
    "return_item",
    "silver_bar_item",
    "estimate_totals",
    "FineCalculationCase",
    "WageCalculationCase",
    "fine_calculation_cases",
    "wage_calculation_cases",
]
