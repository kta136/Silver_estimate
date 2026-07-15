from __future__ import annotations

import os

import pytest

from silverestimate.persistence.temp_database_store import TempDatabaseStore


@pytest.fixture
def temp_store_factory():
    entries = {}
    created = []

    class StubSettings:
        def setValue(self, key, value):
            entries[key] = value

        def remove(self, key):
            entries.pop(key, None)

        def sync(self):
            pass

    stub_settings = StubSettings()
    def factory(**kwargs):
        store = TempDatabaseStore(
            settings_factory=lambda: stub_settings,
            **kwargs,
        )
        created.append(store)
        return store

    yield factory, entries

    for store in created:
        store.cleanup()


def test_create_allocates_file(temp_store_factory):
    factory, entries = temp_store_factory
    store = factory()
    path = store.create()
    assert path.exists()
    assert path.name == "session.sqlite"
    assert "silverestimate-db-" in path.parent.name
    assert entries == {}


def test_register_persists_path(temp_store_factory):
    factory, entries = temp_store_factory
    store = factory()
    path = store.create()
    store.register_for_recovery()
    assert entries.get(store.SETTINGS_KEY) == str(path)


def test_cleanup_removes_file_and_settings(temp_store_factory):
    factory, entries = temp_store_factory
    store = factory()
    path = store.create()
    store.register_for_recovery()
    store.cleanup()
    assert not path.exists()
    assert store.SETTINGS_KEY not in entries


def test_cleanup_preserve_keeps_file(temp_store_factory):
    factory, entries = temp_store_factory
    store = factory()
    path = store.create()
    store.cleanup(preserve=True)
    assert path.exists()
    assert entries.get(store.SETTINGS_KEY) == str(path)
    # clean manually
    os.remove(path)


def test_metadata_disabled_skips_registration(temp_store_factory):
    factory, entries = temp_store_factory
    store = factory(store_metadata=False)
    path = store.create()
    store.register_for_recovery()
    assert store.SETTINGS_KEY not in entries
    store.cleanup(preserve=True)
    assert store.SETTINGS_KEY not in entries
    assert path.exists()
    os.remove(path)


def test_temp_directory_has_ownership_and_database_identity(
    temp_store_factory, tmp_path
):
    factory, _entries = temp_store_factory
    encrypted_path = tmp_path / "silver.enc"
    store = factory(encrypted_db_path=str(encrypted_path))
    path = store.create()

    marker = TempDatabaseStore.read_ownership_marker(path)

    assert marker is not None
    assert marker["owner"] == TempDatabaseStore.MARKER_OWNER
    assert marker["pid"] == os.getpid()
    assert marker["created_at"] > 0
    assert marker["encrypted_database_identity"] == (
        TempDatabaseStore.encrypted_database_identity(str(encrypted_path))
    )


def test_cleanup_marked_database_removes_wal_and_shm(temp_store_factory, tmp_path):
    factory, _entries = temp_store_factory
    encrypted_path = tmp_path / "silver.enc"
    store = factory(encrypted_db_path=str(encrypted_path))
    path = store.create()
    wal_path = path.with_name(f"{path.name}-wal")
    shm_path = path.with_name(f"{path.name}-shm")
    wal_path.write_bytes(b"wal")
    shm_path.write_bytes(b"shm")

    assert TempDatabaseStore.cleanup_marked_database(
        path,
        str(encrypted_path),
    )
    assert not path.exists()
    assert not wal_path.exists()
    assert not shm_path.exists()


def test_cleanup_never_removes_unmarked_directory(tmp_path):
    directory = tmp_path / "not-owned"
    directory.mkdir()
    database = directory / "session.sqlite"
    database.write_bytes(b"keep")

    assert not TempDatabaseStore.cleanup_marked_database(
        database,
        str(tmp_path / "silver.enc"),
    )
    assert database.exists()


def test_cleanup_removes_sidecars_when_main_database_is_already_missing(
    temp_store_factory,
):
    factory, _entries = temp_store_factory
    store = factory()
    path = store.create()
    wal_path = path.with_name(f"{path.name}-wal")
    shm_path = path.with_name(f"{path.name}-shm")
    wal_path.write_bytes(b"wal")
    shm_path.write_bytes(b"shm")
    path.unlink()

    store.cleanup()

    assert not wal_path.exists()
    assert not shm_path.exists()
