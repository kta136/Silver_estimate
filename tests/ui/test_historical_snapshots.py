"""Real entry, preview and resave preserve detached historical lines."""

import pytest

from silverestimate.persistence import schema
from silverestimate.ui.estimate_print_document import EstimatePrintDocument
from tests.integration.test_estimate_snapshots import downgrade_to_v8, snapshot_db

__all__ = ["snapshot_db"]


@pytest.mark.parametrize("lost_code", [False, True])
def test_open_preview_and_note_save_preserve_historical_lines(
    snapshot_db, make_estimate_widget, lost_code
):
    db = snapshot_db
    if lost_code:
        downgrade_to_v8(db)
        db.conn.execute("DELETE FROM items WHERE code = 'REG001'")
        db.conn.execute("UPDATE estimate_items SET line_key = ''")
        db.conn.commit()
        schema.run_schema_setup(db)
    else:
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
    assert widget.view_model.compute_totals().regular.fine == before["items"][0]["fine"]
    widget.note_edit.setText("Only the note changed")
    assert widget.workflow_controller.save_estimate(continue_editing=True)
    after = db.get_estimate_by_voucher("1")
    original_item = EstimatePrintDocument.from_mapping(before).items[0]
    assert EstimatePrintDocument.from_mapping(after).items[0] == original_item


def test_continuing_after_save_freezes_draft_preview_metadata(
    snapshot_db, make_estimate_widget
):
    from silverestimate.ui.view_models import EstimateEntryRowState

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
