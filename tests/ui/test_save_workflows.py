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
    history_db, make_estimate_widget, confirmations, action, choice
):
    widget = make_estimate_widget(history_db)
    _draft(widget)
    before = widget.item_table.get_all_rows()
    confirmations.always(choice)
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
    history_db, make_estimate_widget, confirmations
):
    widget = make_estimate_widget(history_db)
    _draft(widget)
    widget.set_voucher_number("TARGET")
    assert widget.workflow_controller.save_estimate(continue_editing=True)
    widget.workflow_controller.clear_form(confirm=False)
    _draft(widget)
    widget.voucher_edit.setText("TARGET")
    confirmations.always("Save")
    widget.workflow_controller.safe_load_estimate()
    assert history_db.get_estimate_by_voucher("DRAFT") is not None
    assert widget.voucher_edit.text() == "TARGET"
    assert not widget.has_unsaved_changes()


def test_failed_save_blocks_new_and_exit(
    history_db, make_estimate_widget, monkeypatch, confirmations
):
    widget = make_estimate_widget(history_db)
    _draft(widget)
    rows = widget.item_table.get_all_rows()
    widget.item_table.replace_all_rows([replace(rows[0], code="UNKNOWN")])
    confirmations.always("Save")
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


@pytest.mark.parametrize(
    ("choice", "saved"), [("Go Back", False), ("Save Anyway", True)]
)
def test_saving_a_row_without_weight_asks_first(
    history_db, make_estimate_widget, confirmations, choice, saved
):
    widget = make_estimate_widget(history_db)
    _draft(widget)
    row = widget.item_table.get_all_rows()[0]
    widget.item_table.replace_all_rows(
        [replace(row, gross=0.0, poly=0.0, net_weight=0.0, fine_weight=0.0)]
    )
    confirmations.answer(choice)

    assert widget.workflow_controller.save_estimate(continue_editing=True) is saved
    assert confirmations.shown == [
        "Rows Without Weight: <b>Row 1 has no gross weight.</b>"
    ]
    assert (history_db.get_estimate_by_voucher("DRAFT") is not None) is saved


def test_delete_row_does_not_ask_and_can_be_undone(
    history_db, make_estimate_widget, monkeypatch
):
    widget = make_estimate_widget(history_db)
    _draft(widget)
    first = widget.item_table.get_all_rows()[0]
    widget.item_table.replace_all_rows([first, replace(first, line_key="second")])
    widget.item_table.setCurrentCell(0, 0)
    asked = []
    monkeypatch.setattr(QMessageBox, "question", lambda *a: asked.append(a))
    monkeypatch.setattr(QMessageBox, "warning", lambda *a: asked.append(a))

    widget.workflow_controller.delete_current_row()

    assert asked == []
    assert [r.line_key for r in widget.item_table.get_all_rows() if r.code] == [
        "second"
    ]
    assert widget.command_undo_row_action.isEnabled()
    assert widget.command_undo_row_action.shortcut().toString() == "Ctrl+Shift+D"
    widget.command_undo_row_action.trigger()
    assert widget.item_table.get_all_rows()[0].line_key == first.line_key


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
    monkeypatch.setattr(widget, "_status", lambda *args: statuses.append(args))
    # A successful save reports in the status line; it must not stop the user
    # with a message box before the preview.
    monkeypatch.setattr(
        QMessageBox,
        "information",
        lambda *_args, **_kwargs: events.append("message box"),
    )
    monkeypatch.setattr(
        widget.workflow_controller, "print_estimate", lambda: events.append("preview")
    )
    widget.primary_actions.save_button.click()
    assert events == ["preview"]
    assert ("Saving estimate DRAFT...", 2000) in statuses
    assert statuses[-1] == ("Estimate 'DRAFT' saved successfully.", 5000)
    assert widget.voucher_edit.text() != "DRAFT"
    assert history_db.get_estimate_by_voucher("DRAFT") is not None
    assert not hasattr(widget.primary_actions, "save_options_button")
    assert not hasattr(widget, "save_and_print")
    assert not hasattr(widget, "save_and_new")


def test_failures_the_user_caused_are_shown_not_only_logged(
    history_db, make_estimate_widget
):
    widget = make_estimate_widget(history_db)
    shown = []
    widget._notify = lambda message, timeout=3000, level="info": shown.append(
        (message, level)
    )
    kept = widget.voucher_edit.text()

    widget.voucher_edit.setText("NOPE")
    widget.workflow_controller.load_estimate()

    assert shown == [("No estimate NOPE. Your current entry was kept.", "warning")]
    assert widget.voucher_edit.text() == kept


def test_a_loaded_note_shows_its_first_words_and_all_of_it_on_hover(
    history_db, make_estimate_widget
):
    note = "Delhi refinery - urgent, deliver by Friday evening without fail"
    assert history_db.save_estimate_with_returns(
        "LONG", "2026-09-05", 75, [], [], {"note": note}
    )
    widget = make_estimate_widget(history_db)

    widget.voucher_edit.setText("LONG")
    widget.workflow_controller.load_estimate()

    assert widget.note_edit.text() == note
    assert widget.note_edit.cursorPosition() == 0
    assert widget.note_edit.toolTip() == note
