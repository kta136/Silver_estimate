"""Recovery is encrypted, transactional and part of the database lifecycle."""

import os
import subprocess
import sys
from pathlib import Path

import pytest

from silverestimate.persistence import schema
from silverestimate.persistence.database_manager import DatabaseManager
from tests.factories import estimate_totals, regular_item


@pytest.fixture
def db(tmp_path):
    manager = DatabaseManager(
        str(tmp_path / "live.db"), "password", device_secret=b"D" * 32
    )
    assert manager.add_item("REG001", "Regular", 90, "WT", 1)
    yield manager
    manager.close()


def test_abrupt_process_exit_preserves_encrypted_recovery(tmp_path):
    path = tmp_path / "crashed.db"
    canary = "PRIVATE_UNFINISHED_ENTRY_CANARY"
    code = """
import os,sys
from silverestimate.persistence.database_manager import DatabaseManager
db=DatabaseManager(sys.argv[1], 'password', device_secret=b'D'*32)
assert db.draft_repository.write('draft-token','UNFINISHED',sys.argv[2],expected_token=None)
os._exit(0)
"""
    subprocess.run(
        [sys.executable, "-c", code, str(path), canary],
        check=True,
        timeout=20,
        env=dict(os.environ, PYTHONPATH=str(Path.cwd())),
    )
    for file in tmp_path.iterdir():
        assert canary.encode() not in file.read_bytes()
    manager = DatabaseManager(str(path), "password", device_secret=b"D" * 32)
    try:
        assert manager.draft_repository.load().payload == canary
        assert manager.conn.execute("SELECT COUNT(*) FROM estimates").fetchone()[0] == 0
        assert (
            manager.conn.execute("SELECT COUNT(*) FROM silver_bars").fetchone()[0] == 0
        )
    finally:
        manager.close()


def test_autosave_never_commits_another_transaction_and_waits_for_maintenance(db):
    db.conn.execute("INSERT INTO items(code,name) VALUES('PENDING','pending')")
    assert not db.draft_repository.write("token", "1", "draft", expected_token=None)
    assert db.conn.in_transaction
    db.conn.rollback()
    assert db.get_item_by_code("PENDING") is None
    with db._broker.maintenance():
        assert not db.draft_repository.write("token", "1", "draft", expected_token=None)
    assert db.draft_repository.write("token", "1", "draft", expected_token=None)


def test_failed_update_preserves_old_copy_and_connection_policy(db):
    repository = db.draft_repository
    assert repository.write("token", "1", "before", expected_token=None)
    timeout = db.conn.execute("PRAGMA busy_timeout").fetchone()[0]
    db.conn.execute(
        "CREATE TRIGGER fail_draft BEFORE UPDATE ON estimate_draft BEGIN SELECT RAISE(ABORT, 'Injected draft failure'); END"
    )
    with pytest.raises(Exception, match="Injected"):
        repository.write("token", "1", "after", expected_token="token")
    assert repository.load().payload == "before"
    assert not db.conn.in_transaction
    assert db.conn.execute("PRAGMA busy_timeout").fetchone()[0] == timeout


def test_recovery_ownership_prevents_accidental_overwrite_or_deletion(db):
    repository = db.draft_repository
    assert repository.write("first", "1", "original", expected_token=None)
    assert not repository.write("second", "2", "replacement", expected_token=None)
    assert not repository.delete("second")
    assert repository.load().payload == "original"


def test_estimate_save_clears_matching_draft_atomically(db):
    assert db.draft_repository.write("token", "1", "draft", expected_token=None)
    db.conn.execute(
        "CREATE TRIGGER fail_save BEFORE INSERT ON estimates BEGIN SELECT RAISE(ABORT, 'Injected'); END"
    )
    assert not db.save_estimate_atomic(
        "1", "2026-09-06", 75, [regular_item()], [], estimate_totals()
    ).success
    assert db.draft_repository.load().payload == "draft"
    db.conn.execute("DROP TRIGGER fail_save")
    assert db.save_estimate_atomic(
        "1", "2026-09-06", 75, [regular_item()], [], estimate_totals()
    ).success
    assert db.draft_repository.load() is None


def test_other_voucher_save_keeps_the_recovery_copy(db):
    assert db.draft_repository.write("token", "OTHER", "draft", expected_token=None)
    assert db.save_estimate_atomic(
        "1", "2026-09-06", 75, [regular_item()], [], estimate_totals()
    ).success
    assert db.draft_repository.load().payload == "draft"


def test_backup_rekey_and_restore_preserve_recovery(db, tmp_path):
    assert db.draft_repository.write(
        "token", "1", "original draft", expected_token=None
    )
    backup = db.create_encrypted_backup(tmp_path / "backup.sedbbackup")
    db.change_passwords("new-password")
    assert db.draft_repository.load().payload == "original draft"
    assert db.draft_repository.write(
        "token", "1", "later draft", expected_token="token"
    )
    db.stage_encrypted_restore(backup.path, "password")
    path = db.database_path
    db.close()
    reopened = DatabaseManager(path, "new-password", device_secret=b"D" * 32)
    try:
        assert reopened.draft_repository.load().payload == "original draft"
    finally:
        reopened.close()


@pytest.mark.parametrize("operation", ["delete_all_estimates", "drop_tables"])
def test_deliberate_purge_removes_recovery(db, operation):
    assert db.draft_repository.write("token", "1", "draft", expected_token=None)
    assert getattr(db, operation)()
    if operation == "drop_tables":
        db.setup_database()
    assert db.draft_repository.load() is None


@pytest.mark.parametrize("fail", [False, True])
def test_v9_upgrade_is_transactional(db, monkeypatch, fail):
    db.conn.execute("DROP TABLE estimate_draft")
    db.conn.execute("DELETE FROM schema_version")
    db.conn.execute(
        "INSERT INTO schema_version(version,applied_date) VALUES(9,'2026-09-06')"
    )
    db.conn.commit()
    if fail:
        with monkeypatch.context() as patch:

            def reject(_db):
                raise RuntimeError("Injected schema validation failure")

            patch.setattr(schema, "_validate_schema", reject)
            with pytest.raises(RuntimeError, match="Injected"):
                db.setup_database()
        assert db._check_schema_version() == 9
        assert not db._table_exists("estimate_draft")
    db.setup_database()
    assert db._check_schema_version() == 10
    assert db.draft_repository.load() is None
    assert db.get_item_by_code("REG001")["name"] == "Regular"
