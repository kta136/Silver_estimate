"""Startup keeps the event loop alive and promotes credentials after UI attach."""

import threading

import pytest
from PySide6.QtCore import QTimer

from silverestimate.controllers import startup_controller as startup_module
from silverestimate.controllers.startup_controller import (
    StartupController,
    StartupStatus,
)
from silverestimate.persistence.database_manager import DatabaseManager
from silverestimate.security import credential_store
from silverestimate.services.auth_service import AuthenticationResult


def test_startup_validation_is_responsive_and_preload_starts_after_ui_attach(
    qtbot, tmp_path, monkeypatch
):
    path = tmp_path / "startup.db"
    owner = threading.get_ident()
    started = threading.Event()
    release = threading.Event()
    ticks = []
    stages = []

    class ObservedDatabase(DatabaseManager):
        def validate_database(self, connection, **kwargs):
            stages.append(("validate", threading.get_ident()))
            started.set()
            assert release.wait(5)
            super().validate_database(connection, **kwargs)

        def start_preload_item_cache(self):
            assert self.conn is not None
            assert self._session.is_owner()
            stages.append(("preload", threading.get_ident()))

    monkeypatch.setattr(startup_module, "DB_PATH", str(path))
    monkeypatch.setattr(startup_module, "DatabaseManager", ObservedDatabase)
    monkeypatch.setattr(
        startup_module.QMessageBox, "critical", lambda *a: pytest.fail(str(a))
    )
    timer = QTimer()

    def heartbeat():
        if started.is_set():
            ticks.append(threading.get_ident())
            if len(ticks) >= 3:
                release.set()

    timer.timeout.connect(heartbeat)
    timer.start(10)
    try:
        database = StartupController()._initialize_database("password", b"S" * 32)
    finally:
        release.set()
        timer.stop()
    assert database is not None
    try:
        assert len(ticks) >= 3
        assert set(ticks) == {owner}
        assert stages[0][0] == "validate" and stages[0][1] != owner
        assert stages[1] == ("preload", owner)
        assert database.conn.execute("SELECT 1").fetchone()[0] == 1
    finally:
        database.close()


@pytest.mark.parametrize("failure", [None, "validation", "attach"])
def test_pending_credentials_promoted_only_after_validated_ui_connection(
    qtbot, tmp_path, monkeypatch, settings_stub, failure
):
    del settings_stub
    path = tmp_path / "startup.db"
    owner = threading.get_ident()
    errors = []
    instances = []

    class ObservedDatabase(DatabaseManager):
        def validate_database(self, connection, **kwargs):
            instances.append(self)
            assert credential_store.get_password_hash("main") is None
            if failure == "validation":
                raise ValueError("injected validation failure")
            super().validate_database(connection, **kwargs)

        def attach_prepared_connection(self):
            assert threading.get_ident() == owner
            assert credential_store.get_password_hash("main") is None
            if failure == "attach":
                raise OSError("injected attach failure")
            super().attach_prepared_connection()

        def start_preload_item_cache(self):
            pass

    monkeypatch.setattr(startup_module, "DB_PATH", str(path))
    monkeypatch.setattr(startup_module, "DatabaseManager", ObservedDatabase)
    monkeypatch.setattr(
        startup_module,
        "run_authentication",
        lambda *a, **kw: AuthenticationResult(
            password="password",
            pending_main_hash="main-hash",
            pending_backup_hash="backup-hash",
        ),
    )
    monkeypatch.setattr(
        startup_module.QMessageBox, "critical", lambda *a: errors.append(a[1])
    )
    monkeypatch.setattr(startup_module.QMessageBox, "information", lambda *a: None)
    result = StartupController().authenticate_and_prepare()
    if failure:
        assert result.status == StartupStatus.FAILED
        assert result.db is None
        assert errors == ["Database Error"]
        assert credential_store.get_password_hash("main") is None
        assert credential_store.get_password_hash("pending_main") == "main-hash"
        assert instances[0].conn is None
    else:
        assert result.status == StartupStatus.OK
        try:
            assert credential_store.get_password_hash("main") == "main-hash"
            assert credential_store.get_password_hash("backup") == "backup-hash"
            assert credential_store.get_password_hash("pending_main") is None
            assert not errors
        finally:
            result.db.close()
