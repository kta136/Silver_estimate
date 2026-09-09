"""Save command semantics and recovery of in-session editing mistakes."""

from dataclasses import replace
from types import SimpleNamespace

import pytest
from PySide6.QtWidgets import QLineEdit, QMessageBox

from silverestimate.ui.estimate_entry_logic.constants import COL_GROSS
from silverestimate.ui.print_payload_builder import PrintPayloadBuilder
from tests.ui.test_history_safeguards import _draft, history_db

__all__ = ["history_db"]


@pytest.mark.parametrize("action", ["new", "exit", "load"])
@pytest.mark.parametrize("choice", ["Save", "Discard", "Cancel"])
def test_unsaved_decisions_use_one_contract(
    history_db, make_estimate_widget, monkeypatch, action, choice
):
    widget = make_estimate_widget(history_db)
    _draft(widget)
    before = widget.item_table.get_all_rows()
    monkeypatch.setattr(
        QMessageBox, "question", lambda *a: getattr(QMessageBox.StandardButton, choice)
    )
    workflow = widget.workflow_controller
    if action == "new":
        workflow.clear_form()
        assert (widget.voucher_edit.text() != "DRAFT") is (choice != "Cancel")
    elif action == "exit":
        assert workflow.confirm_exit() is (choice != "Cancel")
    else:
        # An absent target must retain the old identity and data even after Discard.
        widget.voucher_edit.setText("MISSING")
        workflow.safe_load_estimate()
        assert widget.voucher_edit.text() == "DRAFT"
        rows = widget.item_table.get_all_rows()
        assert rows[0].code == before[0].code
        assert history_db.get_estimate_by_voucher("MISSING") is None
    assert (history_db.get_estimate_by_voucher("DRAFT") is not None) is (
        choice == "Save"
    )


def test_save_before_load_saves_original_voucher(
    history_db, make_estimate_widget, monkeypatch
):
    widget = make_estimate_widget(history_db)
    _draft(widget)
    widget.set_voucher_number("TARGET")
    assert widget.workflow_controller.save_estimate(continue_editing=True)
    widget.workflow_controller.clear_form(confirm=False)
    _draft(widget)
    widget.voucher_edit.setText("TARGET")
    monkeypatch.setattr(
        QMessageBox, "question", lambda *a: QMessageBox.StandardButton.Save
    )
    widget.workflow_controller.safe_load_estimate()
    assert history_db.get_estimate_by_voucher("DRAFT") is not None
    assert widget.voucher_edit.text() == "TARGET"
    assert not widget.has_unsaved_changes()


def test_failed_save_blocks_new_and_exit(history_db, make_estimate_widget, monkeypatch):
    widget = make_estimate_widget(history_db)
    _draft(widget)
    rows = widget.item_table.get_all_rows()
    widget.item_table.replace_all_rows([replace(rows[0], code="UNKNOWN")])
    monkeypatch.setattr(
        QMessageBox, "question", lambda *a: QMessageBox.StandardButton.Save
    )
    monkeypatch.setattr(QMessageBox, "critical", lambda *a: None)
    widget.workflow_controller.clear_form()
    assert widget.voucher_edit.text() == "DRAFT"
    assert not widget.workflow_controller.confirm_exit()
    assert widget.has_unsaved_changes()


def test_preview_state_survives_format_and_tunch_changes(
    history_db, make_estimate_widget
):
    widget = make_estimate_widget(history_db)
    _draft(widget)
    workflow = widget.workflow_controller
    for expected in ("Unsaved draft", "Saved estimate"):
        data = workflow._build_current_estimate_preview_data("DRAFT")
        payload = PrintPayloadBuilder().build_estimate_preview_payload(
            "DRAFT", fetch_estimate=lambda _: None, estimate_data=data
        )
        assert expected in payload.title
        assert expected in payload.format_factory("classic").title
        assert expected in payload.tunch_visibility_factory(True).title
        assert workflow.save_estimate(continue_editing=True)


def test_row_undo_preserves_other_edits_and_line_identity(
    history_db, make_estimate_widget, monkeypatch
):
    widget = make_estimate_widget(history_db)
    _draft(widget)
    first = widget.item_table.get_all_rows()[0]
    second = replace(first, code="RET", line_key="second")
    widget.item_table.replace_all_rows([first, second])
    widget.item_table.setCurrentCell(0, 0)
    monkeypatch.setattr(
        QMessageBox, "question", lambda *a: QMessageBox.StandardButton.Yes
    )
    workflow = widget.workflow_controller
    workflow.delete_current_row()
    widget.item_table.set_row(0, replace(second, gross=20))
    assert workflow.undo_row_deletion()
    restored = widget.item_table.get_all_rows()
    assert restored[0].line_key == first.line_key
    assert restored[0].fine_weight == first.fine_weight
    assert restored[1].gross == 20
    assert widget.has_unsaved_changes()
    assert not workflow.undo_row_deletion()
    workflow.delete_current_row()
    workflow.clear_form(confirm=False)
    assert not workflow.undo_row_deletion()


def test_bad_loaded_rows_do_not_replace_dirty_draft(history_db, make_estimate_widget):
    widget = make_estimate_widget(history_db)
    _draft(widget)
    before = widget.item_table.get_all_rows()
    assert not widget.workflow_controller.apply_loaded_estimate(
        SimpleNamespace(items=[object()])
    )
    assert widget.item_table.get_all_rows() == before
    assert widget.note_edit.text() == "Keep the draft"
    assert widget.has_unsaved_changes()


def test_save_captures_active_cell_editor(history_db, make_estimate_widget, qtbot):
    widget = make_estimate_widget(history_db)
    _draft(widget)
    widget.show()
    widget.activateWindow()
    qtbot.waitExposed(widget)
    qtbot.wait(200)
    table = widget.item_table
    table.commit_active_editor()
    table.setCurrentCell(0, COL_GROSS)
    table.edit(table.model().index(0, COL_GROSS))
    editor = table.focusWidget()
    assert isinstance(editor, QLineEdit)
    editor.setFocus()
    editor.selectAll()
    qtbot.keyClicks(editor, "12.34")
    assert widget.workflow_controller.save_estimate(continue_editing=True)
    saved = history_db.get_estimate_by_voucher("DRAFT")
    assert saved["items"][0]["gross"] == pytest.approx(12.34)


def test_save_button_persists_then_previews_and_clears(
    history_db, make_estimate_widget, monkeypatch
):
    widget = make_estimate_widget(history_db)
    _draft(widget)
    events = []
    statuses = []
    success_messages = []
    monkeypatch.setattr(widget, "_status", lambda *args: statuses.append(args))

    def report_success(_parent, title, message):
        assert title == "Success"
        success_messages.append(message)
        events.append("success")

    monkeypatch.setattr(QMessageBox, "information", report_success)
    monkeypatch.setattr(
        widget.workflow_controller, "print_estimate", lambda: events.append("preview")
    )
    widget.primary_actions.save_button.click()
    assert events == ["success", "preview"]
    assert ("Saving estimate DRAFT...", 2000) in statuses
    assert (success_messages[0], 5000) in statuses
    assert widget.voucher_edit.text() != "DRAFT"
    assert history_db.get_estimate_by_voucher("DRAFT") is not None
    assert not hasattr(widget.primary_actions, "save_options_button")
    assert not hasattr(widget, "save_and_print")
    assert not hasattr(widget, "save_and_new")
