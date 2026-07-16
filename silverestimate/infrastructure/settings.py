"""Utility helpers for application QSettings access."""

from __future__ import annotations

import logging
from typing import Any, Protocol

from PyQt6.QtCore import QSettings

from .app_constants import LEGACY_SETTINGS_ORG, SETTINGS_APP, SETTINGS_ORG

# Marked crash snapshots can be offered for recovery on the next startup.
ENABLE_TEMP_DB_RECOVERY = True
_logger = logging.getLogger(__name__)


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
    """Return canonical QSettings after moving values from the legacy org."""
    primary = QSettings(org, app)
    if org != SETTINGS_ORG:
        return primary

    _migrate_legacy_settings(primary, app=app)
    return primary


def _migrate_legacy_settings(primary: QSettings, *, app: str) -> None:
    legacy = QSettings(LEGACY_SETTINGS_ORG, app)
    try:
        legacy_keys = tuple(str(key) for key in legacy.allKeys())
        if not legacy_keys:
            return

        copied_keys: list[str] = []
        for key in legacy_keys:
            if not primary.contains(key):
                primary.setValue(key, legacy.value(key))
                copied_keys.append(key)
        primary.sync()

        if primary.status() != QSettings.Status.NoError or any(
            not primary.contains(key) for key in copied_keys
        ):
            _logger.warning(
                "Legacy settings were not removed because the canonical write failed"
            )
            return

        for key in legacy_keys:
            legacy.remove(key)
        legacy.sync()
        if legacy.status() != QSettings.Status.NoError:
            _logger.warning("Legacy settings were copied but could not be removed")
    except Exception as exc:  # pragma: no cover - platform-specific QSettings failure
        _logger.warning("Could not migrate legacy application settings: %s", exc)


__all__ = ["get_app_settings", "QSettings", "SettingsReader", "SettingsStore"]
