import threading
from pathlib import Path

import pytest

from silverestimate.persistence import database_driver
from silverestimate.persistence.database_driver import (
    DatabaseAuthenticationError,
    DriverUnavailableError,
    MaintenanceBusyError,
    export_database,
)
from silverestimate.persistence.database_manager import (
    DatabaseManager,
    DatabaseOpenStatus,
    MaintenanceStatus,
    StorageFormat,
)
from silverestimate.persistence.storage_metadata import (
    BindingMigrationJournal,
    KdfMetadata,
    RekeyJournal,
    RestoreJournal,
    StorageMetadataError,
    sha256_file,
    write_journal,
)
from silverestimate.security import encryption

DEVICE_SECRET = b"S" * 32
FOREIGN_DEVICE_SECRET = b"F" * 32


def test_live_database_wal_and_rollback_journal_hide_plaintext_canary(tmp_path):
    path = tmp_path / "estimation.db"
    manager = DatabaseManager(
        str(path), "password", device_secret=DEVICE_SECRET
    )
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


def test_wrong_password_foreign_device_and_plaintext_database_fail_closed(tmp_path):
    path = tmp_path / "estimation.db"
    manager = DatabaseManager(
        str(path), "correct", device_secret=DEVICE_SECRET
    )
    manager.close()
    with pytest.raises(DatabaseAuthenticationError):
        DatabaseManager(str(path), "wrong", device_secret=DEVICE_SECRET)

    with pytest.raises(DatabaseAuthenticationError):
        DatabaseManager(
            str(path),
            "correct",
            device_secret=FOREIGN_DEVICE_SECRET,
        )
    assert not (tmp_path / "estimation.kdf.json").exists()

    plaintext = tmp_path / "plaintext.db"
    plaintext.write_bytes(b"SQLite format 3\x00" + b"\x00" * 100)
    assert DatabaseManager.detect_storage(plaintext) is StorageFormat.PLAINTEXT_SQLITE
    with pytest.raises(StorageMetadataError, match="Plaintext SQLite"):
        DatabaseManager(
            str(plaintext),
            "password",
            device_secret=DEVICE_SECRET,
        )


def test_legacy_two_file_database_migrates_to_one_machine_bound_file(tmp_path):
    password = "legacy-password"
    source_path = tmp_path / "source.db"
    source = DatabaseManager(
        str(source_path),
        password,
        device_secret=DEVICE_SECRET,
    )
    source.conn.execute("INSERT INTO items(code,name) VALUES('M1','Migrated')")
    source.conn.commit()

    legacy_path = tmp_path / "estimation.db"
    metadata = KdfMetadata.create()
    legacy_key = encryption.derive_key(
        password,
        metadata.salt,
        time_cost=metadata.time_cost,
        memory_cost_kib=metadata.memory_cost_kib,
        parallelism=metadata.parallelism,
    )
    export_database(source.conn, legacy_path, legacy_key)
    source.close()
    metadata_path = tmp_path / "estimation.kdf.json"
    metadata.write(metadata_path)

    migrated = DatabaseManager(
        str(legacy_path),
        password,
        device_secret=DEVICE_SECRET,
    )
    try:
        assert (
            migrated.open_status
            is DatabaseOpenStatus.MIGRATED_TO_DEVICE_BOUND
        )
        assert (
            migrated.conn.execute(
                "SELECT name FROM items WHERE code='M1'"
            ).fetchone()[0]
            == "Migrated"
        )
    finally:
        migrated.close()

    assert legacy_path.exists()
    assert not metadata_path.exists()
    assert not legacy_path.with_suffix(".pre-binding.sqlcipher").exists()
    with pytest.raises(DatabaseAuthenticationError):
        DatabaseManager(
            str(legacy_path),
            password,
            device_secret=FOREIGN_DEVICE_SECRET,
        )


