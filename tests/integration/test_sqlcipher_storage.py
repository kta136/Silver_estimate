import json
import threading
from pathlib import Path

import pytest

from silverestimate.persistence import database_driver
from silverestimate.persistence.database_driver import (
    DatabaseAuthenticationError,
    DriverUnavailableError,
    MaintenanceBusyError,
)
from silverestimate.persistence.database_manager import (
    DatabaseManager,
    DatabaseOpenStatus,
    MaintenanceStatus,
    StorageFormat,
)
from silverestimate.persistence.storage_metadata import (
    KdfMetadata,
    RekeyJournal,
    RestoreJournal,
    StorageMetadataError,
    sha256_file,
    write_journal,
)
from silverestimate.security.encrypted_envelope import Argon2Metadata
from silverestimate.security.encryption import derive_key
from tests.legacy_envelope_writer import write_envelope


def test_live_database_wal_and_rollback_journal_hide_plaintext_canary(tmp_path):
    path = tmp_path / "estimation.db"
    manager = DatabaseManager(str(path), "password")
    canary = "SILVERESTIMATE_ACTIVE_SESSION_PLAINTEXT_CANARY"
    try:
        manager.conn.execute(
            "INSERT INTO items(code, name) VALUES (?, ?)", ("CANARY", canary)
        )
        manager.conn.commit()
        for candidate in (path, Path(f"{path}-wal"), Path(f"{path}-shm")):
            if candidate.exists():
                assert canary.encode() not in candidate.read_bytes()

        manager.conn.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone()
        manager.conn.execute("PRAGMA journal_mode=DELETE").fetchone()
        manager.conn.execute("BEGIN IMMEDIATE")
        manager.conn.execute(
            "UPDATE items SET name=? WHERE code='CANARY'", (canary + "2",)
        )
        journal = Path(f"{path}-journal")
        assert journal.exists()
        assert canary.encode() not in journal.read_bytes()
        manager.conn.rollback()
        manager.conn.execute("PRAGMA journal_mode=WAL").fetchone()
    finally:
        manager.close()


def test_wrong_password_tampered_metadata_and_plaintext_database_fail_closed(tmp_path):
    path = tmp_path / "estimation.db"
    manager = DatabaseManager(str(path), "correct")
    manager.close()
    with pytest.raises(DatabaseAuthenticationError):
        DatabaseManager(str(path), "wrong")

    metadata_path = tmp_path / "estimation.kdf.json"
    original = metadata_path.read_text()
    value = json.loads(original)
    value["memory_cost_kib"] = 1024
    metadata_path.write_text(json.dumps(value))
    with pytest.raises(StorageMetadataError, match="weakened"):
        DatabaseManager(str(path), "correct")
    metadata_path.write_text(original)

    plaintext = tmp_path / "plaintext.db"
    plaintext.write_bytes(b"SQLite format 3\x00" + b"\x00" * 100)
    assert DatabaseManager.detect_storage(plaintext) is StorageFormat.PLAINTEXT_SQLITE
    with pytest.raises(StorageMetadataError, match="Plaintext SQLite"):
        DatabaseManager(str(plaintext), "password")


def test_legacy_silvdb01_is_migrated_once_and_retained(tmp_path):
    import sqlite3

    plaintext = tmp_path / "legacy.sqlite"
    connection = sqlite3.connect(plaintext)
    connection.execute(
        "CREATE TABLE items(code TEXT PRIMARY KEY, name TEXT NOT NULL, "
        "purity REAL DEFAULT 0, wage_type TEXT DEFAULT 'P', "
        "wage_rate REAL DEFAULT 0, tunch TEXT)"
    )
    connection.execute("INSERT INTO items(code,name) VALUES ('OLD1', 'Legacy item')")
    connection.commit()
    connection.close()
    metadata = Argon2Metadata(
        salt=b"0123456789abcdef",
        time_cost=3,
        memory_cost_kib=65_536,
        parallelism=4,
    )
    key = derive_key(
        "legacy-password",
        metadata.salt,
        time_cost=metadata.time_cost,
        memory_cost_kib=metadata.memory_cost_kib,
        parallelism=metadata.parallelism,
    )
    live = tmp_path / "estimation.db"
    write_envelope(plaintext, live, key, argon2=metadata)
    plaintext.unlink()

    manager = DatabaseManager(str(live), "legacy-password")
    try:
        assert manager.open_status is DatabaseOpenStatus.MIGRATED_LEGACY
        assert (
            manager.conn.execute("SELECT name FROM items WHERE code='OLD1'").fetchone()[
                0
            ]
            == "Legacy item"
        )
    finally:
        manager.close()
    assert (tmp_path / "estimation.silvdb01.backup").exists()
    assert not list(tmp_path.glob(".silverestimate-legacy-migration-*"))
    assert not live.read_bytes().startswith(b"SILVDB01")


