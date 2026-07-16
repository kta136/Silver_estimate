import os
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from PyQt6.QtCore import QLocale

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_SLOW_PATH_SUFFIXES = {
    "tests/ui/test_estimate_entry_integration.py",
    "tests/ui/test_main_window_interactions.py",
    "tests/ui/test_mode_toggle_buttons.py",
}


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

    class Status:
        NoError = 0

    _data = {}

    def __init__(self, org="SilverEstimate", app="SilverEstimateApp"):
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

    def contains(self, key):
        return key in self._store

    def allKeys(self):
        return list(self._store)

    def status(self):
        return 0

    def sync(self):  # QSettings compatibility
        return True

    @classmethod
    def clear(cls):
        cls._data.clear()


class _CredentialStoreStub:
    """In-memory stand-in for secure credential storage."""

    _store = {}

    @classmethod
    def reset(cls):
        cls._store = {}

    @classmethod
    def get_password_hash(cls, kind):
        return cls._store.get(kind)

    @classmethod
    def set_password_hash(cls, kind, value, *, logger=None):
        cls._store[kind] = value

    @classmethod
    def delete_password_hash(cls, kind, *, logger=None):
        cls._store.pop(kind, None)


@pytest.fixture(scope="session")
def qt_app():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PyQt6.QtWidgets import QApplication

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


@pytest.fixture()
def settings_stub(monkeypatch):
    _SettingsStub.clear()
    _CredentialStoreStub.reset()
    monkeypatch.setattr(
        "silverestimate.persistence.database_manager.QSettings",
        _SettingsStub,
        raising=False,
    )
    monkeypatch.setattr(
        "silverestimate.services.auth_service.QSettings", _SettingsStub, raising=False
    )
    monkeypatch.setattr(
        "silverestimate.services.live_rate_service.QSettings",
        _SettingsStub,
        raising=False,
    )
    monkeypatch.setattr(
        "silverestimate.ui.estimate_entry.QSettings", _SettingsStub, raising=False
    )
    monkeypatch.setattr(
        "silverestimate.infrastructure.logger.QSettings", _SettingsStub, raising=False
    )
    monkeypatch.setattr(
        "silverestimate.infrastructure.settings.QSettings", _SettingsStub, raising=False
    )
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
    monkeypatch.setattr(
        "silverestimate.security.credential_store.get_backend_status",
        lambda: SimpleNamespace(
            available=True, backend_name="tests.stub.keyring", reason=""
        ),
        raising=False,
    )
    yield _SettingsStub
    _SettingsStub.clear()
    _CredentialStoreStub.reset()


def pytest_collection_modifyitems(items):
    run_smoke = bool(items and items[0].config.getoption("--run-smoke"))
    skip_smoke = pytest.mark.skip(reason="use --run-smoke to run smoke tests")
    for item in items:
        path = item.path.as_posix()
        if "/tests/smoke/" in path:
            item.add_marker(pytest.mark.smoke)
        if "/tests/integration/" in path:
            item.add_marker(pytest.mark.integration)
        elif "/tests/smoke/" not in path:
            item.add_marker(pytest.mark.unit)
        if any(path.endswith(suffix) for suffix in _SLOW_PATH_SUFFIXES):
            item.add_marker(pytest.mark.slow)
        if item.get_closest_marker("smoke") and not run_smoke:
            item.add_marker(skip_smoke)


@pytest.fixture(autouse=True)
def estimate_table_locale(monkeypatch):
    monkeypatch.setattr(
        "silverestimate.ui.estimate_table_formatting.get_estimate_table_locale",
        lambda: QLocale(QLocale.Language.English, QLocale.Country.India),
    )


def pytest_addoption(parser):
    parser.addoption(
        "--run-smoke",
        action="store_true",
        default=False,
        help="Run opt-in full-startup smoke tests.",
    )
    parser.addoption(
        "--smoke-screenshots",
        action="store_true",
        default=False,
        help="Capture UI screenshots during smoke tests.",
    )
    parser.addoption(
        "--smoke-artifact-dir",
        action="store",
        default="artifacts/smoke-ui",
        help="Directory where smoke screenshots are written.",
    )
