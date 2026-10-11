"""Unified list/bar browsing, keyboard actions, full totals, and lifecycle."""

from pathlib import Path

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QDialog

from silverestimate.domain.silver_bar_workspace import BarListSnapshot
from silverestimate.ui.print_manager import PrintManager
from silverestimate.ui.print_preview_output import PrintOutputOutcome, PrintOutputStatus
from silverestimate.ui.silver_bar_history import SilverBarHistoryDialog
from silverestimate.ui.silver_bar_management import SilverBarDialog
from tests.silver_bar_workspace_support import seed_workspace_db


@pytest.fixture
def history(qtbot, tmp_path, settings_stub):
    db = seed_workspace_db(tmp_path)
    active = db.add_bars_to_list([1, 6], note="Morning active").unwrap()
    issued = db.add_bars_to_list([2, 3], note="Evening dispatch").unwrap()
    issued = db.issue_printed_list(issued.list_id, issued.signature).unwrap()
    other = db.add_bars_to_list([4], note="Other dispatch").unwrap()
    db.issue_printed_list(other.list_id, other.signature).unwrap()
    dialog = SilverBarHistoryDialog(db)
    qtbot.addWidget(dialog)
    dialog.show()
    dialog.activateWindow()
    qtbot.waitUntil(lambda: dialog.lists_model.rowCount() == 3)
    yield dialog, db, active, issued
    dialog.close()
    db.close()


def select_list(dialog, list_id):
    row = next(
        i
        for i in range(dialog.lists_model.rowCount())
        if dialog.lists_model.row_payload(i)["list_id"] == list_id
    )
    dialog.lists_table.selectRow(row)


def open_issued(qtbot, dialog, issued):
    select_list(dialog, issued.list_id)
    qtbot.keyClick(dialog.lists_table, Qt.Key.Key_Return)
    qtbot.waitUntil(lambda: dialog.snapshot is not None)


def test_all_active_issued_filters_search_and_full_totals(history, qtbot):
    dialog, _, active, issued = history
    select_list(dialog, issued.list_id)
    row = dialog.lists_model.row_payload(dialog.lists_table.currentIndex().row())
    assert row["bar_count"] == 2
    assert row["weight"] == 80.25
    assert row["fine_weight"] == pytest.approx(89.91)
    dialog.list_state_combo.setCurrentText("Active")
    qtbot.waitUntil(
        lambda: dialog.lists_model.rowCount() == 1 and not dialog._loading[0]
    )
    assert dialog.lists_model.row_payload(0)["list_id"] == active.list_id
    dialog.list_state_combo.setCurrentText("Issued")
    qtbot.waitUntil(lambda: dialog.lists_model.rowCount() == 2)
    dialog.list_search_edit.setText("Evening")
    qtbot.waitUntil(
        lambda: dialog.lists_model.rowCount() == 1 and not dialog._loading[0]
    )
    assert dialog.lists_model.row_payload(0)["list_id"] == issued.list_id


def test_enter_active_list_returns_it_for_editing(history, qtbot):
    dialog, _, active, _ = history
    select_list(dialog, active.list_id)
    qtbot.keyClick(dialog.lists_table, Qt.Key.Key_Return)
    qtbot.waitUntil(lambda: dialog.result() == QDialog.DialogCode.Accepted)
    assert dialog.selected_list_id == active.list_id


def test_issued_details_reprint_and_reopen_use_selected_identity(
    history, qtbot, monkeypatch, confirmations
):
    dialog, db, _, issued = history
    select_list(dialog, issued.list_id)
    dialog.lists_table.sortByColumn(1, Qt.SortOrder.DescendingOrder)
    captured = []
    monkeypatch.setattr(
        PrintManager,
        "quick_print",
        lambda _, payload: (
            captured.append(payload) or PrintOutputOutcome(PrintOutputStatus.SUCCESS)
        ),
    )
    qtbot.keyClick(
        dialog.lists_table, Qt.Key.Key_P, Qt.KeyboardModifier.ControlModifier
    )
    qtbot.waitUntil(lambda: dialog.detail_status.text() == "List reprinted.")
    assert captured[0].document.bars[1].purity == 125.5
    assert db.get_silver_bar_list_snapshot(issued.list_id).issued
    confirmations.answer("Reopen List")
    qtbot.keyClick(
        dialog.list_bars_table, Qt.Key.Key_R, Qt.KeyboardModifier.ControlModifier
    )
    assert dialog.selected_list_id == issued.list_id
    reopened = db.get_silver_bar_list_snapshot(issued.list_id)
    assert not reopened.issued
    assert all(bar["status"] == "Assigned" for bar in reopened.bars)


