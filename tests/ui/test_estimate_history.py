from types import SimpleNamespace

import pytest
from PySide6.QtCore import QItemSelectionModel, Qt
from PySide6.QtWidgets import QFrame, QLabel, QScrollArea, QWidget

from silverestimate.domain.pagination import Page
from silverestimate.ui.estimate_history import EstimateHistoryDialog
from silverestimate.ui.themed_controls import ThemedDateEdit


class _ButtonStub:
    def __init__(self, enabled=False):
        self.enabled = enabled

    def setEnabled(self, value):
        self.enabled = bool(value)


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
    harness._closing = False
    harness._load_runner = SimpleNamespace(generation=2)
    harness.search_button = _ButtonStub(enabled=False)
    harness.open_button = _ButtonStub(enabled=False)
    harness.print_button = _ButtonStub(enabled=False)
    harness.delete_button = _ButtonStub(enabled=False)
    harness.load_more_button = _ButtonStub(enabled=False)
    harness._loading = True
    harness.selected = [object()]
    harness.estimates_table = SimpleNamespace(
        selectionModel=lambda: SimpleNamespace(selectedRows=lambda: harness.selected)
    )
    harness._sync_action_buttons = lambda: EstimateHistoryDialog._sync_action_buttons(
        harness
    )
    return harness


@pytest.mark.parametrize(
    "has_selection", [True, False], ids=["estimate-selected", "nothing-selected"]
)
def test_loading_done_re_enables_buttons_and_row_actions_need_a_selection(
    has_selection,
):
    harness = _build_harness()
    if not has_selection:
        harness.selected = []
    EstimateHistoryDialog._loading_done(harness, 2)

    assert harness.search_button.enabled is True
    assert harness.load_more_button.enabled is True
    assert harness.open_button.enabled is has_selection
    assert harness.print_button.enabled is has_selection
    assert harness.delete_button.enabled is has_selection


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
        assert dialog.results_summary_label.text() == "2 estimates in these dates"
        assert dialog.results_summary_label.minimumWidth() >= (
            dialog.results_summary_label.fontMetrics().horizontalAdvance(
                dialog.results_summary_label.text()
            )
            + 24
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
        # Native Windows metrics can differ from the offscreen plugin by one pixel.
        assert dialog.estimates_table.viewport().height() >= 546
    finally:
        dialog.close()
        dialog.deleteLater()


def test_filter_row_keeps_search_in_view_and_says_nothing_twice(qtbot, monkeypatch):
    monkeypatch.setattr(EstimateHistoryDialog, "load_estimates", lambda self: None)
    dialog = EstimateHistoryDialog(_DialogDbStub(), main_window_ref=None)
    qtbot.addWidget(dialog)
    try:
        dialog.resize(1280, 700)
        dialog.show()
        qtbot.waitUntil(lambda: dialog.isVisible(), timeout=1000)
        assert dialog._filter_title.isVisible()

        # Narrow: the heading, which repeats the window title, makes room.
        dialog.resize(dialog.minimumWidth(), 600)
        qtbot.waitUntil(lambda: not dialog._filter_title.isVisible(), timeout=1000)
        assert dialog.search_button.isVisible()

        # An empty result is explained in the table, not a second time here.
        dialog._update_results_summary(0)
        assert dialog.results_summary_label.text() == ""
        assert [
            button.text()
            for button in (
                dialog.open_button,
                dialog.print_button,
                dialog.delete_button,
            )
        ] == ["Open Estimate", "Print Estimate", "Delete Estimate"]
    finally:
        dialog.close()
        dialog.deleteLater()


@pytest.mark.parametrize("size", [(1280, 664), (1216, 624)])
def test_details_panel_needs_no_scrollbar_at_the_size_it_opens_on_1366x768(
    qtbot, monkeypatch, size
):
    # On a 1366x768 screen the dialog opens 1280x664, a taskbar and a title
    # bar short of 768. The selected-estimate panel used to need about 20 px
    # more, so it grew two scrollbars and cut off the voucher number, the
    # date and the amounts.
    monkeypatch.setattr(EstimateHistoryDialog, "load_estimates", lambda self: None)
    dialog = EstimateHistoryDialog(_DialogDbStub(), main_window_ref=None)
    qtbot.addWidget(dialog)
    try:
        # 1280x664 is the size on a 1366x768 screen, 1216x624 the size on a
        # 1600x900 one with Windows at 125% (1280x688 usable).
        dialog.resize(*size)
        dialog.show()
        qtbot.waitUntil(lambda: dialog.isVisible(), timeout=1000)
        dialog.selected_details_strip.set_items(
            [
                ("Voucher No", "2"),
                ("Date", "16/01/2026"),
                ("Note", "Smoke estimate two"),
                ("Silver rate", "₹ 75,250.00"),
                ("Gross", "20.00 g"),
                ("Net Wt", "18.75 g"),
                ("Net Fine", "19.06 g"),
                ("Net Labour", "₹ 6,094.00"),
                ("Grand Total", "₹ 14,40,170.88"),
            ]
        )
        qtbot.wait(50)

        scroll = dialog.selected_details_strip.findChild(QScrollArea)
        assert scroll is not None
        assert not scroll.verticalScrollBar().isVisible()
        # Nothing is wider than the room it has: the Grand Total row used to
        # carry 28 px of padding that pushed its amount out of view.
        assert scroll.widget().width() <= scroll.viewport().width()
        total = scroll.widget().findChild(QWidget, "RecordInspectorTotal")
        assert total is not None
        for label in total.findChildren(QLabel):
            # A label's size hint includes any style padding: this is the text
            # and nothing more (the row's padding is its layout margin).
            text = label.fontMetrics().horizontalAdvance(label.text())
            assert label.sizeHint().width() <= text + 8, label.text()
        amount = total.findChildren(QLabel)[-1]
        assert amount.mapTo(scroll.viewport(), amount.rect().topRight()).x() <= (
            scroll.viewport().width()
        )
        assert amount.fontMetrics().horizontalAdvance(amount.text()) <= amount.width()
        assert scroll.horizontalScrollBarPolicy() == (
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        for button in (
            dialog.open_button,
            dialog.print_button,
            dialog.delete_button,
        ):
            assert button.isVisible()
            assert button.geometry().bottom() < dialog.selected_details_strip.height()
    finally:
        dialog.close()
        dialog.deleteLater()


def test_history_opens_larger_on_big_screens_and_leaves_room_on_small_ones(
    qtbot, monkeypatch
):
    asked = {}
    monkeypatch.setattr(EstimateHistoryDialog, "load_estimates", lambda self: None)
    monkeypatch.setattr(
        "silverestimate.ui.estimate_history.resize_to_available_screen",
        lambda widget, **kwargs: asked.update(kwargs),
    )

    dialog = EstimateHistoryDialog(_DialogDbStub(), main_window_ref=None)
    qtbot.addWidget(dialog)

    # Capped to the screen on a small one; this much where there is room.
    assert asked["preferred_width"] >= 1400
    assert asked["preferred_height"] >= 780
    # 48 px, not 64: on a 1280x688 screen that is the 16 px that stop the
    # selected-estimate panel needing a scrollbar.
    assert asked["margin"] <= 48
