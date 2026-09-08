"""Real encrypted startup handoffs never transfer an open connection."""

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from silverestimate.persistence.database_driver import DatabaseAuthenticationError
from silverestimate.persistence.database_manager import DatabaseManager
from silverestimate.persistence.storage_metadata import StorageMetadataError

SECRET = b"S" * 32
PASSWORD = "startup-test-password"


def open_database(path):
    return DatabaseManager(str(path), PASSWORD, device_secret=SECRET)


@pytest.mark.parametrize("version", [None, 8, 9, 10])
def test_worker_prepares_and_ui_owns_fresh_current_writer(tmp_path, version):
    path = tmp_path / "startup.db"
    if version is not None:
        initial = open_database(path)
        initial.conn.execute("INSERT INTO items(code,name) VALUES('A','Retained')")
        if version < 10:
            initial.conn.execute("DROP TABLE estimate_draft")
            initial.conn.execute("UPDATE schema_version SET version = ?", (version,))
        if version == 8:
            for column in ("item_code_snapshot", "tunch", "snapshot_version"):
                initial.conn.execute(f"ALTER TABLE estimate_items DROP COLUMN {column}")
        initial.close()
    with ThreadPoolExecutor(max_workers=1) as pool:
        prepared = pool.submit(
            DatabaseManager.prepare_startup, str(path), PASSWORD, device_secret=SECRET
        ).result(timeout=10)
        assert prepared.conn is None
        assert prepared.cursor is None
        assert not prepared._session.is_owner()
        prepared.attach_prepared_connection()
        try:
            assert prepared._session.is_owner()
            assert prepared._check_schema_version() == 10
            assert (
                prepared.conn.execute("SELECT COUNT(*) FROM estimate_draft").fetchone()[
                    0
                ]
                == 0
            )
            if version is not None:
                assert (
                    prepared.conn.execute("SELECT name FROM items").fetchone()[0]
                    == "Retained"
                )
            assert not pool.submit(prepared._session.is_owner).result(timeout=10)
            future = pool.submit(prepared.conn.execute, "SELECT 1")
            with pytest.raises(Exception, match="same thread"):
                future.result(timeout=10)
        finally:
            prepared.close()


@pytest.mark.parametrize("changed_file", ["database", "wal", "journal"])
def test_changed_files_reject_handoff_until_full_validation_again(
    tmp_path, changed_file
):
    path = tmp_path / "startup.db"
    prepared = DatabaseManager.prepare_startup(
        str(path), PASSWORD, device_secret=SECRET
    )
    if changed_file == "database":
        other = open_database(path)
        other.conn.execute("INSERT INTO items(code,name) VALUES('B','Changed')")
        other.close()
    elif changed_file == "wal":
        Path(f"{path}-wal").write_bytes(b"changed")
    else:
        path.with_suffix(".restore.json").write_text("{}")
    with pytest.raises(StorageMetadataError, match="changed during startup"):
        prepared.attach_prepared_connection()
    assert prepared.conn is None
    with pytest.raises(RuntimeError, match="No detached"):
        prepared.attach_prepared_connection()


def test_attachment_is_single_use_and_close_invalidates_unused_handoff(tmp_path):
    path = tmp_path / "startup.db"
    prepared = DatabaseManager.prepare_startup(
        str(path), PASSWORD, device_secret=SECRET
    )
    prepared.attach_prepared_connection()
    try:
        with pytest.raises(RuntimeError, match="No detached"):
            prepared.attach_prepared_connection()
        assert prepared.conn.execute("SELECT 1").fetchone()[0] == 1
    finally:
        prepared.close()
    with pytest.raises(RuntimeError, match="No detached"):
        prepared.attach_prepared_connection()
    prepared = DatabaseManager.prepare_startup(
        str(path), PASSWORD, device_secret=SECRET
    )
    prepared.close()
    with pytest.raises(RuntimeError, match="No detached"):
        prepared.attach_prepared_connection()


@pytest.mark.parametrize("existing", [False, True])
def test_validation_failure_closes_connection_and_rolls_back(tmp_path, existing):
    path = tmp_path / "startup.db"
    if existing:
        open_database(path).close()
    captured = []

    class FailingDatabase(DatabaseManager):
        def validate_database(self, connection, **kwargs):
            captured.append(self)
            connection.execute(
                "INSERT INTO items(code,name) VALUES('BAD','Uncommitted')"
            )
            raise ValueError("injected validation failure")

    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(
            FailingDatabase.prepare_startup, str(path), PASSWORD, device_secret=SECRET
        )
        with pytest.raises(ValueError, match="validation failure"):
            future.result(timeout=10)
    assert captured[0].conn is None
    assert captured[0].cursor is None
    assert not captured[0]._session.is_owner()
    assert path.exists() is existing
    reopened = open_database(path)
    try:
        assert reopened.conn.execute("SELECT COUNT(*) FROM items").fetchone()[0] == 0
    finally:
        reopened.close()


def test_wrong_password_fails_without_changing_existing_data(tmp_path):
    path = tmp_path / "startup.db"
    open_database(path).close()
    before = path.read_bytes()
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(
            DatabaseManager.prepare_startup, str(path), "wrong", device_secret=SECRET
        )
        with pytest.raises(DatabaseAuthenticationError):
            future.result(timeout=10)
    assert path.read_bytes() == before
    open_database(path).close()


def test_failed_ui_attach_releases_new_connection(tmp_path, monkeypatch):
    path = tmp_path / "startup.db"
    prepared = DatabaseManager.prepare_startup(
        str(path), PASSWORD, device_secret=SECRET
    )

    def fail_bind():
        assert prepared.conn is not None
        raise RuntimeError("failed UI bind")

    monkeypatch.setattr(prepared, "_bind_connection", fail_bind)
    with pytest.raises(RuntimeError, match="failed UI bind"):
        prepared.attach_prepared_connection()
    assert prepared.conn is None
    open_database(path).close()
