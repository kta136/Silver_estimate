"""Application startup orchestration for authentication and database initialization."""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass
from enum import Enum, auto
from pathlib import Path
from typing import Any, Optional

from PySide6.QtWidgets import QMessageBox, QWidget

from silverestimate.infrastructure.app_constants import DB_PATH
from silverestimate.security import credential_store
from silverestimate.security.credential_store import CredentialStoreError
from silverestimate.services.auth_service import (
    AuthenticationResult,
    perform_data_wipe,
    run_authentication,
)

# Lazy-loaded and monkeypatch-friendly alias used by tests.
DatabaseManager = None


def _resolve_database_manager():
    global DatabaseManager
    if DatabaseManager is None:
        from silverestimate.persistence.database_manager import DatabaseManager as _DBM

        DatabaseManager = _DBM
    return DatabaseManager


class StartupStatus(Enum):
    """Possible outcomes when preparing the application."""

    OK = auto()
    CANCELLED = auto()
    WIPED = auto()
    FAILED = auto()


@dataclass
class StartupResult:
    """Structured result returned by :class:`StartupController`."""

    status: StartupStatus
    db: Optional[Any] = None
    silent_wipe: bool = False


class StartupController:
    """Coordinate authentication, optional wipes, and database setup."""

    def __init__(
        self,
        *,
        logger: Optional[logging.Logger] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        self._logger = logger or logging.getLogger(__name__)
        self._parent = parent

    def authenticate_and_prepare(self) -> StartupResult:
        """Authenticate the operator and return a initialized database manager."""
        startup_t0 = time.perf_counter()
        self._logger.debug(
            "[perf] startup.auth_flow_start t_unix=%.6f",
            time.time(),
        )
        try:
            auth_result = run_authentication(
                self._logger,
                parent=self._parent,
                db_path=DB_PATH,
            )
        except Exception as exc:  # pragma: no cover - defensive UX handling
            self._logger.critical(
                "Authentication failed with error: %s", exc, exc_info=True
            )
            QMessageBox.critical(
                self._parent,
                "Authentication Error",
                f"Failed to authenticate: {exc}\n\nThe application will now exit.",
            )
            return StartupResult(status=StartupStatus.FAILED)

        if isinstance(auth_result, AuthenticationResult) and auth_result.is_wipe:
            silent = auth_result.silent
            if not silent:
                self._logger.warning("Data wipe requested by operator")
            try:
                if perform_data_wipe(
                    db_path=DB_PATH,
                    logger=self._logger,
                    silent=silent,
                    parent=self._parent,
                ):
                    if not silent:
                        self._logger.info("Data wipe completed; exiting application")
                    return StartupResult(status=StartupStatus.WIPED, silent_wipe=silent)
                if not silent:
                    self._logger.critical("Data wipe failed")
            except Exception as exc:  # pragma: no cover - UX fallback
                if not silent:
                    self._logger.critical(
                        "Data wipe raised exception: %s", exc, exc_info=True
                    )
                QMessageBox.critical(
                    self._parent,
                    "Data Wipe Error",
                    f"Failed to wipe data: {exc}\n\nThe application will now exit.",
                )
                return StartupResult(status=StartupStatus.FAILED)
            return StartupResult(status=StartupStatus.FAILED)

        if auth_result is None:
            self._logger.info(
                "Authentication cancelled or failed; exiting startup sequence"
            )
            return StartupResult(status=StartupStatus.CANCELLED)
        self._logger.debug(
            "[perf] startup.auth_accepted_ms=%.2f t_unix=%.6f",
            (time.perf_counter() - startup_t0) * 1000.0,
            time.time(),
        )

        if not self._protect_pending_credentials(auth_result):
            return StartupResult(status=StartupStatus.FAILED)

        try:
            device_secret = self._prepare_device_binding()
        except CredentialStoreError as exc:
            self._logger.critical(
                "Machine-bound database secret is unavailable: %s",
                exc,
                exc_info=True,
            )
            QMessageBox.critical(
                self._parent,
                "Device Binding Error",
                f"The database cannot be opened on this PC: {exc}",
            )
            return StartupResult(status=StartupStatus.FAILED)

        db_manager = self._initialize_database(
            auth_result.password or "",
            device_secret,
        )
        if db_manager is None:
            return StartupResult(status=StartupStatus.FAILED)
        if auth_result.pending_main_hash and auth_result.pending_backup_hash:
            try:
                credential_store.set_password_hash(
                    "main", auth_result.pending_main_hash, logger=self._logger
                )
                credential_store.set_password_hash(
                    "backup", auth_result.pending_backup_hash, logger=self._logger
                )
                for kind in (
                    "pending_main",
                    "pending_backup",
                    "recovery_main",
                    "recovery_backup",
                ):
                    credential_store.delete_password_hash(kind, logger=self._logger)
            except CredentialStoreError as exc:
                db_manager.close()
                perform_data_wipe(
                    db_path=DB_PATH,
                    logger=self._logger,
                    silent=True,
                    parent=self._parent,
                )
                QMessageBox.critical(
                    self._parent,
                    "Setup Error",
                    f"The database was created but credentials could not be committed: {exc}",
                )
                return StartupResult(status=StartupStatus.FAILED)
            QMessageBox.information(
                self._parent, "Setup Complete", "Passwords created successfully."
            )
        elif auth_result.rollback_pending_credentials:
            for kind in (
                "pending_main",
                "pending_backup",
                "recovery_main",
                "recovery_backup",
            ):
                try:
                    credential_store.delete_password_hash(kind, logger=self._logger)
                except CredentialStoreError:
                    self._logger.warning(
                        "Could not clear rolled-back pending credential %s", kind
                    )
        return StartupResult(status=StartupStatus.OK, db=db_manager)

    def _protect_pending_credentials(
        self,
        auth_result: AuthenticationResult,
    ) -> bool:
        """Persist recoverable hashes before a first database is created."""
        if not (
            auth_result.pending_main_hash and auth_result.pending_backup_hash
        ):
            return True
        try:
            credential_store.set_password_hash(
                "pending_main",
                auth_result.pending_main_hash,
                logger=self._logger,
            )
            credential_store.set_password_hash(
                "pending_backup",
                auth_result.pending_backup_hash,
                logger=self._logger,
            )
        except CredentialStoreError as exc:
            QMessageBox.critical(
                self._parent,
                "Setup Error",
                f"Pending credentials could not be protected: {exc}",
            )
            return False
        return True

    def _prepare_device_binding(self) -> bytes:
        """Load the local secret, creating it only for new or legacy-local data."""
        secret = credential_store.get_device_binding_secret()
        if secret is not None:
            return credential_store.create_device_binding_secret(logger=self._logger)
        database = Path(DB_PATH).resolve()
        legacy_metadata = database.with_name(f"{database.stem}.kdf.json")
        if database.is_file() and not legacy_metadata.is_file():
            raise CredentialStoreError(
                "the required device-binding secret is missing; copied databases "
                "cannot be registered to a different PC"
            )
        return credential_store.create_device_binding_secret(logger=self._logger)

    def _initialize_database(
        self,
        password: str,
        device_secret: bytes,
    ) -> Optional[Any]:
        """Create the encrypted database connection, handling recovery prompts."""
        db_t0 = time.perf_counter()
        db_cls = _resolve_database_manager()
        try:
            os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
        except OSError as exc:
            self._logger.critical(
                "Failed to prepare database directory: %s", exc, exc_info=True
            )
            QMessageBox.critical(
                self._parent,
                "Database Error",
                f"Unable to prepare database directory: {exc}",
            )
            return None

        try:
            db_manager = db_cls(
                DB_PATH,
                password=password,
                device_secret=device_secret,
            )
            self._start_background_preload(db_manager)
            self._logger.info("Database connection established")
            self._logger.debug(
                "[perf] startup.db_ready_ms=%.2f t_unix=%.6f",
                (time.perf_counter() - db_t0) * 1000.0,
                time.time(),
            )
            self._logger.info(
                '[telemetry] {"metric":"startup.database_initialize_ms",'
                '"duration_ms":%.3f}',
                (time.perf_counter() - db_t0) * 1000.0,
            )
            return db_manager
        except Exception as exc:
            self._logger.critical(
                "Failed to connect to encrypted database: %s", exc, exc_info=True
            )
            error_details = (
                f"Failed to connect to encrypted database: {exc}\n\n"
                "This could be due to:\n"
                "- Incorrect password\n"
                "- Corrupted database file\n"
                "- Missing permissions\n\n"
                "The application cannot continue without a valid database connection."
            )
            QMessageBox.critical(self._parent, "Database Error", error_details)
            return None

    def _start_background_preload(self, db_manager: Any) -> None:
        """Warm caches during startup so MainWindow stays UI-focused."""
        try:
            db_manager.start_preload_item_cache()
        except Exception as exc:
            self._logger.debug("Item cache preload failed during startup: %s", exc)
