import pytest

from silverestimate.domain.estimate_models import EstimateLineCategory
from silverestimate.ui.estimate_entry_totals_controller import (
    EstimateEntryTotalsController,
)
from silverestimate.ui.view_models import EstimateEntryRowState, EstimateEntryViewModel


def _make_row(
    *,
    code: str,
    category: EstimateLineCategory,
    gross: float,
    poly: float,
    net_weight: float,
    fine_weight: float,
    wage_amount: float,
    purity: float = 0.0,
    wage_rate: float = 0.0,
    pieces: int = 1,
    row_index: int | None = None,
) -> EstimateEntryRowState:
    return EstimateEntryRowState(
        code=code,
        name=f"{code}-name",
        gross=gross,
        poly=poly,
        net_weight=net_weight,
        fine_weight=fine_weight,
        wage_amount=wage_amount,
        purity=purity,
        wage_rate=wage_rate,
        pieces=pieces,
        category=category,
        row_index=row_index or 0,
    )


def test_rows_and_totals_inputs_feed_totals_and_save_snapshot():
    view_model = EstimateEntryViewModel()
    view_model.set_rows(
        [
            _make_row(
                code="REG001",
                category=EstimateLineCategory.REGULAR,
                gross=10.0,
                poly=1.0,
                net_weight=9.0,
                fine_weight=8.325,
                wage_amount=90.0,
                purity=92.5,
                wage_rate=10.0,
            ),
            _make_row(
                code="RET001",
                category=EstimateLineCategory.RETURN,
                gross=2.0,
                poly=0.2,
                net_weight=1.8,
                fine_weight=1.35,
                wage_amount=0.0,
                purity=75.0,
                wage_rate=0.0,
            ),
        ]
    )
    view_model.set_totals_inputs(
        silver_rate=75.0,
        last_balance_silver=0.5,
        last_balance_amount=100.0,
    )

    totals = EstimateEntryTotalsController.build_totals(
        view_model.rows(),
        silver_rate=view_model.silver_rate,
        last_balance_silver=view_model.last_balance_silver,
        last_balance_amount=view_model.last_balance_amount,
    )

    assert totals.overall_gross == pytest.approx(12.0)
    assert totals.overall_poly == pytest.approx(1.2)
    assert totals.regular.fine == pytest.approx(8.325)
    assert totals.returns.fine == pytest.approx(1.35)
    assert totals.net_fine_core == pytest.approx(6.975)
    assert totals.net_fine == pytest.approx(7.475)
    assert totals.net_wage_core == pytest.approx(90.0)
    assert totals.net_wage == pytest.approx(190.0)
    assert totals.grand_total == pytest.approx(750.63)

    state = view_model.as_save_snapshot()
    assert len(state.rows) == 2
    assert state.silver_rate == pytest.approx(75.0)
    assert state.last_balance_silver == pytest.approx(0.5)
    assert state.last_balance_amount == pytest.approx(100.0)


def test_set_modes_updates_only_given_flags():
    view_model = EstimateEntryViewModel()
    view_model.set_modes(return_mode=True)
    assert view_model.return_mode is True
    assert view_model.silver_bar_mode is False

    view_model.set_modes(silver_bar_mode=True)
    assert view_model.silver_bar_mode is True
