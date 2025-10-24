from __future__ import annotations

import pytest

from silverestimate.domain.estimate_models import EstimateLineCategory
from silverestimate.presenter import SaveItem, SaveOutcome
from silverestimate.services.estimate_entry_persistence import (
    EstimateEntryPersistenceService,
)
from silverestimate.ui.view_models import (
    EstimateEntryRowState,
    EstimateEntryViewModel,
)


def _row(
    code: str,
    category: EstimateLineCategory,
    *,
    gross: float,
    poly: float,
    net: float,
    fine: float,
    wage: float,
    purity: float = 0.0,
    wage_rate: float = 0.0,
    pieces: int = 1,
) -> EstimateEntryRowState:
    return EstimateEntryRowState(
        code=code,
        name=f"{code}-name",
        gross=gross,
        poly=poly,
        net_weight=net,
        fine_weight=fine,
        wage_amount=wage,
        purity=purity,
        wage_rate=wage_rate,
        pieces=pieces,
        category=category,
    )


class _PresenterStub:
    def __init__(self):
        self.last_payload = None

    def save_estimate(self, payload):
        self.last_payload = payload
        return SaveOutcome(success=True, message="Saved")


def test_prepare_save_payload_aggregates_rows():
    view_model = EstimateEntryViewModel()
    view_model.set_rows(
        [
            _row(
                "REG001",
                EstimateLineCategory.REGULAR,
                gross=10.0,
                poly=1.0,
                net=9.0,
                fine=8.325,
                wage=90.0,
                purity=92.5,
                wage_rate=10.0,
            ),
            _row(
                "RET001",
                EstimateLineCategory.RETURN,
                gross=2.0,
                poly=0.2,
                net=1.8,
                fine=1.35,
                wage=0.0,
                purity=75.0,
            ),
            _row(
                "BAR001",
                EstimateLineCategory.SILVER_BAR,
                gross=3.0,
                poly=0.0,
                net=3.0,
                fine=2.997,
                wage=0.0,
                purity=99.9,
            ),
        ]
    )
    view_model.set_totals_inputs(
        silver_rate=75.0,
        last_balance_silver=0.5,
        last_balance_amount=50.0,
    )

    service = EstimateEntryPersistenceService(view_model)
    prep = service.prepare_save_payload(
        voucher_no="ABC123",
        date="2025-10-17",
        note="hello",
    )

    assert prep.skipped_rows == []
    assert prep.row_errors == {}

    payload = prep.payload
    assert payload.voucher_no == "ABC123"
    assert payload.silver_rate == pytest.approx(75.0)
    assert len(payload.items) == 3
    assert {item.code for item in payload.regular_items} == {"REG001"}
    assert {item.code for item in payload.return_items} == {"RET001", "BAR001"}
    assert payload.totals["total_gross"] == pytest.approx(15.0)
    assert payload.totals["total_net"] == pytest.approx(13.8)
    assert payload.totals["net_fine"] == pytest.approx(3.978)
    assert payload.totals["net_wage"] == pytest.approx(90.0)


def test_prepare_save_payload_skips_invalid_rows():
    view_model = EstimateEntryViewModel()
    view_model.set_rows(
        [
            _row(
                "GOOD",
                EstimateLineCategory.REGULAR,
                gross=5.0,
                poly=0.5,
                net=4.5,
                fine=4.1625,
                wage=45.0,
                wage_rate=10.0,
                purity=92.5,
            ),
            _row(
                "BAD",
                EstimateLineCategory.RETURN,
                gross=1.0,
                poly=0.1,
                net=-0.2,
                fine=0.5,
                wage=0.0,
            ),
        ]
    )

    service = EstimateEntryPersistenceService(view_model)
    prep = service.prepare_save_payload(
        voucher_no="SKIP",
        date="2025-10-17",
        note="note",
    )

    assert prep.skipped_rows == [2]
    assert "cannot be negative" in prep.row_errors[2].lower()
    assert len(prep.payload.items) == 1
    assert prep.payload.items[0].code == "GOOD"


def test_prepare_save_payload_raises_when_no_valid_rows():
    view_model = EstimateEntryViewModel()
    view_model.set_rows(
        [
            _row(
                "NEG",
                EstimateLineCategory.REGULAR,
                gross=1.0,
                poly=0.0,
                net=-1.0,
                fine=-0.5,
                wage=-10.0,
            )
        ]
    )

    service = EstimateEntryPersistenceService(view_model)

    with pytest.raises(ValueError):
        service.prepare_save_payload(
            voucher_no="FAIL",
            date="2025-10-17",
            note="",
        )


def test_execute_save_invokes_presenter():
    view_model = EstimateEntryViewModel()
    view_model.set_rows(
        [
            _row(
                "SAVE",
                EstimateLineCategory.REGULAR,
                gross=4.0,
                poly=0.5,
                net=3.5,
                fine=3.2375,
                wage=35.0,
            )
        ]
    )

    presenter = _PresenterStub()
    service = EstimateEntryPersistenceService(view_model)

    outcome, prep = service.execute_save(
        voucher_no="DOIT",
        date="2025-10-17",
        note="",
        presenter=presenter,
    )

    assert outcome.success is True
    assert presenter.last_payload.voucher_no == "DOIT"
    assert prep.skipped_rows == []


def test_build_row_states_from_items_roundtrip():
    items = [
        SaveItem(
            code="R1",
            row_number=1,
            name="Regular One",
            gross=5.0,
            poly=0.5,
            net_wt=4.5,
            purity=90.0,
            wage_rate=10.0,
            pieces=1,
            wage=45.0,
            fine=4.05,
            is_return=False,
            is_silver_bar=False,
        ),
        SaveItem(
            code="RET",
            row_number=2,
            name="Return",
            gross=1.0,
            poly=0.1,
            net_wt=0.9,
            purity=80.0,
            wage_rate=0.0,
            pieces=1,
            wage=0.0,
            fine=0.72,
            is_return=True,
            is_silver_bar=False,
        ),
    ]

    rows = EstimateEntryPersistenceService.build_row_states_from_items(items)
    assert [row.code for row in rows] == ["R1", "RET"]
    assert rows[0].category.is_regular()
    assert rows[1].category.is_return()
    assert rows[1].row_index == 2
