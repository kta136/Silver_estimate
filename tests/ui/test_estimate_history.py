from PyQt5.QtCore import QItemSelectionModel
from PyQt5.QtWidgets import QFrame

from silverestimate.ui.estimate_history import EstimateHistoryDialog


class _ButtonStub:
    def __init__(self, enabled=False):
        self.enabled = enabled

    def setEnabled(self, value):
        self.enabled = bool(value)


class _ThreadStub:
    def __init__(self):
        self.quit_called = False
        self.wait_called = False
        self.deleted = False

    def quit(self):
        self.quit_called = True

    def wait(self, _timeout):
        self.wait_called = True
        return True

    def deleteLater(self):
        self.deleted = True


class _WorkerStub:
    def __init__(self):
        self.deleted = False

    def deleteLater(self):
        self.deleted = True


class _ProgressStub:
    def __init__(self):
        self.closed = False
        self.deleted = False

    def close(self):
        self.closed = True

    def deleteLater(self):
        self.deleted = True


class _HistoryHarness:
    pass


class _DialogDbStub:
    temp_db_path = ":memory:"

    def get_first_estimate_date(self):
        return "2026-01-01"


def _build_harness():
    harness = _HistoryHarness()
    harness._load_request_id = 2
    harness._active_load_workers = {}
    harness.search_button = _ButtonStub(enabled=False)
    harness.open_button = _ButtonStub(enabled=False)
    harness.print_button = _ButtonStub(enabled=False)
    harness.delete_button = _ButtonStub(enabled=False)
    return harness


def test_loading_done_re_enables_buttons_for_current_request():
    harness = _build_harness()
    thread = _ThreadStub()
    worker = _WorkerStub()
    harness._active_load_workers[thread] = worker

    EstimateHistoryDialog._loading_done(harness, thread, worker, 2)

    assert thread.quit_called is True
    assert thread.wait_called is True
    assert worker.deleted is True
    assert thread not in harness._active_load_workers
    assert harness.search_button.enabled is True
    assert harness.open_button.enabled is True
    assert harness.print_button.enabled is True
    assert harness.delete_button.enabled is True


def test_loading_done_does_not_touch_buttons_for_stale_request():
    harness = _build_harness()
    thread = _ThreadStub()
    worker = _WorkerStub()
    harness._active_load_workers[thread] = worker

    EstimateHistoryDialog._loading_done(harness, thread, worker, 1)

    assert thread.quit_called is True
    assert thread.wait_called is True
    assert worker.deleted is True
    assert thread not in harness._active_load_workers
    assert harness.search_button.enabled is False
    assert harness.open_button.enabled is False
    assert harness.print_button.enabled is False
    assert harness.delete_button.enabled is False


def test_finish_print_preview_build_cleans_up_worker():
    harness = _HistoryHarness()
    harness._print_preview_request_id = 2
    harness._active_print_preview_workers = {}
    harness.logger = type("_Logger", (), {"debug": lambda *args, **kwargs: None})()
    thread = _ThreadStub()
    worker = _WorkerStub()
    progress = _ProgressStub()
    harness._active_print_preview_workers[thread] = worker

    EstimateHistoryDialog._finish_print_preview_build(
        harness,
        2,
        thread=thread,
        worker=worker,
        progress=progress,
    )

    assert thread.quit_called is True
    assert thread.wait_called is True
    assert thread.deleted is True
    assert worker.deleted is True
    assert progress.closed is True
    assert progress.deleted is True
    assert thread not in harness._active_print_preview_workers


def test_populate_table_uses_model_rows_and_selection_lookup(qtbot, monkeypatch):
    monkeypatch.setattr(EstimateHistoryDialog, "load_estimates", lambda self: None)
    dialog = EstimateHistoryDialog(_DialogDbStub(), main_window_ref=None)
    qtbot.addWidget(dialog)
    try:
        dialog.show()
        qtbot.waitUntil(lambda: dialog.isVisible(), timeout=1000)

        dialog._populate_table(
            headers=[
                {
                    "voucher_no": "V002",
                    "date": "2026-03-02",
                    "note": "Second note",
                    "silver_rate": 95.5,
                    "total_fine": 1.25,
                    "total_wage": 100.0,
                    "last_balance_amount": 10.0,
                },
                {
                    "voucher_no": "V001",
                    "date": "2026-03-01",
                    "note": "First note",
                    "silver_rate": 90.0,
                    "total_fine": 2.0,
                    "total_wage": 75.0,
                    "last_balance_amount": 5.0,
                },
            ],
            agg_map={
                "V001": (2.5, 2.25),
                "V002": (1.5, 1.25),
            },
            request_id=dialog._load_request_id,
        )

        assert dialog.estimates_model.rowCount() == 2
        assert dialog.results_summary_label.text() == "2 estimates in current date range"

        target_row = next(
            row
            for row in range(dialog.estimates_model.rowCount())
            if dialog.estimates_model.row_payload(row).voucher_no == "V002"
        )
        index = dialog.estimates_model.index(target_row, 0)
        dialog.estimates_table.setCurrentIndex(index)
        dialog.estimates_table.selectionModel().select(
            index,
            QItemSelectionModel.ClearAndSelect | QItemSelectionModel.Rows,
        )

        assert dialog.get_selected_voucher() == "V002"
        assert (
            dialog.estimates_model.data(dialog.estimates_model.index(target_row, 8))
            == "229.38"
        )
    finally:
        dialog.deleteLater()


def test_estimate_history_uses_compact_top_controls(qtbot, monkeypatch):
    monkeypatch.setattr(EstimateHistoryDialog, "load_estimates", lambda self: None)
    dialog = EstimateHistoryDialog(_DialogDbStub(), main_window_ref=None)
    qtbot.addWidget(dialog)
    try:
        dialog.resize(1280, 800)
        dialog.show()
        qtbot.waitUntil(lambda: dialog.isVisible(), timeout=1000)

        header_card = dialog.findChild(QFrame, "HistoryHeaderCard")
        filter_card = dialog.findChild(QFrame, "HistoryFilterCard")

        assert header_card is not None
        assert filter_card is not None
        assert header_card.height() <= 54
        assert filter_card.height() <= 56
        assert dialog.estimates_table.viewport().height() >= 560
    finally:
        dialog.deleteLater()
