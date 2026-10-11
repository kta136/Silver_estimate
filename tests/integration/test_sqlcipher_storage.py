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
    RekeyJournal,
    RestoreJournal,
    StorageMetadataError,
    sha256_file,
    write_journal,
)

DEVICE_SECRET = b"S" * 32
FOREIGN_DEVICE_SECRET = b"F" * 32


def test_live_database_wal_and_rollback_journal_hide_plaintext_canary(tmp_path):
    path = tmp_path / "estimation.db"
    manager = DatabaseManager(str(path), "password", device_secret=DEVICE_SECRET)
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
    manager = DatabaseManager(str(path), "correct", device_secret=DEVICE_SECRET)
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


def test_encrypted_backup_historical_password_restore_and_rekey(tmp_path):
    path = tmp_path / "estimation.db"
    manager = DatabaseManager(str(path), "old-password", device_secret=DEVICE_SECRET)
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

    reopened = DatabaseManager(str(path), "new-password", device_secret=DEVICE_SECRET)
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


def test_invalid_pending_restore_rolls_back_to_original_database(tmp_path):
    path = tmp_path / "estimation.db"
    manager = DatabaseManager(str(path), "password", device_secret=DEVICE_SECRET)
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

    reopened = DatabaseManager(str(path), "password", device_secret=DEVICE_SECRET)
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
    manager = DatabaseManager(str(path), "password", device_secret=DEVICE_SECRET)
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

    reopened = DatabaseManager(str(path), "password", device_secret=DEVICE_SECRET)
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
