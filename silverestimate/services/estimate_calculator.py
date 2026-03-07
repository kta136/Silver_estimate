"""Pure calculation helpers for estimate entry."""

from __future__ import annotations

from typing import Iterable

from silverestimate.domain.estimate_models import (
    CategoryTotals,
    EstimateLine,
    EstimateLineCategory,
    TotalsResult,
)
from silverestimate.domain.estimate_totals import build_totals_result


def compute_net_weight(gross: float, poly: float) -> float:
    """Return the non-negative net weight for a line item."""
    net = gross - poly
    return net if net > 0 else 0.0


def compute_fine_weight(net_weight: float, purity: float) -> float:
    """Return the fine weight based on net weight and purity percentage."""
    if purity <= 0:
        return 0.0
    return net_weight * (purity / 100.0)


def compute_wage_amount(
    basis: str | None, *, net_weight: float, wage_rate: float, pieces: int
) -> float:
    """Return the wage amount using either per-piece or weight basis."""
    basis_normalized = (basis or "").strip().upper()
    if basis_normalized == "PC":
        return float(pieces) * wage_rate
    return net_weight * wage_rate


def compute_category_totals(
    lines: Iterable[EstimateLine], category: EstimateLineCategory
) -> CategoryTotals:
    """Aggregate totals for the specified category."""
    gross = net = fine = wage = 0.0
    for line in lines:
        if line.category is not category:
            continue
        gross += line.gross
        net += line.net_weight
        fine += line.fine_weight
        wage += line.wage_amount
    return CategoryTotals(gross=gross, net=net, fine=fine, wage=wage)


def compute_totals(
    lines: Iterable[EstimateLine],
    *,
    silver_rate: float,
    last_balance_silver: float = 0.0,
    last_balance_amount: float = 0.0,
) -> TotalsResult:
    """Compute aggregate totals across all line items."""
    line_list = list(lines)

    overall_gross = sum(line.gross for line in line_list)
    overall_poly = sum(line.poly for line in line_list)

    regular_totals = compute_category_totals(line_list, EstimateLineCategory.REGULAR)
    return_totals = compute_category_totals(line_list, EstimateLineCategory.RETURN)
    bar_totals = compute_category_totals(line_list, EstimateLineCategory.SILVER_BAR)

    return build_totals_result(
        overall_gross=overall_gross,
        overall_poly=overall_poly,
        regular=regular_totals,
        returns=return_totals,
        silver_bars=bar_totals,
        silver_rate=silver_rate,
        last_balance_silver=last_balance_silver,
        last_balance_amount=last_balance_amount,
    )
