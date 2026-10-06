import threading

import pytest
from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QInputDialog

from silverestimate.persistence.repository_results import (
    RepositoryFailureKind,
    RepositoryResult,
)
from silverestimate.persistence.silver_bars_snapshot_repository import (
    SilverBarsSnapshotRepository,
)
from silverestimate.ui.silver_bar_management import SilverBarDialog
from tests.silver_bar_workspace_support import seed_workspace_db


@pytest.fixture
def workspace(qtbot, tmp_path, settings_stub):
    db = seed_workspace_db(tmp_path)
    dialog = SilverBarDialog(db)
    qtbot.addWidget(dialog)
    dialog.show()
    dialog.activateWindow()
    qtbot.waitUntil(dialog.weight_search_edit.hasFocus)
    yield dialog, db
    dialog.done(0)
    db.close()


def add(qtbot, dialog, text="40", count=1):
    dialog.focus_weight()
    qtbot.keyClicks(dialog.weight_search_edit, text)
    qtbot.keyClick(dialog.weight_search_edit, Qt.Key.Key_Return)
    qtbot.waitUntil(lambda: dialog.list_bars_model.rowCount() == count)


def available_ids(dialog):
    return [
        dialog.suggestions_model.bar_id_at(row)
        for row in range(dialog.suggestions_model.rowCount())
    ]


def wait_for_available(qtbot, dialog, ids):
    qtbot.waitUntil(
        lambda: (
            dialog._load_controller.ready_prefix == ""
            and not dialog._load_controller.loading
            and available_ids(dialog) == ids
        )
    )


def test_opening_shows_available_bars_without_creating_a_list(workspace, qtbot):
    dialog, db = workspace
    wait_for_available(qtbot, dialog, [6, 1, 2, 3, 7, 5, 4])
    assert dialog.suggestions_panel.isVisible()
    assert dialog.weight_search_edit.text() == ""
    assert dialog.weight_search_edit.hasFocus()
    assert dialog.current_list_id is None
    assert db.get_silver_bar_lists() == []


def test_blank_input_supports_repeated_adds_and_clearing_restores_all(workspace, qtbot):
    dialog, db = workspace
    wait_for_available(qtbot, dialog, [6, 1, 2, 3, 7, 5, 4])
    qtbot.keyClick(dialog.weight_search_edit, Qt.Key.Key_Return)
    wait_for_available(qtbot, dialog, [1, 2, 3, 7, 5, 4])
    assert dialog.snapshot.bars[0]["bar_id"] == 6
    assert dialog.snapshot.fine_weight == 12.55
    qtbot.keyClick(dialog.weight_search_edit, Qt.Key.Key_Down)
    qtbot.keyClick(dialog.weight_search_edit, Qt.Key.Key_Return)
    wait_for_available(qtbot, dialog, [1, 3, 7, 5, 4])
    assert [bar["bar_id"] for bar in dialog.snapshot.bars] == [2, 6]
    assert len(db.get_silver_bar_lists()) == 1
    dialog.weight_search_edit.setText("40")
    qtbot.waitUntil(lambda: dialog._load_controller.ready_prefix == "40")
    assert available_ids(dialog) == [1, 3, 4]
    dialog.weight_search_edit.clear()
    wait_for_available(qtbot, dialog, [1, 3, 7, 5, 4])
    assert dialog.suggestions_panel.isVisible()


def test_fast_enter_adds_once_autosaves_and_restores_input_focus(workspace, qtbot):
    dialog, db = workspace
    assert dialog.current_list_id is None
    assert not db.get_silver_bar_lists()
    add(qtbot, dialog)
    assert dialog.weight_search_edit.text() == ""
    assert dialog.weight_search_edit.hasFocus()
    assert not dialog.suggestions_panel.isVisible()
    assert dialog.snapshot.bars[0]["bar_id"] == 1
    assert len(db.get_silver_bar_lists()) == 1
    qtbot.keyClick(dialog.weight_search_edit, Qt.Key.Key_Return)
    assert dialog.list_bars_model.rowCount() == 1
    wait_for_available(qtbot, dialog, [6, 2, 3, 7, 5, 4])
    assert dialog.suggestions_panel.isVisible()


