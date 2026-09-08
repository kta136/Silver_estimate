"""Shared helpers for rendering numeric values with stable column alignment."""

from __future__ import annotations

from PySide6.QtGui import QFont


def numeric_table_font(base_font: QFont | None = None) -> QFont:
    """Return a numeric-friendly font derived from the current table font."""

    candidate = QFont(base_font) if base_font is not None else QFont()
    candidate.setFeature(QFont.Tag.fromString("tnum"), 1)
    candidate.setKerning(False)
    return candidate
