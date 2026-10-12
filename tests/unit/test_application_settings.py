from __future__ import annotations

from typing import Any

import pytest

from silverestimate.infrastructure.settings import (
    SETTINGS_SCHEMA_VERSION,
    ApplicationSettings,
    SettingsKey,
    migrate_settings,
)


class MemorySettingsBackend:
    def __init__(self, values: dict[str, object] | None = None) -> None:
        self.values = dict(values or {})
        self.sync_count = 0

    def value(
        self,
        key: str,
        default: Any = None,
        type: Any = None,  # noqa: A002 - mirrors QSettings
        **_kwargs: Any,
    ) -> Any:
        value = self.values.get(key, default)
        return type(value) if type is not None and value is not None else value

    def setValue(self, key: str, value: Any) -> None:
        self.values[key] = value

    def remove(self, key: str) -> None:
        self.values.pop(key, None)

    def sync(self) -> None:
        self.sync_count += 1

    def contains(self, key: str) -> bool:
        return key in self.values


def test_typed_settings_normalize_values_and_enforce_ranges() -> None:
    backend = MemorySettingsBackend(
        {
            str(SettingsKey.RATES_LIVE_ENABLED): "yes",
            str(SettingsKey.LOGGING_CLEANUP_DAYS): "999",
            str(SettingsKey.PRINT_PREVIEW_ZOOM): "0.05",
            str(SettingsKey.PRINT_DEFAULT_PRINTER): 42,
            str(SettingsKey.UI_ESTIMATE_TABLE_COLUMN_WIDTHS): (90, 120),
        }
    )
    settings = ApplicationSettings(backend, migrate=False)

    assert settings.get_bool(SettingsKey.RATES_LIVE_ENABLED)
    assert (
        settings.get_int(
            SettingsKey.LOGGING_CLEANUP_DAYS,
            30,
            minimum=1,
            maximum=365,
        )
        == 365
    )
    assert (
        settings.get_float(
            SettingsKey.PRINT_PREVIEW_ZOOM,
            1.0,
            minimum=0.25,
            maximum=4.0,
        )
        == 0.25
    )
    assert settings.get_text(SettingsKey.PRINT_DEFAULT_PRINTER) == "42"
    assert settings.get_list(SettingsKey.UI_ESTIMATE_TABLE_COLUMN_WIDTHS) == [90, 120]


def test_future_settings_schema_is_left_untouched() -> None:
    future_version = SETTINGS_SCHEMA_VERSION + 4
    backend = MemorySettingsBackend(
        {
            str(SettingsKey.SCHEMA_VERSION): future_version,
            str(SettingsKey.PRINT_PAGE_SIZE): "Letter / ANSI A",
            "rates/refresh_interval_sec": 15,
        }
    )

    assert migrate_settings(backend) == future_version
    assert backend.values[str(SettingsKey.PRINT_PAGE_SIZE)] == "Letter / ANSI A"
    assert backend.values["rates/refresh_interval_sec"] == 15
    assert backend.sync_count == 0


def test_current_settings_schema_does_not_force_a_backend_sync() -> None:
    backend = MemorySettingsBackend(
        {str(SettingsKey.SCHEMA_VERSION): SETTINGS_SCHEMA_VERSION}
    )

    assert migrate_settings(backend) == SETTINGS_SCHEMA_VERSION
    assert backend.sync_count == 0


@pytest.mark.parametrize(
    ("stored", "level"),
    [
        ({"logging/debug_mode": "true"}, "detailed"),
        ({"logging/enable_info": False}, "errors"),
        ({"logging/enable_critical": False, "logging/enable_debug": True}, "normal"),
        ({}, None),
    ],
)
def test_v3_migration_turns_the_four_logging_switches_into_one_level(stored, level):
    backend = MemorySettingsBackend(
        {str(SettingsKey.SCHEMA_VERSION): 2, "logging/cleanup_days": 7, **stored}
    )

    assert migrate_settings(backend) == SETTINGS_SCHEMA_VERSION == 3

    assert backend.values.get("logging/level") == level
    assert backend.values["logging/cleanup_days"] == 7
    assert not any(
        key in backend.values
        for key in (
            "logging/debug_mode",
            "logging/enable_info",
            "logging/enable_critical",
            "logging/enable_debug",
        )
    )