def test_reopen_cancel_preserves_issued_state(history, qtbot, confirmations):
    dialog, db, _, issued = history
    open_issued(qtbot, dialog, issued)
    confirmations.answer("Cancel")
    dialog.reactivate_list()
    assert confirmations.shown == [
        f"Reopen Issued List: <b>Reopen {issued.details['list_identifier']} "
        "for editing?</b>"
    ]
    assert dialog.selected_list_id is None
    assert db.get_silver_bar_list_snapshot(issued.list_id).issued
    assert dialog.isVisible()


def test_bars_status_names_and_link_to_issued_list(history, qtbot):
    dialog, _, _, issued = history
    qtbot.keyClick(
        dialog.list_search_edit, Qt.Key.Key_2, Qt.KeyboardModifier.ControlModifier
    )
    qtbot.waitUntil(lambda: dialog.bars_model.rowCount() == 7)
    assert dialog.status_combo.findText("Assigned") == -1
    dialog.status_combo.setCurrentText("In active list")
    qtbot.waitUntil(
        lambda: dialog.bars_model.rowCount() == 2 and not dialog._loading[1]
    )
    assert dialog.bars_model.display_value(0, 5) == "In active list"
    assert dialog.bars_model.tooltip_value(0, 5) == "In active list"
    dialog.status_combo.setCurrentText("Issued")
    qtbot.waitUntil(lambda: dialog.bars_model.rowCount() == 3)
    row = next(
        i
        for i in range(3)
        if dialog.bars_model.row_payload(i)["list_id"] == issued.list_id
    )
    dialog.bars_table.selectRow(row)
    qtbot.keyClick(dialog.bars_table, Qt.Key.Key_Return)
    qtbot.waitUntil(lambda: dialog.snapshot is not None)
    assert dialog.snapshot.list_id == issued.list_id
    qtbot.keyClick(dialog.list_bars_table, Qt.Key.Key_Escape)
    assert dialog.pages.currentIndex() == 0
    assert dialog.status_combo.currentText() == "Issued"


def test_details_totals_and_print_include_rows_after_visible_page(
    history, qtbot, monkeypatch
):
    dialog, _, _, issued = history
    snapshot = BarListSnapshot(
        issued.details, tuple({**issued.bars[1], "bar_id": i} for i in range(1601))
    )
    dialog.pages.setCurrentIndex(1)
    dialog._details_ready(0, snapshot)
    assert dialog.list_bars_model.rowCount() == 1500
    assert "1601 bars" in dialog.list_totals_label.text()
    assert fixed_total(snapshot.fine_weight) in dialog.list_totals_label.text()
    captured = []
    monkeypatch.setattr(
        PrintManager,
        "quick_print",
        lambda _, payload: (
            captured.append(payload) or PrintOutputOutcome(PrintOutputStatus.SUCCESS)
        ),
    )
    dialog.print_list()
    qtbot.waitUntil(lambda: len(captured) == 1)
    assert len(captured[0].document.bars) == 1601
    dialog.load_more_details()
    assert dialog.list_bars_model.rowCount() == 1601


def fixed_total(value):
    from silverestimate.domain.numeric_policy import fixed_decimal

    return fixed_decimal(value, 2)


