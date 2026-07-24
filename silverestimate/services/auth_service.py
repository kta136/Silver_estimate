"""Authentication and data-wipe services for SilverEstimate."""

from __future__ import annotations

import logging
import shutil
import time
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Callable, Optional

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QDialog, QMessageBox, QWidget

from silverestimate.infrastructure.app_constants import DB_PATH, LOG_DIR
from silverestimate.infrastructure.settings import get_app_settings
from silverestimate.security import credential_store
from silverestimate.security.credential_store import CredentialStoreError

if TYPE_CHECKING:
    from silverestimate.security.password_service import (
        PasswordHashService,
        PasswordVerification,
    )

LoginDialog = None
_password_service: PasswordHashService | None = None


def _resolve_login_dialog():
    global LoginDialog
    if LoginDialog is None:
        from silverestimate.ui.login_dialog import LoginDialog as _LoginDialog

        LoginDialog = _LoginDialog
    return LoginDialog


def _get_password_service() -> PasswordHashService:
    global _password_service
    if _password_service is None:
        from silverestimate.security.password_service import PasswordHashService

        _password_service = PasswordHashService()
    return _password_service


def _warm_password_service() -> None:
    try:
        _get_password_service()
    except Exception:
        logging.getLogger(__name__).debug(
            "Password service warm-up failed",
            exc_info=True,
        )


def _schedule_password_service_warmup() -> None:
    QTimer.singleShot(0, _warm_password_service)


def hash_password(
    password: str,
    *,
    logger: logging.Logger | None = None,
) -> str | None:
    """Hash a new password without exposing the security implementation to UI code."""
    logger = logger or logging.getLogger(__name__)
    try:
        return _get_password_service().hash_password(password)
    except Exception:
        logger.error("Password hashing failed", exc_info=True)
        return None


def _verify_password_hash(
    stored_hash: str,
    provided_password: str,
    *,
    logger: logging.Logger,
) -> PasswordVerification:
    from silverestimate.security.password_service import (
        MalformedPasswordHashError,
        PasswordHashError,
        PasswordVerification,
    )

    try:
        return _get_password_service().verify_password(
            stored_hash,
            provided_password,
        )
    except MalformedPasswordHashError:
        logger.error("Stored password hash is malformed", exc_info=True)
    except PasswordHashError:
        logger.error("Password verification failed", exc_info=True)
    except Exception:
        logger.error("Password verifier is unavailable", exc_info=True)
    return PasswordVerification(verified=False)


def verify_password(
    stored_hash: str,
    provided_password: str,
    *,
    logger: logging.Logger | None = None,
) -> bool:
    """Return whether a password matches, logging malformed hashes separately."""
    return _verify_password_hash(
        stored_hash,
        provided_password,
        logger=logger or logging.getLogger(__name__),
    ).verified


def _verify_credential_password(
    stored_hash: str,
    provided_password: str,
    *,
    logger: logging.Logger,
) -> PasswordVerification:
    started_at = time.perf_counter()
    verification = _verify_password_hash(
        stored_hash,
        provided_password,
        logger=logger,
    )
    logger.info(
        '[telemetry] {"metric":"startup.password_hash_verify_ms","duration_ms":%.3f}',
        (time.perf_counter() - started_at) * 1000.0,
    )
    return verification


@dataclass(frozen=True)
class AuthenticationResult:
    """Outcome of the authentication flow."""

    password: Optional[str] = None
    wipe_requested: bool = False
    silent: bool = False
    pending_main_hash: Optional[str] = None
    pending_backup_hash: Optional[str] = None
    rollback_pending_credentials: bool = False

    @property
    def is_wipe(self) -> bool:
        return self.wipe_requested


