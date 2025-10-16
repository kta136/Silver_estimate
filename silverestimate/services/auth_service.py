"""Authentication and data-wipe services for SilverEstimate."""
from __future__ import annotations

import logging
import os
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from PyQt5.QtWidgets import QMessageBox, QDialog

from silverestimate.infrastructure.settings import get_app_settings

from silverestimate.infrastructure.app_constants import DB_PATH, LOG_DIR
from silverestimate.security import credential_store
from silverestimate.security.credential_store import CredentialStoreError
try:
    from silverestimate.ui.login_dialog import LoginDialog  # type: ignore
except Exception:  # pragma: no cover - lazy import fallback
    LoginDialog = None


@dataclass(frozen=True)
class AuthenticationResult:
    """Outcome of the authentication flow."""

    password: Optional[str] = None
    wipe_requested: bool = False
    silent: bool = False

    @property
    def is_wipe(self) -> bool:
        return self.wipe_requested


def run_authentication(
    logger: Optional[logging.Logger] = None,
) -> Optional[AuthenticationResult]:
    """Handle authentication flow using the LoginDialog."""
    global LoginDialog
    if LoginDialog is None:
        from silverestimate.ui.login_dialog import LoginDialog as _LoginDialog  # lazy import
        LoginDialog = _LoginDialog
    logger = logger or logging.getLogger(__name__)
    logger.info("Starting authentication process")

    settings = get_app_settings()
    try:
        password_hash = credential_store.get_password_hash(
            "main", settings=settings, logger=logger
        )
        backup_hash = credential_store.get_password_hash(
            "backup", settings=settings, logger=logger
        )
    except CredentialStoreError as exc:
        logger.critical("Secure credential storage unavailable: %s", exc, exc_info=True)
        QMessageBox.critical(
            None,
            "Authentication Error",
            "Secure credential storage is not available on this system. "
            "Install and configure the Python 'keyring' backend, then restart the application.",
        )
        return None

    if password_hash and backup_hash:
        logger.debug("Found existing password hashes, showing login dialog")
        login_dialog = LoginDialog(is_setup=False)
        result = login_dialog.exec_()

        if result == QDialog.Accepted:
            if login_dialog.was_reset_requested():
                if logger:
                    logger.warning("Data wipe requested via reset button")
                return AuthenticationResult(wipe_requested=True, silent=False)

            entered_password = login_dialog.get_password()
            if LoginDialog.verify_password(password_hash, entered_password):
                if logger:
                    logger.info("Authentication successful")
                return AuthenticationResult(password=entered_password)
            if LoginDialog.verify_password(backup_hash, entered_password):
                return AuthenticationResult(wipe_requested=True, silent=True)
            if logger:
                logger.warning("Authentication failed: incorrect password")
            QMessageBox.warning(None, "Login Failed", "Incorrect password.")
            return None
        if logger:
            logger.info("Login cancelled by user")
        return None

    if logger:
        logger.info("Password hashes not found in settings. Starting first-time setup.")
    setup_dialog = LoginDialog(is_setup=True)
    result = setup_dialog.exec_()
    if result == QDialog.Accepted:
        if logger:
            logger.info("First-time setup completed")
        password = setup_dialog.get_password()
        backup_password = setup_dialog.get_backup_password()
        hashed_password = LoginDialog.hash_password(password)
        hashed_backup = LoginDialog.hash_password(backup_password)
        if not hashed_password or not hashed_backup:
            if logger:
                logger.error("Failed to hash passwords during setup")
            QMessageBox.critical(None, "Setup Error", "Failed to hash passwords.")
            return None
        try:
            credential_store.set_password_hash(
                "main", hashed_password, settings=settings, logger=logger
            )
            credential_store.set_password_hash(
                "backup", hashed_backup, settings=settings, logger=logger
            )
        except CredentialStoreError as exc:
            logger.critical("Failed to persist passwords in secure store: %s", exc, exc_info=True)
            QMessageBox.critical(
                None,
                "Setup Error",
                "Failed to store passwords securely. Please ensure the system keyring is available.",
            )
            return None
        if logger:
            logger.info("Passwords created and stored successfully")
        QMessageBox.information(None, "Setup Complete", "Passwords created successfully.")
        return AuthenticationResult(password=password)
    if logger:
        logger.info("Setup cancelled by user")
    return None


def perform_data_wipe(
    db_path: str = DB_PATH,
    logger: Optional[logging.Logger] = None,
    *,
    silent: bool = False,
) -> bool:
    """Delete encrypted DB and clear credentials from settings."""
    logger = logger or logging.getLogger(__name__)

    def _log(level: str, message: str, *args, **kwargs) -> None:
        if not silent:
            getattr(logger, level)(message, *args, **kwargs)

    _log("warning", "Initiating data wipe for encrypted database: %s", db_path)
    try:
        if os.path.exists(db_path):
            os.remove(db_path)
            _log("info", "Successfully deleted encrypted database file: %s", db_path)
        else:
            _log("warning", "Encrypted database file not found (already deleted?): %s", db_path)

        settings = get_app_settings()
        temp_path = settings.value("security/last_temp_db_path")
        if isinstance(temp_path, str) and temp_path and os.path.exists(temp_path):
            try:
                os.remove(temp_path)
                _log("info", "Removed temporary plaintext DB: %s", temp_path)
            except OSError as exc:
                _log("warning", "Could not remove temporary plaintext DB: %s", exc)

        for key in ("security/db_salt", "security/last_temp_db_path"):
            settings.remove(key)
        for kind in ("main", "backup"):
            try:
                cred_logger = None if silent else logger
                credential_store.delete_password_hash(
                    kind,
                    settings=settings,
                    logger=cred_logger,
                )
            except CredentialStoreError:
                # Delete best-effort; continue wiping remaining artifacts.
                pass
        settings.sync()
        if silent:
            _clear_log_artifacts()
        _log("info", "Cleared password hashes and database salt from application settings.")
        return True
    except Exception as exc:
        error_message = f"A critical error occurred during data wipe: {exc}"
        if not silent:
            logger.critical(error_message, exc_info=True)
        QMessageBox.critical(None, "Data Wipe Error", error_message)
        return False


def _clear_log_artifacts() -> None:
    """Remove application log files and directories without emitting logs."""
    try:
        from silverestimate.infrastructure.logger import get_log_config  # local import to avoid cycles
    except Exception:
        get_log_config = None  # type: ignore[assignment]

    configured_dir = LOG_DIR
    if get_log_config:
        try:
            configured = get_log_config().get("log_dir")
            if configured:
                configured_dir = configured
        except Exception:
            configured_dir = LOG_DIR

    log_dir_path = Path(configured_dir).expanduser()
    if not log_dir_path.is_absolute():
        log_dir_path = Path.cwd() / log_dir_path

    if not log_dir_path.exists():
        return

    try:
        logging.shutdown()
    except Exception:
        pass

    try:
        shutil.rmtree(log_dir_path, ignore_errors=False)
    except Exception:
        # Swallow errors silently to avoid leaking wipe events.
        pass
