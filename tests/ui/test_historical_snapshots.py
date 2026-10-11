"""Real entry, preview and resave preserve detached historical lines."""

from silverestimate.ui.estimate_entry_totals_controller import (
    EstimateEntryTotalsController,
)
from silverestimate.ui.estimate_print_document import EstimatePrintDocument
from tests.integration.test_estimate_snapshots import snapshot_db


def _snapshot_totals(widget):
    snapshot = widget.workflow_controller._capture_snapshot()
    return EstimateEntryTotalsController.build_totals(
        snapshot.rows,
        silver_rate=snapshot.silver_rate,
        last_balance_silver=snapshot.last_balance_silver,
        last_balance_amount=snapshot.last_balance_amount,
    )


__all__ = ["snapshot_db"]


def test_open_preview_and_note_save_preserve_historical_lines(
    snapshot_db, make_estimate_widget
):
    db = snapshot_db
    assert db.delete_item("REG001")
    before = db.get_estimate_by_voucher("1")
    widget = make_estimate_widget(db)
    assert widget.workflow_controller.apply_loaded_estimate(
        widget.presenter.load_estimate("1")
    )
    active = [row for row in widget.item_table.get_all_rows() if not row.is_empty()]
    assert len(active) == 1
    assert active[0].name == "Saved name"
    assert active[0].fine_weight == before["items"][0]["fine"]
    preview = widget.workflow_controller._build_current_estimate_preview_data("1")
    assert len(preview["items"]) == 1
    assert preview["items"][0]["tunch"] == before["items"][0]["tunch"]
    assert preview["items"][0]["fine"] == before["items"][0]["fine"]
    assert _snapshot_totals(widget).regular.fine == before["items"][0]["fine"]
    widget.note_edit.setText("Only the note changed")
    assert widget.workflow_controller.save_estimate(continue_editing=True)
    after = db.get_estimate_by_voucher("1")
    original_item = EstimatePrintDocument.from_mapping(before).items[0]
    assert EstimatePrintDocument.from_mapping(after).items[0] == original_item


def test_continuing_after_save_freezes_draft_preview_metadata(
    snapshot_db, make_estimate_widget
):
    from silverestimate.domain.estimate_entry import EstimateEntryRowState

    db = snapshot_db
    widget = make_estimate_widget(db)
    widget.voucher_edit.setText("2")
    widget.item_table.replace_all_rows(
        [
            EstimateEntryRowState(
                code="REG001",
                name="New",
                gross=1,
                net_weight=1,
                purity=90,
                fine_weight=0.9,
            )
        ]
    )
    assert widget.workflow_controller.save_estimate(continue_editing=True)
    assert db.update_item("REG001", "Changed", 50, "PC", 1, tunch="Changed")
    preview = widget.workflow_controller._build_current_estimate_preview_data("2")
    assert preview["items"][0]["tunch"] == "91 + loss"
