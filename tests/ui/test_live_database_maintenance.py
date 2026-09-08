"""Real SQLCipher maintenance through the responsive Qt owner/worker handoff."""

import threading
from types import SimpleNamespace

import pytest
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QMessageBox, QWidget

from silverestimate.persistence.database_driver import (
    DatabaseAuthenticationError,
    MaintenanceBusyError,
)
from silverestimate.persistence.database_manager import DatabaseManager
from silverestimate.security import credential_store
from silverestimate.services import main_commands
from silverestimate.services.item_catalog_transfer import export_item_catalog_rows
from silverestimate.services.password_change_service import PasswordChangeStatus
from silverestimate.ui.database_maintenance import run_database_maintenance
from silverestimate.ui.settings_security_page import (
    SecuritySettingsPage,
    SettingsSecurityController,
)

SECRET = b"M" * 32


@pytest.fixture
def database(tmp_path):
    db = DatabaseManager(
        str(tmp_path / "live.db"), "old-password", device_secret=SECRET
    )
    db.conn.execute("INSERT INTO items(code,name) VALUES('OLD','Retained item')")
    db.conn.commit()
    yield db
    db.close()


def test_waiting_for_readers_and_worker_operation_keep_ui_alive(qtbot, database):
    owner = threading.get_ident()
    reader = database.open_read_connection()
    release = threading.Event()
    started = threading.Event()
    ticks = []
    timer = QTimer()

    def tick():
        ticks.append(1)
        if len(ticks) == 3:
            reader.close()
        if started.is_set():
            assert database.conn is None
            assert database._broker.maintenance_active
            with pytest.raises(MaintenanceBusyError):
                database.open_read_connection()
            release.set()

    def operation(worker):
        assert threading.get_ident() != owner
        assert worker is not database and worker._session.is_owner()
        started.set()
        assert release.wait(5)
        worker.conn.execute("INSERT INTO items(code,name) VALUES('NEW','Imported')")
        worker.conn.commit()
        return "complete"

    timer.timeout.connect(tick)
    timer.start(10)
    try:
        assert run_database_maintenance(database, operation, "Test") == "complete"
    finally:
        release.set()
        timer.stop()
        reader.close()
    assert len(ticks) >= 4
    assert database._session.is_owner()
    assert not database._broker.maintenance_active
    assert (
        database.conn.execute("SELECT name FROM items WHERE code='NEW'").fetchone()[0]
        == "Imported"
    )


@pytest.mark.parametrize("raises", [True, False])
def test_unfinished_worker_transaction_rolls_back_and_owner_resumes(
    qtbot, database, raises
):
    def operation(worker):
        worker.conn.execute("INSERT INTO items(code,name) VALUES('BAD','Uncommitted')")
        if raises:
            raise ValueError("injected failure")

    with pytest.raises((ValueError, RuntimeError)):
        run_database_maintenance(database, operation, "Test failure")
    assert (
        database.conn.execute("SELECT COUNT(*) FROM items WHERE code='BAD'").fetchone()[
            0
        ]
        == 0
    )
    assert database._session.is_owner()
    assert not database._broker.maintenance_active


def test_owner_transaction_and_duplicate_jobs_are_rejected(database):
    database.conn.execute("INSERT INTO items(code,name) VALUES('PENDING','Pending')")
    with pytest.raises(RuntimeError, match="transaction"):
        database.create_maintenance_job()
    assert database.conn.in_transaction
    database.conn.rollback()
    job = database.create_maintenance_job()
    try:
        with pytest.raises(MaintenanceBusyError):
            database.create_maintenance_job()
    finally:
        job.resume_owner()
    assert not database._broker.maintenance_active


def test_reader_drain_failure_keeps_original_writer(qtbot, database, monkeypatch):
    original = database.conn

    def fail(**kwargs):
        raise MaintenanceBusyError("injected drain timeout")

    monkeypatch.setattr(database._broker, "drain_readers", fail)
    with pytest.raises(MaintenanceBusyError, match="timeout"):
        run_database_maintenance(
            database, lambda worker: pytest.fail("must not run"), "Test"
        )
    assert database.conn is original
    assert not database._broker.maintenance_active
    assert database.conn.execute("SELECT 1").fetchone()[0] == 1


