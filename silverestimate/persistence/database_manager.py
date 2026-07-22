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
    Connection,
    DatabaseError,
    DriverIdentity,
    Error,
    ReadConnection,
    SqlCipherConnectionBroker,
    configure_connection,
    export_database,
    open_plaintext_legacy,
    require_driver,
)
from silverestimate.persistence.database_repository_facade import (
    DatabaseRepositoryFacadeMixin,
)
from silverestimate.persistence.storage_metadata import (
    BackupManifest,
    KdfMetadata,
    MigrationJournal,
    RekeyJournal,
    RestoreJournal,
    StorageMetadataError,
    read_json,
    sha256_file,
    write_journal,
)
from silverestimate.security import encryption as crypto_utils
from silverestimate.security.encrypted_envelope import (
    MAGIC as LEGACY_MAGIC,
)
from silverestimate.security.encrypted_envelope import (
    decrypt_envelope_to_path,
    read_envelope_metadata,
)

SQLITE_HEADER = b"SQLite format 3\x00"
BACKUP_FORMAT_VERSION = 1
JOURNAL_VERSION = 1


class StorageFormat(Enum):
    MISSING = auto()
    LEGACY_SILVDB01 = auto()
    PLAINTEXT_SQLITE = auto()
    SQLCIPHER = auto()


