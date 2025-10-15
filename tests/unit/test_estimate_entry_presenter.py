import logging
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional

import pytest

from silverestimate.presenter import (
    EstimateEntryPresenter,
    EstimateEntryViewState,
    LoadedEstimate,
    SaveItem,
    SaveOutcome,
    SavePayload,
)


@dataclass
class _StateFixture:
    lines: Iterable[SaveItem]
    silver_rate: float = 0.0
    last_balance_silver: float = 0.0
    last_balance_amount: float = 0.0

    def to_view_state(self) -> EstimateEntryViewState:
        return EstimateEntryViewState(
            lines=list(self.lines),
            silver_rate=self.silver_rate,
            last_balance_silver=self.last_balance_silver,
            last_balance_amount=self.last_balance_amount,
        )


class FakeRepository:
    def __init__(self):
        self.generated_voucher = "V001"
        self.load_estimate_response: Optional[Dict] = None
        self.estimate_exists_flag = False
        self.save_calls: List[Dict] = []
        self.save_result = True
        self.last_error_value: Optional[str] = None
        self.fetch_item_map: Dict[str, Dict] = {}
        self.fetched_silver_bars: List[Dict] = []
        self.update_bar_results: List[bool] = []
        self.add_bar_results: List[Optional[int]] = []
        self.deleted_vouchers: List[str] = []
        self.notify_calls: List[str] = []

    def generate_voucher_no(self) -> str:
        return self.generated_voucher

    def load_estimate(self, voucher_no: str) -> Optional[Dict]:
        return self.load_estimate_response

    def fetch_item(self, code: str) -> Optional[Dict]:
        return self.fetch_item_map.get(code)

    def estimate_exists(self, voucher_no: str) -> bool:
        return self.estimate_exists_flag

    def notify_silver_bars_for_estimate(self, voucher_no: str) -> None:
        self.notify_calls.append(voucher_no)

    def save_estimate(self, voucher_no: str, date: str, silver_rate: float,
                      regular_items: Iterable[Dict], return_items: Iterable[Dict], totals: Dict) -> bool:
        self.save_calls.append(
            {
                "voucher": voucher_no,
                "date": date,
                "silver_rate": silver_rate,
                "regular": list(regular_items),
                "returns": list(return_items),
                "totals": totals,
            }
        )
        return self.save_result

    def fetch_silver_bars_for_estimate(self, voucher_no: str) -> List[Dict]:
        return list(self.fetched_silver_bars)

    def update_silver_bar(self, bar_id: int, weight: float, purity: float) -> bool:
        if self.update_bar_results:
            return self.update_bar_results.pop(0)
        return True

    def add_silver_bar(self, voucher_no: str, weight: float, purity: float) -> Optional[int]:
        if self.add_bar_results:
            return self.add_bar_results.pop(0)
        return 1

    def last_error(self) -> Optional[str]:
        return self.last_error_value

    def delete_estimate(self, voucher_no: str) -> bool:
        self.deleted_vouchers.append(voucher_no)
        return True


class FakeView:
    def __init__(self):
        self.voucher_number: Optional[str] = None
        self.status_messages: List[str] = []
        self.history_return: Optional[str] = None
        self.apply_loaded_estimate_result = True
        self.loaded_estimate: Optional[LoadedEstimate] = None
        self.history_called = False
        self.silver_bar_called = False
        self.populate_row_calls: List[Dict] = []
        self.focus_calls: List[int] = []
        self.prompt_return: Optional[Dict] = None
        self.state_fixture = _StateFixture(lines=[])

    def capture_state(self) -> EstimateEntryViewState:
        return self.state_fixture.to_view_state()

    def apply_totals(self, totals):  # pragma: no cover - not used directly here
        self.last_totals = totals

    def set_voucher_number(self, voucher_no: str) -> None:
        self.voucher_number = voucher_no

    def show_status(self, message: str, timeout: int = 3000, level: str = "info") -> None:
        self.status_messages.append(message)

    def populate_row(self, row_index: int, item_data: Dict) -> None:
        self.populate_row_calls.append({"row": row_index, "item": item_data})

    def prompt_item_selection(self, code: str) -> Optional[Dict]:
        return self.prompt_return

    def focus_after_item_lookup(self, row_index: int) -> None:
        self.focus_calls.append(row_index)

    def open_history_dialog(self) -> Optional[str]:
        self.history_called = True
        return self.history_return

    def show_silver_bar_management(self) -> None:
        self.silver_bar_called = True

    def apply_loaded_estimate(self, loaded: LoadedEstimate) -> bool:
        self.loaded_estimate = loaded
        return self.apply_loaded_estimate_result


@pytest.fixture
def presenter_fixtures():
    repo = FakeRepository()
    view = FakeView()
    presenter = EstimateEntryPresenter(view, repo)
    return presenter, view, repo


