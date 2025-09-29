"""Application startup orchestration for authentication and database initialization."""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from enum import Enum, auto
from typing import Optional

from PyQt5.QtWidgets import QMessageBox

from silverestimate.infrastructure.app_constants import DB_PATH
from silverestimate.persistence.database_manager import DatabaseManager
from silverestimate.services.auth_service import perform_data_wipe, run_authentication


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
    db: Optional[DatabaseManager] = None


class StartupController:
    """Coordinate authentication, optional wipes, and database setup."""

    def __init__(self, *, logger: Optional[logging.Logger] = None) -> None:
        self._logger = logger or logging.getLogger(__name__)

    def authenticate_and_prepare(self) -> StartupResult:
        """Authenticate the operator and return a initialized database manager."""
        try:
            auth_result = run_authentication(self._logger)
        except Exception as exc:  # pragma: no cover - defensive UX handling
            self._logger.critical("Authentication failed with error: %s", exc, exc_info=True)
            QMessageBox.critical(
                None,
                "Authentication Error",
                f"Failed to authenticate: {exc}\n\nThe application will now exit.",
            )
            return StartupResult(status=StartupStatus.FAILED)

        if auth_result == "wipe":
            self._logger.warning("Data wipe requested by operator")
            try:
                if perform_data_wipe(db_path=DB_PATH, logger=self._logger):
                    self._logger.info("Data wipe completed; exiting application")
                    return StartupResult(status=StartupStatus.WIPED)
                self._logger.critical("Data wipe failed")
            except Exception as exc:  # pragma: no cover - UX fallback
                self._logger.critical("Data wipe raised exception: %s", exc, exc_info=True)
                QMessageBox.critical(
                    None,
                    "Data Wipe Error",
                    f"Failed to wipe data: {exc}\n\nThe application will now exit.",
                )
                return StartupResult(status=StartupStatus.FAILED)
            return StartupResult(status=StartupStatus.FAILED)

        if not auth_result:
            self._logger.info("Authentication cancelled or failed; exiting startup sequence")
            return StartupResult(status=StartupStatus.CANCELLED)

        db_manager = self._initialize_database(auth_result)
        if db_manager is None:
            return StartupResult(status=StartupStatus.FAILED)
        return StartupResult(status=StartupStatus.OK, db=db_manager)

    def _initialize_database(self, password: str) -> Optional[DatabaseManager]:
        """Create the encrypted database connection, handling recovery prompts."""
        try:
            os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
        except OSError as exc:
            self._logger.critical("Failed to prepare database directory: %s", exc, exc_info=True)
            QMessageBox.critical(
                None,
                "Database Error",
                f"Unable to prepare database directory: {exc}",
            )
            return None

        try:
            candidate = DatabaseManager.check_recovery_candidate(DB_PATH)
        except Exception as exc:  # pragma: no cover - defensive logging
            self._logger.error("Recovery candidate check failed: %s", exc, exc_info=True)
            candidate = None

        if candidate:
            self._logger.warning("Found recovery candidate: %s", candidate)
            message = (
                "A newer unsaved database state was found from a previous session.\n"
                "Would you like to recover it now?"
            )
            reply = QMessageBox.question(
                None,
                "Recover Unsaved Data",
                message,
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.Yes,
            )
            if reply == QMessageBox.Yes:
                try:
                    if DatabaseManager.recover_encrypt_plain_to_encrypted(
                        candidate,
                        DB_PATH,
                        password,
                        logger=self._logger,
                    ):
                        self._logger.info("Recovery successful; continuing startup")
                    else:
                        self._logger.error("Recovery failed; continuing with last encrypted state")
                except Exception as exc:  # pragma: no cover - best effort logging
                    self._logger.error("Recovery operation raised error: %s", exc, exc_info=True)

        try:
            db_manager = DatabaseManager(DB_PATH, password=password)
            self._logger.info("Database connection established")
            return db_manager
        except Exception as exc:
            self._logger.critical("Failed to connect to encrypted database: %s", exc, exc_info=True)
            error_details = (
                f"Failed to connect to encrypted database: {exc}\n\n"
                "This could be due to:\n"
                "- Incorrect password\n"
                "- Corrupted database file\n"
                "- Missing permissions\n\n"
                "The application cannot continue without a valid database connection."
            )
            QMessageBox.critical(None, "Database Error", error_details)
            return None