class DatabaseOpenStatus(Enum):
    CREATED = auto()
    OPENED = auto()
    MIGRATED_LEGACY = auto()
    RESTORE_ACTIVATED = auto()


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

    def __init__(self, db_path: str, password: str):
        self.logger = logging.getLogger(__name__)
        self.database_path = str(Path(db_path).resolve())
        # Compatibility is intentionally path-only; it is never a plaintext temp DB.
        self.encrypted_db_path = self.database_path
        self.last_error: str | None = None
        self.conn: Connection | None = None
        self.cursor: Any | None = None
        self._session = ConnectionThreadGuard(logger=self.logger)
        self._item_cache_controller = ItemCacheController(logger=self.logger)
        self._items_repo: Any | None = None
        self._estimates_repo: Any | None = None
        self._silver_bars_repo: Any | None = None
        self._path = Path(self.database_path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._metadata_path = self._path.with_name(f"{self._path.stem}.kdf.json")
        self._migration_journal = self._path.with_suffix(".migration.json")
        self._rekey_journal = self._path.with_suffix(".rekey.json")
        self._restore_journal = self._path.with_suffix(".restore.json")
        self._cleanup_interrupted_legacy_workspace()
        self._recover_missing_live_from_journal()

        storage_format = self.detect_storage(self._path)
        if storage_format is StorageFormat.PLAINTEXT_SQLITE:
            raise StorageMetadataError(
                "Plaintext SQLite application databases are forbidden; import a SILVDB01 backup"
            )
        if storage_format is StorageFormat.MISSING:
            self._metadata = KdfMetadata.create()
            self.key = self._derive_key(password, self._metadata)
            self._broker = SqlCipherConnectionBroker(
                self._path, self.key, logger=self.logger
            )
            self.conn, self.driver_identity = self._broker.open_writer(create=True)
            try:
                self._bind_connection()
                self.setup_database()
                self.validate_database(self.conn)
                self._metadata.write(self._metadata_path)
            except BaseException:
                self._close_connection()
                self._remove_database_family(self._path)
                self._metadata_path.unlink(missing_ok=True)
                raise
            self.open_status = DatabaseOpenStatus.CREATED
            return

        if storage_format is StorageFormat.LEGACY_SILVDB01:
            self._migrate_legacy(password)
            self.open_status = DatabaseOpenStatus.MIGRATED_LEGACY
        else:
            self.open_status = DatabaseOpenStatus.OPENED

        self._metadata = KdfMetadata.read(self._metadata_path)
        self.key = self._derive_key(password, self._metadata)
        self._activate_pending_restore()
        self._resolve_interrupted_rekey(password)
        self._broker = SqlCipherConnectionBroker(
            self._path, self.key, logger=self.logger
        )
        self.conn, self.driver_identity = self._broker.open_writer()
        self._bind_connection()
        self.setup_database()
        self.validate_database(self.conn)
        self._migration_journal.unlink(missing_ok=True)

    @staticmethod
    def detect_storage(path: str | Path) -> StorageFormat:
        candidate = Path(path)
        if not candidate.exists() or candidate.stat().st_size == 0:
            return StorageFormat.MISSING
        header = candidate.read_bytes()[: len(SQLITE_HEADER)]
        if header.startswith(LEGACY_MAGIC):
            return StorageFormat.LEGACY_SILVDB01
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

    def _derive_key(self, password: str, metadata: KdfMetadata) -> bytes:
        return crypto_utils.derive_key(
            password,
            metadata.salt,
            time_cost=metadata.time_cost,
            memory_cost_kib=metadata.memory_cost_kib,
            parallelism=metadata.parallelism,
            logger=self.logger,
        )

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
            assert self.conn is not None and self.cursor is not None
            self.cursor.execute(
                "CREATE TABLE schema_version ("
                "id INTEGER PRIMARY KEY, version INTEGER NOT NULL, "
                "applied_date TEXT NOT NULL)"
            )
            self.cursor.execute(
                "INSERT INTO schema_version(version, applied_date) VALUES (0, ?)",
                (datetime.now().strftime("%Y-%m-%d %H:%M:%S"),),
            )
            self.conn.commit()
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
        from silverestimate.persistence import migrations

        migrations.run_schema_setup(self)

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
        from silverestimate.persistence.migrations import CURRENT_SCHEMA_VERSION

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
                metadata_copy = stage_dir / "estimation.kdf.json"
                export_database(self.conn, database_copy, self.key)
                self._metadata.write(metadata_copy)
                self._validate_external(database_copy, self.key)
                schema_version = self._check_schema_version()
                manifest = BackupManifest(
                    version=BACKUP_FORMAT_VERSION,
                    created_utc=datetime.now(UTC).isoformat(),
                    database_sha256=sha256_file(database_copy),
                    kdf_sha256=sha256_file(metadata_copy),
                    schema_version=schema_version,
                    sqlcipher_version=self.driver_identity.sqlcipher_version,
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
                    archive.write(metadata_copy, "estimation.kdf.json")
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
                        "estimation.kdf.json",
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
                archived_db = stage_dir / "database.sqlcipher"
                archived_kdf = stage_dir / "estimation.kdf.json"
                if sha256_file(archived_db) != manifest.get("database_sha256"):
                    raise StorageMetadataError("Backup database digest mismatch")
                if sha256_file(archived_kdf) != manifest.get("kdf_sha256"):
                    raise StorageMetadataError("Backup KDF digest mismatch")
                backup_metadata = KdfMetadata.read(archived_kdf)
                backup_key = self._derive_key(archive_password, backup_metadata)
                source_broker = SqlCipherConnectionBroker(archived_db, backup_key)
                source, _ = source_broker.open_writer()
                staged = self._path.with_suffix(".restore.staged")
                self._remove_database_family(staged)
                try:
                    export_database(source, staged, self.key)
                finally:
                    source.close()
                self._validate_external(staged, self.key)
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

    def reencrypt_with_new_password(self, new_password: str) -> bool:
        """Compatibility wrapper; new callers should inspect ``change_passwords``."""
        return self._copy_switch_rekey(new_password).status is MaintenanceStatus.SUCCESS

    def _copy_switch_rekey(self, new_password: str) -> MaintenanceOutcome:
        old_key = self.key
        new_metadata = KdfMetadata.create()
        new_key = self._derive_key(new_password, new_metadata)
        target = self._path.with_suffix(".rekey.target")
        retained = self._path.with_suffix(".pre-rekey.sqlcipher")
        retained_metadata = self._metadata_path.with_suffix(".pre-rekey.json")
        metadata_target = self._metadata_path.with_suffix(".json.rekey")
        with self._broker.maintenance():
            assert self.conn is not None
            self.conn.commit()
            self._remove_database_family(target)
            export_database(self.conn, target, new_key)
            self._validate_external(target, new_key)
            new_metadata.write(metadata_target)
            journal = RekeyJournal(
                version=JOURNAL_VERSION,
                phase="ready",
                old_database_sha256=sha256_file(self._path),
                old_metadata_sha256=sha256_file(self._metadata_path),
                target_path=str(target),
                retained_path=str(retained),
                retained_metadata_path=str(retained_metadata),
            )
            write_journal(self._rekey_journal, journal)
            self._close_connection()
            try:
                self._remove_database_family(retained)
                retained_metadata.unlink(missing_ok=True)
                shutil.copy2(self._metadata_path, retained_metadata)
                os.replace(self._path, retained)
                os.replace(target, self._path)
                os.replace(metadata_target, self._metadata_path)
                self._metadata = new_metadata
                self.key = new_key
                self._broker = SqlCipherConnectionBroker(
                    self._path, self.key, logger=self.logger
                )
                self.conn, self.driver_identity = self._broker.open_writer()
                self._bind_connection()
                self.validate_database(self.conn)
                self._rekey_journal.unlink(missing_ok=True)
            except BaseException as exc:
                self.logger.exception("Rekey activation failed; rolling back")
                self._close_connection()
                if retained.exists():
                    self._remove_database_family(self._path)
                    os.replace(retained, self._path)
                if retained_metadata.exists():
                    os.replace(retained_metadata, self._metadata_path)
                self._metadata = KdfMetadata.read(self._metadata_path)
                self.key = old_key
                self._broker = SqlCipherConnectionBroker(self._path, self.key)
                self.conn, self.driver_identity = self._broker.open_writer()
                self._bind_connection()
                return MaintenanceOutcome(
                    MaintenanceStatus.ROLLED_BACK,
                    f"Password change failed and the original database was restored: {exc}",
                )
        return MaintenanceOutcome(
            MaintenanceStatus.SUCCESS,
            "Database was copied, validated, and switched to the new password",
            str(retained),
        )

    def _validate_external(self, path: Path, key: bytes) -> DriverIdentity:
        broker = SqlCipherConnectionBroker(path, key, logger=self.logger)
        connection, identity = broker.open_writer()
        try:
            self.validate_database(connection)
        finally:
            connection.close()
        return identity

    def _migrate_legacy(self, password: str) -> None:
        metadata = read_envelope_metadata(self._path)
        legacy_key = crypto_utils.derive_key(
            password,
            metadata.argon2.salt,
            time_cost=metadata.argon2.time_cost,
            memory_cost_kib=metadata.argon2.memory_cost_kib,
            parallelism=metadata.argon2.parallelism,
            logger=self.logger,
        )
        backup = self._path.with_name(f"{self._path.stem}.silvdb01.backup")
        if not backup.exists():
            shutil.copy2(self._path, backup)
        source_hash = sha256_file(self._path)
        if sha256_file(backup) != source_hash:
            raise StorageMetadataError("Retained SILVDB01 backup digest mismatch")
        workspace = Path(
            tempfile.mkdtemp(
                prefix=".silverestimate-legacy-migration-", dir=self._path.parent
            )
        )
        marker = workspace / ".silverestimate-plaintext-migration"
        marker.write_text("application-owned one-time plaintext workspace\n")
        plaintext = workspace / "legacy.sqlite"
        target = self._path.with_suffix(".migrating")
        new_metadata = KdfMetadata.create()
        new_key = self._derive_key(password, new_metadata)
        write_journal(
            self._migration_journal,
            MigrationJournal(
                version=JOURNAL_VERSION,
                phase="decrypting",
                source_sha256=source_hash,
                backup_path=str(backup),
                target_path=str(target),
            ),
        )
        try:
            decrypt_envelope_to_path(self._path, plaintext, legacy_key)
            self._assert_plaintext_sqlite(plaintext)
            source_counts, source_digests = self._database_fingerprints_plaintext(
                plaintext
            )
            self._remove_database_family(target)
            driver = require_driver()
            probe = driver.connect(":memory:")
            try:
                identity = configure_connection(
                    probe,
                    raw_key=os.urandom(32),
                    writer=False,
                    authenticate=False,
                )
            finally:
                probe.close()
            source = driver.connect(str(plaintext))
            try:
                # This is the only production plaintext connection and is confined to
                # the marked migration workspace.
                source.execute("PRAGMA temp_store = MEMORY")
                source.execute("PRAGMA mmap_size = 0")
                source.execute("SELECT count(*) FROM sqlite_master").fetchone()
                export_database(source, target, new_key)
            finally:
                source.close()
            target_counts, target_digests = self._database_fingerprints_cipher(
                target, new_key
            )
            if source_counts != target_counts or source_digests != target_digests:
                raise DatabaseError("Legacy migration count/digest comparison failed")
            self._prepare_external_schema(target, new_key)
            new_metadata.write(self._metadata_path)
            os.replace(target, self._path)
            self._migration_journal.unlink(missing_ok=True)
            self.driver_identity = identity
        finally:
            self._remove_database_family(target)
            shutil.rmtree(workspace, ignore_errors=True)

    def _prepare_external_schema(self, path: Path, key: bytes) -> None:
        """Migrate and validate a staged target before it can become live."""
        broker = SqlCipherConnectionBroker(path, key, logger=self.logger)
        connection, _ = broker.open_writer()
        self.conn = connection
        try:
            self._bind_connection()
            self.setup_database()
            self.validate_database(connection)
        finally:
            connection.close()
            self.conn = None
            self.cursor = None
            self._session.clear()

    @staticmethod
    def _assert_plaintext_sqlite(path: Path) -> None:
        if path.read_bytes()[: len(SQLITE_HEADER)] != SQLITE_HEADER:
            raise DatabaseError("Legacy envelope did not contain a SQLite database")

    @staticmethod
    def _typed_digest(rows: list[tuple[Any, ...]]) -> str:
        digest = hashlib.sha256()
        for row in rows:
            encoded = []
            for value in row:
                if value is None:
                    encoded.append(["null", None])
                elif isinstance(value, bytes):
                    encoded.append(["blob", value.hex()])
                elif isinstance(value, int):
                    encoded.append(["int", str(value)])
                elif isinstance(value, float):
                    encoded.append(["real", value.hex()])
                else:
                    encoded.append(["text", str(value)])
            digest.update(json.dumps(encoded, separators=(",", ":")).encode())
            digest.update(b"\n")
        return digest.hexdigest()

    @classmethod
    def _fingerprints(cls, connection: Any) -> tuple[dict[str, int], dict[str, str]]:
        tables = [
            str(row[0])
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table' "
                "AND name NOT LIKE 'sqlite_%' ORDER BY name"
            )
        ]
        counts: dict[str, int] = {}
        digests: dict[str, str] = {}
        for table in tables:
            quoted = table.replace('"', '""')
            columns = [
                str(row[1])
                for row in connection.execute(f'PRAGMA table_info("{quoted}")')
            ]
            order = ",".join(
                f'"{column.replace(chr(34), chr(34) * 2)}"' for column in columns
            )
            rows = [
                tuple(row)
                for row in connection.execute(
                    f'SELECT * FROM "{quoted}"'
                    + (f" ORDER BY {order}" if order else "")
                )
            ]
            counts[table] = len(rows)
            digests[table] = cls._typed_digest(rows)
        return counts, digests

    @classmethod
    def _database_fingerprints_plaintext(
        cls, path: Path
    ) -> tuple[dict[str, int], dict[str, str]]:
        connection = open_plaintext_legacy(path)
        try:
            return cls._fingerprints(connection)
        finally:
            connection.close()

    @classmethod
    def _database_fingerprints_cipher(
        cls, path: Path, key: bytes
    ) -> tuple[dict[str, int], dict[str, str]]:
        broker = SqlCipherConnectionBroker(path, key)
        connection, _ = broker.open_writer()
        try:
            return cls._fingerprints(connection)
        finally:
            connection.close()

    def _activate_pending_restore(self) -> None:
        if not self._restore_journal.exists():
            return
        journal = read_json(self._restore_journal)
        if journal.get("version") != JOURNAL_VERSION or journal.get("phase") != "ready":
            raise StorageMetadataError("Unsupported interrupted restore journal")
        staged = Path(str(journal.get("staged_path", "")))
        retained = Path(str(journal.get("retained_path", "")))
        if not staged.is_file() or sha256_file(staged) != journal.get("staged_sha256"):
            raise StorageMetadataError("Pending restore target is missing or corrupt")
        self._remove_database_family(retained)
        os.replace(self._path, retained)
        os.replace(staged, self._path)
        try:
            self._validate_external(self._path, self.key)
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
        # An unfinished switch is never selected by filename. If the live DB still
        # authenticates under current metadata, retain it and discard only the target.
        journal = read_json(self._rekey_journal)
        target = Path(str(journal.get("target_path", "")))
        retained = Path(str(journal.get("retained_path", "")))
        retained_metadata = Path(str(journal.get("retained_metadata_path", "")))
        try:
            self._validate_external(self._path, self.key)
        except BaseException as exc:
            if not retained.is_file():
                raise StorageMetadataError(
                    "Interrupted password change requires recovery"
                ) from exc
            self._remove_database_family(self._path)
            os.replace(retained, self._path)
            if retained_metadata.is_file():
                os.replace(retained_metadata, self._metadata_path)
                self._metadata = KdfMetadata.read(self._metadata_path)
                self.key = self._derive_key(password, self._metadata)
            self._validate_external(self._path, self.key)
        self._remove_database_family(target)
        self._rekey_journal.unlink(missing_ok=True)

    def _recover_missing_live_from_journal(self) -> None:
        if self._path.exists():
            return
        if self._rekey_journal.exists():
            journal = read_json(self._rekey_journal)
            retained = Path(str(journal.get("retained_path", "")))
            retained_metadata = Path(str(journal.get("retained_metadata_path", "")))
            if not retained.is_file():
                raise StorageMetadataError(
                    "Interrupted rekey has no recoverable database"
                )
            os.replace(retained, self._path)
            if retained_metadata.is_file():
                os.replace(retained_metadata, self._metadata_path)
            return
        if self._restore_journal.exists():
            journal = read_json(self._restore_journal)
            retained = Path(str(journal.get("retained_path", "")))
            if not retained.is_file():
                raise StorageMetadataError(
                    "Interrupted restore has no recoverable database"
                )
            os.replace(retained, self._path)

    def _cleanup_interrupted_legacy_workspace(self) -> None:
        prefix = ".silverestimate-legacy-migration-"
        for child in self._path.parent.glob(f"{prefix}*"):
            try:
                resolved = child.resolve()
                if (
                    child.is_dir()
                    and resolved.parent == self._path.parent.resolve()
                    and child.name.startswith(prefix)
                    and (child / ".silverestimate-plaintext-migration").exists()
                ):
                    shutil.rmtree(resolved)
            except OSError as exc:
                self.logger.warning(
                    "Could not clean legacy workspace %s: %s", child, exc
                )

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