def _make_sample_payload() -> SavePayload:
    regular = SaveItem(
        code="REG",
        row_number=1,
        name="Ring",
        gross=10.0,
        poly=1.0,
        net_wt=9.0,
        purity=90.0,
        wage_rate=50.0,
        pieces=1,
        wage=450.0,
        fine=8.1,
        is_return=False,
        is_silver_bar=False,
    )
    bar = SaveItem(
        code="BAR",
        row_number=2,
        name="Bar",
        gross=2.0,
        poly=0.0,
        net_wt=2.0,
        purity=99.0,
        wage_rate=0.0,
        pieces=1,
        wage=0.0,
        fine=1.98,
        is_return=False,
        is_silver_bar=True,
    )
    totals = {
        "total_gross": 12.0,
        "total_net": 11.0,
        "net_fine": 8.1,
        "net_wage": 450.0,
    }
    return SavePayload(
        voucher_no="V100",
        date="2025-01-01",
        silver_rate=70000.0,
        note="",
        last_balance_silver=0.0,
        last_balance_amount=0.0,
        items=(regular, bar),
        regular_items=(regular,),
        return_items=(bar,),
        totals=totals,
    )


def test_open_history_successful_load(presenter_fixtures):
    presenter, view, repo = presenter_fixtures
    view.history_return = "V123"
    repo.load_estimate_response = {
        "header": {
            "voucher_no": "V123",
            "date": "2025-01-02",
            "silver_rate": 65000.0,
            "note": "Loaded",
            "last_balance_silver": 1.0,
            "last_balance_amount": 500.0,
        },
        "items": [
            {
                "item_code": "R1",
                "item_name": "Ring",
                "gross": 10.0,
                "poly": 1.0,
                "net_wt": 9.0,
                "purity": 90.0,
                "wage_rate": 50.0,
                "pieces": 1,
                "wage": 450.0,
                "fine": 8.1,
                "is_return": 0,
                "is_silver_bar": 0,
            }
        ],
    }

    presenter.open_history()

    assert view.history_called
    assert view.loaded_estimate is not None
    assert view.loaded_estimate.voucher_no == "V123"
    assert view.status_messages[-1] == "Loaded estimate V123 from history."


def test_open_history_no_selection(presenter_fixtures):
    presenter, view, repo = presenter_fixtures
    view.history_return = None

    presenter.open_history()

    assert view.history_called
    assert view.status_messages[-1] == "No estimate selected from history."


def test_open_history_not_found(presenter_fixtures):
    presenter, view, repo = presenter_fixtures
    view.history_return = "MISSING"
    repo.load_estimate_response = None

    presenter.open_history()

    assert view.status_messages[-1] == "Estimate MISSING not found."


def test_open_history_apply_failure(presenter_fixtures):
    presenter, view, repo = presenter_fixtures
    view.history_return = "V200"
    repo.load_estimate_response = {"header": {}, "items": []}
    view.apply_loaded_estimate_result = False

    presenter.open_history()

    assert view.status_messages[-1] == "Estimate V200 could not be loaded."


def test_open_silver_bar_management_delegates_to_view(presenter_fixtures):
    presenter, view, repo = presenter_fixtures

    presenter.open_silver_bar_management()

    assert view.silver_bar_called


def test_save_estimate_success_adds_new_bar(presenter_fixtures):
    presenter, view, repo = presenter_fixtures
    payload = _Make_sample_payload()
    repo.add_bar_results = [10]
    repo.fetched_silver_bars = []

    outcome = presenter.save_estimate(payload)

    assert outcome.success
    assert outcome.bars_added == 1
    assert "saved successfully" in outcome.message
    assert repo.save_calls


def test_save_estimate_failure_returns_error(presenter_fixtures):
    presenter, view, repo = presenter_fixtures
    payload = _Make_sample_payload()
    repo.save_result = False
    repo.last_error_value = "database failure"

    outcome = presenter.save_estimate(payload)

    assert not outcome.success
    assert outcome.error_detail == "database failure"
    assert "Failed to save" in outcome.message


def test_delete_estimate_delegates_to_repository(presenter_fixtures):
    presenter, view, repo = presenter_fixtures

    assert presenter.delete_estimate("V500")
    assert repo.deleted_vouchers == ["V500"]


def test_load_estimate_transforms_repository_response(presenter_fixtures):
    presenter, view, repo = presenter_fixtures
    repo.load_estimate_response = {
        "header": {
            "voucher_no": "VX",
            "date": "2025-02-02",
            "silver_rate": 62000.0,
            "note": "Sample",
            "last_balance_silver": 2.5,
            "last_balance_amount": 300.0,
        },
        "items": [
            {
                "item_code": "ITM",
                "item_name": "Item",
                "gross": 5.0,
                "poly": 0.5,
                "net_wt": 4.5,
                "purity": 91.0,
                "wage_rate": 20.0,
                "pieces": 1,
                "wage": 90.0,
                "fine": 4.095,
                "is_return": 1,
                "is_silver_bar": 0,
            }
        ],
    }

    loaded = presenter.load_estimate("VX")

    assert isinstance(loaded, LoadedEstimate)
    assert loaded.voucher_no == "VX"
    assert len(loaded.items) == 1
    assert loaded.items[0].is_return is True


# Helpers -----------------------------------------------------------------


def _Make_sample_payload() -> SavePayload:
    return _make_sample_payload()
