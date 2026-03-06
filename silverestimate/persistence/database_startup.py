"""Startup/open coordination for encrypted database sessions."""

from __future__ import annotations

import logging
from typing import Callable, Optional

from silverestimate.persistence.temp_database_store import TempDatabaseStore

StringSetter = Callable[[str | None], None]
StatusCallback = Callable[[], str]
VoidCallback = Callable[[], None]


class DatabaseStartupCoordinator:
    """Coordinate temp-db creation, decrypt/open flow, and init cleanup."""

    def __init__(
        self,
        *,
        temp_store: TempDatabaseStore,
        set_temp_db_path: StringSetter,
        decrypt_db: StatusCallback,
        connect_temp_db: VoidCallback,
        setup_database: VoidCallback,
        cleanup_temp_db: VoidCallback,
        reset_connection_state: VoidCallback,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        self._temp_store = temp_store
        self._set_temp_db_path = set_temp_db_path
        self._decrypt_db = decrypt_db
        self._connect_temp_db = connect_temp_db
        self._setup_database = setup_database
        self._cleanup_temp_db = cleanup_temp_db
        self._reset_connection_state = reset_connection_state
        self._logger = logger or logging.getLogger(__name__)

    def initialize(self) -> None:
        """Create the temp DB, open/decrypt it, and run schema setup."""
        try:
            temp_path = self._temp_store.create()
            self._set_temp_db_path(str(temp_path))
            self._temp_store.register_for_recovery()
            self._logger.debug("Using temporary database at: %s", temp_path)

            decryption_result = self._decrypt_db()
            if decryption_result == "success":
                self._logger.info("Database decrypted successfully")
                self._connect_temp_db()
                self._setup_database()
                return
            if decryption_result == "first_run":
                self._logger.info(
                    "Encrypted database not found or empty. Initializing new database."
                )
                self._connect_temp_db()
                self._setup_database()
                return

            self._logger.critical(
                "Database decryption failed. Incorrect password or corrupted file."
            )
            raise Exception(
                "Database decryption failed. Incorrect password or corrupted file."
            )
        except Exception as exc:
            self._logger.critical(
                "Failed to initialize DatabaseManager: %s",
                exc,
                exc_info=True,
            )
            self._cleanup_temp_db()
            self._reset_connection_state()
            raise


__all__ = ["DatabaseStartupCoordinator"]
