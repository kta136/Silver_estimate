import pytest

from silverestimate.domain.estimate_models import CategoryTotals
from silverestimate.domain.estimate_totals import build_totals_result


def test_build_totals_result_combines_categories_balances_and_rate():
    totals = build_totals_result(
        overall_gross=15.0,
        overall_poly=1.2,
        regular=CategoryTotals(gross=10.0, net=9.0, fine=8.325, wage=90.0),
        returns=CategoryTotals(gross=2.0, net=1.8, fine=1.35, wage=10.0),
        silver_bars=CategoryTotals(gross=3.0, net=3.0, fine=2.997, wage=5.0),
        silver_rate=75.0,
        last_balance_silver=0.5,
        last_balance_amount=50.0,
    )

    assert totals.overall_gross == pytest.approx(15.0)
    assert totals.overall_poly == pytest.approx(1.2)
    assert totals.net_fine_core == pytest.approx(3.978)
    assert totals.net_wage_core == pytest.approx(75.0)
    assert totals.net_value_core == pytest.approx(298.35)
    assert totals.net_fine == pytest.approx(4.478)
    assert totals.net_wage == pytest.approx(125.0)
    assert totals.net_value == pytest.approx(335.85)
    assert totals.grand_total == pytest.approx(460.85)


def test_build_totals_result_zero_or_negative_rate_zeroes_value_fields():
    totals = build_totals_result(
        overall_gross=5.0,
        overall_poly=0.5,
        regular=CategoryTotals(fine=4.0, wage=100.0),
        returns=CategoryTotals(fine=1.0, wage=25.0),
        silver_bars=CategoryTotals(fine=0.5, wage=10.0),
        silver_rate=0.0,
        last_balance_silver=2.0,
        last_balance_amount=40.0,
    )

    assert totals.net_fine_core == pytest.approx(2.5)
    assert totals.net_fine == pytest.approx(4.5)
    assert totals.net_wage_core == pytest.approx(65.0)
    assert totals.net_wage == pytest.approx(105.0)
    assert totals.net_value_core == pytest.approx(0.0)
    assert totals.net_value == pytest.approx(0.0)
    assert totals.grand_total == pytest.approx(105.0)
