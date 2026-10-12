"""Complete print/issue and keyboard workspace flows against encrypted inventory."""

from types import SimpleNamespace

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog

from silverestimate.domain.silver_bar_workspace import BarListSnapshot
from silverestimate.persistence.repository_results import (
    RepositoryFailureKind,
    RepositoryResult,
)
from silverestimate.ui.print_manager import PrintManager
from silverestimate.ui.print_preview_output import PrintOutputOutcome, PrintOutputStatus
from silverestimate.ui.silver_bar_management import SilverBarWidget
from tests.silver_bar_workspace_support import bar_list_count, seed_workspace_db


@pytest.fixture
def workspace(qtbot, tmp_path, settings_stub):
    db = seed_workspace_db(tmp_path)
    dialog = SilverBarWidget(db)
    qtbot.addWidget(dialog)
    dialog.show()
    dialog.activateWindow()
    dialog.apply_snapshot(db.add_bars_to_list([1, 6]).unwrap())
    yield dialog, db
    dialog.shutdown()
    db.close()


def test_printing_issues_and_starts_fresh_without_confirmation(
    workspace, qtbot, monkeypatch
):
    dialog, db = workspace
    list_id = dialog.current_list_id
    previews = []

    def print_payload(_self, payload):
        previews.append(payload)
        return PrintOutputOutcome(PrintOutputStatus.SUCCESS)

    monkeypatch.setattr(PrintManager, "quick_print", print_payload)
    # Ctrl+P and File > Print reach this through the main window; see
    # tests/ui/test_silver_bar_screen.py.
    dialog.print_selected_list()
    qtbot.waitUntil(lambda: dialog.current_list_id is None)
    qtbot.waitUntil(dialog.weight_search_edit.hasFocus)
    issued = db.get_silver_bar_list_snapshot(list_id)
    assert issued.issued
    assert len(previews[0].document.bars) == 2
    assert previews[0].document.bars[1].purity == 125.5
    assert bar_list_count(db) == 1
    qtbot.waitUntil(lambda: dialog._load_controller.ready_prefix == "")
    assert dialog.suggestions_panel.isVisible()
    available = {
        dialog.suggestions_model.bar_id_at(row)
        for row in range(dialog.suggestions_model.rowCount())
    }
    assert available == {2, 3, 4, 5, 7}


@pytest.mark.parametrize(
    "status",
    [
        PrintOutputStatus.CANCELLED,
        PrintOutputStatus.FAILED,
        PrintOutputStatus.VALIDATION_FAILED,
    ],
)
def test_cancelled_or_failed_print_keeps_current_list(
    workspace, qtbot, monkeypatch, status
):
    dialog, db = workspace
    list_id = dialog.current_list_id
    monkeypatch.setattr(
        PrintManager, "quick_print", lambda *a, **k: PrintOutputOutcome(status)
    )
    dialog.print_selected_list()
    qtbot.waitUntil(lambda: not dialog._busy)
    assert dialog.current_list_id == list_id
    assert not db.get_silver_bar_list_snapshot(list_id).issued


def test_storage_failure_retries_with_ctrl_p_without_reprinting(
    workspace, qtbot, monkeypatch
):
    dialog, db = workspace
    printed = []
    monkeypatch.setattr(
        PrintManager,
        "quick_print",
        lambda *a: printed.append(a) or PrintOutputOutcome(PrintOutputStatus.SUCCESS),
    )
    original = db.issue_printed_list
    monkeypatch.setattr(
        db,
        "issue_printed_list",
        lambda *a: RepositoryResult.failed(
            RepositoryFailureKind.STORAGE, "Busy database"
        ),
    )
    dialog.print_selected_list()
    qtbot.waitUntil(lambda: dialog.retry_issue_button.isVisible())
    assert dialog._list_print_controller.printed is not None
    assert "without printing again" in dialog.status_label.text()
    monkeypatch.setattr(db, "issue_printed_list", original)
    dialog.print_selected_list()
    assert dialog.current_list_id is None
    assert len(printed) == 1


def test_pdf_only_preview_keeps_list_active(workspace, qtbot, monkeypatch):
    dialog, db = workspace
    list_id = dialog.current_list_id
    monkeypatch.setattr(
        PrintManager,
        "show_preview",
        lambda *a, **k: PrintOutputOutcome(PrintOutputStatus.CANCELLED),
    )
    dialog.preview_selected_list()
    qtbot.waitUntil(lambda: not dialog._busy)
    assert dialog.current_list_id == list_id
    assert not db.get_silver_bar_list_snapshot(list_id).issued


