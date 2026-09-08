"""Real dialog/controller boundaries with encrypted inventory and worker ownership."""

import pytest
from PySide6.QtWidgets import QInputDialog, QMessageBox

from silverestimate.persistence.database_manager import DatabaseManager
from silverestimate.ui.silver_bar_management import SilverBarDialog
from tests.factories import estimate_totals, silver_bar_item


@pytest.fixture
def management(qtbot, tmp_path, settings_stub, monkeypatch):
    db = DatabaseManager(
        str(tmp_path / "inventory.db"), "test-pass", device_secret=b"C" * 32
    )
    assert db.add_item("BAR001", "Silver", 99, "WT", 0)
    bars = [
        silver_bar_item(
            line_key=f"bar-{i}",
            gross=weight,
            net_wt=weight,
            purity=99,
            fine=weight * 0.99,
        )
        for i, weight in enumerate([5, 8])
    ]
    assert db.save_estimate_atomic(
        "1", "2026-09-06", 100, [], bars, estimate_totals()
    ).success
    messages = []
    for name in ("information", "warning", "critical"):
        monkeypatch.setattr(QMessageBox, name, lambda *args: messages.append(args[2]))
    monkeypatch.setattr(
        QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.Yes
    )
    monkeypatch.setattr(
        QInputDialog, "getText", lambda *a, **k: ("Contract test", True)
    )
    dialog = SilverBarDialog(db)
    qtbot.addWidget(dialog)
    qtbot.waitUntil(lambda: dialog.available_bars_model.rowCount() == 2)
    try:
        yield dialog, db, messages
    finally:
        dialog.close()
        db.close()


def test_create_from_selection_and_transfer_use_real_collaborators(management, qtbot):
    dialog, db, messages = management
    dialog.available_bars_table.selectRow(0)
    bar_id = dialog.available_bars_model.bar_id_at(0)
    # These host names used to shadow the controller's own methods through HostProxy.
    dialog._selected_rows = lambda *a: []
    dialog._bar_ids_from_indexes = lambda *a: []
    dialog._create_list_from_selection()
    list_id = dialog.current_list_id
    assert list_id is not None
    qtbot.waitUntil(lambda: dialog.list_bars_model.rowCount() == 1)
    assert dialog.list_bars_model.bar_id_at(0) == bar_id
    row = db.conn.execute(
        "SELECT list_id,status FROM silver_bars WHERE bar_id=?", (bar_id,)
    ).fetchone()
    assert tuple(row) == (list_id, "Assigned")
    assert any("added 1 bar" in message for message in messages)
    dialog.list_bars_table.selectRow(0)
    dialog.remove_selected_from_list()
    qtbot.waitUntil(
        lambda: (
            dialog.list_bars_model.rowCount() == 0
            and dialog.available_bars_model.rowCount() == 2
        )
    )
    dialog.add_all_filtered_to_list()
    qtbot.waitUntil(lambda: dialog.list_bars_model.rowCount() == 2)
    dialog.mark_list_as_issued()
    assert (
        db.conn.execute(
            "SELECT COUNT(*) FROM silver_bars WHERE status='Issued'"
        ).fetchone()[0]
        == 2
    )
    assert db.get_silver_bar_list_details(list_id)["issued_date"]


def test_loader_shutdown_state_is_not_overridden_by_dialog(management):
    dialog, _db, _messages = management
    controller = dialog._load_controller
    dialog._load_shutdown = True
    assert not controller._load_shutdown
    controller._shutdown_loads()
    dialog._load_shutdown = False
    assert controller._load_shutdown
    assert controller._start_bars_load("available", {}) == 0
