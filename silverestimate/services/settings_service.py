"""Application settings service built on QSettings."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from PySide6.QtGui import QFont

from silverestimate.infrastructure.settings import QSettings, get_app_settings


@dataclass
class FontSettings:
    family: str
    size: float
    bold: bool

    def to_qfont(self) -> QFont:
        font = QFont(self.family)
        font.setPointSizeF(self.size)
        font.setBold(self.bold)
        return font

    @classmethod
    def from_qfont(cls, font: QFont) -> "FontSettings":
        return cls(font.family(), font.pointSizeF(), font.bold())


class SettingsService:
    def __init__(self) -> None:
        self._settings = get_app_settings()

    # --- Fonts ---------------------------------------------------------
    def load_print_font(self, default_font: QFont) -> QFont:
        family_value = self._settings.value(
            "font/family", default_font.family(), type=str
        )
        size_value = self._settings.value(
            "font/size_float", default_font.pointSizeF(), type=float
        )
        bold_value = self._settings.value("font/bold", default_font.bold(), type=bool)
        family = str(family_value or default_font.family())
        try:
            size = float(size_value) if isinstance(size_value, (int, float, str)) else 0
        except ValueError:
            size = 0
        size = max(5.0, size or default_font.pointSizeF())
        bold = bold_value if isinstance(bold_value, bool) else default_font.bold()
        return FontSettings(family, size, bold).to_qfont()

    def save_print_font(self, font: QFont) -> None:
        settings = FontSettings.from_qfont(font)
        self._settings.setValue("font/family", settings.family)
        self._settings.setValue("font/size_float", settings.size)
        self._settings.setValue("font/bold", settings.bold)
        self._settings.sync()

    def load_table_font_size(self, default_size: int = 9) -> int:
        size = self._settings.value(
            "ui/table_font_size", defaultValue=int(default_size), type=int
        )
        try:
            if isinstance(size, (int, float, str, bytes, bytearray)):
                return int(size)
        except TypeError, ValueError:
            pass
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
            try:
                restored = bool(window.restoreGeometry(geometry)) or restored
            except Exception as exc:
                logging.getLogger(__name__).debug(
                    "Failed to restore window geometry: %s", exc
                )
        if state is not None:
            try:
                restored = bool(window.restoreState(state)) or restored
            except Exception as exc:
                logging.getLogger(__name__).debug(
                    "Failed to restore window state: %s", exc
                )
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