@pytest.mark.parametrize("shortcut", [Qt.Key.Key_O, Qt.Key.Key_H])
def test_workspace_open_and_history_use_same_browser(
    history, qtbot, monkeypatch, shortcut
):
    browser, db, active, _ = history
    browser.hide()
    workspace = SilverBarDialog(db)
    qtbot.addWidget(workspace)
    opened = []

    def choose(dialog):
        opened.append(dialog)
        dialog.selected_list_id = active.list_id
        dialog.done(QDialog.DialogCode.Accepted)
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(SilverBarHistoryDialog, "exec", choose)
    workspace.show()
    workspace.activateWindow()
    qtbot.waitUntil(workspace.isActiveWindow)
    qtbot.keyClick(
        workspace.weight_search_edit, shortcut, Qt.KeyboardModifier.ControlModifier
    )
    qtbot.waitUntil(lambda: workspace.current_list_id == active.list_id)
    assert len(opened) == 1
    workspace.close()


def test_copy_and_child_shortcuts_do_not_change_history(history, qtbot):
    dialog, _, _, issued = history
    open_issued(qtbot, dialog, issued)
    dialog.list_bars_table.selectRow(0)
    dialog.copy_selected_rows(dialog.list_bars_table)
    assert QApplication.clipboard().text().startswith("40.00\t98.50")
    child = QDialog(dialog)
    child.setModal(True)
    qtbot.addWidget(child)
    child.show()
    child.activateWindow()
    qtbot.keyClick(child, Qt.Key.Key_F, Qt.KeyboardModifier.ControlModifier)
    assert dialog.pages.currentIndex() == 1
    child.close()


def test_view_shortcut_during_print_does_not_desynchronize_filters(history, qtbot):
    dialog, _, _, issued = history
    open_issued(qtbot, dialog, issued)
    dialog._busy = True
    dialog._update_actions()
    qtbot.keyClick(
        dialog.list_bars_table, Qt.Key.Key_2, Qt.KeyboardModifier.ControlModifier
    )
    assert dialog.view_combo.currentIndex() == 0
    assert dialog.filters.currentIndex() == 0
    assert dialog.pages.currentIndex() == 1
    dialog._busy = False


def test_unified_history_screenshots(history, qtbot, qt_application_state):
    from silverestimate.ui.application_theme import apply_light_application_theme

    dialog, _, _, issued = history
    apply_light_application_theme(QApplication.instance())
    dialog.resize(1120, 760)
    QApplication.processEvents()
    # Header and filter rows sit above the table in the redesigned window.
    assert dialog.lists_table.height() > 560
    assert dialog.grab().save(str(Path(".pytest_cache/silver-bar-history-lists.png")))
    open_issued(qtbot, dialog, issued)
    assert dialog.grab().save(str(Path(".pytest_cache/silver-bar-history-issued.png")))
    dialog.back_to_results()
    dialog.view_combo.setCurrentIndex(1)
    qtbot.waitUntil(lambda: dialog.bars_model.rowCount() == 7)
    assert dialog.grab().save(str(Path(".pytest_cache/silver-bar-history-bars.png")))
    dialog.resize(760, 520)
    QApplication.processEvents()
    assert dialog.height() == 520
    # Narrow windows move the status chips to their own row.
    assert dialog.bars_table.height() > 280


def test_clear_filters_shows_only_while_a_filter_is_set(history, qtbot):
    dialog, *_ = history
    assert not dialog.clear_button.isVisible()

    dialog.list_state_combo.setCurrentText("Issued")
    qtbot.waitUntil(lambda: dialog.clear_button.isVisible())

    dialog.clear_filters()
    assert not dialog.clear_button.isVisible()
    assert dialog.list_state_combo.currentIndex() == 0


def test_bar_history_writes_voucher_and_note_like_the_workspace(history, qtbot):
    dialog, db, *_ = history
    dialog.view_combo.setCurrentIndex(1)
    qtbot.waitUntil(lambda: dialog.bars_model.rowCount() > 0 and not dialog._loading[1])

    assert dialog.bars_model.HEADERS[3] == "Purity (%)"
    texts = [
        dialog.bars_model.display_value(row, 1)
        for row in range(dialog.bars_model.rowCount())
    ]
    # "voucher · note", never "voucher (note)".
    assert all("(" not in text for text in texts)
