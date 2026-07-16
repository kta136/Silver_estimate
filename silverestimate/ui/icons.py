"""Shared application icon helpers backed by Qt's native icon set."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final, cast

from PyQt6.QtCore import QSize
from PyQt6.QtGui import QColor, QIcon, QPainter, QPixmap
from PyQt6.QtWidgets import QApplication, QStyle, QWidget


@dataclass(frozen=True)
class IconSpec:
    """Description of an app icon with theme and native fallbacks."""

    theme_name: str | None = None
    fallback: QStyle.StandardPixmap | None = None


_DEFAULT_COLOR = "#334155"
_DISABLED_COLOR = "#94a3b8"
_ICON_SIZES: Final[tuple[int, ...]] = (16, 20, 24, 32)
_ICON_CACHE: dict[tuple[str, str, str, str], QIcon] = {}

_ICON_SPECS: Final[dict[str, IconSpec]] = {
    "estimate_entry": IconSpec(
        fallback=QStyle.StandardPixmap.SP_FileDialogDetailedView
    ),
    "item_master": IconSpec(fallback=QStyle.StandardPixmap.SP_FileDialogContentsView),
    "tools": IconSpec(fallback=QStyle.StandardPixmap.SP_FileDialogDetailedView),
    "save": IconSpec("document-save", QStyle.StandardPixmap.SP_DialogSaveButton),
    "search": IconSpec("edit-find", QStyle.StandardPixmap.SP_FileDialogContentsView),
    "open": IconSpec("document-open", QStyle.StandardPixmap.SP_DialogOpenButton),
    "print": IconSpec("document-print", QStyle.StandardPixmap.SP_FileIcon),
    "print_estimate": IconSpec("document-print", QStyle.StandardPixmap.SP_FileIcon),
    "delete": IconSpec("edit-delete", QStyle.StandardPixmap.SP_TrashIcon),
    "delete_row": IconSpec(fallback=QStyle.StandardPixmap.SP_TrashIcon),
    "delete_estimate": IconSpec(fallback=QStyle.StandardPixmap.SP_TrashIcon),
    "clear_filters": IconSpec("edit-clear", QStyle.StandardPixmap.SP_DialogResetButton),
    "edit_note": IconSpec(
        "document-edit", QStyle.StandardPixmap.SP_FileDialogDetailedView
    ),
    "mark_issued": IconSpec(
        "emblem-default", QStyle.StandardPixmap.SP_DialogApplyButton
    ),
    "export_csv": IconSpec(
        "document-save-as", QStyle.StandardPixmap.SP_DialogSaveButton
    ),
    "generate_optimal": IconSpec("system-run", QStyle.StandardPixmap.SP_BrowserReload),
    "close": IconSpec("window-close", QStyle.StandardPixmap.SP_DialogCloseButton),
    "refresh": IconSpec("view-refresh", QStyle.StandardPixmap.SP_BrowserReload),
    "save_pdf": IconSpec("document-save", QStyle.StandardPixmap.SP_DialogSaveButton),
    "page_setup": IconSpec(
        "document-properties", QStyle.StandardPixmap.SP_FileDialogDetailedView
    ),
    "new": IconSpec(fallback=QStyle.StandardPixmap.SP_FileDialogNewFolder),
    "zoom_in": IconSpec("zoom-in", QStyle.StandardPixmap.SP_ArrowUp),
    "zoom_out": IconSpec("zoom-out", QStyle.StandardPixmap.SP_ArrowDown),
    "fit_width": IconSpec(
        "zoom-fit-width", QStyle.StandardPixmap.SP_TitleBarShadeButton
    ),
    "fit_page": IconSpec(
        "zoom-fit-best", QStyle.StandardPixmap.SP_TitleBarUnshadeButton
    ),
    "view_single_page": IconSpec(fallback=QStyle.StandardPixmap.SP_FileIcon),
    "view_facing_pages": IconSpec(fallback=QStyle.StandardPixmap.SP_DirOpenIcon),
    "view_overview": IconSpec(fallback=QStyle.StandardPixmap.SP_FileDialogListView),
    "page_first": IconSpec("go-first", QStyle.StandardPixmap.SP_MediaSkipBackward),
    "page_previous": IconSpec(
        "go-previous", QStyle.StandardPixmap.SP_MediaSeekBackward
    ),
    "page_next": IconSpec("go-next", QStyle.StandardPixmap.SP_MediaSeekForward),
    "page_last": IconSpec("go-last", QStyle.StandardPixmap.SP_MediaSkipForward),
    "printer_select": IconSpec("printer", QStyle.StandardPixmap.SP_ComputerIcon),
    "exit": IconSpec(fallback=QStyle.StandardPixmap.SP_DialogCloseButton),
    "silver_bars": IconSpec(fallback=QStyle.StandardPixmap.SP_DriveHDIcon),
    "silver_history": IconSpec(
        fallback=QStyle.StandardPixmap.SP_FileDialogDetailedView
    ),
    "settings": IconSpec(fallback=QStyle.StandardPixmap.SP_FileDialogDetailedView),
    "about": IconSpec(fallback=QStyle.StandardPixmap.SP_MessageBoxInformation),
    "balance": IconSpec(fallback=QStyle.StandardPixmap.SP_DialogApplyButton),
    "history": IconSpec(fallback=QStyle.StandardPixmap.SP_FileDialogDetailedView),
    "return_mode": IconSpec(fallback=QStyle.StandardPixmap.SP_ArrowBack),
    "bar_mode": IconSpec(fallback=QStyle.StandardPixmap.SP_DriveHDIcon),
    "move_right": IconSpec(fallback=QStyle.StandardPixmap.SP_ArrowRight),
    "move_left": IconSpec(fallback=QStyle.StandardPixmap.SP_ArrowLeft),
    "move_all_right": IconSpec(fallback=QStyle.StandardPixmap.SP_MediaSkipForward),
    "move_all_left": IconSpec(fallback=QStyle.StandardPixmap.SP_MediaSkipBackward),
    "reset_layout": IconSpec(fallback=QStyle.StandardPixmap.SP_DialogResetButton),
    "user_interface": IconSpec(fallback=QStyle.StandardPixmap.SP_DesktopIcon),
    "live_rates": IconSpec(fallback=QStyle.StandardPixmap.SP_BrowserReload),
    "printing": IconSpec(fallback=QStyle.StandardPixmap.SP_FileDialogDetailedView),
    "data_management": IconSpec(fallback=QStyle.StandardPixmap.SP_DirHomeIcon),
    "security": IconSpec(fallback=QStyle.StandardPixmap.SP_MessageBoxWarning),
    "import_export": IconSpec(fallback=QStyle.StandardPixmap.SP_DialogOpenButton),
    "logging": IconSpec(fallback=QStyle.StandardPixmap.SP_FileDialogInfoView),
}


def get_icon(
    name: str,
    *,
    widget: QWidget | None = None,
    color: str | None = None,
    active_color: str | None = None,
) -> QIcon:
    """Resolve and cache a semantic icon using Qt theme/native resources only."""

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

    spec = _ICON_SPECS.get(name)
    source = _source_icon(style, spec)
    icon = _colored_icon(source, icon_color, active_icon_color)
    _ICON_CACHE[cache_key] = icon
    return QIcon(icon)


def clear_icon_cache() -> None:
    """Clear rendered icons after an application style or palette change."""

    _ICON_CACHE.clear()


def _source_icon(style: QStyle, spec: IconSpec | None) -> QIcon:
    if spec is not None and spec.theme_name:
        themed = QIcon.fromTheme(spec.theme_name)
        if not themed.isNull():
            return themed

    fallback = spec.fallback if spec is not None else QStyle.StandardPixmap.SP_FileIcon
    icon = style.standardIcon(fallback or QStyle.StandardPixmap.SP_FileIcon)
    if not icon.isNull():
        return icon
    return style.standardIcon(QStyle.StandardPixmap.SP_FileIcon)


def _colored_icon(source: QIcon, color: str, active_color: str) -> QIcon:
    rendered = QIcon()
    mode_colors = (
        (QIcon.Mode.Normal, color),
        (QIcon.Mode.Active, active_color),
        (QIcon.Mode.Selected, active_color),
        (QIcon.Mode.Disabled, _DISABLED_COLOR),
    )
    for size in _ICON_SIZES:
        dimensions = QSize(size, size)
        source_pixmap = source.pixmap(dimensions)
        if source_pixmap.isNull():
            continue
        for mode, mode_color in mode_colors:
            rendered.addPixmap(_tint(source_pixmap, mode_color), mode)
    return rendered if not rendered.isNull() else source


def _tint(source: QPixmap, color: str) -> QPixmap:
    result = QPixmap(source)
    painter = QPainter(result)
    painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
    painter.fillRect(result.rect(), QColor(color))
    painter.end()
    return result


def _resolve_style(widget: QWidget | None) -> QStyle | None:
    if widget is not None:
        return widget.style()
    app = cast(QApplication | None, QApplication.instance())
    if app is None:
        return None
    return app.style()
