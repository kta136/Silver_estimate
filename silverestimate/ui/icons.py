"""Deterministic vector icons for the desktop application.

The Windows Qt style exposes several ``StandardPixmap`` values as historically named
bitmaps. Recolouring those bitmaps turns them into solid squares, especially in
disabled menu states. These icons are painted from simple vector primitives so
they stay crisp, transparent, and semantically stable on every supported PC.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import cos, pi, sin
from typing import Final, cast

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import (
    QColor,
    QIcon,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QPolygonF,
)
from PyQt6.QtWidgets import QApplication, QStyle, QWidget


@dataclass(frozen=True)
class IconSpec:
    """Map a public semantic name to an app-drawn vector symbol."""

    symbol: str


_DEFAULT_COLOR = "#334155"
_DISABLED_COLOR = "#94a3b8"
_ICON_SIZES: Final[tuple[int, ...]] = (16, 20, 24, 32)
_ICON_CACHE: dict[tuple[str, str, str, str], QIcon] = {}

_ICON_SPECS: Final[dict[str, IconSpec]] = {
    "estimate_entry": IconSpec("calculator"),
    "item_master": IconSpec("clipboard"),
    "tools": IconSpec("toolbox"),
    "save": IconSpec("save"),
    "search": IconSpec("search"),
    "open": IconSpec("folder_open"),
    "print": IconSpec("printer"),
    "print_estimate": IconSpec("printer"),
    "delete": IconSpec("trash"),
    "delete_row": IconSpec("delete_row"),
    "delete_estimate": IconSpec("trash"),
    "clear_filters": IconSpec("clear_filter"),
    "edit_note": IconSpec("edit_note"),
    "mark_issued": IconSpec("check_box"),
    "export_csv": IconSpec("export_file"),
    "generate_optimal": IconSpec("magic"),
    "close": IconSpec("close"),
    "refresh": IconSpec("refresh"),
    "save_pdf": IconSpec("pdf"),
    "page_setup": IconSpec("page_setup"),
    "new": IconSpec("new_file"),
    "zoom_in": IconSpec("zoom_in"),
    "zoom_out": IconSpec("zoom_out"),
    "fit_width": IconSpec("fit_width"),
    "fit_page": IconSpec("fit_page"),
    "view_single_page": IconSpec("page"),
    "view_facing_pages": IconSpec("facing_pages"),
    "view_overview": IconSpec("grid"),
    "page_first": IconSpec("page_first"),
    "page_previous": IconSpec("page_previous"),
    "page_next": IconSpec("page_next"),
    "page_last": IconSpec("page_last"),
    "printer_select": IconSpec("printer_select"),
    "exit": IconSpec("exit"),
    "silver_bars": IconSpec("ingot"),
    "silver_history": IconSpec("history"),
    "settings": IconSpec("settings"),
    "about": IconSpec("about"),
    "balance": IconSpec("balance"),
    "history": IconSpec("history"),
    "return_mode": IconSpec("return"),
    "bar_mode": IconSpec("weight"),
    "move_right": IconSpec("arrow_right"),
    "move_left": IconSpec("arrow_left"),
    "move_all_right": IconSpec("page_last"),
    "move_all_left": IconSpec("page_first"),
    "reset_layout": IconSpec("columns"),
    "user_interface": IconSpec("monitor"),
    "live_rates": IconSpec("chart"),
    "printing": IconSpec("printer"),
    "data_management": IconSpec("database"),
    "security": IconSpec("shield"),
    "import_export": IconSpec("import_export"),
    "logging": IconSpec("clipboard_text"),
}


def get_icon(
    name: str,
    *,
    widget: QWidget | None = None,
    color: str | None = None,
    active_color: str | None = None,
) -> QIcon:
    """Resolve and cache a semantic app-drawn icon."""

    style = _resolve_style(widget)
    if style is None:
        return QIcon()

    icon_color = color or _DEFAULT_COLOR
    active_icon_color = active_color or icon_color
    style_key = f"{type(style).__name__}:{style.objectName()}"
    cache_key = (name, style_key, icon_color, active_icon_color)
    cached = _ICON_CACHE.get(cache_key)
    if cached is not None:
        return QIcon(cached)

    spec = _ICON_SPECS.get(name, IconSpec("page"))
    icon = _vector_icon(spec.symbol, icon_color, active_icon_color)
    _ICON_CACHE[cache_key] = icon
    return QIcon(icon)


def clear_icon_cache() -> None:
    """Clear rendered icons after an application style or palette change."""

    _ICON_CACHE.clear()


def _vector_icon(symbol: str, color: str, active_color: str) -> QIcon:
    rendered = QIcon()
    mode_colors = (
        (QIcon.Mode.Normal, color),
        (QIcon.Mode.Active, active_color),
        (QIcon.Mode.Selected, active_color),
        (QIcon.Mode.Disabled, _DISABLED_COLOR),
    )
    for size in _ICON_SIZES:
        for mode, mode_color in mode_colors:
            rendered.addPixmap(_paint_pixmap(symbol, size, mode_color), mode)
    return rendered


def _paint_pixmap(symbol: str, size: int, color: str) -> QPixmap:
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.scale(size / 24.0, size / 24.0)
    pen = QPen(QColor(color), 1.8)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    painter.setPen(pen)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    _draw_symbol(painter, symbol)
    painter.end()
    return pixmap


def _draw_symbol(  # noqa: C901, PLR0911, PLR0912, PLR0915
    painter: QPainter, symbol: str
) -> None:
    if symbol == "calculator":
        painter.drawRoundedRect(QRectF(4, 2, 16, 20), 2, 2)
        painter.drawRect(QRectF(7, 5, 10, 4))
        for y in (13, 17):
            for x in (8, 12, 16):
                painter.drawPoint(QPointF(x, y))
        return
    if symbol in {"clipboard", "clipboard_text"}:
        painter.drawRoundedRect(QRectF(5, 4, 14, 18), 1.5, 1.5)
        painter.drawRoundedRect(QRectF(9, 2, 6, 5), 1.5, 1.5)
        if symbol == "clipboard_text":
            for y in (10, 14, 18):
                painter.drawLine(QPointF(8, y), QPointF(16, y))
        else:
            for y in (11, 15):
                painter.drawLine(QPointF(8, y), QPointF(16, y))
        return
    if symbol == "toolbox":
        painter.drawRoundedRect(QRectF(3, 8, 18, 12), 2, 2)
        painter.drawRoundedRect(QRectF(8, 4, 8, 5), 1.5, 1.5)
        painter.drawLine(QPointF(3, 13), QPointF(21, 13))
        painter.drawLine(QPointF(10, 11.5), QPointF(14, 11.5))
        return
    if symbol == "save":
        painter.drawRoundedRect(QRectF(4, 3, 16, 18), 1.5, 1.5)
        painter.drawRect(QRectF(7, 3, 9, 6))
        painter.drawRect(QRectF(7, 14, 10, 7))
        painter.drawPoint(QPointF(14, 6))
        return
    if symbol == "search":
        _draw_search(painter)
        return
    if symbol == "folder_open":
        path = QPainterPath(QPointF(2, 7))
        path.lineTo(9, 7)
        path.lineTo(11, 10)
        path.lineTo(22, 10)
        path.lineTo(19, 20)
        path.lineTo(3, 20)
        path.closeSubpath()
        painter.drawPath(path)
        return
    if symbol in {"printer", "printer_select"}:
        _draw_printer(painter)
        if symbol == "printer_select":
            _draw_check(painter, 14, 5, 0.65)
        return
    if symbol in {"trash", "delete_row"}:
        if symbol == "delete_row":
            painter.drawRect(QRectF(2.5, 5, 8, 14))
            for y in (9, 13, 17):
                painter.drawLine(QPointF(3, y), QPointF(10, y))
            _draw_close(painter, 14, 9, 0.72)
        else:
            _draw_trash(painter)
        return
    if symbol == "clear_filter":
        path = QPainterPath(QPointF(3, 4))
        path.lineTo(21, 4)
        path.lineTo(14, 12)
        path.lineTo(14, 20)
        path.lineTo(10, 18)
        path.lineTo(10, 12)
        path.closeSubpath()
        painter.drawPath(path)
        _draw_close(painter, 16.5, 15.5, 0.5)
        return
    if symbol == "edit_note":
        _draw_page(painter, QRectF(4, 2, 14, 20))
        painter.drawLine(QPointF(9, 17), QPointF(19, 7))
        painter.drawLine(QPointF(8, 20), QPointF(9, 17))
        painter.drawLine(QPointF(19, 7), QPointF(21, 9))
        return
    if symbol == "check_box":
        painter.drawRoundedRect(QRectF(3, 3, 18, 18), 2, 2)
        _draw_check(painter, 6, 8, 1.0)
        return
    if symbol == "export_file":
        _draw_page(painter, QRectF(3, 2, 13, 20))
        _draw_arrow(painter, QPointF(11, 15), QPointF(22, 15))
        return
    if symbol == "magic":
        painter.drawLine(QPointF(5, 20), QPointF(18, 7))
        painter.drawLine(QPointF(15.5, 5), QPointF(20, 9.5))
        _draw_spark(painter, 7, 7, 2.5)
        _draw_spark(painter, 18.5, 17.5, 2)
        return
    if symbol == "close":
        _draw_close(painter, 12, 12, 1.0)
        return
    if symbol == "refresh":
        _draw_refresh(painter)
        return
    if symbol == "pdf":
        _draw_page(painter, QRectF(4, 2, 16, 20))
        painter.drawLine(QPointF(7, 16), QPointF(17, 16))
        painter.drawLine(QPointF(7, 19), QPointF(15, 19))
        painter.drawRoundedRect(QRectF(7, 10, 10, 3), 1, 1)
        return
    if symbol == "page_setup":
        _draw_page(painter, QRectF(3, 2, 14, 20))
        for y, knob in ((9, 8), (14, 13), (19, 9)):
            painter.drawLine(QPointF(7, y), QPointF(21, y))
            painter.drawEllipse(QPointF(knob, y), 1.2, 1.2)
        return
    if symbol == "new_file":
        _draw_page(painter, QRectF(4, 2, 14, 20))
        _draw_plus(painter, 16, 16, 4)
        return
    if symbol in {"zoom_in", "zoom_out"}:
        _draw_search(painter)
        if symbol == "zoom_in":
            _draw_plus(painter, 10, 10, 3)
        else:
            painter.drawLine(QPointF(7, 10), QPointF(13, 10))
        return
    if symbol == "fit_width":
        painter.drawLine(QPointF(3, 4), QPointF(3, 20))
        painter.drawLine(QPointF(21, 4), QPointF(21, 20))
        _draw_double_arrow(painter, QPointF(5, 12), QPointF(19, 12))
        return
    if symbol == "fit_page":
        painter.drawRect(QRectF(6, 3, 12, 18))
        for x, y, dx, dy in (
            (3, 7, 3, -3),
            (21, 7, -3, -3),
            (3, 17, 3, 3),
            (21, 17, -3, 3),
        ):
            painter.drawLine(QPointF(x, y), QPointF(x + dx, y))
            painter.drawLine(QPointF(x, y), QPointF(x, y + dy))
        return
    if symbol == "page":
        _draw_page(painter, QRectF(5, 2, 14, 20))
        return
    if symbol == "facing_pages":
        _draw_page(painter, QRectF(2, 4, 9, 16), fold=2)
        _draw_page(painter, QRectF(13, 4, 9, 16), fold=2)
        return
    if symbol == "grid":
        for x in (3, 13):
            for y in (3, 13):
                painter.drawRoundedRect(QRectF(x, y, 8, 8), 1, 1)
        return
    if symbol.startswith("page_"):
        _draw_page_navigation(painter, symbol)
        return
    if symbol == "exit":
        painter.drawRect(QRectF(4, 3, 10, 18))
        painter.drawPoint(QPointF(11, 12))
        _draw_arrow(painter, QPointF(9, 12), QPointF(21, 12))
        return
    if symbol == "ingot":
        path = QPainterPath(QPointF(6, 7))
        path.lineTo(18, 7)
        path.lineTo(22, 18)
        path.lineTo(2, 18)
        path.closeSubpath()
        painter.drawPath(path)
        painter.drawLine(QPointF(5, 14), QPointF(19, 14))
        return
    if symbol == "history":
        painter.drawArc(QRectF(3, 3, 18, 18), 35 * 16, 300 * 16)
        painter.drawLine(QPointF(4.1, 5.3), QPointF(4.1, 10))
        painter.drawLine(QPointF(4.1, 5.3), QPointF(8.7, 5.3))
        painter.drawLine(QPointF(12, 7), QPointF(12, 12))
        painter.drawLine(QPointF(12, 12), QPointF(16, 14))
        return
    if symbol == "settings":
        _draw_gear(painter)
        return
    if symbol == "about":
        painter.drawEllipse(QRectF(3, 3, 18, 18))
        painter.drawLine(QPointF(12, 10), QPointF(12, 17))
        painter.drawPoint(QPointF(12, 7))
        return
    if symbol == "balance":
        painter.drawLine(QPointF(12, 4), QPointF(12, 20))
        painter.drawLine(QPointF(5, 8), QPointF(19, 8))
        painter.drawLine(QPointF(7, 8), QPointF(4, 15))
        painter.drawLine(QPointF(17, 8), QPointF(20, 15))
        painter.drawArc(QRectF(1, 12, 7, 6), 180 * 16, 180 * 16)
        painter.drawArc(QRectF(16, 12, 7, 6), 180 * 16, 180 * 16)
        painter.drawLine(QPointF(7, 20), QPointF(17, 20))
        return
    if symbol == "return":
        painter.drawArc(QRectF(5, 5, 15, 14), -80 * 16, 250 * 16)
        painter.drawLine(QPointF(5.2, 13), QPointF(2.5, 9.5))
        painter.drawLine(QPointF(5.2, 13), QPointF(9, 11))
        return
    if symbol == "weight":
        painter.drawArc(QRectF(8, 3, 8, 7), 0, 180 * 16)
        path = QPainterPath(QPointF(6, 8))
        path.lineTo(18, 8)
        path.lineTo(21, 21)
        path.lineTo(3, 21)
        path.closeSubpath()
        painter.drawPath(path)
        return
    if symbol in {"arrow_right", "arrow_left"}:
        if symbol == "arrow_right":
            _draw_arrow(painter, QPointF(3, 12), QPointF(21, 12))
        else:
            _draw_arrow(painter, QPointF(21, 12), QPointF(3, 12))
        return
    if symbol == "columns":
        painter.drawRect(QRectF(3, 5, 5, 14))
        painter.drawRect(QRectF(10, 5, 4, 14))
        painter.drawRect(QRectF(16, 5, 5, 14))
        painter.drawLine(QPointF(9, 3), QPointF(15, 3))
        painter.drawLine(QPointF(9, 21), QPointF(15, 21))
        return
    if symbol == "monitor":
        painter.drawRoundedRect(QRectF(2, 3, 20, 15), 2, 2)
        painter.drawLine(QPointF(12, 18), QPointF(12, 21))
        painter.drawLine(QPointF(7, 21), QPointF(17, 21))
        painter.drawRect(QRectF(5, 7, 5, 7))
        painter.drawLine(QPointF(13, 8), QPointF(19, 8))
        painter.drawLine(QPointF(13, 12), QPointF(19, 12))
        return
    if symbol == "chart":
        painter.drawLine(QPointF(4, 3), QPointF(4, 20))
        painter.drawLine(QPointF(4, 20), QPointF(21, 20))
        painter.drawPolyline(
            QPolygonF(
                [QPointF(6, 16), QPointF(10, 11), QPointF(14, 14), QPointF(20, 6)]
            )
        )
        return
    if symbol == "database":
        painter.drawEllipse(QRectF(4, 3, 16, 6))
        painter.drawArc(QRectF(4, 8, 16, 6), 180 * 16, 180 * 16)
        painter.drawArc(QRectF(4, 13, 16, 6), 180 * 16, 180 * 16)
        painter.drawArc(QRectF(4, 16, 16, 6), 180 * 16, 180 * 16)
        painter.drawLine(QPointF(4, 6), QPointF(4, 19))
        painter.drawLine(QPointF(20, 6), QPointF(20, 19))
        return
    if symbol == "shield":
        path = QPainterPath(QPointF(12, 2))
        path.lineTo(20, 5)
        path.lineTo(19, 13)
        path.cubicTo(18, 18, 15, 21, 12, 22)
        path.cubicTo(9, 21, 6, 18, 5, 13)
        path.lineTo(4, 5)
        path.closeSubpath()
        painter.drawPath(path)
        painter.drawRoundedRect(QRectF(9, 11, 6, 6), 1, 1)
        painter.drawArc(QRectF(10, 7, 4, 7), 0, 180 * 16)
        return
    if symbol == "import_export":
        _draw_arrow(painter, QPointF(3, 8), QPointF(18, 8))
        _draw_arrow(painter, QPointF(21, 16), QPointF(6, 16))
        return

    _draw_page(painter, QRectF(5, 2, 14, 20))


def _draw_page(painter: QPainter, rect: QRectF, *, fold: float = 4) -> None:
    path = QPainterPath(QPointF(rect.left(), rect.top()))
    path.lineTo(rect.right() - fold, rect.top())
    path.lineTo(rect.right(), rect.top() + fold)
    path.lineTo(rect.right(), rect.bottom())
    path.lineTo(rect.left(), rect.bottom())
    path.closeSubpath()
    painter.drawPath(path)
    painter.drawLine(
        QPointF(rect.right() - fold, rect.top()),
        QPointF(rect.right() - fold, rect.top() + fold),
    )
    painter.drawLine(
        QPointF(rect.right() - fold, rect.top() + fold),
        QPointF(rect.right(), rect.top() + fold),
    )


def _draw_search(painter: QPainter) -> None:
    painter.drawEllipse(QRectF(3, 3, 14, 14))
    painter.drawLine(QPointF(15, 15), QPointF(21, 21))


def _draw_printer(painter: QPainter) -> None:
    painter.drawRect(QRectF(6, 3, 12, 6))
    painter.drawRoundedRect(QRectF(3, 8, 18, 9), 2, 2)
    painter.drawRect(QRectF(6, 14, 12, 7))
    painter.drawPoint(QPointF(18, 11))


def _draw_trash(painter: QPainter) -> None:
    painter.drawLine(QPointF(4, 6), QPointF(20, 6))
    painter.drawLine(QPointF(9, 3), QPointF(15, 3))
    painter.drawRoundedRect(QRectF(6, 6, 12, 15), 1, 1)
    painter.drawLine(QPointF(10, 10), QPointF(10, 17))
    painter.drawLine(QPointF(14, 10), QPointF(14, 17))


def _draw_close(
    painter: QPainter, center_x: float, center_y: float, scale: float
) -> None:
    radius = 7 * scale
    painter.drawLine(
        QPointF(center_x - radius, center_y - radius),
        QPointF(center_x + radius, center_y + radius),
    )
    painter.drawLine(
        QPointF(center_x + radius, center_y - radius),
        QPointF(center_x - radius, center_y + radius),
    )


def _draw_plus(
    painter: QPainter, center_x: float, center_y: float, radius: float
) -> None:
    painter.drawLine(
        QPointF(center_x - radius, center_y), QPointF(center_x + radius, center_y)
    )
    painter.drawLine(
        QPointF(center_x, center_y - radius), QPointF(center_x, center_y + radius)
    )


def _draw_check(painter: QPainter, x: float, y: float, scale: float) -> None:
    painter.drawPolyline(
        QPolygonF(
            [
                QPointF(x, y + 4 * scale),
                QPointF(x + 4 * scale, y + 8 * scale),
                QPointF(x + 11 * scale, y),
            ]
        )
    )


def _draw_arrow(painter: QPainter, start: QPointF, end: QPointF) -> None:
    painter.drawLine(start, end)
    angle = 0.0 if end.x() > start.x() else pi
    if abs(end.y() - start.y()) > abs(end.x() - start.x()):
        angle = pi / 2 if end.y() > start.y() else -pi / 2
    head = 4.2
    wing = 0.65
    painter.drawLine(
        end,
        QPointF(
            end.x() - head * cos(angle - wing),
            end.y() - head * sin(angle - wing),
        ),
    )
    painter.drawLine(
        end,
        QPointF(
            end.x() - head * cos(angle + wing),
            end.y() - head * sin(angle + wing),
        ),
    )


def _draw_double_arrow(painter: QPainter, start: QPointF, end: QPointF) -> None:
    _draw_arrow(painter, start, end)
    _draw_arrow(painter, end, start)


def _draw_refresh(painter: QPainter) -> None:
    painter.drawArc(QRectF(3, 3, 18, 18), 30 * 16, 145 * 16)
    painter.drawArc(QRectF(3, 3, 18, 18), 210 * 16, 145 * 16)
    painter.drawLine(QPointF(18.5, 4.5), QPointF(18.5, 9))
    painter.drawLine(QPointF(18.5, 4.5), QPointF(14, 4.5))
    painter.drawLine(QPointF(5.5, 19.5), QPointF(5.5, 15))
    painter.drawLine(QPointF(5.5, 19.5), QPointF(10, 19.5))


def _draw_spark(painter: QPainter, x: float, y: float, radius: float) -> None:
    painter.drawLine(QPointF(x - radius, y), QPointF(x + radius, y))
    painter.drawLine(QPointF(x, y - radius), QPointF(x, y + radius))


def _draw_page_navigation(painter: QPainter, symbol: str) -> None:
    is_next = symbol in {"page_next", "page_last"}
    if is_next:
        _draw_arrow(painter, QPointF(5, 12), QPointF(18, 12))
        if symbol == "page_last":
            painter.drawLine(QPointF(20, 5), QPointF(20, 19))
    else:
        _draw_arrow(painter, QPointF(19, 12), QPointF(6, 12))
        if symbol == "page_first":
            painter.drawLine(QPointF(4, 5), QPointF(4, 19))


def _draw_gear(painter: QPainter) -> None:
    painter.drawEllipse(QRectF(5, 5, 14, 14))
    painter.drawEllipse(QRectF(9, 9, 6, 6))
    for index in range(8):
        angle = index * pi / 4
        painter.drawLine(
            QPointF(12 + 7.5 * cos(angle), 12 + 7.5 * sin(angle)),
            QPointF(12 + 10 * cos(angle), 12 + 10 * sin(angle)),
        )


def _resolve_style(widget: QWidget | None) -> QStyle | None:
    if widget is not None:
        return widget.style()
    app = cast(QApplication | None, QApplication.instance())
    if app is None:
        return None
    return app.style()
