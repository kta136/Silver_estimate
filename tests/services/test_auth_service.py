import logging

from PySide6.QtWidgets import QDialog

from silverestimate.security import credential_store
from silverestimate.security.password_service import PasswordVerification
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


class _PasswordServiceStub:
    def __init__(
        self,
        *,
        matches=(),
    ):
        self._matches = set(matches)

    @staticmethod
    def hash_password(value):
        return f"hashed-{value}"

    def verify_password(self, stored, provided):
        verified = (stored, provided) in self._matches
        return PasswordVerification(verified=verified)


def test_run_authentication_first_time(tmp_path, monkeypatch, settings_stub):
    _MessageBoxStub.reset()

    class _SetupDialog:
        def __init__(self, is_setup=False, parent=None):
            assert is_setup is True

        def exec(self):
            return QDialog.DialogCode.Accepted

        def get_password(self):
            return "primary-pass"

        def get_backup_password(self):
            return "backup-pass"

    monkeypatch.setattr(auth_service, "LoginDialog", _SetupDialog)
    monkeypatch.setattr(auth_service, "_password_service", _PasswordServiceStub())
    monkeypatch.setattr(auth_service, "QMessageBox", _MessageBoxStub)

    result = auth_service.run_authentication(
        logging.getLogger("test-auth-setup"),
        db_path=str(tmp_path / "estimation.db"),
    )

    assert isinstance(result, auth_service.AuthenticationResult)
    assert result.password == "primary-pass"
    assert result.wipe_requested is False
    assert result.pending_main_hash == "hashed-primary-pass"
    assert result.pending_backup_hash == "hashed-backup-pass"
    assert credential_store.get_password_hash("main") is None
    assert credential_store.get_password_hash("backup") is None


def test_existing_database_without_local_credentials_fails_closed(
    tmp_path, monkeypatch, settings_stub
):
    _MessageBoxStub.reset()
    db_path = tmp_path / "estimation.db"
    db_path.write_bytes(b"encrypted-database")

    class _UnexpectedDialog:
        def __init__(self, *args, **kwargs):
            raise AssertionError("A foreign database must not start setup")

    monkeypatch.setattr(auth_service, "LoginDialog", _UnexpectedDialog)
    monkeypatch.setattr(auth_service, "QMessageBox", _MessageBoxStub)

    result = auth_service.run_authentication(
        logging.getLogger("test-auth-foreign-db"),
        db_path=str(db_path),
    )

    assert result is None
    assert _MessageBoxStub.critical_calls
    assert (
        "copied database cannot be adopted" in _MessageBoxStub.critical_calls[0][0][2]
    )


def test_run_authentication_existing_password(monkeypatch, settings_stub):
    _MessageBoxStub.reset()
    credential_store.set_password_hash("main", "stored-hash")
    credential_store.set_password_hash("backup", "backup-hash")

    class _LoginDialog:
        def __init__(self, is_setup=False, parent=None):
            assert is_setup is False

        def exec(self):
            return QDialog.DialogCode.Accepted

        def was_reset_requested(self):
            return False

        def get_password(self):
            return "secret"

    monkeypatch.setattr(auth_service, "LoginDialog", _LoginDialog)
    monkeypatch.setattr(
        auth_service,
        "_password_service",
        _PasswordServiceStub(matches={("stored-hash", "secret")}),
    )
    monkeypatch.setattr(auth_service, "QMessageBox", _MessageBoxStub)

    result = auth_service.run_authentication(logging.getLogger("test-auth-login"))

    assert isinstance(result, auth_service.AuthenticationResult)
    assert result.password == "secret"
    assert result.wipe_requested is False
    assert credential_store.get_password_hash("main") == "stored-hash"
    assert credential_store.get_password_hash("backup") == "backup-hash"