def test_changed_list_rejects_old_print_and_reprint_of_issued_list_does_not_issue_again(
    workspace, monkeypatch
):
    dialog, db = workspace
    controller = dialog._list_print_controller
    controller.printed = dialog.snapshot
    db.remove_list_bars(dialog.current_list_id, [1]).unwrap()
    controller.complete_issue()
    assert controller.printed is None
    assert "changed after printing" in dialog.status_label.text()
    current = db.get_silver_bar_list_snapshot(dialog.current_list_id)
    issued = db.issue_printed_list(current.list_id, current.signature).unwrap()
    dialog.apply_snapshot(issued)
    manager = SimpleNamespace(
        quick_print=lambda *a, **k: PrintOutputOutcome(PrintOutputStatus.SUCCESS)
    )
    controller._preview_ready(manager, None, issued)
    assert dialog.current_list_id == issued.list_id
    assert "reprinted" in dialog.status_label.text()
    assert not dialog.weight_search_edit.isEnabled()


def test_totals_and_print_use_every_bar_beyond_display_page(workspace, monkeypatch):
    dialog, _ = workspace
    original = dialog.snapshot
    bars = tuple({**original.bars[1], "bar_id": i} for i in range(1, 1602))
    snapshot = BarListSnapshot(original.details, bars)
    dialog.apply_snapshot(snapshot)
    assert dialog.list_bars_model.rowCount() == 1500
    assert "1601 bars" in dialog.list_totals_label.text()
    assert snapshot.fine_weight == 20092.55
    assert dialog.load_more_button.isVisible()
    dialog.load_more_list_rows()
    assert dialog.list_bars_model.rowCount() == 1601
    assert not dialog.load_more_button.isVisible()


def test_optimizer_opens_a_separate_saved_list(workspace):
    dialog, db = workspace
    old_id = dialog.current_list_id

    class AcceptedTarget:
        def __init__(self, _parent):
            self.min_target, self.max_target = 39.39, 39.41
            self.list_name = "Optimized"
            self.optimization_type = "min_bars"

        def exec(self):
            return QDialog.DialogCode.Accepted

        def deleteLater(self):
            pass

    dialog._optimization_controller.generate_optimal_list(AcceptedTarget)
    assert dialog.current_list_id != old_id
    assert dialog.snapshot.details["list_note"] == "Optimized"
    assert dialog.snapshot.bars[0]["bar_id"] == 2
    assert bar_list_count(db) == 2


def test_modal_child_shortcuts_do_not_change_parent_list(workspace, qtbot):
    dialog, _ = workspace
    list_id = dialog.current_list_id
    child = QDialog(dialog)
    child.setModal(True)
    qtbot.addWidget(child)
    child.show()
    child.activateWindow()
    qtbot.keyClick(child, Qt.Key.Key_N, Qt.KeyboardModifier.ControlModifier)
    assert dialog.current_list_id == list_id
    child.reject()


def test_an_issued_list_is_a_centred_column_on_a_wide_screen(workspace, qtbot):
    dialog, db = workspace
    dialog.resize(1600, 800)
    dialog.show()
    qtbot.wait(40)

    # Active: two panes share the screen.
    assert dialog.available_card.isVisible()
    assert dialog.list_card.maximumWidth() > 1000
    assert dialog.list_card.width() < 1000

    current = db.get_silver_bar_list_snapshot(dialog.current_list_id)
    dialog.apply_snapshot(
        db.issue_printed_list(current.list_id, current.signature).unwrap()
    )
    qtbot.wait(40)

    # Issued: one column, no wider than 1000 px, with equal space either side.
    assert not dialog.available_card.isVisible()
    assert dialog.issued_banner.isVisible()
    for widget in (dialog.list_card, dialog.issued_banner):
        assert widget.width() <= 1000
        assert widget.width() >= 900
        left = widget.mapTo(dialog, widget.rect().topLeft()).x()
        right = dialog.width() - (left + widget.width())
        assert abs(left - right) <= 2

    # A new list gives the screen back to the two panes.
    dialog.create_new_list()
    qtbot.wait(40)
    assert dialog.available_card.isVisible()
    assert dialog.list_card.maximumWidth() > 1000
    assert dialog.list_card.width() < 1000
