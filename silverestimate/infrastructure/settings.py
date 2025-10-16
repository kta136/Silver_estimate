"""Utility helpers for application QSettings access."""
from PyQt5.QtCore import QSettings

from .app_constants import SETTINGS_ORG, SETTINGS_APP


ENABLE_TEMP_DB_RECOVERY = True


def get_app_settings(*, org: str = SETTINGS_ORG, app: str = SETTINGS_APP) -> QSettings:
    """Return a QSettings instance using the default org/app identifiers."""
    return QSettings(org, app)


__all__ = ["get_app_settings", "QSettings"]