def test_arrows_disambiguate_weight_and_tab_delete_release_bar(workspace, qtbot):
    dialog, db = workspace
    qtbot.keyClicks(dialog.weight_search_edit, "40")
    qtbot.waitUntil(lambda: dialog.suggestions_model.rowCount() == 4)
    qtbot.keyClick(dialog.weight_search_edit, Qt.Key.Key_Down)
    qtbot.keyClick(dialog.weight_search_edit, Qt.Key.Key_Return)
    assert dialog.snapshot.bars[0]["bar_id"] == 2
    qtbot.keyClick(dialog.weight_search_edit, Qt.Key.Key_Tab)
    assert dialog.list_bars_table.hasFocus()
    qtbot.keyClick(dialog.list_bars_table, Qt.Key.Key_Delete)
    assert not dialog.snapshot.bars
    assert (
        db.conn.execute("SELECT status FROM silver_bars WHERE bar_id=2").fetchone()[0]
        == "In Stock"
    )
    qtbot.keyClick(
        dialog.list_bars_table, Qt.Key.Key_F, Qt.KeyboardModifier.ControlModifier
    )
    assert dialog.weight_search_edit.hasFocus()
    wait_for_available(qtbot, dialog, [6, 1, 2, 3, 7, 5, 4])
    assert dialog.suggestions_panel.isVisible()


def test_delete_in_weight_input_never_removes_list_row(workspace, qtbot):
    dialog, _ = workspace
    add(qtbot, dialog)
    dialog.weight_search_edit.setText("85")
    dialog.weight_search_edit.selectAll()
    qtbot.keyClick(dialog.weight_search_edit, Qt.Key.Key_Delete)
    assert dialog.list_bars_model.rowCount() == 1
    assert dialog.weight_search_edit.text() == ""


def test_new_list_starts_empty_and_saved_list_reopens(workspace, qtbot):
    dialog, db = workspace
    add(qtbot, dialog, "10")
    list_id = dialog.current_list_id
    qtbot.keyClick(
        dialog.weight_search_edit, Qt.Key.Key_N, Qt.KeyboardModifier.ControlModifier
    )
    assert dialog.current_list_id is None
    assert len(db.get_silver_bar_lists()) == 1
    wait_for_available(qtbot, dialog, [1, 2, 3, 7, 5, 4])
    dialog.open_list(list_id)
    qtbot.waitUntil(lambda: dialog.snapshot is not None)
    assert dialog.snapshot.fine_weight == 12.55
    assert dialog.weight_search_edit.hasFocus()
    wait_for_available(qtbot, dialog, [1, 2, 3, 7, 5, 4])


def test_stale_search_cannot_add_previous_weight(workspace, qtbot):
    dialog, _ = workspace
    dialog.weight_search_edit.setText("40")
    qtbot.waitUntil(lambda: dialog.suggestions_model.rowCount() == 4)
    dialog.weight_search_edit.setText("85")
    qtbot.keyClick(dialog.weight_search_edit, Qt.Key.Key_Return)
    qtbot.waitUntil(lambda: dialog.snapshot is not None)
    assert dialog.snapshot.bars[0]["weight"] == 85.25


def test_error_keeps_input_and_does_not_create_list(workspace, qtbot, monkeypatch):
    dialog, db = workspace
    monkeypatch.setattr(
        db,
        "add_bars_to_list",
        lambda *a: RepositoryResult.failed(
            RepositoryFailureKind.STORAGE, "Disk unavailable"
        ),
    )
    dialog.weight_search_edit.setText("40")
    qtbot.keyClick(dialog.weight_search_edit, Qt.Key.Key_Return)
    qtbot.waitUntil(lambda: "Disk unavailable" in dialog.status_label.text())
    assert dialog.weight_search_edit.text() == "40"
    assert dialog.current_list_id is None
    assert not db.get_silver_bar_lists()


def test_invalid_and_unmatched_input_do_not_add(workspace, qtbot):
    dialog, _ = workspace
    for text in ("nan", "-10", "%", "1000"):
        dialog.weight_search_edit.setText(text)
        qtbot.keyClick(dialog.weight_search_edit, Qt.Key.Key_Return)
    qtbot.waitUntil(lambda: "No available bars" in dialog.status_label.text())
    assert dialog.current_list_id is None


@pytest.mark.parametrize("prefix", ["", "40"])
def test_auto_repeated_enter_never_adds_another_bar(workspace, qtbot, prefix):
    dialog, _ = workspace
    dialog.weight_search_edit.setText(prefix)
    qtbot.waitUntil(lambda: dialog._load_controller.ready_prefix == prefix)
    repeat = QKeyEvent(
        QEvent.Type.KeyPress,
        Qt.Key.Key_Return,
        Qt.KeyboardModifier.NoModifier,
        "",
        True,
    )
    assert dialog.eventFilter(dialog.weight_search_edit, repeat)
    assert dialog.snapshot is None


