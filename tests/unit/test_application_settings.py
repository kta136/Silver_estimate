from __future__ import annotations

from typing import Any

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
            str(SettingsKey.PRINT_ESTIMATE_LAYOUT): 42,
            str(SettingsKey.UI_SILVER_BARS_AVAILABLE_COLUMNS): (90, 120),
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
    assert settings.get_text(SettingsKey.PRINT_ESTIMATE_LAYOUT) == "42"
    assert settings.get_list(SettingsKey.UI_SILVER_BARS_AVAILABLE_COLUMNS) == [90, 120]


def test_v1_migration_normalizes_alias_and_removes_retired_key() -> None:
    backend = MemorySettingsBackend(
        {
            str(SettingsKey.PRINT_PAGE_SIZE): "Letter / ANSI A",
            "rates/refresh_interval_sec": 15,
        }
    )

    version = migrate_settings(backend)

    assert version == SETTINGS_SCHEMA_VERSION == 1
    assert backend.values[str(SettingsKey.SCHEMA_VERSION)] == 1
    assert backend.values[str(SettingsKey.PRINT_PAGE_SIZE)] == "Letter"
    assert "rates/refresh_interval_sec" not in backend.values
    assert backend.sync_count == 1


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


def test_application_settings_only_accepts_declared_keys_for_typed_writes() -> None:
    backend = MemorySettingsBackend()
    settings = ApplicationSettings(backend, migrate=False)

    settings.set(SettingsKey.PRINT_SHOW_TUNCH, True)
    settings.remove(SettingsKey.PRINT_SHOW_TUNCH)

    assert not backend.values
