import logging

from PyQt5.QtWidgets import QDialog

from silverestimate.services import auth_service


class _MessageBoxStub:
    @staticmethod
    def information(*args, **kwargs):
        return None

    @staticmethod
    def warning(*args, **kwargs):
        return None

    @staticmethod
    def critical(*args, **kwargs):
        return None


def test_run_authentication_first_time(monkeypatch, settings_stub):
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
    settings = settings_stub()
    assert settings.value("security/password_hash") == "hashed-primary-pass"
    assert settings.value("security/backup_hash") == "hashed-backup-pass"


def test_run_authentication_existing_password(monkeypatch, settings_stub):
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


def test_perform_data_wipe_removes_files(tmp_path, monkeypatch, settings_stub):
    db_file = tmp_path / "estimation.db"
    db_file.write_text("encrypted")
    temp_file = tmp_path / "temp.sqlite"
    temp_file.write_text("temp")

    settings = settings_stub()
    settings.setValue("security/password_hash", "hash")
    settings.setValue("security/backup_hash", "backup")
    settings.setValue("security/db_salt", b"salt")
    settings.setValue("security/last_temp_db_path", str(temp_file))

    monkeypatch.setattr(auth_service, "QMessageBox", _MessageBoxStub)

    result = auth_service.perform_data_wipe(db_path=str(db_file), logger=logging.getLogger("test-wipe"))

    assert result is True
    assert not db_file.exists()
    assert not temp_file.exists()
    for key in (
        "security/password_hash",
        "security/backup_hash",
        "security/db_salt",
        "security/last_temp_db_path",
    ):
        assert settings.value(key) is None
