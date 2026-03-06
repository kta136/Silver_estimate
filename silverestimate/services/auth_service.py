"""Authentication and data-wipe services for SilverEstimate."""

from __future__ import annotations

import logging
import os
import shutil
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

from PyQt5.QtWidgets import QDialog, QMessageBox, QWidget

from silverestimate.infrastructure.app_constants import DB_PATH, LOG_DIR
from silverestimate.infrastructure.settings import get_app_settings
from silverestimate.security import credential_store
from silverestimate.security.credential_store import CredentialStoreError

LoginDialog = None


def _resolve_login_dialog():
    global LoginDialog
    if LoginDialog is None:
        from silverestimate.ui.login_dialog import LoginDialog as _LoginDialog

        LoginDialog = _LoginDialog
    return LoginDialog


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
    *,
    parent: Optional[QWidget] = None,
) -> Optional[AuthenticationResult]:
    """Handle authentication flow using the LoginDialog."""
    logger = logger or logging.getLogger(__name__)
    flow_started_at = time.perf_counter()
    logger.info("Starting authentication process")
    logger.debug("[perf] startup.auth_dialog_prepare_start t_unix=%.6f", time.time())
    login_dialog_cls = _resolve_login_dialog()

    settings = get_app_settings()
    backend_status = credential_store.get_backend_status()
    if not backend_status.available:
        logger.critical(
            "Secure credential storage unavailable: %s (%s)",
            backend_status.backend_name,
            backend_status.reason,
        )
        QMessageBox.critical(
            parent,
            "Authentication Error",
            "Secure credential storage is unavailable.\n\n"
            f"Backend: {backend_status.backend_name}\n"
            f"Details: {backend_status.reason}\n\n"
            "Configure an OS keyring backend (Windows Credential Manager, macOS Keychain, "
            "or SecretService/libsecret on Linux), then restart the application.",
        )
        return None
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
            parent,
            "Authentication Error",
            "Secure credential storage is not available on this system.\n\n"
            f"Details: {exc}\n\n"
            "Install/configure an OS keyring backend and restart the application.",
        )
        return None

    if password_hash and backup_hash:
        logger.debug("Found existing password hashes, showing login dialog")
        attempt = 0
        while True:
            attempt += 1
            logger.debug(
                "[perf] startup.auth_dialog_shown_ms=%.2f t_unix=%.6f attempt=%s",
                (time.perf_counter() - flow_started_at) * 1000.0,
                time.time(),
                attempt,
            )
            login_dialog = login_dialog_cls(is_setup=False, parent=parent)
            result = login_dialog.exec_()

            if result != QDialog.Accepted:
                if logger:
                    logger.info("Login cancelled by user")
                return None

            if login_dialog.was_reset_requested():
                if logger:
                    logger.warning("Data wipe requested via reset button")
                return AuthenticationResult(wipe_requested=True, silent=False)

            entered_password = login_dialog.get_password()
            if login_dialog_cls.verify_password(password_hash, entered_password):
                if logger:
                    logger.info("Authentication successful on attempt %s", attempt)
                    logger.debug(
                        "[perf] startup.auth_dialog_accepted_ms=%.2f t_unix=%.6f attempt=%s",
                        (time.perf_counter() - flow_started_at) * 1000.0,
                        time.time(),
                        attempt,
                    )
                return AuthenticationResult(password=entered_password)
            if login_dialog_cls.verify_password(backup_hash, entered_password):
                logger.debug(
                    "[perf] startup.auth_dialog_accepted_ms=%.2f t_unix=%.6f attempt=%s mode=backup",
                    (time.perf_counter() - flow_started_at) * 1000.0,
                    time.time(),
                    attempt,
                )
                return AuthenticationResult(wipe_requested=True, silent=True)

            if logger:
                logger.warning(
                    "Authentication failed: incorrect password (attempt %s)", attempt
                )
            QMessageBox.warning(
                parent,
                "Login Failed",
                "Incorrect password. Please try again or use Wipe All Data.",
            )

    if logger:
        logger.info("Password hashes not found in settings. Starting first-time setup.")
    logger.debug(
        "[perf] startup.auth_dialog_shown_ms=%.2f t_unix=%.6f mode=setup",
        (time.perf_counter() - flow_started_at) * 1000.0,
        time.time(),
    )
    setup_dialog = login_dialog_cls(is_setup=True, parent=parent)
    result = setup_dialog.exec_()
    if result == QDialog.Accepted:
        if logger:
            logger.info("First-time setup completed")
        password = setup_dialog.get_password()
        backup_password = setup_dialog.get_backup_password()
        hashed_password = login_dialog_cls.hash_password(password)
        hashed_backup = login_dialog_cls.hash_password(backup_password)
        if not hashed_password or not hashed_backup:
            if logger:
                logger.error("Failed to hash passwords during setup")
            QMessageBox.critical(parent, "Setup Error", "Failed to hash passwords.")
            return None
        try:
            credential_store.set_password_hash(
                "main", hashed_password, settings=settings, logger=logger
            )
            credential_store.set_password_hash(
                "backup", hashed_backup, settings=settings, logger=logger
            )
        except CredentialStoreError as exc:
            logger.critical(
                "Failed to persist passwords in secure store: %s", exc, exc_info=True
            )
            QMessageBox.critical(
                parent,
                "Setup Error",
                "Failed to store passwords securely. Please ensure the system keyring is available.",
            )
            return None
        if logger:
            logger.info("Passwords created and stored successfully")
        QMessageBox.information(
            parent, "Setup Complete", "Passwords created successfully."
        )
        logger.debug(
            "[perf] startup.auth_dialog_accepted_ms=%.2f t_unix=%.6f mode=setup",
            (time.perf_counter() - flow_started_at) * 1000.0,
            time.time(),
        )
        return AuthenticationResult(password=password)
    if logger:
        logger.info("Setup cancelled by user")
    return None


def perform_data_wipe(
    db_path: str = DB_PATH,
    logger: Optional[logging.Logger] = None,
    *,
    silent: bool = False,
    parent: Optional[QWidget] = None,
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
            _log(
                "warning",
                "Encrypted database file not found (already deleted?): %s",
                db_path,
            )

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
        _log(
            "info",
            "Cleared password hashes and database salt from application settings.",
        )
        return True
    except Exception as exc:
        error_message = f"A critical error occurred during data wipe: {exc}"
        if not silent:
            logger.critical(error_message, exc_info=True)
        QMessageBox.critical(parent, "Data Wipe Error", error_message)
        return False


def _clear_log_artifacts() -> None:
    """Remove application log files and directories without emitting logs."""
    get_log_config_fn: Callable[[], dict[str, object]] | None = None
    try:
        from silverestimate.infrastructure.logger import (  # local import to avoid cycles
            get_log_config as _get_log_config,
        )

        get_log_config_fn = _get_log_config
    except Exception:
        get_log_config_fn = None

    configured_dir = LOG_DIR
    if get_log_config_fn is not None:
        try:
            configured = get_log_config_fn().get("log_dir")
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
