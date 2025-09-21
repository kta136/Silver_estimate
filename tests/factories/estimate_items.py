from __future__ import annotations

from typing import Any, Dict


def _build(base: Dict[str, Any], **overrides: Any) -> Dict[str, Any]:
    item = base.copy()
    item.update(overrides)
    return item


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
