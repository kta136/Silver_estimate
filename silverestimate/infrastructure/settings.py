"""Utility helpers for application QSettings access."""

from __future__ import annotations

from typing import Any, Protocol

from PyQt5.QtCore import QSettings

from .app_constants import LEGACY_SETTINGS_ORG, SETTINGS_APP, SETTINGS_ORG

ENABLE_TEMP_DB_RECOVERY = True


class SettingsReader(Protocol):
    """Subset of QSettings used by read-only call sites."""

    def value(  # noqa: A002 - match QSettings API
        self, key: str, default: Any = None, type: Any = None
    ) -> Any: ...


class SettingsStore(SettingsReader, Protocol):
    """Subset of QSettings used by writable call sites."""

    def setValue(self, key: str, value: Any) -> None: ...

    def remove(self, key: str) -> None: ...

    def sync(self) -> Any: ...


def get_app_settings(*, org: str = SETTINGS_ORG, app: str = SETTINGS_APP) -> QSettings:
    """Return QSettings, preferring new org identifiers with legacy fallback."""
    primary = QSettings(org, app)
    if org != SETTINGS_ORG:
        return primary

    # For upgraded installs keep using legacy storage when existing keys are present.
    critical_keys = (
        "security/db_salt",
        "security/password_hash",
        "security/backup_hash",
        "rates/live_enabled",
    )
    if any(primary.value(key) is not None for key in critical_keys):
        return primary

    legacy = QSettings(LEGACY_SETTINGS_ORG, app)
    if any(legacy.value(key) is not None for key in critical_keys):
        return legacy
    return primary


__all__ = ["get_app_settings", "QSettings", "SettingsReader", "SettingsStore"]