def test_escape_dismisses_then_clears_then_closes(workspace, qtbot):
    dialog, _ = workspace
    dialog.weight_search_edit.setText("40")
    qtbot.waitUntil(lambda: dialog.suggestions_panel.isVisible())
    qtbot.keyClick(dialog.weight_search_edit, Qt.Key.Key_Escape)
    assert not dialog.suggestions_panel.isVisible()
    assert dialog.isVisible()
    qtbot.keyClick(dialog.weight_search_edit, Qt.Key.Key_Escape)
    assert dialog.weight_search_edit.text() == ""
    qtbot.wait(150)
    assert not dialog.suggestions_panel.isVisible()
    qtbot.keyClick(dialog.weight_search_edit, Qt.Key.Key_Escape)
    assert not dialog.isVisible()
    assert dialog._load_controller.shutdown_called


def test_note_edit_saves_and_invalidates_print_confirmation(
    workspace, qtbot, monkeypatch
):
    dialog, _ = workspace
    add(qtbot, dialog)
    dialog._list_print_controller.printed = dialog.snapshot
    monkeypatch.setattr(QInputDialog, "getText", lambda *a: ("Dispatch A", True))
    dialog.edit_list_note()
    assert dialog.snapshot.details["list_note"] == "Dispatch A"
    assert dialog._list_print_controller.printed is None


@pytest.mark.parametrize("prefix", ["", "4"])
def test_suggestion_paging_works_from_arrow_key(workspace, qtbot, prefix):
    dialog, db = workspace
    for i in range(55):
        db.silver_bar_command_repo.add_silver_bar("1", 400 + i, 99)
    dialog.weight_search_edit.setText(prefix)
    dialog.focus_weight()
    qtbot.waitUntil(lambda: dialog.suggestions_model.rowCount() == 50)
    dialog.suggestions_table.selectRow(49)
    qtbot.keyClick(dialog.weight_search_edit, Qt.Key.Key_Down)
    qtbot.waitUntil(lambda: dialog.suggestions_model.rowCount() > 50)
    assert dialog.suggestions_table.currentIndex().row() == 50
    chosen = dialog.suggestions_model.bar_id_at(50)
    qtbot.keyClick(dialog.weight_search_edit, Qt.Key.Key_Return)
    assert dialog.snapshot.bars[0]["bar_id"] == chosen


def test_escape_dismisses_blank_browsing_until_explicit_reopen(workspace, qtbot):
    dialog, _ = workspace
    wait_for_available(qtbot, dialog, [6, 1, 2, 3, 7, 5, 4])
    qtbot.keyClick(dialog.weight_search_edit, Qt.Key.Key_Escape)
    qtbot.keyClick(dialog.weight_search_edit, Qt.Key.Key_Return)
    qtbot.wait(150)
    assert not dialog.suggestions_panel.isVisible()
    assert dialog.current_list_id is None
    qtbot.keyClick(
        dialog.weight_search_edit, Qt.Key.Key_F, Qt.KeyboardModifier.ControlModifier
    )
    wait_for_available(qtbot, dialog, [6, 1, 2, 3, 7, 5, 4])
    assert dialog.suggestions_panel.isVisible()


def test_empty_inventory_is_distinct_from_unmatched_filter(workspace, qtbot):
    dialog, db = workspace
    db.add_bars_to_list(list(range(1, 8))).unwrap()
    dialog.focus_weight()
    qtbot.waitUntil(lambda: dialog.status_label.text() == "No available bars.")
    assert not dialog.suggestions_panel.isVisible()
    qtbot.keyClick(dialog.weight_search_edit, Qt.Key.Key_Return)
    assert dialog.current_list_id is None
    dialog.weight_search_edit.setText("40")
    qtbot.waitUntil(lambda: "match this weight" in dialog.status_label.text())


@pytest.mark.parametrize("action", ["tab", "escape", "filter"])
def test_delayed_blank_results_cannot_reopen_or_add_stale_bar(
    workspace, qtbot, monkeypatch, action
):
    dialog, _ = workspace
    wait_for_available(qtbot, dialog, [6, 1, 2, 3, 7, 5, 4])
    started, release, finished = threading.Event(), threading.Event(), threading.Event()
    original = SilverBarsSnapshotRepository.search_weight_prefix

    def delayed(repo, prefix, **kwargs):
        page = original(repo, prefix, **kwargs)
        if prefix == "":
            started.set()
            release.wait(5)
            finished.set()
        return page

    monkeypatch.setattr(SilverBarsSnapshotRepository, "search_weight_prefix", delayed)
    dialog.focus_weight()
    try:
        qtbot.waitUntil(started.is_set)
        qtbot.keyClick(dialog.weight_search_edit, Qt.Key.Key_Return)
        assert dialog.current_list_id is None
        if action == "filter":
            dialog.weight_search_edit.setText("85")
            qtbot.keyClick(dialog.weight_search_edit, Qt.Key.Key_Return)
        else:
            qtbot.keyClick(
                dialog.weight_search_edit,
                Qt.Key.Key_Tab if action == "tab" else Qt.Key.Key_Escape,
            )
        release.set()
        qtbot.waitUntil(finished.is_set)
        if action == "filter":
            qtbot.waitUntil(lambda: dialog.snapshot is not None)
            assert dialog.snapshot.bars[0]["weight"] == 85.25
        else:
            qtbot.wait(150)
            assert not dialog.suggestions_panel.isVisible()
            assert dialog.current_list_id is None
    finally:
        release.set()


