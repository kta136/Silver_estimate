import logging

import pytest

from silverestimate.controllers import startup_controller as startup_module
from silverestimate.controllers.startup_controller import (
    StartupController,
    StartupStatus,
)
from silverestimate.security.credential_store import CredentialStoreError
from silverestimate.services.auth_service import AuthenticationResult


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


def test_device_binding_refuses_existing_bound_database_without_local_secret(
    tmp_path, monkeypatch, settings_stub
):
    path = tmp_path / "estimation.db"
    path.write_bytes(b"bound-database")
    monkeypatch.setattr(startup_module, "DB_PATH", str(path))

    controller = StartupController(logger=logging.getLogger("test-device-binding"))

    with pytest.raises(CredentialStoreError, match="copied databases"):
        controller._prepare_device_binding()


def test_device_binding_is_created_for_authenticated_legacy_database(
    tmp_path, monkeypatch, settings_stub
):
    path = tmp_path / "estimation.db"
    path.write_bytes(b"legacy-database")
    path.with_name("estimation.kdf.json").write_text("{}")
    monkeypatch.setattr(startup_module, "DB_PATH", str(path))

    controller = StartupController(
        logger=logging.getLogger("test-legacy-device-binding")
    )
    first = controller._prepare_device_binding()
    second = controller._prepare_device_binding()

    assert first == second
    assert len(first) == 32
