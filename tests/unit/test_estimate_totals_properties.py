import pytest

from silverestimate.domain.estimate_models import CategoryTotals
from silverestimate.domain.estimate_totals import build_totals_result

try:
    from hypothesis import given
    from hypothesis import strategies as st

    _HYPOTHESIS_AVAILABLE = True
except ModuleNotFoundError:
    _HYPOTHESIS_AVAILABLE = False


if _HYPOTHESIS_AVAILABLE:
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

        expected_net_fine_core = regular.fine - silver_bars.fine - returns.fine
        expected_net_wage_core = regular.wage - silver_bars.wage - returns.wage

        assert totals.overall_gross == pytest.approx(overall_gross)
        assert totals.overall_poly == pytest.approx(overall_poly)
        assert totals.net_fine_core == pytest.approx(expected_net_fine_core)
        assert totals.net_wage_core == pytest.approx(expected_net_wage_core)
        assert totals.net_fine == pytest.approx(
            expected_net_fine_core + last_balance_silver
        )
        assert totals.net_wage == pytest.approx(
            expected_net_wage_core + last_balance_amount
        )

        if silver_rate > 0:
            assert totals.net_value_core == pytest.approx(
                expected_net_fine_core * silver_rate
            )
            assert totals.net_value == pytest.approx(totals.net_fine * silver_rate)
            assert totals.grand_total == pytest.approx(
                totals.net_value + totals.net_wage
            )
        else:
            assert totals.net_value_core == pytest.approx(0.0)
            assert totals.net_value == pytest.approx(0.0)
            assert totals.grand_total == pytest.approx(totals.net_wage)

else:

    @pytest.mark.skip(reason="hypothesis not installed")
    def test_build_totals_result_preserves_core_invariants():
        pytest.skip("hypothesis not installed")
