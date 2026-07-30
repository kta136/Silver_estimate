from __future__ import annotations

from typing import Any

import pytest

from silverestimate.ui.settings_logging_page import (
    LoggingSettingsActions,
    LoggingSettingsState,
    SettingsLoggingController,
)


class _MemorySettings:
    def __init__(self, values: dict[str, object] | None = None) -> None:
        self.values = dict(values or {})

    def value(  # noqa: A002 - mirrors the QSettings API
        self,
        key: str,
        default: Any = None,
        type: Any = None,
    ) -> Any:
        del type
        return self.values.get(key, default)

    def setValue(self, key: str, value: Any) -> None:
        self.values[key] = value

    def remove(self, key: str) -> None:
        self.values.pop(key, None)

    def sync(self) -> bool:
        return True


def _actions(
    *,
    reconfigure=lambda: None,
    cleanup=lambda _days: 0,
    open_logs_folder=lambda: True,
) -> LoggingSettingsActions:
    return LoggingSettingsActions(
        reconfigure=reconfigure,
        cleanup=cleanup,
        open_logs_folder=open_logs_folder,
    )


def test_load_state_normalizes_logging_values() -> None:
    settings = _MemorySettings(
        {
            "logging/debug_mode": "yes",
            "logging/enable_info": "off",
            "logging/enable_critical": 1,
            "logging/enable_debug": 0,
            "logging/auto_cleanup": "enabled",
            "logging/cleanup_days": 900,
        }
    )

    state = SettingsLoggingController(settings, _actions()).load_state()

    assert state == LoggingSettingsState(
        debug_mode=True,
        enable_info=False,
        enable_critical=True,
        enable_debug=False,
        auto_cleanup=True,
        cleanup_days=365,
    )


def test_apply_state_persists_group_before_reconfiguring_runtime() -> None:
    settings = _MemorySettings()
    observed: list[dict[str, object]] = []
    controller = SettingsLoggingController(
        settings,
        _actions(reconfigure=lambda: observed.append(dict(settings.values))),
    )
    state = LoggingSettingsState(
        debug_mode=True,
        enable_info=False,
        enable_critical=True,
        enable_debug=True,
        auto_cleanup=True,
        cleanup_days=30,
    )

    controller.apply_state(state)

    assert observed == [settings.values]
    assert settings.values == {
        "logging/debug_mode": True,
        "logging/enable_info": False,
        "logging/enable_critical": True,
        "logging/enable_debug": True,
        "logging/auto_cleanup": True,
        "logging/cleanup_days": 30,
    }


def test_apply_failure_restores_previous_logging_state() -> None:
    previous = LoggingSettingsState()
    settings = _MemorySettings(
        {
            "logging/debug_mode": previous.debug_mode,
            "logging/enable_info": previous.enable_info,
            "logging/enable_critical": previous.enable_critical,
            "logging/enable_debug": previous.enable_debug,
            "logging/auto_cleanup": previous.auto_cleanup,
            "logging/cleanup_days": previous.cleanup_days,
        }
    )
    attempts = 0

    def reconfigure() -> None:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise RuntimeError("handler setup failed")

    controller = SettingsLoggingController(
        settings,
        _actions(reconfigure=reconfigure),
    )

    with pytest.raises(RuntimeError, match="handler setup failed"):
        controller.apply_state(LoggingSettingsState(debug_mode=True, cleanup_days=90))

    assert controller.load_state() == previous
    assert attempts == 2


def test_cleanup_and_folder_actions_return_explicit_outcomes() -> None:
    controller = SettingsLoggingController(
        _MemorySettings(),
        _actions(
            cleanup=lambda days: days + 2,
            open_logs_folder=lambda: False,
        ),
    )

    cleanup = controller.cleanup_logs(5)
    invalid_cleanup = controller.cleanup_logs(0)
    open_folder = controller.open_logs_folder()

    assert cleanup.succeeded
    assert cleanup.removed_count == 7
    assert not invalid_cleanup.succeeded
    assert not open_folder.succeeded