def test_interrupted_binding_switch_finalizes_only_after_bound_db_validates(tmp_path):
    password = "migration-password"
    live = tmp_path / "estimation.db"
    retained = live.with_suffix(".pre-binding.sqlcipher")
    target = live.with_suffix(".binding.target")
    metadata_path = tmp_path / "estimation.kdf.json"
    retained_metadata = metadata_path.with_suffix(".pre-binding.json")

    legacy_source = DatabaseManager(
        str(tmp_path / "legacy-source.db"),
        password,
        device_secret=DEVICE_SECRET,
    )
    metadata = KdfMetadata.create()
    legacy_key = encryption.derive_key(
        password,
        metadata.salt,
        time_cost=metadata.time_cost,
        memory_cost_kib=metadata.memory_cost_kib,
        parallelism=metadata.parallelism,
    )
    export_database(legacy_source.conn, retained, legacy_key)
    legacy_source.close()
    metadata.write(metadata_path)
    metadata.write(retained_metadata)

    bound_target = DatabaseManager(
        str(target),
        password,
        device_secret=DEVICE_SECRET,
    )
    bound_target.conn.execute(
        "INSERT INTO items(code,name) VALUES('RECOVER','Bound')"
    )
    bound_target.conn.commit()
    bound_target.close()
    target.replace(live)

    write_journal(
        live.with_suffix(".binding.json"),
        BindingMigrationJournal(
            version=1,
            phase="ready",
            old_database_sha256=sha256_file(retained),
            target_sha256=sha256_file(live),
            target_path=str(target),
            retained_path=str(retained),
            retained_metadata_path=str(retained_metadata),
        ),
    )

    recovered = DatabaseManager(
        str(live),
        password,
        device_secret=DEVICE_SECRET,
    )
    try:
        assert (
            recovered.open_status
            is DatabaseOpenStatus.MIGRATED_TO_DEVICE_BOUND
        )
        assert (
            recovered.conn.execute(
                "SELECT name FROM items WHERE code='RECOVER'"
            ).fetchone()[0]
            == "Bound"
        )
    finally:
        recovered.close()

    assert not metadata_path.exists()
    assert not retained.exists()
    assert not retained_metadata.exists()
    assert not live.with_suffix(".binding.json").exists()


def test_encrypted_backup_historical_password_restore_and_rekey(tmp_path):
    path = tmp_path / "estimation.db"
    manager = DatabaseManager(
        str(path), "old-password", device_secret=DEVICE_SECRET
    )
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

    reopened = DatabaseManager(
        str(path), "new-password", device_secret=DEVICE_SECRET
    )
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


def test_encrypted_backup_rejects_a_foreign_device_secret(tmp_path):
    source = DatabaseManager(
        str(tmp_path / "source.db"),
        "source-password",
        device_secret=DEVICE_SECRET,
    )
    backup = source.create_encrypted_backup(tmp_path / "bound.sedbbackup")
    source.close()

    foreign = DatabaseManager(
        str(tmp_path / "foreign.db"),
        "foreign-password",
        device_secret=FOREIGN_DEVICE_SECRET,
    )
    try:
        with pytest.raises(StorageMetadataError, match="different PC"):
            foreign.stage_encrypted_restore(backup.path, "source-password")
    finally:
        foreign.close()


def test_maintenance_blocks_new_readers_until_existing_reader_drains(tmp_path):
    manager = DatabaseManager(
        str(tmp_path / "estimation.db"),
        "password",
        device_secret=DEVICE_SECRET,
    )
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
    manager = DatabaseManager(
        str(path), "password", device_secret=DEVICE_SECRET
    )
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

    reopened = DatabaseManager(
        str(path), "password", device_secret=DEVICE_SECRET
    )
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
    manager = DatabaseManager(
        str(path), "password", device_secret=DEVICE_SECRET
    )
    manager.close()
    target = path.with_suffix(".rekey.target")
    target.write_bytes(b"incomplete target")
    write_journal(
        path.with_suffix(".rekey.json"),
        RekeyJournal(
            version=2,
            phase="ready",
            old_database_sha256=sha256_file(path),
            target_path=str(target),
            retained_path=str(path.with_suffix(".pre-rekey.sqlcipher")),
        ),
    )

    reopened = DatabaseManager(
        str(path), "password", device_secret=DEVICE_SECRET
    )
    reopened.close()
    assert not target.exists()
    assert not path.with_suffix(".rekey.json").exists()


def test_unexpected_runtime_series_is_rejected_without_test_override(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(database_driver, "EXPECTED_SQLCIPHER_SERIES", "9.99.")
    with pytest.raises(DriverUnavailableError, match="9.99"):
        DatabaseManager(
            str(tmp_path / "strict.db"),
            "password",
            device_secret=DEVICE_SECRET,
        )
