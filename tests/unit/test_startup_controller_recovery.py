import logging

from silverestimate.controllers import startup_controller as startup_module
from silverestimate.controllers.startup_controller import (
    StartupController,
    StartupStatus,
)
from silverestimate.services.auth_service import AuthenticationResult


def test_initialize_database_recovers_candidate_before_connect(monkeypatch, tmp_path):
    calls = {}
    db_path = tmp_path / "db" / "estimation.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)

    class StubMessageBox:
        Yes = 1
        No = 2

        @staticmethod
        def question(parent, title, message, buttons, default):
            calls["question"] = (title, message, buttons, default)
            return StubMessageBox.Yes

        @staticmethod
        def critical(parent, title, message):
            calls["critical"] = (title, message)

    class StubDatabaseManager:
        @staticmethod
        def check_recovery_candidate(encrypted_db_path):
            calls["candidate_path"] = encrypted_db_path
            return str(tmp_path / "recover.sqlite")

        @staticmethod
        def recover_encrypt_plain_to_encrypted(
            plain_temp_path, encrypted_db_path, password, logger=None
        ):
            calls["recovered"] = (plain_temp_path, encrypted_db_path, password)
            return True

        def __init__(self, db_path, password):
            calls["init"] = (db_path, password)

    monkeypatch.setattr(startup_module, "QMessageBox", StubMessageBox)
    monkeypatch.setattr(startup_module, "DatabaseManager", StubDatabaseManager)
    monkeypatch.setattr(startup_module, "DB_PATH", str(db_path))

    controller = StartupController(logger=logging.getLogger("test-startup-recovery"))
    db = controller._initialize_database("secret-pass")

    assert db is not None
    assert calls["candidate_path"] == str(db_path)
    assert calls["recovered"] == (
        str(tmp_path / "recover.sqlite"),
        str(db_path),
        "secret-pass",
    )
    assert calls["init"] == (str(db_path), "secret-pass")


def test_authenticate_cancelled_skips_database_initialization(monkeypatch):
    calls = {"db_init": 0}

    class StubDatabaseManager:
        def __init__(self, *args, **kwargs):
            calls["db_init"] += 1

    monkeypatch.setattr(startup_module, "run_authentication", lambda *_a, **_k: None)
    monkeypatch.setattr(startup_module, "DatabaseManager", StubDatabaseManager)

    controller = StartupController(logger=logging.getLogger("test-startup-cancel"))
    result = controller.authenticate_and_prepare()

    assert result.status == StartupStatus.CANCELLED
    assert calls["db_init"] == 0


def test_authenticate_wipe_skips_database_initialization(monkeypatch):
    calls = {"wipe": 0, "db_init": 0}

    class StubDatabaseManager:
        def __init__(self, *args, **kwargs):
            calls["db_init"] += 1

    def _wipe(**kwargs):
        calls["wipe"] += 1
        return True

    monkeypatch.setattr(
        startup_module,
        "run_authentication",
        lambda *_a, **_k: AuthenticationResult(wipe_requested=True, silent=False),
    )
    monkeypatch.setattr(startup_module, "perform_data_wipe", _wipe)
    monkeypatch.setattr(startup_module, "DatabaseManager", StubDatabaseManager)

    controller = StartupController(logger=logging.getLogger("test-startup-wipe"))
    result = controller.authenticate_and_prepare()

    assert result.status == StartupStatus.WIPED
    assert calls["wipe"] == 1
    assert calls["db_init"] == 0
