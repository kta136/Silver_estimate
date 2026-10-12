from __future__ import annotations

import pytest

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


@pytest.mark.parametrize(
    "stored, geometry_result, state_result, restored, state_calls",
    [
        pytest.param(
            {"ui/main_geometry": b"bad-bytes", "ui/main_state": b"bad-state"},
            False,
            False,
            False,
            [b"bad-state"],
            id="neither-restores",
        ),
        pytest.param(
            {"ui/main_geometry": b"ok-geometry"},
            True,
            False,
            True,
            [],
            id="geometry-restores",
        ),
        pytest.param(
            {"ui/main_geometry": b"bad-geometry", "ui/main_state": b"ok-state"},
            False,
            True,
            True,
            [b"ok-state"],
            id="state-restores",
        ),
    ],
)
def test_restore_geometry_reports_whether_anything_was_restored(
    monkeypatch, stored, geometry_result, state_result, restored, state_calls
):
    service = _build_service(monkeypatch, stored)
    window = _WindowStub(geometry_result=geometry_result, state_result=state_result)

    assert service.restore_geometry(window) is restored
    assert window.geometry_calls == [stored["ui/main_geometry"]]
    assert window.state_calls == state_calls
