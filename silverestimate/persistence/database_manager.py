#!/usr/bin/env python
import logging
import os
import shutil
import sqlite3
from typing import Optional

from silverestimate.infrastructure import settings as settings_module
from silverestimate.infrastructure.db_session import ConnectionThreadGuard
from silverestimate.infrastructure.item_cache import ItemCacheController
from silverestimate.infrastructure.settings import get_app_settings
from silverestimate.persistence.database_lifecycle import DatabaseLifecycleCoordinator
from silverestimate.persistence.database_repository_facade import (
    DatabaseRepositoryFacadeMixin,
)
from silverestimate.persistence.database_startup import DatabaseStartupCoordinator
from silverestimate.persistence.encrypted_database_store import (
    DecryptionOutcome,
    EncryptedDatabaseStore,
)
from silverestimate.persistence.sqlite_database_runtime import SqliteDatabaseRuntime
from silverestimate.persistence.temp_database_store import TempDatabaseStore
from silverestimate.security import encryption as crypto_utils
from silverestimate.security.encrypted_envelope import (
    Argon2Metadata,
    EnvelopeError,
    is_current_envelope,
)

# Constants
KDF_ITERATIONS = crypto_utils.DEFAULT_KDF_ITERATIONS  # PBKDF2 iteration count


class _TempDatabaseStore(TempDatabaseStore):
    """Compatibility wrapper keeping tests and call sites stable."""

    def __init__(
        self,
        *,
        logger: Optional[logging.Logger] = None,
        store_metadata: bool = True,
        encrypted_db_path: str | None = None,
    ) -> None:
        super().__init__(
            logger=logger,
            store_metadata=store_metadata,
            encrypted_db_path=encrypted_db_path,
            settings_factory=get_app_settings,
        )


