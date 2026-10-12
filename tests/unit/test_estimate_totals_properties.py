from decimal import ROUND_HALF_UP, Decimal

import pytest
from hypothesis import example, given
from hypothesis import strategies as st

from silverestimate.domain.estimate_models import CategoryTotals
from silverestimate.domain.estimate_totals import build_totals_result

_non_negative = st.floats(
    min_value=0.0,
    max_value=100000.0,
    allow_nan=False,
    allow_infinity=False,
)
_signed = st.floats(
    min_value=-100000.0,
    max_value=100000.0,
    allow_nan=False,
    allow_infinity=False,
)
_category_totals = st.builds(
    CategoryTotals,
    gross=_non_negative,
    net=_non_negative,
    fine=_non_negative,
    wage=_signed,
)


@given(
    overall_gross=_non_negative,
    overall_poly=_non_negative,
    regular=_category_totals,
    returns=_category_totals,
    silver_bars=_category_totals,
    silver_rate=_signed,
    last_balance_silver=_signed,
    last_balance_amount=_signed,
)
# The exact total is -2147512334.3449995984544512; its nearest float prints as
# -2147512334.345 and would round to the wrong paisa.
@example(
    overall_gross=0.0,
    overall_poly=0.0,
    regular=CategoryTotals(gross=0.0, net=0.0, fine=0.0, wage=0.0),
    returns=CategoryTotals(gross=0.0, net=0.0, fine=0.0, wage=0.0),
    silver_bars=CategoryTotals(
        gross=0.0, net=0.0, fine=62236.8125, wage=1.8462485999334604
    ),
    silver_rate=34505.5,
    last_balance_silver=0.0,
    last_balance_amount=1.2212490014790092,
)
def test_build_totals_result_preserves_core_invariants(
    overall_gross,
    overall_poly,
    regular,
    returns,
    silver_bars,
    silver_rate,
    last_balance_silver,
    last_balance_amount,
):
    totals = build_totals_result(
        overall_gross=overall_gross,
        overall_poly=overall_poly,
        regular=regular,
        returns=returns,
        silver_bars=silver_bars,
        silver_rate=silver_rate,
        last_balance_silver=last_balance_silver,
        last_balance_amount=last_balance_amount,
    )

    expected_net_fine_core = float(
        Decimal(str(regular.fine))
        - Decimal(str(silver_bars.fine))
        - Decimal(str(returns.fine))
    )
    expected_net_wage_core = float(
        Decimal(str(regular.wage))
        - Decimal(str(silver_bars.wage))
        - Decimal(str(returns.wage))
    )

    assert totals.overall_gross == pytest.approx(overall_gross)
    assert totals.overall_poly == pytest.approx(overall_poly)
    assert totals.net_fine_core == pytest.approx(expected_net_fine_core)
    assert totals.net_wage_core == pytest.approx(expected_net_wage_core)
    assert totals.net_fine == pytest.approx(
        float(Decimal(str(expected_net_fine_core)) + Decimal(str(last_balance_silver)))
    )
    assert totals.net_wage == pytest.approx(
        float(Decimal(str(expected_net_wage_core)) + Decimal(str(last_balance_amount)))
    )

    if silver_rate > 0:
        assert totals.net_value_core == pytest.approx(
            float(
                (
                    Decimal(str(expected_net_fine_core)) * Decimal(str(silver_rate))
                ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            )
        )
        assert totals.net_value == float(
            (Decimal(str(totals.net_fine)) * Decimal(str(silver_rate))).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )
        )
    else:
        assert totals.net_value_core == pytest.approx(0.0)
        assert totals.net_value == pytest.approx(0.0)
    expected_total = (
        Decimal(str(totals.net_value))
        + Decimal(str(expected_net_wage_core))
        + Decimal(str(last_balance_amount))
    )
    assert totals.grand_total == float(
        expected_total.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    )
