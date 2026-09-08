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
from silverestimate.domain.numeric_policy import (
    fine_weight,
    net_weight,
    sum_values,
    wage_amount,
)


def compute_net_weight(gross: float, poly: float) -> float:
    """Return the non-negative net weight for a line item."""
    return net_weight(gross, poly)


def compute_fine_weight(net_weight: float, purity: float) -> float:
    """Return the fine weight based on net weight and purity percentage."""
    return fine_weight(net_weight, purity)


def compute_wage_amount(
    basis: str | None, *, net_weight: float, wage_rate: float, pieces: int
) -> float:
    """Return the wage amount using either per-piece or weight basis."""
    basis_normalized = (basis or "").strip().upper()
    if basis_normalized == "PC":
        return wage_amount(pieces, wage_rate)
    return wage_amount(net_weight, wage_rate)


def compute_category_totals(
    lines: Iterable[EstimateLine], category: EstimateLineCategory
) -> CategoryTotals:
    """Aggregate totals for the specified category."""
    selected = [line for line in lines if line.category is category]
    return CategoryTotals(
        gross=sum_values(line.gross for line in selected),
        net=sum_values(line.net_weight for line in selected),
        fine=sum_values(line.fine_weight for line in selected),
        wage=sum_values(line.wage_amount for line in selected),
    )


def compute_totals(
    lines: Iterable[EstimateLine],
    *,
    silver_rate: float,
    last_balance_silver: float = 0.0,
    last_balance_amount: float = 0.0,
) -> TotalsResult:
    """Compute aggregate totals across all line items."""
    line_list = list(lines)

    overall_gross = sum_values(line.gross for line in line_list)
    overall_poly = sum_values(line.poly for line in line_list)

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