@pytest.mark.parametrize(
    "mode",
    ["success", "wrong_password", "rollback", "preparation_error", "credential_error"],
)
def test_real_password_page_rekey_failures_and_credential_recovery(
    qtbot, database, settings_stub, monkeypatch, mode
):
    del settings_stub
    owner = threading.get_ident()
    calls = []
    credential_store.set_password_hash("main", "old-main-hash")
    credential_store.set_password_hash("backup", "old-backup-hash")

    def verify(stored, provided, **kwargs):
        calls.append(threading.get_ident())
        return provided == "old-password"

    monkeypatch.setattr("silverestimate.services.auth_service.verify_password", verify)
    monkeypatch.setattr(
        "silverestimate.services.auth_service.hash_password",
        lambda value, **kw: "hash-" + value,
    )
    if mode == "rollback":
        from silverestimate.persistence import database_manager as storage

        replace = storage.os.replace

        def fail_target(source, target):
            if str(source).endswith(".rekey.target"):
                raise OSError("injected activation failure")
            return replace(source, target)

        monkeypatch.setattr(storage.os, "replace", fail_target)
    elif mode == "preparation_error":

        def fail_validation(*args, **kwargs):
            raise ValueError("injected export validation failure")

        monkeypatch.setattr(DatabaseManager, "_validate_external", fail_validation)
    elif mode == "credential_error":
        save = credential_store.set_password_hash

        def fail_promotion(kind, value, **kwargs):
            if kind == "main":
                raise RuntimeError("injected credential promotion failure")
            save(kind, value, **kwargs)

        monkeypatch.setattr(credential_store, "set_password_hash", fail_promotion)

    def provider():
        assert threading.get_ident() == owner
        return database

    page = SecuritySettingsPage(SettingsSecurityController(provider))
    qtbot.addWidget(page)
    messages = []

    def record(*args):
        assert threading.get_ident() == owner
        assert database._session.is_owner()
        messages.append(args[1])

    for method in ("information", "warning", "critical"):
        monkeypatch.setattr(QMessageBox, method, record)
    page.current_password_input.setText(
        "wrong" if mode == "wrong_password" else "old-password"
    )
    page.new_password_input.setText("new-password")
    page.confirm_new_password_input.setText("new-password")
    page.new_secondary_password_input.setText("new-recovery")
    page.confirm_new_secondary_password_input.setText("new-recovery")
    result = page.change_passwords()
    assert calls and set(calls) != {owner}
    assert page.change_password_button.isEnabled() and not page._maintenance_active
    assert (
        database.conn.execute("SELECT name FROM items").fetchone()[0] == "Retained item"
    )
    assert not database._broker.maintenance_active
    with database.open_read_connection() as reader:
        assert reader.execute("SELECT name FROM items").fetchone()[0] == "Retained item"
    new_key_active = mode in {"success", "credential_error"}
    expected_status = {
        "success": PasswordChangeStatus.SUCCESS,
        "wrong_password": PasswordChangeStatus.VALIDATION_FAILED,
        "rollback": PasswordChangeStatus.ROLLED_BACK,
        "preparation_error": PasswordChangeStatus.FAILED,
        "credential_error": PasswordChangeStatus.FAILED,
    }[mode]
    assert result.status is expected_status
    assert credential_store.get_password_hash("main") == (
        "hash-new-password" if mode == "success" else "old-main-hash"
    )
    assert (credential_store.get_password_hash("pending_main") is not None) == (
        mode in {"preparation_error", "credential_error"}
    )
    database.close()
    reopened = DatabaseManager(
        database.database_path,
        "new-password" if new_key_active else "old-password",
        device_secret=SECRET,
    )
    reopened.close()
    if mode == "success":
        with pytest.raises(DatabaseAuthenticationError):
            DatabaseManager(
                database.database_path, "old-password", device_secret=SECRET
            )


