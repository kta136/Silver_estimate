"""Typed application-settings schema over the canonical QSettings backend."""

from __future__ import annotations

from collections.abc import Callable
from enum import StrEnum
from typing import Any, Protocol, cast

from PySide6.QtCore import QSettings

from .app_constants import SETTINGS_APP, SETTINGS_ORG

SETTINGS_SCHEMA_VERSION = 3


class SettingsKey(StrEnum):
    """Canonical keys for every production application preference."""

    SCHEMA_VERSION = "meta/settings_schema_version"
    BACKUP_LAST_VALIDATED_UTC = "backup/last_validated_utc"

    FONT_FAMILY = "font/family"
    FONT_SIZE = "font/size_float"
    FONT_BOLD = "font/bold"

    UI_MAIN_GEOMETRY = "ui/main_geometry"
    UI_MAIN_STATE = "ui/main_state"
    UI_SETTINGS_LAST_TAB = "ui/settings_last_tab"
    UI_FONT_FAMILY = "ui/font_family"
    UI_ROW_DENSITY = "ui/row_density"
    UI_ALTERNATING_ROWS = "ui/alternating_rows"
    UI_TABLE_FONT_SIZE = "ui/table_font_size"
    UI_BREAKDOWN_FONT_SIZE = "ui/breakdown_font_size"
    UI_FINAL_CALC_FONT_SIZE = "ui/final_calc_font_size"
    UI_ESTIMATE_TOTALS_SECTION_ORDER = "ui/estimate_totals_section_order"
    UI_ESTIMATE_TABLE_AUTOFIT_MODE = "ui/estimate_table_autofit_mode"
    UI_ESTIMATE_TABLE_COLUMN_WIDTHS = "ui/estimate_table_column_widths"

    PRINT_MARGINS = "print/margins"
    PRINT_DEFAULT_PRINTER = "print/default_printer"
    PRINT_PAGE_SIZE = "print/page_size"
    PRINT_PAGE_SIZE_NAME = "print/page_size_name"
    PRINT_PAGE_WIDTH_MM = "print/page_width_mm"
    PRINT_PAGE_HEIGHT_MM = "print/page_height_mm"
    PRINT_ORIENTATION = "print/orientation"
    PRINT_PREVIEW_ZOOM = "print/preview_zoom"
    PRINT_SHOW_TUNCH = "print/show_tunch"
    PRINT_LAST_EXPORT_DIR = "print/last_export_dir"

    RATES_LIVE_ENABLED = "rates/live_enabled"
    RATES_AUTO_REFRESH_ENABLED = "rates/auto_refresh_enabled"
    RATES_VERIFIED_SNAPSHOT = "rates/dda_last_verified_snapshot"

    LOGGING_LEVEL = "logging/level"
    LOGGING_AUTO_CLEANUP = "logging/auto_cleanup"
    LOGGING_CLEANUP_DAYS = "logging/cleanup_days"


class RawSettingsBackend(Protocol):
    """QSettings-shaped backend isolated behind :class:`ApplicationSettings`."""

    def value(  # noqa: A002 - mirrors QSettings
        self,
        key: str,
        default: Any = None,
        type: Any = None,
        **kwargs: Any,
    ) -> Any: ...

    def setValue(self, key: str, value: Any) -> None: ...

    def remove(self, key: str) -> None: ...

    def sync(self) -> Any: ...


class SettingsReader(Protocol):
    """Typed read-only settings boundary used by production consumers."""

    def read(self, key: SettingsKey, default: object = None) -> object: ...

    def get_bool(self, key: SettingsKey, default: bool = False) -> bool: ...

    def get_int(
        self,
        key: SettingsKey,
        default: int = 0,
        *,
        minimum: int | None = None,
        maximum: int | None = None,
    ) -> int: ...

    def get_float(
        self,
        key: SettingsKey,
        default: float = 0.0,
        *,
        minimum: float | None = None,
        maximum: float | None = None,
    ) -> float: ...

    def get_text(self, key: SettingsKey, default: str = "") -> str: ...

    def get_list(
        self,
        key: SettingsKey,
        default: tuple[object, ...] = (),
    ) -> list[object]: ...

    def contains(self, key: SettingsKey) -> bool: ...


class SettingsStore(SettingsReader, Protocol):
    """Typed writable settings boundary used by production consumers."""

    def set(self, key: SettingsKey, value: object) -> None: ...

    def remove(self, key: SettingsKey) -> None: ...

    def sync(self) -> Any: ...


