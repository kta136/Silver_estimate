"""Utility helpers for application QSettings access."""

from __future__ import annotations

from typing import Any, Protocol

from PyQt6.QtCore import QSettings

from .app_constants import SETTINGS_APP, SETTINGS_ORG

# Marked crash snapshots can be offered for recovery on the next startup.
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


def get_app_settings() -> QSettings:
    """Return the canonical application settings store."""
    return QSettings(SETTINGS_ORG, SETTINGS_APP)


__all__ = ["get_app_settings", "QSettings", "SettingsReader", "SettingsStore"]
