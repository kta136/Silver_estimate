from PyQt6.QtCore import QItemSelectionModel
from PyQt6.QtWidgets import QFrame

from silverestimate.domain.pagination import Page
from silverestimate.ui.estimate_history import EstimateHistoryDialog
from silverestimate.ui.themed_controls import ThemedDateEdit


class _ButtonStub:
    def __init__(self, enabled=False):
        self.enabled = enabled

    def setEnabled(self, value):
        self.enabled = bool(value)


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

    def get_estimate_history_page(self, **kwargs):
        del kwargs
        return Page((), 0, None)


def _build_harness():
    harness = _HistoryHarness()
    harness.search_button = _ButtonStub(enabled=False)
    harness.open_button = _ButtonStub(enabled=False)
    harness.print_button = _ButtonStub(enabled=False)
    harness.delete_button = _ButtonStub(enabled=False)
    harness.load_more_button = _ButtonStub(enabled=False)
    return harness


def test_loading_done_re_enables_buttons_in_finally_path():
    harness = _build_harness()
    EstimateHistoryDialog._loading_done(harness, 2)

    assert harness.search_button.enabled is True
    assert harness.open_button.enabled is True
    assert harness.print_button.enabled is True
    assert harness.delete_button.enabled is True
    assert harness.load_more_button.enabled is True


def test_finish_print_preview_build_cleans_up_progress():
    harness = _HistoryHarness()
    progress = _ProgressStub()
    harness._print_preview_progress = progress
    harness._dispose_print_preview_progress = lambda: (
        EstimateHistoryDialog._dispose_print_preview_progress(harness)
    )

    EstimateHistoryDialog._finish_print_preview_build(harness, 2)

    assert progress.closed is True
    assert progress.deleted is True
    assert harness._print_preview_progress is None


def test_populate_table_uses_model_rows_and_selection_lookup(qtbot, monkeypatch):
    monkeypatch.setattr(EstimateHistoryDialog, "load_estimates", lambda self: None)
    dialog = EstimateHistoryDialog(_DialogDbStub(), main_window_ref=None)
    qtbot.addWidget(dialog)
    try:
        dialog.show()
        qtbot.waitUntil(lambda: dialog.isVisible(), timeout=1000)

        dialog._populate_table(
            Page(
                (
                    {
                        "voucher_no": "V002",
                        "date": "2026-03-02",
                        "note": "Second note",
                        "silver_rate": 95.5,
                        "total_gross": 1.5,
                        "total_net": 1.25,
                        "total_fine": 1.25,
                        "total_wage": 100.0,
                        "last_balance_amount": 10.0,
                    },
                    {
                        "voucher_no": "V001",
                        "date": "2026-03-01",
                        "note": "First note",
                        "silver_rate": 90.0,
                        "total_gross": 2.5,
                        "total_net": 2.25,
                        "total_fine": 2.0,
                        "total_wage": 75.0,
                        "last_balance_amount": 5.0,
                    },
                ),
                2,
                None,
            ),
        )

        assert dialog.estimates_model.rowCount() == 2
        assert (
            dialog.results_summary_label.text()
            == "2 of 2 estimates in current date range"
        )

        target_row = next(
            row
            for row in range(dialog.estimates_model.rowCount())
            if dialog.estimates_model.row_payload(row).voucher_no == "V002"
        )
        index = dialog.estimates_model.index(target_row, 0)
        dialog.estimates_table.setCurrentIndex(index)
        dialog.estimates_table.selectionModel().select(
            index,
            QItemSelectionModel.SelectionFlag.ClearAndSelect
            | QItemSelectionModel.SelectionFlag.Rows,
        )

        assert dialog.get_selected_voucher() == "V002"
        assert (
            dialog.estimates_model.data(dialog.estimates_model.index(target_row, 8))
            == "₹ 229.38"
        )
    finally:
        dialog.close()
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
        assert dialog.minimumWidth() <= 820
        assert isinstance(dialog.date_from, ThemedDateEdit)
        assert isinstance(dialog.date_to, ThemedDateEdit)
        assert dialog.date_from.maximumWidth() <= 180
        assert "QCalendarWidget QToolButton" in dialog.styleSheet()
        assert header_card.height() <= 54
        assert filter_card.height() <= 56
        assert dialog.estimates_table.viewport().height() >= 548
    finally:
        dialog.close()
        dialog.deleteLater()