def test_encrypted_backup_historical_password_restore_and_rekey(tmp_path):
    path = tmp_path / "estimation.db"
    manager = DatabaseManager(str(path), "old-password")
    manager.conn.execute("INSERT INTO items(code,name) VALUES('B1','Before')")
    manager.conn.commit()
    backup = manager.create_encrypted_backup(tmp_path / "history.sedbbackup")
    assert backup.status is MaintenanceStatus.SUCCESS
    assert b"Before" not in Path(backup.path).read_bytes()

    outcome = manager.change_passwords("new-password")
    assert outcome.status is MaintenanceStatus.SUCCESS
    manager.conn.execute("UPDATE items SET name='After' WHERE code='B1'")
    manager.conn.commit()
    restore = manager.stage_encrypted_restore(backup.path, "old-password")
    assert restore.status is MaintenanceStatus.STAGED_RESTART_REQUIRED
    manager.close()

    reopened = DatabaseManager(str(path), "new-password")
    try:
        assert reopened.open_status is DatabaseOpenStatus.RESTORE_ACTIVATED
        assert (
            reopened.conn.execute("SELECT name FROM items WHERE code='B1'").fetchone()[
                0
            ]
            == "Before"
        )
    finally:
        reopened.close()


def test_maintenance_blocks_new_readers_until_existing_reader_drains(tmp_path):
    manager = DatabaseManager(str(tmp_path / "estimation.db"), "password")
    reader = manager.open_read_connection(threading.Event())
    try:
        with (
            pytest.raises(MaintenanceBusyError, match="draining"),
            manager._broker.maintenance(timeout_seconds=0.01),
        ):
            pass
    finally:
        reader.close()
        manager.close()


def test_kdf_metadata_requires_exact_version_one_policy():
    metadata = KdfMetadata.create()
    assert len(metadata.salt) == 16
    assert metadata.output_bytes == 32
    value = {
        "version": 2,
        "algorithm": "argon2id",
        "salt_b64": metadata.salt_b64,
        "time_cost": 3,
        "memory_cost_kib": 65_536,
        "parallelism": 4,
        "output_bytes": 32,
    }
    with pytest.raises(StorageMetadataError):
        KdfMetadata.from_dict(value)


def test_invalid_pending_restore_rolls_back_to_original_database(tmp_path):
    path = tmp_path / "estimation.db"
    manager = DatabaseManager(str(path), "password")
    manager.conn.execute("INSERT INTO items(code,name) VALUES('SAFE','Original')")
    manager.conn.commit()
    manager.close()

    staged = path.with_suffix(".restore.staged")
    staged.write_bytes(b"not a SQLCipher database")
    write_journal(
        path.with_suffix(".restore.json"),
        RestoreJournal(
            version=1,
            phase="ready",
            staged_path=str(staged),
            staged_sha256=sha256_file(staged),
            retained_path=str(path.with_suffix(".pre-restore.sqlcipher")),
        ),
    )

    reopened = DatabaseManager(str(path), "password")
    try:
        assert (
            reopened.conn.execute(
                "SELECT name FROM items WHERE code='SAFE'"
            ).fetchone()[0]
            == "Original"
        )
    finally:
        reopened.close()
    assert path.with_suffix(".restore.failed").exists()
    assert not path.with_suffix(".restore.json").exists()


def test_interrupted_rekey_target_is_never_selected_by_filename(tmp_path):
    path = tmp_path / "estimation.db"
    manager = DatabaseManager(str(path), "password")
    manager.close()
    target = path.with_suffix(".rekey.target")
    target.write_bytes(b"incomplete target")
    metadata = tmp_path / "estimation.kdf.json"
    write_journal(
        path.with_suffix(".rekey.json"),
        RekeyJournal(
            version=1,
            phase="ready",
            old_database_sha256=sha256_file(path),
            old_metadata_sha256=sha256_file(metadata),
            target_path=str(target),
            retained_path=str(path.with_suffix(".pre-rekey.sqlcipher")),
            retained_metadata_path=str(metadata.with_suffix(".pre-rekey.json")),
        ),
    )

    reopened = DatabaseManager(str(path), "password")
    reopened.close()
    assert not target.exists()
    assert not path.with_suffix(".rekey.json").exists()


def test_unexpected_runtime_series_is_rejected_without_test_override(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(database_driver, "EXPECTED_SQLCIPHER_SERIES", "9.99.")
    with pytest.raises(DriverUnavailableError, match="9.99"):
        DatabaseManager(str(tmp_path / "strict.db"), "password")
