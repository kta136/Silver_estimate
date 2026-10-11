"""Helpers for keeping secondary windows usable at high DPI."""

from __future__ import annotations

from PySide6.QtWidgets import QWidget

# Height of a window's title bar and frame, which sit outside its minimum size.
TITLE_BAR_ALLOWANCE = 40


def resize_to_available_screen(
    widget: QWidget,
    *,
    preferred_width: int,
    preferred_height: int,
    margin: int = 64,
) -> None:
    """Resize a window without exceeding the available desktop geometry."""

    screen = widget.screen()
    available = screen.availableGeometry()
    width_margin = min(margin, max(0, available.width() // 8))
    height_margin = min(margin, max(0, available.height() // 8))
    max_width = max(1, available.width() - width_margin)
    max_height = max(1, available.height() - height_margin)
    target_width = min(preferred_width, max(widget.minimumWidth(), max_width))
    target_height = min(preferred_height, max(widget.minimumHeight(), max_height))
    widget.resize(target_width, target_height)


def set_usable_minimum_size(widget: QWidget, *, width: int, height: int) -> None:
    """Set a minimum size the window stays usable at, never beyond the screen.

    A minimum larger than the desktop would push part of the window off-screen
    on a small or heavily scaled display, so it is capped to the space there,
    less the room a maximized window's title bar takes.
    """

    available = widget.screen().availableGeometry()
    widget.setMinimumSize(
        max(1, min(width, available.width())),
        max(1, min(height, available.height() - TITLE_BAR_ALLOWANCE)),
    )
