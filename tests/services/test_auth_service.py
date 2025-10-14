import logging
import types

from PyQt5.QtWidgets import QDialog

from silverestimate.security import credential_store
from silverestimate.services import auth_service


class _MessageBoxStub:
    information_calls = []
    warning_calls = []
    critical_calls = []

    @classmethod
    def reset(cls):
        cls.information_calls = []
        cls.warning_calls = []
        cls.critical_calls = []

    @classmethod
    def information(cls, *args, **kwargs):
        cls.information_calls.append((args, kwargs))
        return None

    @classmethod
    def warning(cls, *args, **kwargs):
        cls.warning_calls.append((args, kwargs))
        return None

    @classmethod
    def critical(cls, *args, **kwargs):
        cls.critical_calls.append((args, kwargs))
        return None


def test_run_authentication_first_time(monkeypatch, settings_stub):
    _MessageBoxStub.reset()
    class _SetupDialog:
        def __init__(self, is_setup=False):
            assert is_setup is True

        def exec_(self):
            return QDialog.Accepted

        def get_password(self):
            return "primary-pass"

        def get_backup_password(self):
            return "backup-pass"

        @staticmethod
        def hash_password(value):
            return f"hashed-{value}"

    monkeypatch.setattr(auth_service, "LoginDialog", _SetupDialog)
    monkeypatch.setattr(auth_service, "QMessageBox", _MessageBoxStub)

    result = auth_service.run_authentication(logging.getLogger("test-auth-setup"))

    assert result == "primary-pass"
    assert credential_store.get_password_hash("main") == "hashed-primary-pass"
    assert credential_store.get_password_hash("backup") == "hashed-backup-pass"
    settings = settings_stub()
    assert settings.value("security/password_hash") is None
    assert settings.value("security/backup_hash") is None


def test_run_authentication_existing_password(monkeypatch, settings_stub):
    _MessageBoxStub.reset()
    settings = settings_stub()
    settings.setValue("security/password_hash", "stored-hash")
    settings.setValue("security/backup_hash", "backup-hash")

    class _LoginDialog:
        def __init__(self, is_setup=False):
            assert is_setup is False

        def exec_(self):
            return QDialog.Accepted

        def was_reset_requested(self):
            return False

        def get_password(self):
            return "secret"

        @staticmethod
        def verify_password(stored, provided):
            return stored == "stored-hash" and provided == "secret"

    monkeypatch.setattr(auth_service, "LoginDialog", _LoginDialog)
    monkeypatch.setattr(auth_service, "QMessageBox", _MessageBoxStub)

    result = auth_service.run_authentication(logging.getLogger("test-auth-login"))

    assert result == "secret"
    # Legacy values should migrate to secure store.
    assert credential_store.get_password_hash("main") == "stored-hash"
    assert credential_store.get_password_hash("backup") == "backup-hash"
    assert settings.value("security/password_hash") is None
    assert settings.value("security/backup_hash") is None


def test_perform_data_wipe_removes_files(tmp_path, monkeypatch, settings_stub):
    _MessageBoxStub.reset()
    db_file = tmp_path / "estimation.db"
    db_file.write_text("encrypted")
    temp_file = tmp_path / "temp.sqlite"
    temp_file.write_text("temp")

    settings = settings_stub()
    settings.setValue("security/password_hash", "legacy-hash")
    settings.setValue("security/backup_hash", "legacy-backup")
    settings.setValue("security/db_salt", b"salt")
    settings.setValue("security/last_temp_db_path", str(temp_file))
    credential_store.set_password_hash("main", "hash")
    credential_store.set_password_hash("backup", "backup")

    monkeypatch.setattr(auth_service, "QMessageBox", _MessageBoxStub)

    result = auth_service.perform_data_wipe(db_path=str(db_file), logger=logging.getLogger("test-wipe"))

    assert result is True
    assert not db_file.exists()
    assert not temp_file.exists()
    assert credential_store.get_password_hash("main") is None
    assert credential_store.get_password_hash("backup") is None
    for key in ("security/password_hash", "security/backup_hash", "security/db_salt", "security/last_temp_db_path"):
        assert settings.value(key) is None


def test_perform_data_wipe_failure_notifies_user(tmp_path, monkeypatch, settings_stub):
    _MessageBoxStub.reset()
    db_file = tmp_path / "estimation.db"
    db_file.write_text("encrypted")

    settings = settings_stub()
    settings.setValue("security/password_hash", "hash")
    credential_store.set_password_hash("main", "hash")

    def _boom(path):  # noqa: ARG001
        raise OSError("boom")

    monkeypatch.setattr(auth_service, "os", types.SimpleNamespace(remove=_boom, path=auth_service.os.path))
    monkeypatch.setattr(auth_service, "QMessageBox", _MessageBoxStub)

    result = auth_service.perform_data_wipe(db_path=str(db_file), logger=logging.getLogger("test-wipe-fail"))

    assert result is False
    assert db_file.exists()
    # Secure store should still contain the credential because wipe failed.
    assert credential_store.get_password_hash("main") == "hash"
    assert settings.value("security/password_hash") == "hash"
    assert _MessageBoxStub.critical_calls

    # restore os module after test via monkeypatch context in pytest
