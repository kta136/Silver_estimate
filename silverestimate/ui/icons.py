"""Shared application icon helpers."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Final

from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QApplication, QStyle, QWidget

LOGGER = logging.getLogger(__name__)

try:
    import qtawesome as _qtawesome
except Exception:  # pragma: no cover - dependency availability varies by env
    _qtawesome = None


@dataclass(frozen=True)
class IconSpec:
    """Description of an app icon with fallback metadata."""

    mdi6_name: str
    theme_name: str | None = None
    fallback: QStyle.StandardPixmap | None = None


_DEFAULT_COLOR = "#334155"
_DISABLED_COLOR = "#94a3b8"

_ICON_SPECS: Final[dict[str, IconSpec]] = {
    "estimate_entry": IconSpec("mdi6.calculator-variant-outline"),
    "item_master": IconSpec("mdi6.clipboard-list-outline"),
    "save": IconSpec(
        "mdi6.content-save-outline",
        fallback=QStyle.SP_DialogSaveButton,
    ),
    "search": IconSpec(
        "mdi6.magnify",
        theme_name="edit-find",
        fallback=QStyle.SP_FileDialogContentsView,
    ),
    "open": IconSpec(
        "mdi6.folder-open-outline",
        theme_name="document-open",
        fallback=QStyle.SP_DialogOpenButton,
    ),
    "print": IconSpec(
        "mdi6.printer-outline",
        theme_name="document-print",
        fallback=QStyle.SP_FileIcon,
    ),
    "print_estimate": IconSpec(
        "mdi6.printer",
        theme_name="document-print",
        fallback=QStyle.SP_FileIcon,
    ),
    "delete": IconSpec(
        "mdi6.delete-outline",
        theme_name="edit-delete",
        fallback=QStyle.SP_TrashIcon,
    ),
    "delete_row": IconSpec("mdi6.table-row-remove"),
    "delete_estimate": IconSpec("mdi6.trash-can-outline"),
    "close": IconSpec(
        "mdi6.close-thick",
        theme_name="window-close",
        fallback=QStyle.SP_DialogCloseButton,
    ),
    "refresh": IconSpec(
        "mdi6.refresh",
        theme_name="view-refresh",
        fallback=QStyle.SP_BrowserReload,
    ),
    "save_pdf": IconSpec(
        "mdi6.file-pdf-box",
        theme_name="document-save",
        fallback=QStyle.SP_DialogSaveButton,
    ),
    "page_setup": IconSpec(
        "mdi6.file-document-edit-outline",
        theme_name="document-properties",
        fallback=QStyle.SP_FileDialogDetailedView,
    ),
    "new": IconSpec("mdi6.file-plus-outline"),
    "zoom_in": IconSpec(
        "mdi6.magnify-plus-outline",
        theme_name="zoom-in",
        fallback=QStyle.SP_ArrowUp,
    ),
    "zoom_out": IconSpec(
        "mdi6.magnify-minus-outline",
        theme_name="zoom-out",
        fallback=QStyle.SP_ArrowDown,
    ),
    "fit_width": IconSpec(
        "mdi6.arrow-expand-horizontal",
        theme_name="zoom-fit-width",
        fallback=QStyle.SP_TitleBarShadeButton,
    ),
    "fit_page": IconSpec(
        "mdi6.fit-to-page-outline",
        theme_name="zoom-fit-best",
        fallback=QStyle.SP_TitleBarUnshadeButton,
    ),
    "page_first": IconSpec(
        "mdi6.page-first",
        theme_name="go-first",
        fallback=QStyle.SP_MediaSkipBackward,
    ),
    "page_previous": IconSpec(
        "mdi6.page-previous",
        theme_name="go-previous",
        fallback=QStyle.SP_MediaSeekBackward,
    ),
    "page_next": IconSpec(
        "mdi6.page-next",
        theme_name="go-next",
        fallback=QStyle.SP_MediaSeekForward,
    ),
    "page_last": IconSpec(
        "mdi6.page-last",
        theme_name="go-last",
        fallback=QStyle.SP_MediaSkipForward,
    ),
    "printer_select": IconSpec(
        "mdi6.printer-settings",
        theme_name="printer",
        fallback=QStyle.SP_ComputerIcon,
    ),
    "exit": IconSpec("mdi6.exit-to-app"),
    "silver_bars": IconSpec("mdi6.silverware-fork-knife"),
    "silver_history": IconSpec("mdi6.history"),
    "settings": IconSpec("mdi6.cog-outline"),
    "about": IconSpec("mdi6.information-outline"),
    "balance": IconSpec("mdi6.bank-outline"),
    "history": IconSpec("mdi6.history"),
    "return_mode": IconSpec("mdi6.cash-refund"),
    "bar_mode": IconSpec("mdi6.silverware-fork-knife"),
    "reset_layout": IconSpec("mdi6.table-column-width"),
    "user_interface": IconSpec(
        "mdi6.monitor-dashboard",
        fallback=QStyle.SP_DesktopIcon,
    ),
    "live_rates": IconSpec(
        "mdi6.chart-line",
        fallback=QStyle.SP_BrowserReload,
    ),
    "printing": IconSpec(
        "mdi6.printer-outline",
        fallback=QStyle.SP_FileDialogDetailedView,
    ),
    "data_management": IconSpec(
        "mdi6.database-cog-outline",
        fallback=QStyle.SP_DirHomeIcon,
    ),
    "security": IconSpec(
        "mdi6.shield-lock-outline",
        fallback=QStyle.SP_MessageBoxWarning,
    ),
    "import_export": IconSpec(
        "mdi6.file-import-outline",
        fallback=QStyle.SP_DialogOpenButton,
    ),
    "logging": IconSpec(
        "mdi6.clipboard-text-outline",
        fallback=QStyle.SP_FileDialogInfoView,
    ),
}


def get_icon(
    name: str,
    *,
    widget: QWidget | None = None,
    color: str | None = None,
    active_color: str | None = None,
) -> QIcon:
    """Resolve a semantic icon using mdi6 with Qt/theme fallbacks."""

    spec = _ICON_SPECS.get(name)
    mdi6_name = (
        spec.mdi6_name
        if spec is not None
        else name
        if "." in name
        else f"mdi6.{name}"
    )

    if _qtawesome is not None:
        try:
            icon_color = color or _DEFAULT_COLOR
            return _qtawesome.icon(
                mdi6_name,
                color=icon_color,
                color_active=active_color or icon_color,
                color_disabled=_DISABLED_COLOR,
            )
        except Exception as exc:  # pragma: no cover - depends on QtAwesome state
            LOGGER.debug("Failed to build qtawesome icon %s: %s", mdi6_name, exc)

    if spec is not None and spec.theme_name:
        themed = QIcon.fromTheme(spec.theme_name)
        if not themed.isNull():
            return themed

    style = _resolve_style(widget)
    if style is not None and spec is not None and spec.fallback is not None:
        return style.standardIcon(spec.fallback)
    return QIcon()


def _resolve_style(widget: QWidget | None) -> QStyle | None:
    if widget is not None:
        return widget.style()
    app = QApplication.instance()
    if app is None:
        return None
    return app.style()