@pytest.mark.parametrize(
    "replace, invalid", [(False, False), (True, False), (True, True)]
)
def test_catalog_command_runs_import_on_worker_and_refreshes_on_ui(
    qtbot, database, tmp_path, monkeypatch, replace, invalid
):
    owner = threading.get_ident()
    path = tmp_path / "items.seitems.json"
    export_item_catalog_rows(
        [dict(code="NEW", name="New item", purity=92.5, wage_type="WT", wage_rate=1.0)],
        str(path),
    )
    if invalid:
        path.write_text('{"format":"unsupported"}')
    host = QWidget()
    qtbot.addWidget(host)
    refreshed = []
    host.item_master_widget = SimpleNamespace(
        isVisible=lambda: True,
        load_items=lambda: refreshed.append(threading.get_ident()),
    )
    monkeypatch.setattr(
        main_commands.QFileDialog, "getOpenFileName", lambda *a: (str(path), "")
    )

    def confirm(box):
        box.checkBox().setChecked(replace)
        return QMessageBox.StandardButton.Yes

    monkeypatch.setattr(QMessageBox, "exec", confirm)
    messages = []
    for method in ("information", "critical"):
        monkeypatch.setattr(
            QMessageBox,
            method,
            lambda *args: messages.append((args[1], threading.get_ident())),
        )
    from silverestimate.services import item_catalog_transfer as transfer

    load = transfer.load_item_catalog_file
    worker_ids = []

    def observed_load(file_path):
        worker_ids.append(threading.get_ident())
        return load(file_path)

    monkeypatch.setattr(transfer, "load_item_catalog_file", observed_load)
    commands = main_commands.MainCommands(host, database)
    result = commands.restore_item_catalog()
    assert result.succeeded is not invalid
    assert worker_ids and worker_ids[0] != owner
    assert all(thread == owner for _, thread in messages)
    assert not commands._catalog_import_active
    assert not database._broker.maintenance_active
    codes = {row[0] for row in database.conn.execute("SELECT code FROM items")}
    assert codes == ({"OLD"} if invalid else {"NEW"} if replace else {"OLD", "NEW"})
    if not invalid:
        assert refreshed == [owner]
        assert database.get_item_by_code("NEW")["name"] == "New item"
        if replace:
            assert database.get_item_by_code("OLD") is None
    else:
        assert not refreshed


def test_owner_release_failure_unwinds_without_running_operation(
    qtbot, database, monkeypatch
):
    from silverestimate.persistence.database_maintenance import DatabaseMaintenanceJob

    original = database.conn

    def fail(self):
        raise RuntimeError("injected owner release failure")

    monkeypatch.setattr(DatabaseMaintenanceJob, "release_owner", fail)
    with pytest.raises(RuntimeError, match="release failure"):
        run_database_maintenance(
            database, lambda worker: pytest.fail("must not run"), "Test"
        )
    assert database.conn is original
    assert not database._broker.maintenance_active
    assert database.conn.execute("SELECT 1").fetchone()[0] == 1


def test_failed_ui_resume_keeps_access_blocked_and_committed_data_recoverable(
    qtbot, database, monkeypatch
):
    def fail(**kwargs):
        raise OSError("injected UI open failure")

    monkeypatch.setattr(database._broker, "open_writer", fail)

    def operation(worker):
        worker.conn.execute(
            "INSERT INTO items(code,name) VALUES('COMMITTED','Retained')"
        )
        worker.conn.commit()

    with pytest.raises(RuntimeError, match="Restart the application"):
        run_database_maintenance(database, operation, "Test")
    assert database.conn is None
    assert database._broker.maintenance_active
    with pytest.raises(MaintenanceBusyError):
        database.open_read_connection()
    reopened = DatabaseManager(
        database.database_path, "old-password", device_secret=SECRET
    )
    try:
        assert (
            reopened.conn.execute(
                "SELECT name FROM items WHERE code='COMMITTED'"
            ).fetchone()[0]
            == "Retained"
        )
    finally:
        reopened.close()
