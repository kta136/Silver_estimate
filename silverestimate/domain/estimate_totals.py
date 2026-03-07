"""Pure helpers for assembling estimate totals from category aggregates."""

from __future__ import annotations

from silverestimate.domain.estimate_models import CategoryTotals, TotalsResult


def build_totals_result(
    *,
    overall_gross: float,
    overall_poly: float,
    regular: CategoryTotals,
    returns: CategoryTotals,
    silver_bars: CategoryTotals,
    silver_rate: float,
    last_balance_silver: float = 0.0,
    last_balance_amount: float = 0.0,
) -> TotalsResult:
    """Build the final totals payload from pre-aggregated category totals."""
    net_fine_core = regular.fine - silver_bars.fine - returns.fine
    net_wage_core = regular.wage - silver_bars.wage - returns.wage
    net_value_core = net_fine_core * silver_rate if silver_rate > 0 else 0.0

    net_fine = net_fine_core + last_balance_silver
    net_wage = net_wage_core + last_balance_amount
    net_value = net_fine * silver_rate if silver_rate > 0 else 0.0
    grand_total = net_value + net_wage if silver_rate > 0 else net_wage

    return TotalsResult(
        overall_gross=float(overall_gross),
        overall_poly=float(overall_poly),
        regular=regular,
        returns=returns,
        silver_bars=silver_bars,
        net_fine_core=net_fine_core,
        net_wage_core=net_wage_core,
        net_value_core=net_value_core,
        net_fine=net_fine,
        net_wage=net_wage,
        net_value=net_value,
        grand_total=grand_total,
        silver_rate=float(silver_rate),
        last_balance_silver=float(last_balance_silver),
        last_balance_amount=float(last_balance_amount),
    )
