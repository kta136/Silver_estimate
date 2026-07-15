"""Small themed widgets that keep control affordances visible under QSS."""

from __future__ import annotations

from typing import Literal

from PyQt6.QtCore import QPointF, QRect, Qt
from PyQt6.QtGui import QColor, QPainter, QPaintEvent, QPolygonF
from PyQt6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QDoubleSpinBox,
    QFontComboBox,
    QSpinBox,
    QStyle,
    QStyleOptionComboBox,
    QStyleOptionSpinBox,
)

from .theme_tokens import HEADER_TEXT, TEXT_MUTED

ArrowDirection = Literal["up", "down"]


def _control_arrow_color(widget) -> QColor:
    return QColor(HEADER_TEXT if widget.isEnabled() else TEXT_MUTED)


def _fallback_spin_rect(widget, direction: ArrowDirection) -> QRect:
    button_width = max(22, min(30, widget.height()))
    half_height = max(1, widget.height() // 2)
    x = max(0, widget.width() - button_width)
    y = 0 if direction == "up" else half_height
    height = half_height if direction == "up" else widget.height() - half_height
    return QRect(x, y, button_width, max(1, height))


def _draw_arrow(
    painter: QPainter,
    rect: QRect,
    direction: ArrowDirection,
    color: QColor,
) -> None:
    if not rect.isValid() or rect.width() <= 0 or rect.height() <= 0:
        return

    center = rect.center()
    width = float(max(7, min(10, rect.width() * 0.36)))
    height = float(max(4, min(6, rect.height() * 0.34)))
    cx = float(center.x())
    cy = float(center.y())

    if direction == "up":
        points = [
            QPointF(cx, cy - height / 2),
            QPointF(cx - width / 2, cy + height / 2),
            QPointF(cx + width / 2, cy + height / 2),
        ]
    else:
        points = [
            QPointF(cx - width / 2, cy - height / 2),
            QPointF(cx + width / 2, cy - height / 2),
            QPointF(cx, cy + height / 2),
        ]

    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(color)
    painter.drawPolygon(QPolygonF(points))


def _paint_spinbox_arrows(widget) -> None:
    option = QStyleOptionSpinBox()
    widget.initStyleOption(option)
    style = widget.style()
    up_rect = style.subControlRect(
        QStyle.ComplexControl.CC_SpinBox,
        option,
        QStyle.SubControl.SC_SpinBoxUp,
        widget,
    )
    down_rect = style.subControlRect(
        QStyle.ComplexControl.CC_SpinBox,
        option,
        QStyle.SubControl.SC_SpinBoxDown,
        widget,
    )
    if not up_rect.isValid() or up_rect.width() <= 0:
        up_rect = _fallback_spin_rect(widget, "up")
    if not down_rect.isValid() or down_rect.width() <= 0:
        down_rect = _fallback_spin_rect(widget, "down")

    painter = QPainter(widget)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    color = _control_arrow_color(widget)
    _draw_arrow(painter, up_rect, "up", color)
    _draw_arrow(painter, down_rect, "down", color)
    painter.end()


def _paint_combo_arrow(widget) -> None:
    option = QStyleOptionComboBox()
    widget.initStyleOption(option)
    rect = widget.style().subControlRect(
        QStyle.ComplexControl.CC_ComboBox,
        option,
        QStyle.SubControl.SC_ComboBoxArrow,
        widget,
    )
    if not rect.isValid() or rect.width() <= 0:
        rect = QRect(max(0, widget.width() - 30), 0, 30, widget.height())

    painter = QPainter(widget)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    _draw_arrow(painter, rect, "down", _control_arrow_color(widget))
    painter.end()


class ThemedSpinBox(QSpinBox):
    """Spin box that redraws visible up/down arrows after QSS styling."""

    def paintEvent(self, event: QPaintEvent | None) -> None:
        super().paintEvent(event)
        _paint_spinbox_arrows(self)


class ThemedDoubleSpinBox(QDoubleSpinBox):
    """Double spin box that redraws visible up/down arrows after QSS styling."""

    def paintEvent(self, event: QPaintEvent | None) -> None:
        super().paintEvent(event)
        _paint_spinbox_arrows(self)


class ThemedDateEdit(QDateEdit):
    """Date edit that redraws visible up/down arrows after QSS styling."""

    def paintEvent(self, event: QPaintEvent | None) -> None:
        super().paintEvent(event)
        _paint_spinbox_arrows(self)


class ThemedComboBox(QComboBox):
    """Combo box that redraws a visible dropdown arrow after QSS styling."""

    def paintEvent(self, event: QPaintEvent | None) -> None:
        super().paintEvent(event)
        _paint_combo_arrow(self)


class ThemedFontComboBox(QFontComboBox):
    """Font combo box with the same visible dropdown arrow treatment."""

    def paintEvent(self, event: QPaintEvent | None) -> None:
        super().paintEvent(event)
        _paint_combo_arrow(self)
