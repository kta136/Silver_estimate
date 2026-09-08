"""Load-more updates exercise the real dialog/widget integration."""

import time
from types import SimpleNamespace

from PySide6.QtCore import QPersistentModelIndex

from silverestimate.domain.pagination import (
    EstimateHistoryCursor,
    ItemCursor,
    Page,
    SilverBarHistoryCursor,
)
from silverestimate.ui.estimate_history import EstimateHistoryDialog
from silverestimate.ui.item_master import ItemMasterWidget
from silverestimate.ui.silver_bar_history import SilverBarHistoryDialog
from tests.ui.test_estimate_history import _DialogDbStub
from tests.ui.test_item_master import _StubDbManager
from tests.ui.test_silver_bar_history import _FakeSilverBarHistoryDb


def test_estimate_append_calculates_only_new_rows_and_preserves_selected_voucher(
    qtbot, monkeypatch
):
    import silverestimate.ui.estimate_history as module

    monkeypatch.setattr(EstimateHistoryDialog, "load_estimates", lambda self: None)
    dialog = EstimateHistoryDialog(_DialogDbStub(), main_window_ref=None)
    qtbot.addWidget(dialog)
    try:
        first = tuple(
            dict(voucher_no=str(n), total_fine=n, date="2026-09-06") for n in (10, 8)
        )
        dialog._populate_table(Page(first, 4, EstimateHistoryCursor(8, "8")))
        dialog.estimates_table.selectRow(1)
        selected = dialog.get_selected_voucher()
        old = dialog.estimates_model.row_payload(1)
        persistent = QPersistentModelIndex(dialog.estimates_model.index(1, 0))
        reset = []
        dialog.estimates_model.modelReset.connect(lambda: reset.append(True))
        calls = []
        original = module.calculate_grand_total

        def calculate(**kwargs):
            calls.append(kwargs)
            return original(**kwargs)

        monkeypatch.setattr(module, "calculate_grand_total", calculate)
        dialog._populate_table(
            Page((dict(voucher_no="6", total_fine=6),), None, None), append=True
        )
        assert len(calls) == 1
        assert not reset
        assert dialog.get_selected_voucher() == selected
        assert dialog.estimates_model.row_payload(persistent.row()) is old
        assert "3 estimates loaded" in dialog.results_summary_label.text()
    finally:
        dialog.close()


def test_item_append_preserves_selected_item_without_reset(qtbot):
    widget = ItemMasterWidget(_StubDbManager())
    qtbot.addWidget(widget)
    try:
        widget.items_table.selectRow(1)
        persistent = QPersistentModelIndex(widget.items_model.index(1, 0))
        old = widget.items_model.row_payload(1)
        reset = []
        widget.items_model.modelReset.connect(lambda: reset.append(True))
        widget._apply_loaded_items(
            Page(
                (dict(code="ITM003", name="Third"),),
                None,
                ItemCursor("ITM003", "ITM003"),
            ),
            search_term="",
            started_at=time.perf_counter(),
            append=True,
        )
        assert not reset
        assert widget.items_model.row_payload(persistent.row()) is old
        assert (
            widget.items_model.row_payload(
                widget.items_table.selectionModel().selectedRows()[0].row()
            )
            is old
        )
        assert "3 items loaded" in widget._item_count_label.text()
    finally:
        widget.close()


def test_bar_history_append_preserves_selection(qtbot):
    dialog = SilverBarHistoryDialog(_FakeSilverBarHistoryDb())
    qtbot.addWidget(dialog)
    try:
        dialog.bars_table.selectRow(1)
        selected = dialog.bars_model.bar_id_at(1)
        reset = []
        dialog.bars_model.modelReset.connect(lambda: reset.append(True))
        request = SimpleNamespace(append=True)
        page = Page(
            (
                dict(
                    bar_id=999,
                    estimate_voucher_no="X",
                    weight=1,
                    date_added="2026-09-06",
                ),
            ),
            None,
            SilverBarHistoryCursor("2026-09-06", 999),
        )
        dialog._on_bars_load_ready(0, (request, page))
        assert not reset
        assert (
            dialog.bars_model.bar_id_at(
                dialog.bars_table.selectionModel().selectedRows()[0].row()
            )
            == selected
        )
    finally:
        dialog.close()