class ApplicationSettings:
    """Normalize QSettings values and enforce the current settings schema."""

    def __init__(
        self,
        backend: RawSettingsBackend | None = None,
        *,
        migrate: bool = True,
    ) -> None:
        self._backend = cast(
            RawSettingsBackend,
            backend or QSettings(SETTINGS_ORG, SETTINGS_APP),
        )
        if migrate:
            migrate_settings(self._backend)

    def read(self, key: SettingsKey, default: object = None) -> object:
        return self._backend.value(str(key), default)

    def get_bool(self, key: SettingsKey, default: bool = False) -> bool:
        value = self.read(key, default)
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"1", "true", "yes", "on", "enabled"}:
                return True
            if normalized in {"0", "false", "no", "off", "disabled", ""}:
                return False
        if value is None:
            return default
        return bool(value)

    def get_int(
        self,
        key: SettingsKey,
        default: int = 0,
        *,
        minimum: int | None = None,
        maximum: int | None = None,
    ) -> int:
        raw = self.read(key, default)
        try:
            value = int(raw) if isinstance(raw, (str, int, float)) else default
        except TypeError, ValueError:
            value = default
        if minimum is not None:
            value = max(minimum, value)
        if maximum is not None:
            value = min(maximum, value)
        return value

    def get_float(
        self,
        key: SettingsKey,
        default: float = 0.0,
        *,
        minimum: float | None = None,
        maximum: float | None = None,
    ) -> float:
        raw = self.read(key, default)
        try:
            value = float(raw) if isinstance(raw, (str, int, float)) else default
        except TypeError, ValueError:
            value = default
        if minimum is not None:
            value = max(minimum, value)
        if maximum is not None:
            value = min(maximum, value)
        return value

    def get_text(self, key: SettingsKey, default: str = "") -> str:
        value = self.read(key, default)
        if value is None:
            return default
        return str(value)

    def get_list(
        self,
        key: SettingsKey,
        default: tuple[object, ...] = (),
    ) -> list[object]:
        value = self.read(key, list(default))
        if isinstance(value, (list, tuple)):
            return list(value)
        return list(default)

    def contains(self, key: SettingsKey) -> bool:
        contains = getattr(self._backend, "contains", None)
        if callable(contains):
            return bool(contains(str(key)))
        sentinel = object()
        return self._backend.value(str(key), sentinel) is not sentinel

    def set(self, key: SettingsKey, value: object) -> None:
        self._backend.setValue(str(key), value)

    def remove(self, key: SettingsKey) -> None:
        self._backend.remove(str(key))

    def sync(self) -> Any:
        return self._backend.sync()

    def clear(self) -> None:
        clear = getattr(self._backend, "clear", None)
        if callable(clear):
            clear()

    # Compatibility for tests and transitional external integrations. Production
    # modules use the typed methods above; architecture tests enforce that rule.
    def value(  # noqa: A002 - mirrors QSettings
        self,
        key: str | SettingsKey,
        defaultValue: object = None,
        type: type | None = None,
    ) -> object:
        raw = self._backend.value(str(key), defaultValue)
        if type is None or raw is None:
            return raw
        if type is bool:
            return self._coerce_compat_bool(raw, defaultValue)
        try:
            return type(raw)
        except TypeError, ValueError:
            return defaultValue

    def setValue(self, key: str | SettingsKey, value: object) -> None:
        self._backend.setValue(str(key), value)

    def allKeys(self) -> list[str]:
        all_keys = getattr(self._backend, "allKeys", None)
        return list(all_keys()) if callable(all_keys) else []

    @staticmethod
    def _coerce_compat_bool(value: object, default: object) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.strip().lower() in {"1", "true", "yes", "on", "enabled"}
        if value is None:
            return bool(default) if isinstance(default, bool) else False
        return bool(value)


def as_settings_store(
    settings: ApplicationSettings | SettingsStore | RawSettingsBackend,
    *,
    migrate: bool = False,
) -> ApplicationSettings:
    """Return a typed store for a production or in-memory QSettings backend."""
    if isinstance(settings, ApplicationSettings):
        return settings
    return ApplicationSettings(cast(RawSettingsBackend, settings), migrate=migrate)


def as_settings_reader(
    settings: SettingsReader | RawSettingsBackend,
    *,
    migrate: bool = False,
) -> SettingsReader:
    """Return a typed reader for typed stores or QSettings-shaped test backends."""
    if callable(getattr(settings, "get_bool", None)) and callable(
        getattr(settings, "read", None)
    ):
        return cast(SettingsReader, settings)
    return ApplicationSettings(
        cast(RawSettingsBackend, settings),
        migrate=migrate,
    )


def _stored_flag(backend: RawSettingsBackend, key: str, default: bool) -> bool:
    value = backend.value(key, default)
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on", "enabled"}
    return bool(value)


def _migrate_to_v3(backend: RawSettingsBackend) -> None:
    """Replace the four logging switches of v4.07 and earlier with one level."""
    old_keys = {
        "logging/debug_mode": False,
        "logging/enable_info": True,
        "logging/enable_critical": True,
        "logging/enable_debug": True,
    }
    missing = object()
    if any(backend.value(key, missing) is not missing for key in old_keys):
        if _stored_flag(backend, "logging/debug_mode", False):
            level = "detailed"
        elif _stored_flag(backend, "logging/enable_info", True):
            level = "normal"
        else:
            level = "errors"
        backend.setValue(str(SettingsKey.LOGGING_LEVEL), level)
    for key in old_keys:
        backend.remove(key)


# Versions 1 and 2 are stamped only: every install already ran them, and a
# new install starts from the same defaults the code uses.
_MIGRATIONS: dict[int, Callable[[RawSettingsBackend], None]] = {3: _migrate_to_v3}


def migrate_settings(backend: RawSettingsBackend) -> int:
    """Apply ordered forward-only settings migrations and return the version."""
    version = _read_schema_version(backend)
    if version >= SETTINGS_SCHEMA_VERSION:
        return version
    for next_version in range(version + 1, SETTINGS_SCHEMA_VERSION + 1):
        migration = _MIGRATIONS.get(next_version)
        if migration is not None:
            migration(backend)
    backend.setValue(str(SettingsKey.SCHEMA_VERSION), SETTINGS_SCHEMA_VERSION)
    backend.sync()
    return SETTINGS_SCHEMA_VERSION


def _read_schema_version(backend: RawSettingsBackend) -> int:
    raw = backend.value(str(SettingsKey.SCHEMA_VERSION), 0)
    try:
        return max(0, int(raw))
    except TypeError, ValueError:
        return 0


def get_app_settings() -> ApplicationSettings:
    """Return the canonical typed application settings store."""
    return ApplicationSettings()


__all__ = [
    "ApplicationSettings",
    "QSettings",
    "RawSettingsBackend",
    "SETTINGS_SCHEMA_VERSION",
    "SettingsKey",
    "SettingsReader",
    "SettingsStore",
    "as_settings_reader",
    "as_settings_store",
    "get_app_settings",
    "migrate_settings",
]
