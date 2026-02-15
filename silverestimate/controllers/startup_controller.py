"""Application startup orchestration for authentication and database initialization."""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass
from enum import Enum, auto
from typing import Any, Optional

from PyQt5.QtWidgets import QMessageBox, QWidget

from silverestimate.infrastructure.app_constants import DB_PATH
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
            auth_result = run_authentication(self._logger, parent=self._parent)
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

        if not isinstance(auth_result, AuthenticationResult):
            self._logger.critical(
                "Unexpected authentication result type: %r", auth_result
            )
            return StartupResult(status=StartupStatus.FAILED)
        self._logger.debug(
            "[perf] startup.auth_accepted_ms=%.2f t_unix=%.6f",
            (time.perf_counter() - startup_t0) * 1000.0,
            time.time(),
        )

        db_manager = self._initialize_database(auth_result.password or "")
        if db_manager is None:
            return StartupResult(status=StartupStatus.FAILED)
        return StartupResult(status=StartupStatus.OK, db=db_manager)

    def _initialize_database(self, password: str) -> Optional[Any]:
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
            candidate = db_cls.check_recovery_candidate(DB_PATH)
        except Exception as exc:  # pragma: no cover - defensive logging
            self._logger.error(
                "Recovery candidate check failed: %s", exc, exc_info=True
            )
            candidate = None

        if candidate:
            self._logger.warning("Found recovery candidate: %s", candidate)
            message = (
                "A newer unsaved database state was found from a previous session.\n"
                "Would you like to recover it now?"
            )
            reply = QMessageBox.question(
                self._parent,
                "Recover Unsaved Data",
                message,
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.Yes,
            )
            if reply == QMessageBox.Yes:
                try:
                    if db_cls.recover_encrypt_plain_to_encrypted(
                        candidate,
                        DB_PATH,
                        password,
                        logger=self._logger,
                    ):
                        self._logger.info("Recovery successful; continuing startup")
                    else:
                        self._logger.error(
                            "Recovery failed; continuing with last encrypted state"
                        )
                except Exception as exc:  # pragma: no cover - best effort logging
                    self._logger.error(
                        "Recovery operation raised error: %s", exc, exc_info=True
                    )

        try:
            db_manager = db_cls(DB_PATH, password=password)
            self._logger.info("Database connection established")
            self._logger.debug(
                "[perf] startup.db_ready_ms=%.2f t_unix=%.6f",
                (time.perf_counter() - db_t0) * 1000.0,
                time.time(),
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