class DatabaseManager(DatabaseRepositoryFacadeMixin):
    """
    Manages SQLite database operations for the Silver Estimation App,
    including file-level encryption/decryption.
    """

    def __init__(self, db_path, password):
        """
        Initialize the database manager. Decrypts the database to a temporary
        file or creates a new encrypted database if it doesn't exist.
        """
        # Set up logging
        self.logger = logging.getLogger(__name__)
        self.logger.info(f"Initializing DatabaseManager for {db_path}")

        self.encrypted_db_path = db_path
        self._envelope_metadata_error: EnvelopeError | None = None
        try:
            envelope_metadata = EncryptedDatabaseStore.read_metadata(db_path)
        except EnvelopeError as exc:
            envelope_metadata = None
            self._envelope_metadata_error = exc
        self._argon2_metadata = (
            envelope_metadata.argon2
            if envelope_metadata is not None
            else Argon2Metadata(
                salt=self._get_or_create_salt(),
                time_cost=crypto_utils.DEFAULT_ARGON2_TIME_COST,
                memory_cost_kib=crypto_utils.DEFAULT_ARGON2_MEMORY_COST_KIB,
                parallelism=crypto_utils.DEFAULT_ARGON2_PARALLELISM,
            )
        )
        self.salt = self._argon2_metadata.salt
        self._preferred_key = self._derive_key(password, self.salt)
        self._password = password
        self._legacy_key: bytes | None = None
        self.key = self._preferred_key
        self._pending_kdf_migration = False
        self._pending_envelope_migration = False
        self._active_kdf_algorithm = crypto_utils.PREFERRED_KDF_ALGORITHM
        self._encrypted_store = EncryptedDatabaseStore(
            self.encrypted_db_path,
            key=self.key,
            argon2_metadata=self._argon2_metadata,
            logger=self.logger,
        )
        self.temp_db_path = None  # Will hold the temporary file path
        self.conn = None
        self.cursor = None
        self.last_error = None
        self._session = ConnectionThreadGuard(logger=self.logger)
        self._sqlite_runtime = SqliteDatabaseRuntime(
            logger=self.logger,
            session=self._session,
        )
        # Optional status callbacks registered by the application shell.
        self._on_flush_queued = None
        self._on_flush_done = None
        self._lifecycle = DatabaseLifecycleCoordinator(
            encrypted_store=self._encrypted_store,
            connection_getter=lambda: self.conn,
            temp_db_path_getter=lambda: self.temp_db_path,
            key_getter=lambda: self.key,
            key_setter=lambda value: setattr(self, "key", value),
            commit=lambda: self._session.commit_if_owner(self.conn),
            checkpoint=self._checkpoint_wal,
            logger=self.logger,
            on_queued_getter=lambda: self._on_flush_queued,
            on_done_getter=lambda: self._on_flush_done,
        )
        self._item_cache_controller = ItemCacheController(logger=self.logger)

        self._items_repo = None
        self._estimates_repo = None
        self._silver_bars_repo = None

        # Ensure directory for encrypted DB exists
        os.makedirs(os.path.dirname(self.encrypted_db_path), exist_ok=True)

        recovery_enabled = getattr(settings_module, "ENABLE_TEMP_DB_RECOVERY", False)
        self._recovery_enabled = recovery_enabled
        self._temp_store = _TempDatabaseStore(
            logger=self.logger,
            store_metadata=recovery_enabled,
            encrypted_db_path=self.encrypted_db_path,
        )
        self._startup = DatabaseStartupCoordinator(
            temp_store=self._temp_store,
            set_temp_db_path=lambda value: setattr(self, "temp_db_path", value),
            decrypt_db=self._decrypt_db,
            connect_temp_db=self._connect_temp_db,
            setup_database=self.setup_database,
            cleanup_temp_db=self._cleanup_temp_db,
            reset_connection_state=self._discard_connection_after_init_failure,
            logger=self.logger,
        )
        self._startup.initialize()
        self._migrate_legacy_kdf_if_needed()

    @property
    def items_repo(self):
        """Lazy-load the ItemsRepository instance."""
        if self._items_repo is None:
            from silverestimate.persistence.items_repository import ItemsRepository

            self._items_repo = ItemsRepository(self)
        return self._items_repo

    @property
    def estimates_repo(self):
        """Lazy-load the EstimatesRepository instance."""
        if self._estimates_repo is None:
            from silverestimate.persistence.estimates_repository import (
                EstimatesRepository,
            )

            self._estimates_repo = EstimatesRepository(self)
        return self._estimates_repo

    @property
    def silver_bars_repo(self):
        """Lazy-load the SilverBarsRepository instance."""
        if self._silver_bars_repo is None:
            from silverestimate.persistence.silver_bars_repository import (
                SilverBarsRepository,
            )

            self._silver_bars_repo = SilverBarsRepository(self)
        return self._silver_bars_repo

    @property
    def item_cache_controller(self):
        return self._item_cache_controller

    def _connect_temp_db(self):
        """Connects sqlite3 to the temporary database file."""
        assert self.temp_db_path is not None
        state = self._sqlite_runtime.connect(self.temp_db_path)
        self.conn = state.conn
        self.cursor = state.cursor
        self._c_get_item_by_code = state.get_item_by_code_cursor
        self._sql_get_item_by_code = state.get_item_by_code_sql
        self._c_insert_estimate_item = state.insert_estimate_item_cursor
        self._sql_insert_estimate_item = state.insert_estimate_item_sql

    def _get_or_create_salt(self):
        """Retrieves the salt from QSettings or creates and saves a new one."""
        return EncryptedDatabaseStore.get_or_create_salt(
            logger=self.logger,
            settings_factory=get_app_settings,
        )

    def _derive_key(
        self,
        password,
        salt,
        *,
        algorithm=crypto_utils.PREFERRED_KDF_ALGORITHM,
    ):
        """Derive a 32-byte AES key from the password and salt."""
        return crypto_utils.derive_key(
            password,
            salt,
            algorithm=algorithm,
            iterations=KDF_ITERATIONS,
            time_cost=self._argon2_metadata.time_cost,
            memory_cost_kib=self._argon2_metadata.memory_cost_kib,
            parallelism=self._argon2_metadata.parallelism,
            logger=self.logger,
        )

    def set_flush_status_callbacks(self, *, on_queued=None, on_done=None) -> None:
        """Register application-shell callbacks for debounced flush status."""
        self._on_flush_queued = on_queued
        self._on_flush_done = on_done

    def _encrypt_db(self):
        """Encrypt the temporary DB file and atomically save it to the encrypted path."""
        return self._lifecycle.encrypt_current_state()

    def reencrypt_with_new_password(self, new_password: str) -> bool:
        """Re-encrypt the encrypted DB using a new password-derived key.

        Writes atomically to the encrypted store. On success, updates in-memory
        password/key so subsequent flushes use the new key. On failure, keeps
        the old key/password and returns False.
        """
        return self._lifecycle.reencrypt_with_new_password(
            new_password,
            salt=self.salt,
            derive_key=self._derive_key,
        )

    def _decrypt_db(self):
        """Decrypt the database, falling back to the legacy KDF when needed."""
        preferred_status = self._decrypt_db_with_key(
            self._preferred_key,
            crypto_utils.PREFERRED_KDF_ALGORITHM,
        )
        if preferred_status != "error":
            if (
                preferred_status == "success"
                and self._encrypted_store.last_decryption_result.outcome
                == DecryptionOutcome.LEGACY
            ):
                self._pending_envelope_migration = True
            return preferred_status

        if self._envelope_metadata_error is not None or is_current_envelope(
            self.encrypted_db_path
        ):
            return preferred_status

        self.logger.warning(
            "Preferred KDF decryption failed; trying legacy %s for migration",
            crypto_utils.LEGACY_KDF_ALGORITHM,
        )
        if self._legacy_key is None:
            self._legacy_key = self._derive_key(
                self._password,
                self.salt,
                algorithm=crypto_utils.LEGACY_KDF_ALGORITHM,
            )
        legacy_key = self._legacy_key
        assert legacy_key is not None
        legacy_status = self._decrypt_db_with_key(
            legacy_key,
            crypto_utils.LEGACY_KDF_ALGORITHM,
        )
        if legacy_status == "success":
            self.key = legacy_key
            self._active_kdf_algorithm = crypto_utils.LEGACY_KDF_ALGORITHM
            self._pending_kdf_migration = True
            self._pending_envelope_migration = True
            self.logger.warning(
                "Database opened using legacy %s; migration to %s is pending.",
                crypto_utils.LEGACY_KDF_ALGORITHM,
                crypto_utils.PREFERRED_KDF_ALGORITHM,
            )
            return legacy_status

        self._cleanup_temp_db(keep_file=False)
        return legacy_status

    def _decrypt_db_with_key(self, key: bytes, algorithm: str) -> str:
        """Attempt a database decrypt using a specific derived key."""
        self.key = key
        self._active_kdf_algorithm = algorithm
        self._encrypted_store.set_key(key)
        return self._encrypted_store.decrypt_to_path(self.temp_db_path)

    def _migrate_legacy_kdf_if_needed(self) -> None:
        """Rewrite authenticated legacy payloads into the current envelope."""
        if not (self._pending_kdf_migration or self._pending_envelope_migration):
            return

        self.logger.info(
            "Migrating encrypted database from %s to %s",
            crypto_utils.LEGACY_KDF_ALGORITHM,
            crypto_utils.PREFERRED_KDF_ALGORITHM,
        )
        backup_path = f"{self.encrypted_db_path}.legacy.bak"
        try:
            if not os.path.exists(backup_path):
                shutil.copy2(self.encrypted_db_path, backup_path)
        except OSError as exc:
            self.logger.error("Could not create encrypted migration backup: %s", exc)
            return
        self.key = self._preferred_key
        self._active_kdf_algorithm = crypto_utils.PREFERRED_KDF_ALGORITHM

        if self._encrypt_db() and self._encrypted_store.verify_current_envelope():
            self._pending_kdf_migration = False
            self._pending_envelope_migration = False
            try:
                os.remove(backup_path)
            except OSError as exc:
                self.logger.warning(
                    "Could not remove verified encrypted migration backup: %s", exc
                )
            self.logger.info(
                "Encrypted database migrated and verified successfully to %s",
                crypto_utils.PREFERRED_KDF_ALGORITHM,
            )
            return

        try:
            shutil.copy2(backup_path, self.encrypted_db_path)
        except OSError as exc:
            self.logger.critical(
                "Failed to restore encrypted migration backup: %s", exc
            )
        self.key = self._preferred_key
        self._active_kdf_algorithm = crypto_utils.PREFERRED_KDF_ALGORITHM
        self.logger.warning(
            "Encrypted database migration verification failed; the authenticated legacy backup was retained.",
        )

    def _cleanup_temp_db(self, keep_file=False):
        """Safely deletes the temporary database file."""
        if getattr(self, "_temp_store", None) is not None:
            self._temp_store.cleanup(preserve=keep_file)
        if not keep_file:
            self.temp_db_path = None

    def _table_exists(self, table_name):
        """Check if a table exists in the database."""
        return self._sqlite_runtime.table_exists(self.cursor, table_name)

    def _column_exists(self, table_name, column_name):
        """Check if a column exists in a table."""
        return self._sqlite_runtime.column_exists(
            self.cursor,
            table_name,
            column_name,
        )

    def _is_column_unique(self, table_name, column_name):
        """Check if a column has a UNIQUE constraint via PK or unique index."""
        return self._sqlite_runtime.is_column_unique(
            self.cursor,
            table_name,
            column_name,
        )

    def _check_schema_version(self):
        """Check if the database has the schema version table and current version."""
        return self._sqlite_runtime.check_schema_version(self.conn, self.cursor)

    def _update_schema_version(self, new_version):
        """Update the schema version in the database."""
        return self._sqlite_runtime.update_schema_version(
            self.conn,
            self.cursor,
            new_version,
        )

    def setup_database(self):
        """Create/update the necessary tables in the temporary database."""
        from silverestimate.persistence import migrations as persistence_migrations

        persistence_migrations.run_schema_setup(self)

    # --- Utility Methods ---
    def drop_tables(self):
        """Drops all known application tables from the temporary database."""
        if not self.conn or not self.cursor:
            return False
        # Added schema_version to the list
        tables = [
            "estimate_items",
            "estimates",
            "items",
            "bar_transfers",
            "silver_bars",
            "silver_bar_lists",
            "schema_version",
        ]
        try:
            self.logger.warning("Dropping all application tables from database")
            self.conn.execute("BEGIN TRANSACTION")
            for table in tables:
                self.logger.debug(f"Dropping table {table}")
                self.cursor.execute(f"DROP TABLE IF EXISTS {table}")
            self.conn.commit()
            self.logger.info("All application tables dropped successfully")
            return True
        except sqlite3.Error as e:
            self.conn.rollback()
            self.logger.error(
                f"Database error dropping tables: {str(e)}", exc_info=True
            )
            return False

    def close(self):
        """Encrypts the temporary DB, closes the connection, and cleans up."""
        self._lifecycle.close(
            close_connection=self._close_connection,
            cleanup_temp_db=lambda preserve: self._cleanup_temp_db(keep_file=preserve),
            preserve_plaintext_on_failure=self._recovery_enabled,
        )

    def flush_to_encrypted(self):
        """Flush current temp DB state to encrypted file safely (atomic replace)."""
        return self._lifecycle.flush_to_encrypted()

    def request_flush(self, delay_seconds: float = 2.0):
        """Debounce and asynchronously flush the temp DB to the encrypted file."""
        self._lifecycle.request_flush(delay_seconds=delay_seconds)

    def _close_connection(self) -> None:
        """Close the active SQLite connection and reset session state."""
        if self.conn is None:
            return
        self.conn.close()
        self.conn = None
        self.cursor = None
        try:
            self._session.clear()
        except Exception as exc:
            self.logger.debug("Failed to clear connection thread guard: %s", exc)

    def _discard_connection_after_init_failure(self) -> None:
        """Best-effort cleanup when initialization fails mid-startup."""
        try:
            self._close_connection()
        except Exception:
            self.conn = None
            self.cursor = None
            try:
                self._session.clear()
            except Exception as clear_error:
                self.logger.debug(
                    "Failed to clear connection thread guard after init failure: %s",
                    clear_error,
                )

    # --- Startup Recovery Utilities ---
    def _snapshot_temp_db_copy(self):
        """Create a consistent snapshot of the temp DB using SQLite backup API.

        Returns path to the snapshot file, or None if backup failed.
        """
        return self._encrypted_store.snapshot_copy(self.temp_db_path)

    def _checkpoint_wal(self):
        """Force a WAL checkpoint so the main DB file contains latest data.

        Uses a short-lived separate connection so it is safe from any thread.
        """
        return self._encrypted_store.checkpoint_wal(self.temp_db_path)

    @staticmethod
    def check_recovery_candidate(encrypted_db_path):
        """Return path to prior temp DB if it exists and is newer than encrypted file."""
        return EncryptedDatabaseStore.check_recovery_candidate(
            encrypted_db_path,
            settings_factory=get_app_settings,
        )

    @staticmethod
    def recover_encrypt_plain_to_encrypted(
        plain_temp_path, encrypted_db_path, password, logger=None
    ):
        """Encrypt a plaintext SQLite DB file to the encrypted DB atomically using the app's KDF.

        Returns True on success, False otherwise.
        """
        return EncryptedDatabaseStore.recover_encrypt_plain_to_encrypted(
            plain_temp_path,
            encrypted_db_path,
            password,
            logger=logger,
            settings_factory=get_app_settings,
            iterations=KDF_ITERATIONS,
        )

    @staticmethod
    def discard_recovery_candidate(plain_temp_path, encrypted_db_path, logger=None):
        """Securely discard a declined marked recovery candidate."""
        return EncryptedDatabaseStore.discard_recovery_candidate(
            plain_temp_path,
            encrypted_db_path,
            logger=logger,
            settings_factory=get_app_settings,
        )
