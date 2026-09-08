"""Exercise the real nested event loop, worker lifetime and backup feedback."""

import threading
from types import SimpleNamespace

import pytest
from PySide6.QtCore import QTimer

from silverestimate.infrastructure.settings import SettingsKey, get_app_settings
from silverestimate.ui.maintenance_progress import MaintenanceProgressDialog
from silverestimate.ui.settings_data_page import (
    DataActionResult,
    DataManagementActions,
    DataManagementPage,
    SettingsDataController,
)


def test_progress_keeps_ui_responsive_and_cannot_close_early(qtbot):
    release = threading.Event()
    started = threading.Event()
    worker_ids = []
    ticks = []
    owner = threading.get_ident()

    def work():
        worker_ids.append(threading.get_ident())
        started.set()
        assert release.wait(5)
        return "completed"

    dialog = MaintenanceProgressDialog(work, "Test")
    qtbot.addWidget(dialog)
    timer = QTimer(dialog)

    def heartbeat():
        if started.is_set():
            ticks.append(1)
            dialog.reject()
            dialog.close()
            assert dialog.isVisible()
            if len(ticks) >= 3:
                release.set()

    timer.timeout.connect(heartbeat)
    timer.start(10)
    try:
        assert dialog.run_operation() == "completed"
    finally:
        release.set()
        timer.stop()
    assert len(ticks) >= 3
    assert worker_ids[0] != owner
    assert not dialog._worker.isRunning()


def test_worker_error_returns_only_after_thread_stops(qtbot):
    def fail():
        raise OSError("disk failure")

    dialog = MaintenanceProgressDialog(fail, "Test")
    qtbot.addWidget(dialog)
    with pytest.raises(OSError, match="disk failure"):
        dialog.run_operation()
    assert not dialog._worker.isRunning()


def make_page(qtbot, database):
    actions = DataManagementActions(*(lambda: None for _ in range(4)))
    owner = threading.get_ident()

    def provider():
        assert threading.get_ident() == owner
        return database

    page = DataManagementPage(SettingsDataController(provider, actions))
    qtbot.addWidget(page)
    return page


@pytest.mark.parametrize("succeeded", [True, False])
def test_backup_timestamp_changes_only_after_success(
    qtbot, settings_stub, monkeypatch, succeeded
):
    del settings_stub
    settings = get_app_settings()
    settings.set(SettingsKey.BACKUP_LAST_VALIDATED_UTC, "previous")
    calls = []

    def backup(path):
        calls.append((path, threading.get_ident()))
        if not succeeded:
            raise OSError("disk full")
        return SimpleNamespace(message="Validated", path=path)

    page = make_page(qtbot, SimpleNamespace(create_encrypted_backup=backup))
    module = "silverestimate.ui.settings_data_page"
    monkeypatch.setattr(
        f"{module}.QFileDialog.getSaveFileName", lambda *a: ("backup", "")
    )
    monkeypatch.setattr(f"{module}.QMessageBox.information", lambda *a: None)
    monkeypatch.setattr(f"{module}.QMessageBox.critical", lambda *a: None)
    page._create_database_backup()
    assert calls[0][0] == "backup.sedbbackup"
    assert calls[0][1] != threading.get_ident()
    stamp = settings.get_text(SettingsKey.BACKUP_LAST_VALIDATED_UTC)
    assert (stamp != "previous") is succeeded
    assert stamp in page.backup_status_label.text()
    assert not page._maintenance_active


def test_page_rejects_duplicate_maintenance(qtbot, settings_stub):
    del settings_stub
    page = make_page(qtbot, None)
    page._maintenance_active = True
    result = page._run_maintenance(lambda: pytest.fail("must not run"), "Duplicate")
    assert not result.succeeded
    assert "already active" in result.message


def test_controller_does_not_report_failed_maintenance_as_success():
    outcome = SimpleNamespace(
        status=SimpleNamespace(name="RECOVERY_REQUIRED"), message="Failed"
    )
    result = SettingsDataController._maintenance_result(outcome, "backup")
    assert isinstance(result, DataActionResult)
    assert not result.succeeded


def test_real_settings_backup_restore_round_trip(
    qtbot, settings_stub, tmp_path, monkeypatch
):
    from silverestimate.persistence.database_manager import DatabaseManager

    del settings_stub
    path = tmp_path / "live.db"
    backup = tmp_path / "backup.sedbbackup"
    db = DatabaseManager(str(path), "password", device_secret=b"S" * 32)
    page = make_page(qtbot, db)
    module = "silverestimate.ui.settings_data_page"
    messages = []
    monkeypatch.setattr(
        f"{module}.QFileDialog.getSaveFileName", lambda *a: (str(backup), "")
    )
    monkeypatch.setattr(
        f"{module}.QFileDialog.getOpenFileName", lambda *a: (str(backup), "")
    )
    monkeypatch.setattr(f"{module}.QInputDialog.getText", lambda *a: ("password", True))
    monkeypatch.setattr(
        f"{module}.QMessageBox.information", lambda *a: messages.append(a[1])
    )
    monkeypatch.setattr(
        f"{module}.QMessageBox.critical", lambda *a: pytest.fail(str(a))
    )
    try:
        db.conn.execute("INSERT INTO items(code,name) VALUES('A','Before')")
        db.conn.commit()
        page._create_database_backup()
        db.conn.execute("UPDATE items SET name='After'")
        db.conn.commit()
        page._stage_database_restore()
        assert db.conn.execute("SELECT name FROM items").fetchone()[0] == "After"
        assert messages == ["Encrypted Backup Created", "Restore Staged"]
    finally:
        db.close()
    reopened = DatabaseManager(str(path), "password", device_secret=b"S" * 32)
    try:
        assert reopened.conn.execute("SELECT name FROM items").fetchone()[0] == "Before"
    finally:
        reopened.close()
