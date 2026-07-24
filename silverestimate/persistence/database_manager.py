#!/usr/bin/env python
"""Direct SQLCipher database lifecycle and repository facade."""

from __future__ import annotations

import hashlib
import json
import logging
import os
import shutil
import tempfile
import zipfile
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum, auto
from pathlib import Path
from typing import Any

from silverestimate.infrastructure.db_session import ConnectionThreadGuard
from silverestimate.infrastructure.item_cache import ItemCacheController
from silverestimate.persistence.database_driver import (
    SQLCIPHER_SALT_BYTES,
    Connection,
    DatabaseError,
    DriverIdentity,
    Error,
    ReadConnection,
    SqlCipherConnectionBroker,
    export_database,
)
from silverestimate.persistence.database_repository_facade import (
    DatabaseRepositoryFacadeMixin,
)
from silverestimate.persistence.storage_metadata import (
    BackupManifest,
    BindingMigrationJournal,
    KdfMetadata,
    RekeyJournal,
    RestoreJournal,
    StorageMetadataError,
    read_json,
    sha256_file,
    write_journal,
)
from silverestimate.security import encryption as crypto_utils

SQLITE_HEADER = b"SQLite format 3\x00"
BACKUP_FORMAT_VERSION = 2
JOURNAL_VERSION = 2
BINDING_MIGRATION_VERSION = 1


class StorageFormat(Enum):
    MISSING = auto()
    PLAINTEXT_SQLITE = auto()
    SQLCIPHER = auto()


class DatabaseOpenStatus(Enum):
    CREATED = auto()
    OPENED = auto()
    RESTORE_ACTIVATED = auto()
    MIGRATED_TO_DEVICE_BOUND = auto()


class MaintenanceStatus(Enum):
    SUCCESS = auto()
    ROLLED_BACK = auto()
    STAGED_RESTART_REQUIRED = auto()
    RECOVERY_REQUIRED = auto()


@dataclass(frozen=True)
class MaintenanceOutcome:
    status: MaintenanceStatus
    message: str
    path: str | None = None


