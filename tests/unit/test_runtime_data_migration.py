from __future__ import annotations

from silverestimate.infrastructure import paths, settings
from silverestimate.infrastructure.app_constants import (
    LEGACY_SETTINGS_ORG,
    SETTINGS_APP,
    SETTINGS_ORG,
)
from silverestimate.infrastructure.data_migration import migrate_legacy_database


class _MemorySettings:
    class Status:
        NoError = 0

    stores: dict[tuple[str, str], dict[str, object]] = {}

    def __init__(self, org: str, app: str) -> None:
        self.identity = (org, app)
        self.store = self.stores.setdefault(self.identity, {})

    def value(self, key: str, default=None):
        return self.store.get(key, default)

    def setValue(self, key: str, value: object) -> None:
        self.store[key] = value

    def contains(self, key: str) -> bool:
        return key in self.store

    def allKeys(self) -> list[str]:
        return list(self.store)

    def remove(self, key: str) -> None:
        self.store.pop(key, None)

    def sync(self) -> None:
        return None

    def status(self) -> int:
        return self.Status.NoError


def test_database_path_uses_frozen_executable_directory(monkeypatch, tmp_path):
    executable = tmp_path / "SilverEstimate.exe"
    monkeypatch.setattr(paths.sys, "frozen", True, raising=False)
    monkeypatch.setattr(paths.sys, "executable", str(executable))

    assert paths.get_database_path() == tmp_path / "database" / "estimation.db"


def test_legacy_database_is_moved_after_verified_copy(tmp_path):
    source = tmp_path / "old-working-directory" / "database" / "estimation.db"
    target = tmp_path / "exe" / "database" / "estimation.db"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"encrypted database payload")

    result = migrate_legacy_database(target, candidates=[source])

    assert result == target.resolve()
    assert target.read_bytes() == b"encrypted database payload"
    assert not source.exists()


def test_existing_canonical_database_wins_without_deleting_legacy(tmp_path):
    source = tmp_path / "legacy" / "estimation.db"
    target = tmp_path / "exe" / "database" / "estimation.db"
    source.parent.mkdir(parents=True)
    target.parent.mkdir(parents=True)
    source.write_bytes(b"legacy")
    target.write_bytes(b"canonical")

    migrate_legacy_database(target, candidates=[source])

    assert target.read_bytes() == b"canonical"
    assert source.read_bytes() == b"legacy"


def test_get_app_settings_moves_every_legacy_key(monkeypatch):
    _MemorySettings.stores = {}
    monkeypatch.setattr(settings, "QSettings", _MemorySettings)
    legacy = _MemorySettings(LEGACY_SETTINGS_ORG, SETTINGS_APP)
    primary = _MemorySettings(SETTINGS_ORG, SETTINGS_APP)
    legacy.setValue("security/db_salt", b"salt")
    legacy.setValue("print/page/margin", 12)
    legacy.setValue("ui/theme", "legacy")
    primary.setValue("ui/theme", "current")

    migrated = settings.get_app_settings()

    assert migrated.identity == (SETTINGS_ORG, SETTINGS_APP)
    assert migrated.value("security/db_salt") == b"salt"
    assert migrated.value("print/page/margin") == 12
    assert migrated.value("ui/theme") == "current"
    assert legacy.allKeys() == []
