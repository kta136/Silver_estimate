"""Application settings service built on QSettings."""
from __future__ import annotations

from dataclasses import dataclass

from PyQt5.QtCore import QSettings
from PyQt5.QtGui import QFont

from silverestimate.infrastructure.app_constants import SETTINGS_APP, SETTINGS_ORG


@dataclass
class FontSettings:
    family: str
    size: float
    bold: bool

    def to_qfont(self) -> QFont:
        font = QFont(self.family, int(round(self.size)))
        font.setBold(self.bold)
        font.float_size = self.size
        return font

    @classmethod
    def from_qfont(cls, font: QFont) -> "FontSettings":
        size = getattr(font, "float_size", float(font.pointSize()))
        return cls(font.family(), float(size), font.bold())


class SettingsService:
    def __init__(self) -> None:
        self._settings = QSettings(SETTINGS_ORG, SETTINGS_APP)

    # --- Fonts ---------------------------------------------------------
    def load_print_font(self, default_font: QFont) -> QFont:
        family = self._settings.value("font/family", default_font.family(), type=str)
        size = self._settings.value("font/size_float", default_font.pointSizeF(), type=float)
        bold = self._settings.value("font/bold", default_font.bold(), type=bool)
        size = max(5.0, float(size))
        return FontSettings(family, size, bold).to_qfont()

    def save_print_font(self, font: QFont) -> None:
        settings = FontSettings.from_qfont(font)
        self._settings.setValue("font/family", settings.family)
        self._settings.setValue("font/size_float", settings.size)
        self._settings.setValue("font/bold", settings.bold)
        self._settings.sync()

    def load_table_font_size(self, default_size: int = 9) -> int:
        size = self._settings.value("ui/table_font_size", defaultValue=int(default_size), type=int)
        try:
            return int(size)
        except (TypeError, ValueError):
            return int(default_size)

    def save_table_font_size(self, size: int) -> None:
        self._settings.setValue("ui/table_font_size", int(size))
        self._settings.sync()

    # --- Geometry/state -----------------------------------------------
    def restore_geometry(self, window) -> bool:
        geometry = self._settings.value("ui/main_geometry")
        state = self._settings.value("ui/main_state")
        restored = False
        if geometry is not None:
            window.restoreGeometry(geometry)
            restored = True
        if state is not None:
            window.restoreState(state)
            restored = True
        return restored

    def save_geometry(self, window) -> None:
        self._settings.setValue("ui/main_geometry", window.saveGeometry())
        self._settings.setValue("ui/main_state", window.saveState())
        self._settings.sync()

    # --- Convenience ---------------------------------------------------
    def get(self, key: str, default=None, *, type=None):
        return self._settings.value(key, defaultValue=default, type=type)

    def set(self, key: str, value) -> None:
        self._settings.setValue(key, value)
        self._settings.sync()

    def raw(self) -> QSettings:
        return self._settings
