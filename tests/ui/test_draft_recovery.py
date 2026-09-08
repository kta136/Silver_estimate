"""Unfinished entry recovery never changes saved estimates or inventory."""

import json
from dataclasses import replace

import pytest
from PySide6.QtWidgets import QLineEdit, QMessageBox

from silverestimate.domain.estimate_models import EstimateLineCategory
from silverestimate.ui import estimate_draft_recovery as recovery_module
from silverestimate.ui.estimate_draft_recovery import decode_draft
from silverestimate.ui.estimate_entry_logic.constants import COL_GROSS
from tests.ui.test_history_safeguards import _draft, history_db

__all__ = ["history_db"]


def test_recovery_round_trip_retains_precision_modes_and_snapshots(
    history_db, make_estimate_widget, monkeypatch
):
    source = make_estimate_widget(history_db)
    _draft(source)
    row = source.item_table.get_all_rows()[0]
    row = replace(
        row,
        fine_weight=9.365625,
        wage_amount=10.125,
        tunch="Historic",
        snapshot_version=1,
    )
    source.item_table.replace_all_rows(
        [
            row,
            replace(row, line_key="return", category=EstimateLineCategory.RETURN),
            replace(row, line_key="bar", category=EstimateLineCategory.SILVER_BAR),
        ]
    )
    source.last_balance_silver = -1.234
    source.last_balance_amount = -10.12
    source.return_mode = True
    assert source.draft_recovery.flush()
    stored = history_db.draft_repository.load()
    source.draft_recovery.stop()
    target = make_estimate_widget(history_db)
    monkeypatch.setattr(recovery_module, "choose_recovery", lambda *a: "restore")
    target.draft_recovery.offer_recovery()
    rows = target.item_table.get_all_rows()
    assert rows[0].fine_weight == 9.365625 and rows[0].wage_amount == 10.125
    assert rows[0].tunch == "Historic" and rows[0].snapshot_version == 1
    assert rows[0].line_key == row.line_key
    assert rows[1].category is EstimateLineCategory.RETURN
    assert rows[2].category is EstimateLineCategory.SILVER_BAR
    assert target.last_balance_silver == -1.234
    assert target.last_balance_amount == -10.12
    assert target.return_mode and target.has_unsaved_changes()
    assert target.note_edit.text() == "Keep the draft"
    assert history_db.draft_repository.load().token == stored.token
    assert history_db.get_estimate_by_voucher("DRAFT") is None
    assert (
        history_db.conn.execute("SELECT COUNT(*) FROM silver_bars").fetchone()[0] == 0
    )


def test_poll_captures_unfinished_editor_without_closing_it(
    history_db, make_estimate_widget, qtbot, monkeypatch
):
    source = make_estimate_widget(history_db)
    _draft(source)
    source.show()
    qtbot.waitExposed(source)
    qtbot.wait(250)
    table = source.item_table
    table.commit_active_editor()
    table.begin_cell_edit(0, COL_GROSS)
    editor = table.focusWidget()
    assert isinstance(editor, QLineEdit)
    editor.setText("12.")
    editor.setModified(True)
    assert source.draft_recovery.flush()
    assert table.focusWidget() is editor
    assert editor.text() == "12."
    assert table.get_row_state(0).gross == 10
    source.draft_recovery.stop()
    source.hide()
    target = make_estimate_widget(history_db)
    target.show()
    qtbot.wait(250)
    monkeypatch.setattr(recovery_module, "choose_recovery", lambda *a: "restore")
    target.draft_recovery.offer_recovery()
    qtbot.waitUntil(
        lambda: (
            isinstance(target.item_table.focusWidget(), QLineEdit)
            and target.item_table.focusWidget().text() == "12."
        )
    )
    assert target.item_table.get_row_state(0).gross == 10


@pytest.mark.parametrize("choice", ["Discard", "Cancel"])
def test_recovery_choice_preserves_or_removes_only_copy(
    history_db, make_estimate_widget, monkeypatch, choice
):
    source = make_estimate_widget(history_db)
    _draft(source)
    assert source.draft_recovery.flush()
    before = history_db.draft_repository.load()
    source.draft_recovery.stop()
    target = make_estimate_widget(history_db)
    monkeypatch.setattr(recovery_module, "choose_recovery", lambda *a: choice.lower())
    target.draft_recovery.offer_recovery()
    if choice == "Discard":
        assert history_db.draft_repository.load() is None
    else:
        _draft(target)
        target.note_edit.setText("Another entry")
        assert not target.draft_recovery.flush()
        assert history_db.draft_repository.load() == before
    assert history_db.get_estimate_by_voucher("DRAFT") is None


def test_corrupt_recovery_is_retained_for_explicit_discard(
    history_db, make_estimate_widget, monkeypatch
):
    assert history_db.draft_repository.write(
        "token", "1", '{"version":999}', expected_token=None
    )
    target = make_estimate_widget(history_db)
    monkeypatch.setattr(recovery_module, "choose_recovery", lambda *a: "restore")
    monkeypatch.setattr(QMessageBox, "warning", lambda *a: None)
    target.draft_recovery.offer_recovery()
    assert history_db.draft_repository.load() is not None
    assert not target.draft_recovery.flush()
    monkeypatch.setattr(recovery_module, "choose_recovery", lambda *a: "discard")
    target.draft_recovery.offer_recovery()
    assert history_db.draft_repository.load() is None