class DatabaseManager(DatabaseRepositoryFacadeMixin):
    """Manage a live SQLCipher database without plaintext working snapshots."""

    def __init__(self, db_path: str, password: str, *, device_secret: bytes):
        self.logger = logging.getLogger(__name__)
        self.database_path = str(Path(db_path).resolve())
        if len(device_secret) != crypto_utils.DEVICE_BINDING_BYTES:
            raise ValueError("A valid 32-byte device-binding secret is required")
        self._device_secret = bytes(device_secret)
        self.last_error: str | None = None
        self.conn: Connection | None = None
        self.cursor: Any | None = None
        self._session = ConnectionThreadGuard(logger=self.logger)
        self._item_cache_controller = ItemCacheController(logger=self.logger)
        self._items_repo: Any | None = None
        self._estimates_repo: Any | None = None
        self._silver_bars_repo: Any | None = None
        self.database_salt: bytes | None = None
        self._path = Path(self.database_path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._metadata_path = self._path.with_name(f"{self._path.stem}.kdf.json")
        self._rekey_journal = self._path.with_suffix(".rekey.json")
        self._restore_journal = self._path.with_suffix(".restore.json")
        self._binding_journal = self._path.with_suffix(".binding.json")
        self._recover_missing_live_from_journal()
        binding_switch_pending = self._inspect_binding_migration()

        storage_format = self.detect_storage(self._path)
        if storage_format is StorageFormat.PLAINTEXT_SQLITE:
            raise StorageMetadataError(
                "Plaintext SQLite application databases are unsupported"
            )
        if storage_format is StorageFormat.MISSING:
            self.database_salt = os.urandom(SQLCIPHER_SALT_BYTES)
            self.key = self._derive_bound_key(password, self.database_salt)
            self._broker = SqlCipherConnectionBroker(
                self._path,
                self.key,
                database_salt=self.database_salt,
                logger=self.logger,
            )
            self.conn, self.driver_identity = self._broker.open_writer(create=True)
            try:
                self._bind_connection()
                self.setup_database()
                self.validate_database(self.conn)
            except BaseException:
                self._close_connection()
                self._remove_database_family(self._path)
                raise
            self.open_status = DatabaseOpenStatus.CREATED
            return

        self.open_status = DatabaseOpenStatus.OPENED

        if self._metadata_path.is_file() and not binding_switch_pending:
            self._open_legacy_and_migrate(password)
            return

        self.database_salt = self._read_database_salt(self._path)
        self.key = self._derive_bound_key(password, self.database_salt)
        self._activate_pending_restore()
        self._resolve_interrupted_rekey(password)
        self._broker = SqlCipherConnectionBroker(
            self._path,
            self.key,
            database_salt=self.database_salt,
            logger=self.logger,
        )
        self.conn, self.driver_identity = self._broker.open_writer()
        self._bind_connection()
        self.setup_database()
        self.validate_database(self.conn)
        if binding_switch_pending:
            self._finalize_binding_migration()
            self.open_status = DatabaseOpenStatus.MIGRATED_TO_DEVICE_BOUND

    @staticmethod
    def detect_storage(path: str | Path) -> StorageFormat:
        candidate = Path(path)
        if not candidate.exists() or candidate.stat().st_size == 0:
            return StorageFormat.MISSING
        with candidate.open("rb") as stream:
            header = stream.read(len(SQLITE_HEADER))
        if header == SQLITE_HEADER:
            return StorageFormat.PLAINTEXT_SQLITE
        return StorageFormat.SQLCIPHER

    @property
    def items_repo(self):
        if self._items_repo is None:
            from silverestimate.persistence.items_repository import ItemsRepository

            self._items_repo = ItemsRepository(self)
        return self._items_repo

    @property
    def estimates_repo(self):
        if self._estimates_repo is None:
            from silverestimate.persistence.estimates_repository import (
                EstimatesRepository,
            )

            self._estimates_repo = EstimatesRepository(self)
        return self._estimates_repo

    @property
    def silver_bars_repo(self):
        if self._silver_bars_repo is None:
            from silverestimate.persistence.silver_bars_repository import (
                SilverBarsRepository,
            )

            self._silver_bars_repo = SilverBarsRepository(self)
        return self._silver_bars_repo

    @property
    def item_cache_controller(self):
        return self._item_cache_controller

    def _derive_legacy_key(self, password: str, metadata: KdfMetadata) -> bytes:
        return crypto_utils.derive_key(
            password,
            metadata.salt,
            time_cost=metadata.time_cost,
            memory_cost_kib=metadata.memory_cost_kib,
            parallelism=metadata.parallelism,
            logger=self.logger,
        )

    def _derive_bound_key(self, password: str, salt: bytes) -> bytes:
        return crypto_utils.derive_device_bound_key(
            password,
            salt,
            self._device_secret,
            time_cost=KdfMetadata.TIME_COST,
            memory_cost_kib=KdfMetadata.MEMORY_COST_KIB,
            parallelism=KdfMetadata.PARALLELISM,
            logger=self.logger,
        )

    @staticmethod
    def _read_database_salt(path: str | Path) -> bytes:
        candidate = Path(path)
        try:
            with candidate.open("rb") as stream:
                salt = stream.read(SQLCIPHER_SALT_BYTES)
        except OSError as exc:
            raise StorageMetadataError(
                f"Unable to read encrypted database header: {candidate}"
            ) from exc
        if len(salt) != SQLCIPHER_SALT_BYTES or salt == SQLITE_HEADER:
            raise StorageMetadataError("Encrypted database salt is missing or invalid")
        return salt

    def _open_legacy_and_migrate(self, password: str) -> None:
        """Open the former two-file format and atomically bind it to this device."""
        self._metadata = KdfMetadata.read(self._metadata_path)
        self.database_salt = None
        self.key = self._derive_legacy_key(password, self._metadata)
        self._activate_pending_restore()
        self._resolve_interrupted_rekey(password)
        self._broker = SqlCipherConnectionBroker(
            self._path, self.key, logger=self.logger
        )
        self.conn, self.driver_identity = self._broker.open_writer()
        self._bind_connection()
        self.setup_database()
        self.validate_database(self.conn)
        self._migrate_legacy_database(password)

    def _migrate_legacy_database(self, password: str) -> None:
        """Copy-switch a validated legacy database into the device-bound format."""
        target = self._path.with_suffix(".binding.target")
        retained = self._path.with_suffix(".pre-binding.sqlcipher")
        retained_metadata = self._metadata_path.with_suffix(".pre-binding.json")
        new_salt = os.urandom(SQLCIPHER_SALT_BYTES)
        new_key = self._derive_bound_key(password, new_salt)

        assert self.conn is not None
        self.conn.commit()
        self._remove_database_family(target)
        export_database(
            self.conn,
            target,
            new_key,
            target_salt=new_salt,
        )
        self._validate_external(target, new_key, new_salt)
        self._close_connection()

        self._remove_database_family(retained)
        retained_metadata.unlink(missing_ok=True)
        shutil.copy2(self._metadata_path, retained_metadata)
        journal = BindingMigrationJournal(
            version=BINDING_MIGRATION_VERSION,
            phase="ready",
            old_database_sha256=sha256_file(self._path),
            target_sha256=sha256_file(target),
            target_path=str(target),
            retained_path=str(retained),
            retained_metadata_path=str(retained_metadata),
        )
        write_journal(self._binding_journal, journal)

        try:
            os.replace(self._path, retained)
            os.replace(target, self._path)
            self.database_salt = new_salt
            self.key = new_key
            self._broker = SqlCipherConnectionBroker(
                self._path,
                self.key,
                database_salt=self.database_salt,
                logger=self.logger,
            )
            self.conn, self.driver_identity = self._broker.open_writer()
            self._bind_connection()
            self.setup_database()
            self.validate_database(self.conn)
            self._finalize_binding_migration()
            self.open_status = DatabaseOpenStatus.MIGRATED_TO_DEVICE_BOUND
        except BaseException as exc:
            self.logger.exception(
                "Device-binding migration failed; restoring the legacy database"
            )
            self._close_connection()
            if retained.exists():
                self._remove_database_family(self._path)
                os.replace(retained, self._path)
            if retained_metadata.exists() and not self._metadata_path.exists():
                os.replace(retained_metadata, self._metadata_path)
            retained_metadata.unlink(missing_ok=True)
            self._remove_database_family(target)
            self._binding_journal.unlink(missing_ok=True)
            raise StorageMetadataError(
                "Device-binding migration failed and was rolled back"
            ) from exc

    def _inspect_binding_migration(self) -> bool:
        """Recover or resume an interrupted legacy-to-device-bound switch."""
        if not self._binding_journal.exists():
            return False
        journal = read_json(self._binding_journal)
        if (
            journal.get("version") != BINDING_MIGRATION_VERSION
            or journal.get("phase") != "ready"
        ):
            raise StorageMetadataError("Unsupported device-binding migration journal")
        target = self._validated_journal_path(
            journal,
            "target_path",
            self._path.with_suffix(".binding.target"),
        )
        retained = self._validated_journal_path(
            journal,
            "retained_path",
            self._path.with_suffix(".pre-binding.sqlcipher"),
        )
        retained_metadata = self._validated_journal_path(
            journal,
            "retained_metadata_path",
            self._metadata_path.with_suffix(".pre-binding.json"),
        )
        if not self._path.is_file():
            if not retained.is_file():
                raise StorageMetadataError(
                    "Interrupted device-binding migration has no recoverable database"
                )
            os.replace(retained, self._path)
            if retained_metadata.is_file() and not self._metadata_path.exists():
                os.replace(retained_metadata, self._metadata_path)
            retained_metadata.unlink(missing_ok=True)
            self._remove_database_family(target)
            self._binding_journal.unlink(missing_ok=True)
            return False

        live_sha256 = sha256_file(self._path)
        if live_sha256 == journal.get("old_database_sha256"):
            self._remove_database_family(target)
            self._remove_database_family(retained)
            retained_metadata.unlink(missing_ok=True)
            self._binding_journal.unlink(missing_ok=True)
            return False
        if live_sha256 == journal.get("target_sha256"):
            return True
        if retained.is_file() and sha256_file(retained) == journal.get(
            "old_database_sha256"
        ):
            self._remove_database_family(self._path)
            os.replace(retained, self._path)
            if retained_metadata.is_file() and not self._metadata_path.exists():
                os.replace(retained_metadata, self._metadata_path)
            retained_metadata.unlink(missing_ok=True)
            self._remove_database_family(target)
            self._binding_journal.unlink(missing_ok=True)
            return False
        raise StorageMetadataError(
            "Interrupted device-binding migration cannot be recovered safely"
        )

    def _finalize_binding_migration(self) -> None:
        if not self._binding_journal.exists():
            self._metadata_path.unlink(missing_ok=True)
            return
        journal = read_json(self._binding_journal)
        target = self._validated_journal_path(
            journal,
            "target_path",
            self._path.with_suffix(".binding.target"),
        )
        retained = self._validated_journal_path(
            journal,
            "retained_path",
            self._path.with_suffix(".pre-binding.sqlcipher"),
        )
        retained_metadata = self._validated_journal_path(
            journal,
            "retained_metadata_path",
            self._metadata_path.with_suffix(".pre-binding.json"),
        )
        self._metadata_path.unlink(missing_ok=True)
        retained_metadata.unlink(missing_ok=True)
        self._remove_database_family(retained)
        self._remove_database_family(target)
        self._binding_journal.unlink(missing_ok=True)

    @staticmethod
    def _validated_journal_path(
        journal: dict[str, Any],
        field: str,
        expected: Path,
    ) -> Path:
        candidate = Path(str(journal.get(field, ""))).resolve()
        if candidate != expected.resolve():
            raise StorageMetadataError(f"Unsafe path in operation journal: {field}")
        return candidate

    def _bind_connection(self) -> None:
        assert self.conn is not None
        self._session.attach_to_current_thread()
        self.cursor = self.conn.cursor()
        self._c_get_item_by_code = self.conn.cursor()
        self._sql_get_item_by_code = "SELECT * FROM items WHERE code = ? COLLATE NOCASE"
        self._c_insert_estimate_item = self.conn.cursor()
        self._sql_insert_estimate_item = (
            "INSERT INTO estimate_items "
            "(voucher_no, item_code, item_name, gross, poly, net_wt, purity, "
            "wage_rate, pieces, wage_type, wage, fine, is_return, is_silver_bar, "
            "line_key) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
        )

    def open_read_connection(self, cancel_event: Any | None = None) -> ReadConnection:
        return self._broker.open_read_connection(cancel_event)

    def _table_exists(self, table_name: str) -> bool:
        assert self.cursor is not None
        return (
            self.cursor.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
                (table_name,),
            ).fetchone()
            is not None
        )

    def _column_exists(self, table_name: str, column_name: str) -> bool:
        assert self.cursor is not None
        return any(
            str(row[1]) == column_name
            for row in self.cursor.execute(f"PRAGMA table_info({table_name})")
        )

    def _check_schema_version(self) -> int:
        if not self._table_exists("schema_version"):
            return 0
        assert self.cursor is not None
        row = self.cursor.execute("SELECT MAX(version) FROM schema_version").fetchone()
        return int(row[0]) if row and row[0] is not None else 0

    def _update_schema_version(self, new_version: int) -> bool:
        assert self.conn is not None and self.cursor is not None
        self.cursor.execute(
            "INSERT INTO schema_version(version, applied_date) VALUES (?, ?)",
            (new_version, datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        )
        return True

    def setup_database(self) -> None:
        from silverestimate.persistence import schema

        schema.run_schema_setup(self)

    @staticmethod
    def validate_database(connection: Connection) -> None:
        quick = connection.execute("PRAGMA quick_check").fetchone()
        if not quick or str(quick[0]).lower() != "ok":
            raise DatabaseError(f"SQLCipher quick_check failed: {quick!r}")
        cipher_rows = list(connection.execute("PRAGMA cipher_integrity_check"))
        if cipher_rows and any(str(row[0]).lower() != "ok" for row in cipher_rows):
            raise DatabaseError(f"SQLCipher integrity check failed: {cipher_rows!r}")
        violations = list(connection.execute("PRAGMA foreign_key_check"))
        if violations:
            raise DatabaseError(
                f"Foreign-key validation failed with {len(violations)} violation(s)"
            )
        from silverestimate.persistence.schema import CURRENT_SCHEMA_VERSION

        required_tables = {
            "items",
            "estimates",
            "estimate_items",
            "silver_bars",
            "silver_bar_lists",
            "bar_transfers",
            "schema_version",
        }
        tables = {
            str(row[0])
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        missing_tables = required_tables - tables
        if missing_tables:
            raise DatabaseError(
                f"Application schema is missing tables: {sorted(missing_tables)}"
            )
        version = connection.execute(
            "SELECT MAX(version) FROM schema_version"
        ).fetchone()
        if not version or int(version[0] or 0) != CURRENT_SCHEMA_VERSION:
            raise DatabaseError(
                f"Unsupported application schema version: {version[0] if version else None}"
            )
        required_indexes = {
            "idx_items_code_upper",
            "idx_estimates_history_keyset",
            "idx_estimate_items_voucher_line_key",
            "idx_sbars_status_list_weight_date_id",
            "idx_sbars_voucher_line_key",
        }
        indexes = {
            str(row[0])
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='index'"
            )
        }
        missing_indexes = required_indexes - indexes
        if missing_indexes:
            raise DatabaseError(
                f"Application schema is missing indexes: {sorted(missing_indexes)}"
            )

    def close(self) -> None:
        self._close_connection()

    def _close_connection(self) -> None:
        if self.conn is None:
            return
        try:
            self.conn.commit()
            try:
                self.conn.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone()
            except DatabaseError as exc:
                self.logger.debug("Final WAL checkpoint was deferred: %s", exc)
        finally:
            self.conn.close()
            self.conn = None
            self.cursor = None
            self._session.clear()

    def drop_tables(self) -> bool:
        if self.conn is None or self.cursor is None:
            return False
        tables = (
            "estimate_items",
            "estimates",
            "items",
            "bar_transfers",
            "silver_bars",
            "silver_bar_lists",
            "schema_version",
        )
        try:
            self.conn.execute("BEGIN TRANSACTION")
            for table in tables:
                self.cursor.execute(f"DROP TABLE IF EXISTS {table}")
            self.conn.commit()
            return True
        except Error:
            self.conn.rollback()
            self.logger.exception("Database error dropping tables")
            return False

    def create_encrypted_backup(
        self, destination: str | Path | None = None
    ) -> MaintenanceOutcome:
        destination_path = (
            Path(destination) if destination else self._path.with_suffix(".sedbbackup")
        )
        destination_path = destination_path.resolve()
        with self._broker.maintenance():
            assert self.conn is not None
            self.conn.commit()
            stage_dir = Path(
                tempfile.mkdtemp(
                    prefix=".silverestimate-backup-", dir=destination_path.parent
                )
            )
            try:
                database_copy = stage_dir / "database.sqlcipher"
                assert self.database_salt is not None
                export_database(
                    self.conn,
                    database_copy,
                    self.key,
                    target_salt=self.database_salt,
                )
                self._validate_external(
                    database_copy,
                    self.key,
                    self.database_salt,
                )
                schema_version = self._check_schema_version()
                manifest = BackupManifest(
                    version=BACKUP_FORMAT_VERSION,
                    created_utc=datetime.now(UTC).isoformat(),
                    database_sha256=sha256_file(database_copy),
                    schema_version=schema_version,
                    sqlcipher_version=self.driver_identity.sqlcipher_version,
                    device_binding_fingerprint=(
                        crypto_utils.device_binding_fingerprint(self._device_secret)
                    ),
                )
                manifest_bytes = (
                    json.dumps(
                        manifest.to_dict(), sort_keys=True, separators=(",", ":")
                    )
                    + "\n"
                ).encode()
                manifest_digest = hashlib.sha256(manifest_bytes).hexdigest().encode()
                archive_stage = destination_path.with_suffix(
                    destination_path.suffix + ".tmp"
                )
                with zipfile.ZipFile(
                    archive_stage, "w", compression=zipfile.ZIP_STORED
                ) as archive:
                    archive.write(database_copy, "database.sqlcipher")
                    archive.writestr("manifest.json", manifest_bytes)
                    archive.writestr("manifest.sha256", manifest_digest + b"\n")
                os.replace(archive_stage, destination_path)
            finally:
                shutil.rmtree(stage_dir, ignore_errors=True)
        return MaintenanceOutcome(
            MaintenanceStatus.SUCCESS,
            "Encrypted database backup created and validated",
            str(destination_path),
        )

    def stage_encrypted_restore(
        self, archive_path: str | Path, archive_password: str
    ) -> MaintenanceOutcome:
        archive_path = Path(archive_path).resolve()
        with self._broker.maintenance():
            stage_dir = Path(
                tempfile.mkdtemp(
                    prefix=".silverestimate-restore-", dir=self._path.parent
                )
            )
            try:
                with zipfile.ZipFile(archive_path, "r") as archive:
                    expected_names = {
                        "database.sqlcipher",
                        "manifest.json",
                        "manifest.sha256",
                    }
                    if set(archive.namelist()) != expected_names:
                        raise StorageMetadataError("Backup archive members are invalid")
                    archive.extractall(stage_dir)
                manifest_bytes = (stage_dir / "manifest.json").read_bytes()
                recorded = (stage_dir / "manifest.sha256").read_text().strip()
                if not hashlib.sha256(manifest_bytes).hexdigest() == recorded:
                    raise StorageMetadataError("Backup manifest digest mismatch")
                manifest = read_json(stage_dir / "manifest.json")
                if manifest.get("version") != BACKUP_FORMAT_VERSION:
                    raise StorageMetadataError(
                        "Portable or unsupported database backups cannot be restored "
                        "into a machine-bound installation"
                    )
                expected_binding = crypto_utils.device_binding_fingerprint(
                    self._device_secret
                )
                if manifest.get("device_binding_fingerprint") != expected_binding:
                    raise StorageMetadataError(
                        "This database backup belongs to a different PC"
                    )
                archived_db = stage_dir / "database.sqlcipher"
                if sha256_file(archived_db) != manifest.get("database_sha256"):
                    raise StorageMetadataError("Backup database digest mismatch")
                backup_salt = self._read_database_salt(archived_db)
                backup_key = self._derive_bound_key(archive_password, backup_salt)
                source_broker = SqlCipherConnectionBroker(
                    archived_db,
                    backup_key,
                    database_salt=backup_salt,
                )
                source, _ = source_broker.open_writer()
                staged = self._path.with_suffix(".restore.staged")
                self._remove_database_family(staged)
                try:
                    assert self.database_salt is not None
                    export_database(
                        source,
                        staged,
                        self.key,
                        target_salt=self.database_salt,
                    )
                finally:
                    source.close()
                self._validate_external(staged, self.key, self.database_salt)
                journal = RestoreJournal(
                    version=JOURNAL_VERSION,
                    phase="ready",
                    staged_path=str(staged),
                    staged_sha256=sha256_file(staged),
                    retained_path=str(self._path.with_suffix(".pre-restore.sqlcipher")),
                )
                write_journal(self._restore_journal, journal)
            finally:
                shutil.rmtree(stage_dir, ignore_errors=True)
        return MaintenanceOutcome(
            MaintenanceStatus.STAGED_RESTART_REQUIRED,
            "Restore validated and staged; restart Silver Estimate to activate it",
            str(self._path.with_suffix(".restore.staged")),
        )

    def change_passwords(self, new_password: str) -> MaintenanceOutcome:
        return self._copy_switch_rekey(new_password)

    def _copy_switch_rekey(self, new_password: str) -> MaintenanceOutcome:
        old_key = self.key
        old_salt = self.database_salt
        assert old_salt is not None
        new_salt = os.urandom(SQLCIPHER_SALT_BYTES)
        new_key = self._derive_bound_key(new_password, new_salt)
        target = self._path.with_suffix(".rekey.target")
        retained = self._path.with_suffix(".pre-rekey.sqlcipher")
        with self._broker.maintenance():
            assert self.conn is not None
            self.conn.commit()
            self._remove_database_family(target)
            export_database(
                self.conn,
                target,
                new_key,
                target_salt=new_salt,
            )
            self._validate_external(target, new_key, new_salt)
            self._close_connection()
            journal = RekeyJournal(
                version=JOURNAL_VERSION,
                phase="ready",
                old_database_sha256=sha256_file(self._path),
                target_path=str(target),
                retained_path=str(retained),
            )
            write_journal(self._rekey_journal, journal)
            try:
                self._remove_database_family(retained)
                os.replace(self._path, retained)
                os.replace(target, self._path)
                self.database_salt = new_salt
                self.key = new_key
                self._broker = SqlCipherConnectionBroker(
                    self._path,
                    self.key,
                    database_salt=self.database_salt,
                    logger=self.logger,
                )
                self.conn, self.driver_identity = self._broker.open_writer()
                self._bind_connection()
                self.validate_database(self.conn)
                self._rekey_journal.unlink(missing_ok=True)
                self._remove_database_family(retained)
            except BaseException as exc:
                self.logger.exception("Rekey activation failed; rolling back")
                self._close_connection()
                if retained.exists():
                    self._remove_database_family(self._path)
                    os.replace(retained, self._path)
                self.database_salt = old_salt
                self.key = old_key
                self._broker = SqlCipherConnectionBroker(
                    self._path,
                    self.key,
                    database_salt=self.database_salt,
                )
                self.conn, self.driver_identity = self._broker.open_writer()
                self._bind_connection()
                self._rekey_journal.unlink(missing_ok=True)
                self._remove_database_family(target)
                return MaintenanceOutcome(
                    MaintenanceStatus.ROLLED_BACK,
                    f"Password change failed and the original database was restored: {exc}",
                )
        return MaintenanceOutcome(
            MaintenanceStatus.SUCCESS,
            "Database was copied, validated, and switched to the new password",
            None,
        )

    def _validate_external(
        self,
        path: Path,
        key: bytes,
        database_salt: bytes | None = None,
    ) -> DriverIdentity:
        broker = SqlCipherConnectionBroker(
            path,
            key,
            database_salt=database_salt,
            logger=self.logger,
        )
        connection, identity = broker.open_writer()
        try:
            self.validate_database(connection)
        finally:
            connection.close()
        return identity

    def _activate_pending_restore(self) -> None:
        if not self._restore_journal.exists():
            return
        journal = read_json(self._restore_journal)
        if (
            journal.get("version") not in {1, JOURNAL_VERSION}
            or journal.get("phase") != "ready"
        ):
            raise StorageMetadataError("Unsupported interrupted restore journal")
        staged = self._validated_journal_path(
            journal,
            "staged_path",
            self._path.with_suffix(".restore.staged"),
        )
        retained = self._validated_journal_path(
            journal,
            "retained_path",
            self._path.with_suffix(".pre-restore.sqlcipher"),
        )
        if not staged.is_file() or sha256_file(staged) != journal.get("staged_sha256"):
            raise StorageMetadataError("Pending restore target is missing or corrupt")
        if (
            self.database_salt is not None
            and self._read_database_salt(staged) != self.database_salt
        ):
            failed = self._path.with_suffix(".restore.failed")
            self._remove_database_family(failed)
            os.replace(staged, failed)
            self._restore_journal.unlink(missing_ok=True)
            self.logger.error(
                "Pending restore was quarantined because its database salt is invalid"
            )
            return
        self._remove_database_family(retained)
        os.replace(self._path, retained)
        os.replace(staged, self._path)
        try:
            self._validate_external(self._path, self.key, self.database_salt)
        except BaseException as exc:
            failed = self._path.with_suffix(".restore.failed")
            self._remove_database_family(failed)
            if self._path.exists():
                os.replace(self._path, failed)
            os.replace(retained, self._path)
            self._restore_journal.unlink(missing_ok=True)
            self.logger.error(
                "Pending restore activation failed and was rolled back: %s", exc
            )
            return
        self._restore_journal.unlink(missing_ok=True)
        self.open_status = DatabaseOpenStatus.RESTORE_ACTIVATED

    def _resolve_interrupted_rekey(self, password: str) -> None:
        if not self._rekey_journal.exists():
            return
        journal = read_json(self._rekey_journal)
        if journal.get("version") == 1 or self.database_salt is None:
            self._resolve_legacy_interrupted_rekey(password, journal)
            return
        if journal.get("version") != JOURNAL_VERSION or journal.get("phase") != "ready":
            raise StorageMetadataError("Unsupported interrupted rekey journal")
        target = self._validated_journal_path(
            journal,
            "target_path",
            self._path.with_suffix(".rekey.target"),
        )
        retained = self._validated_journal_path(
            journal,
            "retained_path",
            self._path.with_suffix(".pre-rekey.sqlcipher"),
        )
        try:
            self._validate_external(self._path, self.key, self.database_salt)
        except BaseException as exc:
            if not retained.is_file():
                raise StorageMetadataError(
                    "Interrupted password change requires recovery"
                ) from exc
            retained_salt = self._read_database_salt(retained)
            retained_key = self._derive_bound_key(password, retained_salt)
            self._validate_external(retained, retained_key, retained_salt)
            self._remove_database_family(self._path)
            os.replace(retained, self._path)
            self.database_salt = retained_salt
            self.key = retained_key
            self._validate_external(
                self._path,
                self.key,
                self.database_salt,
            )
        self._remove_database_family(target)
        self._remove_database_family(retained)
        self._rekey_journal.unlink(missing_ok=True)

    def _resolve_legacy_interrupted_rekey(
        self,
        password: str,
        journal: dict[str, Any],
    ) -> None:
        if journal.get("phase") != "ready":
            raise StorageMetadataError("Unsupported interrupted legacy rekey journal")
        target = self._validated_journal_path(
            journal,
            "target_path",
            self._path.with_suffix(".rekey.target"),
        )
        retained = self._validated_journal_path(
            journal,
            "retained_path",
            self._path.with_suffix(".pre-rekey.sqlcipher"),
        )
        retained_metadata = self._validated_journal_path(
            journal,
            "retained_metadata_path",
            self._metadata_path.with_suffix(".pre-rekey.json"),
        )
        try:
            self._validate_external(self._path, self.key)
        except BaseException as exc:
            if not retained.is_file():
                raise StorageMetadataError(
                    "Interrupted legacy password change requires recovery"
                ) from exc
            self._remove_database_family(self._path)
            os.replace(retained, self._path)
            if retained_metadata.is_file():
                os.replace(retained_metadata, self._metadata_path)
            self._metadata = KdfMetadata.read(self._metadata_path)
            self.key = self._derive_legacy_key(password, self._metadata)
            self._validate_external(self._path, self.key)
        self._remove_database_family(target)
        self._remove_database_family(retained)
        retained_metadata.unlink(missing_ok=True)
        self._rekey_journal.unlink(missing_ok=True)

    def _recover_missing_live_from_journal(self) -> None:
        if self._path.exists():
            return
        if self._binding_journal.exists():
            journal = read_json(self._binding_journal)
            retained = self._validated_journal_path(
                journal,
                "retained_path",
                self._path.with_suffix(".pre-binding.sqlcipher"),
            )
            retained_metadata = self._validated_journal_path(
                journal,
                "retained_metadata_path",
                self._metadata_path.with_suffix(".pre-binding.json"),
            )
            target = self._validated_journal_path(
                journal,
                "target_path",
                self._path.with_suffix(".binding.target"),
            )
            if not retained.is_file():
                raise StorageMetadataError(
                    "Interrupted device-binding migration has no recoverable database"
                )
            os.replace(retained, self._path)
            if retained_metadata.is_file() and not self._metadata_path.exists():
                os.replace(retained_metadata, self._metadata_path)
            self._remove_database_family(target)
            self._binding_journal.unlink(missing_ok=True)
            return
        if self._rekey_journal.exists():
            journal = read_json(self._rekey_journal)
            retained = self._validated_journal_path(
                journal,
                "retained_path",
                self._path.with_suffix(".pre-rekey.sqlcipher"),
            )
            if not retained.is_file():
                raise StorageMetadataError(
                    "Interrupted rekey has no recoverable database"
                )
            os.replace(retained, self._path)
            if journal.get("version") == 1:
                retained_metadata = self._validated_journal_path(
                    journal,
                    "retained_metadata_path",
                    self._metadata_path.with_suffix(".pre-rekey.json"),
                )
                if retained_metadata.is_file():
                    os.replace(retained_metadata, self._metadata_path)
            return
        if self._restore_journal.exists():
            journal = read_json(self._restore_journal)
            retained = self._validated_journal_path(
                journal,
                "retained_path",
                self._path.with_suffix(".pre-restore.sqlcipher"),
            )
            if not retained.is_file():
                raise StorageMetadataError(
                    "Interrupted restore has no recoverable database"
                )
            os.replace(retained, self._path)

    @staticmethod
    def _remove_database_family(path: Path) -> None:
        for candidate in (
            path,
            Path(f"{path}-wal"),
            Path(f"{path}-shm"),
            Path(f"{path}-journal"),
        ):
            candidate.unlink(missing_ok=True)


__all__ = [
    "DatabaseManager",
    "DatabaseOpenStatus",
    "MaintenanceOutcome",
    "MaintenanceStatus",
    "StorageFormat",
]
