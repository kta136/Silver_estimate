from __future__ import annotations

from typing import Any

import pytest

from silverestimate.ui import settings_logging_page as page_module
from silverestimate.ui.settings_logging_page import (
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


def _controller(
    monkeypatch,
    settings,
    *,
    reconfigure=lambda: None,
    cleanup=lambda _days: 0,
    open_logs_folder=lambda: True,
) -> SettingsLoggingController:
    """A controller whose logging runtime calls are replaced for the test."""
    logger_module = page_module.application_logger
    monkeypatch.setattr(logger_module, "reconfigure_logging", reconfigure)
    monkeypatch.setattr(
        logger_module, "cleanup_old_logs", lambda max_age_days: cleanup(max_age_days)
    )
    monkeypatch.setattr(page_module, "_open_logs_folder", open_logs_folder)
    return SettingsLoggingController(settings)


def test_load_state_normalizes_logging_values() -> None:
    settings = _MemorySettings(
        {
            "logging/level": "detailed",
            "logging/auto_cleanup": "enabled",
            "logging/cleanup_days": 900,
        }
    )

    state = SettingsLoggingController(settings).load_state()

    assert state == LoggingSettingsState(
        level="detailed",
        auto_cleanup=True,
        cleanup_days=365,
    )


def test_apply_state_persists_group_before_reconfiguring_runtime(monkeypatch) -> None:
    settings = _MemorySettings()
    observed: list[dict[str, object]] = []
    controller = _controller(
        monkeypatch,
        settings,
        reconfigure=lambda: observed.append(dict(settings.values)),
    )
    state = LoggingSettingsState(
        level="errors",
        auto_cleanup=True,
        cleanup_days=30,
    )

    controller.apply_state(state)

    assert observed == [settings.values]
    assert settings.values == {
        "logging/level": "errors",
        "logging/auto_cleanup": True,
        "logging/cleanup_days": 30,
    }


def test_apply_failure_restores_previous_logging_state(monkeypatch) -> None:
    previous = LoggingSettingsState()
    settings = _MemorySettings(
        {
            "logging/level": previous.level,
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

    controller = _controller(monkeypatch, settings, reconfigure=reconfigure)

    with pytest.raises(RuntimeError, match="handler setup failed"):
        controller.apply_state(LoggingSettingsState(level="detailed", cleanup_days=90))

    assert controller.load_state() == previous
    assert attempts == 2


def test_cleanup_and_folder_actions_report_their_outcomes(monkeypatch) -> None:
    controller = _controller(
        monkeypatch,
        _MemorySettings(),
        cleanup=lambda days: days + 2,
        open_logs_folder=lambda: False,
    )

    assert controller.cleanup_logs(5) == (True, "Removed 7 old log files.")
    succeeded, message = controller.cleanup_logs(0)
    assert not succeeded and "between 1 and 365" in message
    assert controller.open_logs_folder() == (
        "The operating system could not open the logs folder."
    )


def test_an_unknown_stored_level_falls_back_to_normal_and_cannot_be_applied() -> None:
    settings = _MemorySettings({"logging/level": "verbose"})
    controller = SettingsLoggingController(settings)

    assert controller.load_state().level == "normal"
    with pytest.raises(ValueError, match="detail level"):
        controller.validate_state(LoggingSettingsState(level="verbose"))