def test_blank_search_failure_can_retry_without_typing(workspace, qtbot, monkeypatch):
    dialog, _ = workspace
    wait_for_available(qtbot, dialog, [6, 1, 2, 3, 7, 5, 4])
    original = SilverBarsSnapshotRepository.search_weight_prefix

    def failed(*args, **kwargs):
        raise RuntimeError("Read failed")

    monkeypatch.setattr(SilverBarsSnapshotRepository, "search_weight_prefix", failed)
    dialog.focus_weight()
    qtbot.waitUntil(lambda: "Read failed" in dialog.status_label.text())
    assert dialog.current_list_id is None
    assert not dialog.suggestions_panel.isVisible()
    monkeypatch.setattr(SilverBarsSnapshotRepository, "search_weight_prefix", original)
    qtbot.keyClick(
        dialog.weight_search_edit, Qt.Key.Key_F, Qt.KeyboardModifier.ControlModifier
    )
    wait_for_available(qtbot, dialog, [6, 1, 2, 3, 7, 5, 4])
    assert dialog.suggestions_panel.isVisible()
    assert not dialog.status_label.property("error")
    assert "Read failed" not in dialog.status_label.text()


def test_failure_can_retry_with_same_input_and_no_mouse(workspace, qtbot, monkeypatch):
    dialog, db = workspace
    original = db.add_bars_to_list
    monkeypatch.setattr(
        db,
        "add_bars_to_list",
        lambda *a: RepositoryResult.failed(RepositoryFailureKind.STORAGE, "Try again"),
    )
    dialog.weight_search_edit.setText("40")
    qtbot.keyClick(dialog.weight_search_edit, Qt.Key.Key_Return)
    qtbot.waitUntil(lambda: "Try again" in dialog.status_label.text())
    monkeypatch.setattr(db, "add_bars_to_list", original)
    qtbot.keyClick(dialog.weight_search_edit, Qt.Key.Key_Return)
    qtbot.waitUntil(lambda: dialog.snapshot is not None)
    assert dialog.snapshot.bars[0]["weight"] == 40


def test_keyboard_workspace_layout(workspace, qtbot, qt_application_state):
    from pathlib import Path

    from PySide6.QtWidgets import QApplication

    from silverestimate.ui.application_theme import apply_light_application_theme

    dialog, db = workspace
    apply_light_application_theme(QApplication.instance())
    dialog.apply_snapshot(
        db.add_bars_to_list([5, 6, 7], note="Morning dispatch").unwrap()
    )
    dialog.weight_search_edit.setText("40")
    qtbot.waitUntil(lambda: dialog.suggestions_panel.isVisible())
    for width, height in ((1080, 760), (760, 520)):
        dialog.resize(width, height)
        QApplication.processEvents()
        assert (
            dialog.print_list_button.mapTo(
                dialog, dialog.print_list_button.rect().bottomRight()
            ).y()
            < dialog.height()
        )
        assert (
            dialog.print_list_button.fontMetrics().horizontalAdvance(
                dialog.print_list_button.text()
            )
            < dialog.print_list_button.width()
        )
        assert dialog.list_bars_table.height() >= height * 0.8
        assert dialog.list_bars_table.horizontalScrollBar().maximum() == 0
        if width == 1080:
            image_path = Path(".pytest_cache/silver-bar-keyboard-suggestions.png")
            assert dialog.grab().save(str(image_path))
    dialog.resize(1080, 760)
    dialog.weight_search_edit.clear()
    dialog.set_status("Enter Add · Tab List · Delete Remove · F1 Help")
    QApplication.processEvents()
    assert dialog.grab().save(str(Path(".pytest_cache/silver-bar-keyboard.png")))
    wait_for_available(qtbot, dialog, [1, 2, 3, 4])
    assert dialog.suggestions_panel.isVisible()
    assert dialog.grab().save(str(Path(".pytest_cache/silver-bar-default-bars.png")))
