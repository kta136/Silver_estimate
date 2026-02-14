from __future__ import annotations

from silverestimate.services import settings_service


class _SettingsStub:
    def __init__(self, values=None):
        self._values = dict(values or {})

    def value(self, key, defaultValue=None, type=None):  # noqa: A002 - Qt signature
        value = self._values.get(key, defaultValue)
        if value is defaultValue:
            return defaultValue
        if type is not None and value is not None:
            try:
                return type(value)
            except Exception:
                return defaultValue
        return value

    def setValue(self, key, value):
        self._values[key] = value

    def sync(self):
        return None


class _WindowStub:
    def __init__(self, *, geometry_result=False, state_result=False):
        self.geometry_result = geometry_result
        self.state_result = state_result
        self.geometry_calls = []
        self.state_calls = []

    def restoreGeometry(self, value):
        self.geometry_calls.append(value)
        return self.geometry_result

    def restoreState(self, value):
        self.state_calls.append(value)
        return self.state_result


def _build_service(monkeypatch, values):
    settings = _SettingsStub(values)
    monkeypatch.setattr(settings_service, "get_app_settings", lambda: settings)
    return settings_service.SettingsService()


def test_restore_geometry_returns_false_when_qt_restore_fails(monkeypatch):
    service = _build_service(
        monkeypatch,
        {"ui/main_geometry": b"bad-bytes", "ui/main_state": b"bad-state"},
    )
    window = _WindowStub(geometry_result=False, state_result=False)

    restored = service.restore_geometry(window)

    assert restored is False
    assert window.geometry_calls == [b"bad-bytes"]
    assert window.state_calls == [b"bad-state"]


def test_restore_geometry_returns_true_when_geometry_restores(monkeypatch):
    service = _build_service(
        monkeypatch,
        {"ui/main_geometry": b"ok-geometry"},
    )
    window = _WindowStub(geometry_result=True, state_result=False)

    restored = service.restore_geometry(window)

    assert restored is True
    assert window.geometry_calls == [b"ok-geometry"]
    assert window.state_calls == []


def test_restore_geometry_returns_true_when_state_restores(monkeypatch):
    service = _build_service(
        monkeypatch,
        {"ui/main_geometry": b"bad-geometry", "ui/main_state": b"ok-state"},
    )
    window = _WindowStub(geometry_result=False, state_result=True)

    restored = service.restore_geometry(window)

    assert restored is True
    assert window.geometry_calls == [b"bad-geometry"]
    assert window.state_calls == [b"ok-state"]
