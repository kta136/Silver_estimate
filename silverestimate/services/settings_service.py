"""Focused font and window-state settings service."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from PySide6.QtGui import QFont

from silverestimate.infrastructure.settings import (
    SettingsKey,
    as_settings_store,
    get_app_settings,
)


@dataclass(frozen=True)
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
        self._settings = as_settings_store(get_app_settings())

    # --- Fonts ---------------------------------------------------------
    def load_print_font(self, default_font: QFont) -> QFont:
        family = self._settings.get_text(
            SettingsKey.FONT_FAMILY,
            default_font.family(),
        )
        size = self._settings.get_float(
            SettingsKey.FONT_SIZE,
            default_font.pointSizeF(),
            minimum=5.0,
        )
        bold = self._settings.get_bool(SettingsKey.FONT_BOLD, default_font.bold())
        return FontSettings(family, size, bold).to_qfont()

    def save_print_font(self, font: QFont) -> None:
        settings = FontSettings.from_qfont(font)
        self._settings.set(SettingsKey.FONT_FAMILY, settings.family)
        self._settings.set(SettingsKey.FONT_SIZE, settings.size)
        self._settings.set(SettingsKey.FONT_BOLD, settings.bold)
        self._settings.sync()

    def load_table_font_size(self, default_size: int = 9) -> int:
        return self._settings.get_int(
            SettingsKey.UI_TABLE_FONT_SIZE,
            int(default_size),
        )

    def save_table_font_size(self, size: int) -> None:
        self._settings.set(SettingsKey.UI_TABLE_FONT_SIZE, int(size))
        self._settings.sync()

    # --- Geometry/state -----------------------------------------------
    def restore_geometry(self, window) -> bool:
        geometry = self._settings.read(SettingsKey.UI_MAIN_GEOMETRY)
        state = self._settings.read(SettingsKey.UI_MAIN_STATE)
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
        self._settings.set(SettingsKey.UI_MAIN_GEOMETRY, window.saveGeometry())
        self._settings.set(SettingsKey.UI_MAIN_STATE, window.saveState())
        self._settings.sync()
