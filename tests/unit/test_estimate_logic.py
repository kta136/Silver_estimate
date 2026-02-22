"""Calculator-focused tests replacing legacy EstimateLogic mixin coverage."""

import pytest

from silverestimate.domain.estimate_models import EstimateLine, EstimateLineCategory
from silverestimate.services.estimate_calculator import (
    compute_fine_weight,
    compute_net_weight,
    compute_totals,
    compute_wage_amount,
)

try:
    from hypothesis import given

    _HYPOTHESIS_AVAILABLE = True
except ModuleNotFoundError:
    _HYPOTHESIS_AVAILABLE = False


def test_compute_net_weight_clamps_to_zero():
    assert compute_net_weight(10.0, 1.0) == pytest.approx(9.0)
    assert compute_net_weight(1.0, 10.0) == pytest.approx(0.0)


def test_compute_fine_weight_handles_zero_purity():
    assert compute_fine_weight(9.0, 0.0) == pytest.approx(0.0)
    assert compute_fine_weight(9.0, -5.0) == pytest.approx(0.0)


def test_compute_fine_weight_uses_purity_percentage():
    assert compute_fine_weight(9.0, 92.5) == pytest.approx(8.325)


def test_compute_wage_amount_uses_basis():
    assert compute_wage_amount("WT", net_weight=9.0, wage_rate=10.0, pieces=3) == 90.0
    assert compute_wage_amount("PC", net_weight=9.0, wage_rate=10.0, pieces=3) == 30.0
    assert compute_wage_amount(None, net_weight=9.0, wage_rate=10.0, pieces=3) == 90.0


def test_compute_totals_groups_categories_and_balances():
    lines = [
        EstimateLine(
            code="REG001",
            category=EstimateLineCategory.REGULAR,
            gross=10.0,
            poly=1.0,
            net_weight=9.0,
            fine_weight=8.325,
            wage_amount=90.0,
        ),
        EstimateLine(
            code="RET001",
            category=EstimateLineCategory.RETURN,
            gross=1.5,
            poly=0.5,
            net_weight=1.0,
            fine_weight=0.5,
            wage_amount=0.0,
        ),
        EstimateLine(
            code="BAR001",
            category=EstimateLineCategory.SILVER_BAR,
            gross=2.0,
            poly=0.0,
            net_weight=2.0,
            fine_weight=2.0,
            wage_amount=0.0,
        ),
    ]

    totals = compute_totals(
        lines,
        silver_rate=70000.0,
        last_balance_silver=1.5,
        last_balance_amount=500.0,
    )

    assert totals.overall_gross == pytest.approx(13.5)
    assert totals.overall_poly == pytest.approx(1.5)

    assert totals.regular.fine == pytest.approx(8.325)
    assert totals.returns.fine == pytest.approx(0.5)
    assert totals.silver_bars.fine == pytest.approx(2.0)

    assert totals.net_fine_core == pytest.approx(5.825)
    assert totals.net_wage_core == pytest.approx(90.0)
    assert totals.net_fine == pytest.approx(7.325)
    assert totals.net_wage == pytest.approx(590.0)


if _HYPOTHESIS_AVAILABLE:
    from tests.factories import fine_calculation_cases, wage_calculation_cases

    @given(case=fine_calculation_cases())
    def test_compute_fine_property(case):
        expected_net = max(case.gross - case.poly, 0.0)
        expected_fine = (
            0.0 if case.purity <= 0.0 else expected_net * (case.purity / 100)
        )
        assert compute_net_weight(case.gross, case.poly) == pytest.approx(expected_net)
        assert compute_fine_weight(expected_net, case.purity) == pytest.approx(
            expected_fine
        )

    @given(case=wage_calculation_cases())
    def test_compute_wage_property(case):
        expected = (
            case.pieces * case.wage_rate
            if case.wage_type == "PC"
            else case.net_weight * case.wage_rate
        )
        assert compute_wage_amount(
            case.wage_type,
            net_weight=case.net_weight,
            wage_rate=case.wage_rate,
            pieces=case.pieces,
        ) == pytest.approx(expected)

else:

    @pytest.mark.skip(reason="hypothesis not installed")
    def test_compute_fine_property():  # pragma: no cover - optional dependency
        pytest.skip("hypothesis not installed")

    @pytest.mark.skip(reason="hypothesis not installed")
    def test_compute_wage_property():  # pragma: no cover - optional dependency
        pytest.skip("hypothesis not installed")
