import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _coerce_bool(value, default):
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    if value is None:
        if isinstance(default, bool):
            return default
        return False
    return bool(value)


class _SettingsStub:
    """In-memory replacement for QSettings during tests."""

    _data = {}

    def __init__(self, org="YourCompany", app="SilverEstimateApp"):
        self._key = (org, app)
        self._store = _SettingsStub._data.setdefault(self._key, {})

    def value(self, key, default=None, type=None, **kwargs):  # noqa: A002 - signature mirrors QSettings
        if "defaultValue" in kwargs and default is None:
            default = kwargs["defaultValue"]
        if "type" in kwargs and type is None:
            type = kwargs["type"]
        val = self._store.get(key, default)
        if type is bool:
            return _coerce_bool(val, default)
        return val

    def setValue(self, key, value):
        self._store[key] = value

    def remove(self, key):
        self._store.pop(key, None)

    def sync(self):  # QSettings compatibility
        return True

    @classmethod
    def clear(cls):
        cls._data.clear()


class _CredentialStoreStub:
    """In-memory stand-in for secure credential storage."""

    _store = {}
    _legacy_keys = {
        "main": "security/password_hash",
        "backup": "security/backup_hash",
    }

    @classmethod
    def reset(cls):
        cls._store = {}

    @classmethod
    def _legacy_key(cls, kind: str) -> str:
        return cls._legacy_keys[kind]

    @classmethod
    def get_password_hash(cls, kind, *, settings=None, logger=None):
        value = cls._store.get(kind)
        if value is not None:
            return value
        if settings is None:
            return None
        legacy_key = cls._legacy_key(kind)
        legacy_value = settings.value(legacy_key)
        if legacy_value is not None:
            cls._store[kind] = legacy_value
            settings.remove(legacy_key)
            return legacy_value
        return None

    @classmethod
    def set_password_hash(cls, kind, value, *, settings=None, logger=None):
        cls._store[kind] = value
        if settings is not None:
            settings.remove(cls._legacy_key(kind))

    @classmethod
    def delete_password_hash(cls, kind, *, settings=None, logger=None):
        cls._store.pop(kind, None)
        if settings is not None:
            settings.remove(cls._legacy_key(kind))


@pytest.fixture(scope="session")
def qt_app():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PyQt5.QtWidgets import QApplication

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


@pytest.fixture()
def settings_stub(monkeypatch):
    _SettingsStub.clear()
    _CredentialStoreStub.reset()
    monkeypatch.setattr("silverestimate.persistence.database_manager.QSettings", _SettingsStub, raising=False)
    monkeypatch.setattr("silverestimate.services.auth_service.QSettings", _SettingsStub, raising=False)
    monkeypatch.setattr("silverestimate.services.live_rate_service.QSettings", _SettingsStub, raising=False)
    monkeypatch.setattr("silverestimate.ui.estimate_entry.QSettings", _SettingsStub, raising=False)
    monkeypatch.setattr("silverestimate.infrastructure.logger.QSettings", _SettingsStub, raising=False)
    monkeypatch.setattr("silverestimate.infrastructure.settings.QSettings", _SettingsStub, raising=False)
    monkeypatch.setattr(
        "silverestimate.security.credential_store.get_password_hash",
        _CredentialStoreStub.get_password_hash,
        raising=False,
    )
    monkeypatch.setattr(
        "silverestimate.security.credential_store.set_password_hash",
        _CredentialStoreStub.set_password_hash,
        raising=False,
    )
    monkeypatch.setattr(
        "silverestimate.security.credential_store.delete_password_hash",
        _CredentialStoreStub.delete_password_hash,
        raising=False,
    )
    yield _SettingsStub
    _SettingsStub.clear()
    _CredentialStoreStub.reset()
