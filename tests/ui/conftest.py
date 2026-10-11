from types import SimpleNamespace

import pytest

from silverestimate.domain.estimate_save import EstimateSaveResult
from silverestimate.ui.estimate_entry import EstimateEntryWidget


@pytest.fixture
def fake_db():
    class Database:
        item_cache_controller = None
        generate_calls = 0

        def generate_voucher_no(self):
            self.generate_calls += 1
            return "TEST123"

        def drop_tables(self):
            return True

        def setup_database(self):
            return True

        def delete_all_estimates(self):
            return True

        def get_item_by_code(self, code):
            return {"wage_type": "WT", "wage_rate": 10}

    return Database()


class _EstimateSource:
    """The estimate calls the presenter makes, tolerant of minimal test databases."""

    def __init__(self, db):
        self.db = db

    @property
    def last_error(self):
        return getattr(self.db, "last_error", None)

    def generate_voucher_no(self):
        return self.db.generate_voucher_no()

    def get_estimate_by_voucher(self, voucher_no):
        loader = getattr(self.db, "get_estimate_by_voucher", None)
        return loader(voucher_no) if callable(loader) else None

    def get_item_by_code(self, code):
        return self.db.get_item_by_code(code)

    def get_items_by_codes(self, codes):
        return {
            str(code or "").strip().upper(): item
            for code in codes
            if (item := self.get_item_by_code(code)) is not None
        }

    def save_estimate_atomic(
        self, voucher_no, date, silver_rate, regular_items, return_items, totals
    ):
        saver = getattr(self.db, "save_estimate_atomic", None)
        if callable(saver):
            return saver(
                voucher_no,
                date,
                silver_rate,
                list(regular_items or []),
                list(return_items or []),
                dict(totals or {}),
            )
        return EstimateSaveResult(True)

    def delete_single_estimate(self, voucher_no):
        deleter = getattr(self.db, "delete_single_estimate", None)
        return bool(deleter(voucher_no)) if callable(deleter) else True


@pytest.fixture
def make_estimate_widget(qtbot, settings_stub):
    """Build independent estimate widgets and give pytest-qt ownership of them."""

    def make(db_manager, *, enable_draft_recovery=False):
        host = SimpleNamespace(
            show_inline_status=lambda *args, **kwargs: None,
            show_silver_bars=lambda: None,
        )
        widget = EstimateEntryWidget(db_manager, host, _EstimateSource(db_manager))
        if widget.draft_recovery is not None and not enable_draft_recovery:
            # Autosave scheduling belongs to recovery tests, not unrelated widget tests.
            widget.draft_recovery._started = True
        qtbot.addWidget(
            widget,
            # Teardown must not prompt after committing an unfinished cell editor.
            # Individual tests exercise confirm_exit before this cleanup runs.
            before_close_func=lambda widget: setattr(
                widget, "confirm_exit", lambda: True
            ),
        )
        widget.presenter.handle_item_code = lambda row, code: False
        return widget

    return make
