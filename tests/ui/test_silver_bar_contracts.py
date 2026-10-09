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
from silverestimate.ui.silver_bar_management import SilverBarDialog
from tests.silver_bar_workspace_support import seed_workspace_db


@pytest.fixture
def workspace(qtbot, tmp_path, settings_stub):
    db = seed_workspace_db(tmp_path)
    dialog = SilverBarDialog(db)
    qtbot.addWidget(dialog)
    dialog.show()
    dialog.activateWindow()
    dialog.apply_snapshot(db.add_bars_to_list([1, 6]).unwrap())
    yield dialog, db
    dialog.done(0)
    db.close()


def test_ctrl_p_prints_issues_and_starts_fresh_without_confirmation(
    workspace, qtbot, monkeypatch
):
    dialog, db = workspace
    list_id = dialog.current_list_id
    previews = []

    def print_payload(_self, payload):
        previews.append(payload)
        return PrintOutputOutcome(PrintOutputStatus.SUCCESS)

    monkeypatch.setattr(PrintManager, "quick_print", print_payload)
    qtbot.keyClick(
        dialog.weight_search_edit, Qt.Key.Key_P, Qt.KeyboardModifier.ControlModifier
    )
    qtbot.waitUntil(lambda: dialog.current_list_id is None)
    qtbot.waitUntil(dialog.weight_search_edit.hasFocus)
    issued = db.get_silver_bar_list_snapshot(list_id)
    assert issued.issued
    assert len(previews[0].document.bars) == 2
    assert previews[0].document.bars[1].purity == 125.5
    assert len(db.get_silver_bar_lists()) == 1
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
    assert len(db.get_silver_bar_lists()) == 2


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
