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

    def value(self, key, default=None, type=None):  # noqa: A002 - signature mirrors QSettings
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
    monkeypatch.setattr("silverestimate.persistence.database_manager.QSettings", _SettingsStub, raising=False)
    monkeypatch.setattr("silverestimate.services.auth_service.QSettings", _SettingsStub, raising=False)
    monkeypatch.setattr("silverestimate.services.live_rate_service.QSettings", _SettingsStub, raising=False)
    monkeypatch.setattr("silverestimate.ui.estimate_entry.QSettings", _SettingsStub, raising=False)
    monkeypatch.setattr("silverestimate.infrastructure.logger.QSettings", _SettingsStub, raising=False)
    yield _SettingsStub
    _SettingsStub.clear()