def test_original_save_flow_removes_copy_and_failed_save_keeps_it(
    history_db, make_estimate_widget, monkeypatch
):
    widget = make_estimate_widget(history_db)
    _draft(widget)
    assert widget.draft_recovery.flush()
    history_db.conn.execute(
        "CREATE TRIGGER fail_draft_save BEFORE INSERT ON estimates BEGIN SELECT RAISE(ABORT, 'Injected'); END"
    )
    monkeypatch.setattr(QMessageBox, "critical", lambda *a: None)
    assert not widget.workflow_controller.save_estimate()
    assert history_db.draft_repository.load() is not None
    history_db.conn.execute("DROP TRIGGER fail_draft_save")
    events = []
    monkeypatch.setattr(QMessageBox, "information", lambda *a: events.append("success"))
    monkeypatch.setattr(
        widget.workflow_controller, "print_estimate", lambda: events.append("preview")
    )
    assert widget.workflow_controller.save_estimate()
    assert events == ["success", "preview"]
    assert widget.voucher_edit.text() != "DRAFT"
    assert history_db.draft_repository.load() is None


def test_discard_then_close_does_not_recreate_copy(
    history_db, make_estimate_widget, monkeypatch
):
    widget = make_estimate_widget(history_db)
    _draft(widget)
    assert widget.draft_recovery.flush()
    monkeypatch.setattr(
        QMessageBox, "question", lambda *a: QMessageBox.StandardButton.Discard
    )
    widget.close()
    assert history_db.draft_repository.load() is None
    assert not widget.draft_recovery.flush()


def test_timer_preserves_edits_and_does_not_rewrite_identical_copy(
    history_db, make_estimate_widget, qtbot
):
    widget = make_estimate_widget(history_db, enable_draft_recovery=True)
    _draft(widget)
    widget.show()
    qtbot.waitUntil(lambda: widget.draft_recovery._started)
    widget.draft_recovery._timer.setInterval(30)
    qtbot.waitUntil(lambda: history_db.draft_repository.load() is not None)
    before = history_db.draft_repository.load()
    changes = history_db.conn.total_changes
    qtbot.wait(100)
    assert history_db.conn.total_changes == changes
    assert history_db.draft_repository.load() == before
    widget.draft_recovery.stop()


def test_busy_or_failed_draft_write_preserves_entry(
    history_db, make_estimate_widget, monkeypatch
):
    widget = make_estimate_widget(history_db)
    _draft(widget)
    recovery = widget.draft_recovery
    before = widget.item_table.get_all_rows()
    with history_db._broker.maintenance():
        assert not recovery.flush()
    assert recovery.flush()
    widget.note_edit.setText("Changed")
    monkeypatch.setattr(
        recovery.repository,
        "write",
        lambda *a, **k: (_ for _ in ()).throw(OSError("Injected")),
    )
    assert not recovery.flush()
    assert recovery.status == "Update failed"
    assert widget.item_table.get_all_rows() == before
    assert widget.has_unsaved_changes()


@pytest.mark.parametrize(
    "field,value",
    [
        ("version", 2),
        ("rows", "invalid"),
        ("silver_rate", float("nan")),
        ("date", "bad"),
        ("editor", {"row": 99, "column": 0, "text": "x"}),
    ],
)
def test_invalid_recovery_is_rejected_before_applying(
    history_db, make_estimate_widget, field, value
):
    widget = make_estimate_widget(history_db)
    _draft(widget)
    data = json.loads(widget.draft_recovery.capture())
    data[field] = value
    with pytest.raises((ValueError, TypeError)):
        decode_draft(json.dumps(data))


def test_exit_discard_cannot_be_recreated_by_a_queued_timer(
    history_db, make_estimate_widget, monkeypatch
):
    widget = make_estimate_widget(history_db)
    _draft(widget)
    assert widget.draft_recovery.flush()
    monkeypatch.setattr(
        QMessageBox, "question", lambda *a: QMessageBox.StandardButton.Discard
    )
    assert widget.workflow_controller.confirm_exit()
    assert not widget.draft_recovery.flush()
    assert history_db.draft_repository.load() is None
    # If the entry stays open and is edited again, a new recovery copy is allowed.
    widget.note_edit.setText("A new change")
    assert widget.draft_recovery.flush()


def test_clean_entry_does_not_create_recovery(history_db, make_estimate_widget):
    widget = make_estimate_widget(history_db)
    assert not widget.draft_recovery.flush()
    assert history_db.draft_repository.load() is None


def test_close_cancels_pending_recovery_start(
    history_db, make_estimate_widget, qtbot, monkeypatch
):
    widget = make_estimate_widget(history_db, enable_draft_recovery=True)
    calls = []
    monkeypatch.setattr(
        widget.draft_recovery, "offer_recovery", lambda: calls.append(True)
    )
    widget.show()
    assert widget.draft_recovery._startup_timer.isActive()
    widget.confirm_exit = lambda: True
    widget.close()
    qtbot.wait(300)
    assert not calls
    assert not widget.draft_recovery._timer.isActive()
    widget.show()
    qtbot.waitUntil(lambda: bool(calls))
    assert widget.draft_recovery._timer.isActive()