def test_run_authentication_recovers_pending_first_setup_credentials(
    tmp_path, monkeypatch, settings_stub
):
    _MessageBoxStub.reset()
    credential_store.set_password_hash("pending_main", "pending-main")
    credential_store.set_password_hash("pending_backup", "pending-backup")

    class _LoginDialog:
        def __init__(self, is_setup=False, parent=None):
            assert is_setup is False

        def exec(self):
            return QDialog.DialogCode.Accepted

        def was_reset_requested(self):
            return False

        def get_password(self):
            return "secret"

    monkeypatch.setattr(auth_service, "LoginDialog", _LoginDialog)
    monkeypatch.setattr(
        auth_service,
        "_password_service",
        _PasswordServiceStub(matches={("pending-main", "secret")}),
    )
    monkeypatch.setattr(auth_service, "QMessageBox", _MessageBoxStub)

    result = auth_service.run_authentication(
        logging.getLogger("test-auth-pending-setup"),
        db_path=str(tmp_path / "estimation.db"),
    )

    assert isinstance(result, auth_service.AuthenticationResult)
    assert result.password == "secret"
    assert result.pending_main_hash == "pending-main"
    assert result.pending_backup_hash == "pending-backup"


def test_run_authentication_uses_lazy_login_dialog_resolver(monkeypatch, settings_stub):
    _MessageBoxStub.reset()
    credential_store.set_password_hash("main", "stored-hash")
    credential_store.set_password_hash("backup", "backup-hash")

    calls = {"resolver": 0}

    class _LoginDialog:
        def __init__(self, is_setup=False, parent=None):
            assert is_setup is False

        def exec(self):
            return QDialog.DialogCode.Accepted

        def was_reset_requested(self):
            return False

        def get_password(self):
            return "secret"

    def _resolver():
        calls["resolver"] += 1
        return _LoginDialog

    monkeypatch.setattr(auth_service, "_resolve_login_dialog", _resolver)
    monkeypatch.setattr(
        auth_service,
        "_password_service",
        _PasswordServiceStub(matches={("stored-hash", "secret")}),
    )
    monkeypatch.setattr(auth_service, "QMessageBox", _MessageBoxStub)

    result = auth_service.run_authentication(logging.getLogger("test-auth-lazy"))

    assert isinstance(result, auth_service.AuthenticationResult)
    assert result.password == "secret"
    assert calls["resolver"] == 1


def test_run_authentication_secondary_password_triggers_silent_wipe(
    monkeypatch, settings_stub
):
    _MessageBoxStub.reset()
    credential_store.set_password_hash("main", "stored-hash")
    credential_store.set_password_hash("backup", "backup-hash")

    class _LoginDialog:
        def __init__(self, is_setup=False, parent=None):
            assert is_setup is False

        def exec(self):
            return QDialog.DialogCode.Accepted

        def was_reset_requested(self):
            return False

        def get_password(self):
            return "panic"

    monkeypatch.setattr(auth_service, "LoginDialog", _LoginDialog)
    monkeypatch.setattr(
        auth_service,
        "_password_service",
        _PasswordServiceStub(matches={("backup-hash", "panic")}),
    )
    monkeypatch.setattr(auth_service, "QMessageBox", _MessageBoxStub)

    result = auth_service.run_authentication(logging.getLogger("test-auth-secondary"))

    assert isinstance(result, auth_service.AuthenticationResult)
    assert result.wipe_requested is True
    assert result.silent is True


def test_run_authentication_retries_after_incorrect_password(
    monkeypatch, settings_stub
):
    _MessageBoxStub.reset()
    credential_store.set_password_hash("main", "stored-hash")
    credential_store.set_password_hash("backup", "backup-hash")

    attempts = {"count": 0}

    class _LoginDialog:
        def __init__(self, is_setup=False, parent=None):
            assert is_setup is False
            attempts["count"] += 1
            self._attempt = attempts["count"]

        def exec(self):
            return QDialog.DialogCode.Accepted

        def was_reset_requested(self):
            return False

        def get_password(self):
            return "wrong-pass" if self._attempt == 1 else "secret"

    monkeypatch.setattr(auth_service, "LoginDialog", _LoginDialog)
    monkeypatch.setattr(
        auth_service,
        "_password_service",
        _PasswordServiceStub(matches={("stored-hash", "secret")}),
    )
    monkeypatch.setattr(auth_service, "QMessageBox", _MessageBoxStub)

    result = auth_service.run_authentication(logging.getLogger("test-auth-retry"))

    assert isinstance(result, auth_service.AuthenticationResult)
    assert result.password == "secret"
    assert result.wipe_requested is False
    assert attempts["count"] == 2
    assert len(_MessageBoxStub.warning_calls) == 1


