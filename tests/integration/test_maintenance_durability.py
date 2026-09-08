"""Durable maintenance against real disposable encrypted databases."""

import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from silverestimate.persistence import database_manager as storage
from silverestimate.persistence.database_driver import SqlCipherConnectionBroker
from silverestimate.persistence.database_manager import (
    DatabaseManager,
    MaintenanceStatus,
)
from silverestimate.persistence.storage_metadata import StorageMetadataError


@pytest.fixture
def manager(tmp_path):
    db = DatabaseManager(str(tmp_path / "live.db"), "password", device_secret=b"S" * 32)
    db.conn.execute("INSERT INTO items(code,name) VALUES('A','Saved')")
    db.conn.commit()
    yield db
    db.close()


def test_all_writers_use_full_wal_durability(manager):
    assert manager.conn.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
    assert manager.conn.execute("PRAGMA synchronous").fetchone()[0] == 2

    def check_worker():
        conn, _ = manager._broker.open_writer()
        try:
            return conn.execute("PRAGMA synchronous").fetchone()[0]
        finally:
            conn.close()

    with ThreadPoolExecutor(max_workers=1) as pool:
        assert pool.submit(check_worker).result(timeout=10) == 2


def test_worker_backup_restore_uses_owned_connections(manager, tmp_path, monkeypatch):
    owner = threading.get_ident()
    opened_on = []
    original = SqlCipherConnectionBroker.open_writer

    def track(self, **kwargs):
        opened_on.append(threading.get_ident())
        return original(self, **kwargs)

    monkeypatch.setattr(SqlCipherConnectionBroker, "open_writer", track)
    main_connection = manager.conn
    with ThreadPoolExecutor(max_workers=1) as pool:
        backup = pool.submit(
            manager.create_encrypted_backup, tmp_path / "copy.sedbbackup"
        ).result(timeout=10)
        assert backup.status is MaintenanceStatus.SUCCESS
        restored = pool.submit(
            manager.stage_encrypted_restore, backup.path, "password"
        ).result(timeout=10)
        assert restored.status is MaintenanceStatus.STAGED_RESTART_REQUIRED
    assert opened_on and all(thread != owner for thread in opened_on)
    assert manager.conn is main_connection
    assert (
        manager.conn.execute("SELECT name FROM items WHERE code='A'").fetchone()[0]
        == "Saved"
    )


@pytest.mark.parametrize("failure", ["flush", "publish"])
def test_failed_backup_preserves_previous_archive_and_releases_maintenance(
    manager, tmp_path, monkeypatch, failure
):
    destination = tmp_path / "copy.sedbbackup"
    manager.create_encrypted_backup(destination)
    before = destination.read_bytes()

    def fail(*args):
        raise OSError("injected storage failure")

    monkeypatch.setattr(storage.os, "fsync" if failure == "flush" else "replace", fail)
    with pytest.raises(OSError, match="injected"):
        manager.create_encrypted_backup(destination)
    assert destination.read_bytes() == before
    assert not list(tmp_path.glob(".silverestimate-backup-*"))
    with manager._broker.open_read_connection() as reader:
        assert reader.execute("SELECT COUNT(*) FROM items").fetchone()[0] == 1


def test_second_restore_preserves_validated_stage_and_journal(manager, tmp_path):
    backup = manager.create_encrypted_backup(tmp_path / "copy.sedbbackup")
    first = manager.stage_encrypted_restore(backup.path, "password")
    staged = Path(first.path)
    before = staged.read_bytes(), manager._restore_journal.read_bytes()
    with pytest.raises(StorageMetadataError, match="already staged"):
        manager.stage_encrypted_restore(backup.path, "wrong-password")
    assert (staged.read_bytes(), manager._restore_journal.read_bytes()) == before


def test_failed_restore_validation_never_publishes_stage(
    manager, tmp_path, monkeypatch
):
    backup = manager.create_encrypted_backup(tmp_path / "copy.sedbbackup")

    def fail(*args):
        raise StorageMetadataError("injected validation failure")

    monkeypatch.setattr(manager, "_validate_external", fail)
    with pytest.raises(StorageMetadataError, match="injected"):
        manager.stage_encrypted_restore(backup.path, "password")
    assert not manager._restore_journal.exists()
    assert not (tmp_path / "live.restore.staged").exists()
    assert not list(tmp_path.glob(".silverestimate-restore-*"))
    assert manager.conn.execute("SELECT name FROM items").fetchone()[0] == "Saved"


def test_backup_does_not_commit_or_include_pending_writer_changes(manager, tmp_path):
    import zipfile

    manager.conn.execute("UPDATE items SET name='Unsaved' WHERE code='A'")
    with ThreadPoolExecutor(max_workers=1) as pool:
        backup = pool.submit(
            manager.create_encrypted_backup, tmp_path / "copy.sedbbackup"
        ).result(timeout=10)
    assert manager.conn.in_transaction
    with zipfile.ZipFile(backup.path) as archive:
        archive.extract("database.sqlcipher", tmp_path / "inspect")
    broker = SqlCipherConnectionBroker(
        tmp_path / "inspect" / "database.sqlcipher",
        manager.key,
        database_salt=manager.database_salt,
    )
    copied, _ = broker.open_writer()
    try:
        assert copied.execute("SELECT name FROM items").fetchone()[0] == "Saved"
    finally:
        copied.close()
        manager.conn.rollback()
