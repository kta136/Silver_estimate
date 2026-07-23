"""Helpers for keeping secondary windows usable at high DPI."""

from __future__ import annotations

from PySide6.QtWidgets import QWidget


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