def run_authentication(
    logger: Optional[logging.Logger] = None,
    *,
    parent: Optional[QWidget] = None,
    db_path: str = DB_PATH,
) -> Optional[AuthenticationResult]:
    """Handle authentication flow using the LoginDialog."""
    logger = logger or logging.getLogger(__name__)
    flow_started_at = time.perf_counter()
    logger.info("Starting authentication process")
    logger.debug("[perf] startup.auth_dialog_prepare_start t_unix=%.6f", time.time())
    login_dialog_cls = _resolve_login_dialog()

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
        password_hash = credential_store.get_password_hash("main")
        backup_hash = credential_store.get_password_hash("backup")
        pending_main_hash = credential_store.get_password_hash("pending_main")
        pending_backup_hash = credential_store.get_password_hash("pending_backup")
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

    has_current_credentials = bool(password_hash and backup_hash)
    has_pending_credentials = bool(pending_main_hash and pending_backup_hash)
    if (
        not has_current_credentials
        and not has_pending_credentials
        and Path(db_path).is_file()
    ):
        logger.critical(
            "Existing machine-bound database has no local credential registration"
        )
        QMessageBox.critical(
            parent,
            "Device Binding Error",
            "An existing encrypted database was found, but this Windows PC does not "
            "have its required local credentials.\n\n"
            "For security, a copied database cannot be adopted or opened on another "
            "PC, even with the correct password.",
        )
        return None

    if has_current_credentials or has_pending_credentials:
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
            _schedule_password_service_warmup()
            result = login_dialog.exec()

            if result != QDialog.DialogCode.Accepted:
                if logger:
                    logger.info("Login cancelled by user")
                return None

            if login_dialog.was_reset_requested():
                if logger:
                    logger.warning("Data wipe requested via reset button")
                return AuthenticationResult(wipe_requested=True, silent=False)

            entered_password = login_dialog.get_password()
            if password_hash:
                main_verification = _verify_credential_password(
                    password_hash,
                    entered_password,
                    logger=logger,
                )
                if main_verification.verified:
                    if logger:
                        logger.info("Authentication successful on attempt %s", attempt)
                        logger.debug(
                            "[perf] startup.auth_dialog_accepted_ms=%.2f "
                            "t_unix=%.6f attempt=%s",
                            (time.perf_counter() - flow_started_at) * 1000.0,
                            time.time(),
                            attempt,
                        )
                    return AuthenticationResult(
                        password=entered_password,
                        rollback_pending_credentials=bool(pending_main_hash),
                    )
            if pending_main_hash:
                pending_main_verification = _verify_credential_password(
                    pending_main_hash,
                    entered_password,
                    logger=logger,
                )
                if pending_main_verification.verified:
                    return AuthenticationResult(
                        password=entered_password,
                        pending_main_hash=pending_main_hash,
                        pending_backup_hash=pending_backup_hash,
                    )
            if backup_hash:
                backup_verification = _verify_credential_password(
                    backup_hash,
                    entered_password,
                    logger=logger,
                )
                if backup_verification.verified:
                    logger.debug(
                        "[perf] startup.auth_dialog_accepted_ms=%.2f "
                        "t_unix=%.6f attempt=%s mode=backup",
                        (time.perf_counter() - flow_started_at) * 1000.0,
                        time.time(),
                        attempt,
                    )
                    return AuthenticationResult(wipe_requested=True, silent=True)
            if pending_backup_hash:
                pending_backup_verification = _verify_credential_password(
                    pending_backup_hash,
                    entered_password,
                    logger=logger,
                )
                if pending_backup_verification.verified:
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
        logger.info(
            "Password hashes not found in secure store. Starting first-time setup."
        )
    logger.debug(
        "[perf] startup.auth_dialog_shown_ms=%.2f t_unix=%.6f mode=setup",
        (time.perf_counter() - flow_started_at) * 1000.0,
        time.time(),
    )
    setup_dialog = login_dialog_cls(is_setup=True, parent=parent)
    _schedule_password_service_warmup()
    result = setup_dialog.exec()
    if result == QDialog.DialogCode.Accepted:
        if logger:
            logger.info("First-time setup completed")
        password = setup_dialog.get_password()
        backup_password = setup_dialog.get_backup_password()
        hashed_password = hash_password(password, logger=logger)
        hashed_backup = hash_password(backup_password, logger=logger)
        if not hashed_password or not hashed_backup:
            if logger:
                logger.error("Failed to hash passwords during setup")
            QMessageBox.critical(parent, "Setup Error", "Failed to hash passwords.")
            return None
        logger.debug(
            "[perf] startup.auth_dialog_accepted_ms=%.2f t_unix=%.6f mode=setup",
            (time.perf_counter() - flow_started_at) * 1000.0,
            time.time(),
        )
        return AuthenticationResult(
            password=password,
            pending_main_hash=hashed_password,
            pending_backup_hash=hashed_backup,
        )
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
        database = Path(db_path).resolve()
        parent_dir = database.parent
        explicit = {
            database,
            Path(f"{database}-wal"),
            Path(f"{database}-shm"),
            Path(f"{database}-journal"),
            database.with_name(f"{database.stem}.kdf.json"),
            database.with_suffix(".rekey.json"),
            database.with_suffix(".restore.json"),
            database.with_suffix(".binding.json"),
            database.with_suffix(".rekey.target"),
            database.with_suffix(".restore.staged"),
            database.with_suffix(".binding.target"),
            database.with_suffix(".pre-rekey.sqlcipher"),
            database.with_suffix(".pre-restore.sqlcipher"),
            database.with_suffix(".pre-binding.sqlcipher"),
        }
        explicit.update(parent_dir.glob("*.sedbbackup"))
        explicit.update(parent_dir.glob(f"{database.name}*"))
        explicit.update(parent_dir.glob(f"{database.stem}.kdf*"))
        explicit.update(parent_dir.glob(f"{database.stem}.*.json"))
        for base in tuple(explicit):
            explicit.update(
                {Path(f"{base}-wal"), Path(f"{base}-shm"), Path(f"{base}-journal")}
            )
        for candidate in explicit:
            resolved = candidate.resolve()
            if resolved.parent == parent_dir and resolved.exists():
                resolved.unlink()
                _log("info", "Removed encrypted database artifact: %s", resolved)

        settings = get_app_settings()
        for kind in (
            "main",
            "backup",
            "pending_main",
            "pending_backup",
            "recovery_main",
            "recovery_backup",
            "device_binding",
        ):
            try:
                cred_logger = None if silent else logger
                credential_store.delete_password_hash(
                    kind,
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
            "Cleared password hashes and current encrypted database artifacts.",
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
    except Exception as exc:
        logging.getLogger(__name__).debug(
            "Logging shutdown failed before log directory cleanup: %s", exc
        )

    try:
        shutil.rmtree(log_dir_path, ignore_errors=False)
    except OSError:
        # Swallow errors silently to avoid leaking wipe events.
        return
