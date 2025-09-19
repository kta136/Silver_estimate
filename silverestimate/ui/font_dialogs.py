"""Helpers for font-related Qt dialogs."""

from __future__ import annotations

import logging
from typing import Callable, Optional

from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import QDialog, QWidget

from .custom_font_dialog import CustomFontDialog
from .table_font_size_dialog import TableFontSizeDialog
from silverestimate.services.settings_service import SettingsService

ApplyFontSize = Callable[[int], None]


def _ensure_float_size(font: QFont) -> None:
    """Ensure a QFont instance carries a float_size attribute for persistence."""
    if font is None:
        return
    if hasattr(font, "float_size"):
        return
    size = float(font.pointSizeF())
    if size <= 0:
        size = float(font.pointSize())
    if size <= 0:
        size = 5.0
    font.float_size = size


def choose_print_font(
    parent: Optional[QWidget],
    settings: SettingsService,
    current_font: Optional[QFont],
    logger: Optional[logging.Logger] = None,
) -> QFont:
    """Show the print font dialog and persist the chosen font."""
    if current_font is None:
        fallback = parent.font() if parent is not None else QFont()
        working_font = settings.load_print_font(fallback)
    else:
        working_font = QFont(current_font)
        float_size = getattr(current_font, "float_size", None)
        if float_size is not None:
            working_font.float_size = float(float_size)

    _ensure_float_size(working_font)

    dialog = CustomFontDialog(working_font, parent)
    if dialog.exec_() == QDialog.Accepted:
        selected_font = dialog.get_selected_font()
        _ensure_float_size(selected_font)
        settings.save_print_font(selected_font)
        if logger:
            logger.debug(
                "Stored print font: %s, Size: %spt, Bold=%s",
                selected_font.family(),
                getattr(selected_font, "float_size", selected_font.pointSize()),
                selected_font.bold(),
            )
        return selected_font

    return working_font


def adjust_table_font_size(
    parent: Optional[QWidget],
    settings: SettingsService,
    apply_callback: Optional[ApplyFontSize] = None,
    logger: Optional[logging.Logger] = None,
) -> Optional[int]:
    """Prompt for a new estimate table font size and apply it if accepted."""
    current_size = settings.load_table_font_size()

    dialog = TableFontSizeDialog(current_size=current_size, parent=parent)
    if dialog.exec_() == QDialog.Accepted:
        new_size = dialog.get_selected_size()
        settings.save_table_font_size(new_size)
        if apply_callback is not None:
            try:
                apply_callback(new_size)
            except Exception as exc:
                if logger:
                    logger.exception("Failed to apply table font size: %s", exc)
        return new_size

    return None
