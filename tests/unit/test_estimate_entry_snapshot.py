import pytest

from silverestimate.domain.estimate_entry import (
    EstimateEntryRowState,
    EstimateEntrySnapshot,
)
from silverestimate.domain.estimate_models import EstimateLineCategory
from silverestimate.ui.estimate_entry_totals_controller import (
    EstimateEntryTotalsController,
)


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


def test_captured_rows_and_totals_inputs_feed_totals():
    snapshot = EstimateEntrySnapshot.capture(
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
        ],
        silver_rate=75.0,
        last_balance_silver=0.5,
        last_balance_amount=100.0,
    )

    totals = EstimateEntryTotalsController.build_totals(
        snapshot.rows,
        silver_rate=snapshot.silver_rate,
        last_balance_silver=snapshot.last_balance_silver,
        last_balance_amount=snapshot.last_balance_amount,
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

    assert [row.row_index for row in snapshot.rows] == [1, 2]
    assert all(row.line_key for row in snapshot.rows)
