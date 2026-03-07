"""Shared helpers for rendering numeric values with stable column alignment."""

from __future__ import annotations

from PyQt5.QtGui import QFont, QFontDatabase, QFontInfo


def numeric_table_font(base_font: QFont | None = None) -> QFont:
    """Return a numeric-friendly font derived from the current table font."""

    resolved_base = QFont(base_font) if base_font is not None else QFont()
    candidate = QFont(resolved_base)
    candidate.setStyleHint(QFont.TypeWriter, QFont.PreferDefault)
    candidate.setFixedPitch(True)
    candidate.setKerning(False)

    if QFontInfo(candidate).fixedPitch():
        return candidate

    fallback = QFontDatabase.systemFont(QFontDatabase.FixedFont)
    if fallback.family():
        if resolved_base.pixelSize() > 0:
            fallback.setPixelSize(resolved_base.pixelSize())
        elif resolved_base.pointSizeF() > 0:
            fallback.setPointSizeF(resolved_base.pointSizeF())
        fallback.setBold(resolved_base.bold())
        fallback.setItalic(resolved_base.italic())
        fallback.setUnderline(resolved_base.underline())
        fallback.setStrikeOut(resolved_base.strikeOut())
        fallback.setKerning(False)
        return fallback

    return candidate