def test_verify_password_contains_an_unavailable_verifier(monkeypatch, caplog):
    class _UnavailablePasswordService:
        @staticmethod
        def verify_password(stored, provided):
            raise RuntimeError("unavailable")

    monkeypatch.setattr(
        auth_service,
        "_password_service",
        _UnavailablePasswordService(),
    )

    assert not auth_service.verify_password(
        "stored-hash",
        "provided-password",
        logger=logging.getLogger("test-auth-unavailable-verifier"),
    )
    assert "Password verifier is unavailable" in caplog.text


def test_perform_data_wipe_removes_files(tmp_path, monkeypatch, settings_stub):
    _MessageBoxStub.reset()
    db_file = tmp_path / "estimation.db"
    db_file.write_text("encrypted")

    settings_stub()
    credential_store.set_password_hash("main", "hash")
    credential_store.set_password_hash("backup", "backup")
    device_secret = credential_store.create_device_binding_secret()

    monkeypatch.setattr(auth_service, "QMessageBox", _MessageBoxStub)

    result = auth_service.perform_data_wipe(
        db_path=str(db_file), logger=logging.getLogger("test-wipe")
    )

    assert result is True
    assert not db_file.exists()
    assert credential_store.get_password_hash("main") is None
    assert credential_store.get_password_hash("backup") is None
    assert credential_store.get_device_binding_secret() is None
    assert len(device_secret) == 32


def test_perform_data_wipe_silent_removes_logs(tmp_path, monkeypatch, settings_stub):
    _MessageBoxStub.reset()
    db_file = tmp_path / "estimation.db"
    db_file.write_text("encrypted")

    log_root = tmp_path / "logs"
    (log_root / "archived").mkdir(parents=True)
    (log_root / "silver_app.log").write_text("log")
    (log_root / "archived" / "old.log").write_text("old log")

    settings_stub()
    credential_store.set_password_hash("main", "hash")

    def _get_log_config():
        return {
            "log_dir": str(log_root),
            "debug_mode": False,
            "enable_info": True,
            "enable_error": True,
            "enable_debug": False,
            "auto_cleanup": False,
            "cleanup_days": 1,
        }

    monkeypatch.setattr(auth_service, "QMessageBox", _MessageBoxStub)
    monkeypatch.setattr(
        "silverestimate.infrastructure.logger.get_log_config",
        _get_log_config,
        raising=False,
    )

    result = auth_service.perform_data_wipe(
        db_path=str(db_file),
        logger=logging.getLogger("test-wipe-silent"),
        silent=True,
    )

    assert result is True
    assert not log_root.exists()


def test_perform_data_wipe_failure_notifies_user(tmp_path, monkeypatch, settings_stub):
    _MessageBoxStub.reset()
    db_file = tmp_path / "estimation.db"
    db_file.write_text("encrypted")

    credential_store.set_password_hash("main", "hash")

    def _boom(path, *, missing_ok=False):  # noqa: ARG001
        raise OSError("boom")

    monkeypatch.setattr(auth_service.Path, "unlink", _boom)
    monkeypatch.setattr(auth_service, "QMessageBox", _MessageBoxStub)

    result = auth_service.perform_data_wipe(
        db_path=str(db_file), logger=logging.getLogger("test-wipe-fail")
    )

    assert result is False
    assert db_file.exists()
    # Secure store should still contain the credential because wipe failed.
    assert credential_store.get_password_hash("main") == "hash"
    assert _MessageBoxStub.critical_calls

    # restore os module after test via monkeypatch context in pytest
