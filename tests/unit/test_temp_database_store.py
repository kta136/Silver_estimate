from __future__ import annotations

import os
from pathlib import Path

import pytest

from silverestimate.persistence.database_manager import _TempDatabaseStore


@pytest.fixture
def temp_store_factory(monkeypatch):
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
    monkeypatch.setattr(
        "silverestimate.persistence.database_manager.get_app_settings",
        lambda: stub_settings,
    )

    def factory(**kwargs):
        store = _TempDatabaseStore(**kwargs)
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
