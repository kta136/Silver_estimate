"""The menu bar inside the window's title bar (Windows, Qt 6.9 or newer).

Qt keeps drawing the window icon and the minimise, maximise and close buttons.
The menu bar takes the rest of the strip, so the window gives one row of chrome
back to its content. Everywhere else the window keeps an ordinary title bar.
"""

from __future__ import annotations

import ctypes
import math
import os
from typing import Any

from PySide6.QtCore import QEvent, QSize, Qt
from PySide6.QtGui import QGuiApplication, QMouseEvent, QShowEvent
from PySide6.QtWidgets import QMenuBar, QWidget

# Set to true to keep the ordinary title bar.
CLASSIC_TITLE_BAR_ENV = "SILVER_CLASSIC_TITLE_BAR"
HINT_NAMES = ("ExpandedClientAreaHint", "NoTitleBarBackgroundHint")

# Qt draws its title over the menus, so the window gets a blank one. An empty
# title would be replaced by the application's name.
BLANK_TITLE = " "
# Room for the window icon Qt draws at the left end of the strip.
ICON_SPACE = 40
# Height of a title bar where Windows cannot be asked for it.
DEFAULT_TITLE_HEIGHT = 31.0
# Qt draws three caption buttons, each one and a half title bars wide.
CAPTION_BUTTON_COUNT = 3
CAPTION_BUTTON_ASPECT = 1.5
# The theme's menu-bar items: padding above and below the text, and the
# bar's bottom border.
ITEM_PADDING = 3
ITEM_SIDE_PADDING = 8
BAR_BORDER = 1

# Windows builds the title bar from these three system metrics.
SM_CYCAPTION = 4
SM_CXSIZEFRAME = 32
SM_CXPADDEDBORDER = 92


def _user32() -> Any | None:
    if QGuiApplication.platformName() != "windows":
        return None
    return getattr(getattr(ctypes, "windll", None), "user32", None)


def supported() -> bool:
    """True where Qt can draw the caption buttons over the window's content."""
    if os.environ.get(CLASSIC_TITLE_BAR_ENV, "").lower() in ("true", "1", "yes"):
        return False
    if QGuiApplication.platformName() != "windows":
        return False
    return all(hasattr(Qt.WindowType, name) for name in HINT_NAMES)


def merge_menu_into_title_bar(window: QWidget) -> bool:
    """Run ``window``'s content under its title bar. Call before it is shown."""
    if not supported():
        return False
    window.setWindowFlags(
        window.windowFlags()
        | Qt.WindowType.ExpandedClientAreaHint
        | Qt.WindowType.NoTitleBarBackgroundHint
    )
    # The menu bar belongs in the title bar, not in the safe area below it.
    # Qt 6.11 leaves this off already; it is set in case that changes.
    window.setAttribute(Qt.WidgetAttribute.WA_ContentsMarginsRespectsSafeArea, False)
    return True


def title_bar_height(window: QWidget) -> float:
    """Height, in the window's own units, of the strip the caption buttons fill.

    Qt sizes the buttons from the system metrics at the window's DPI. The safe
    area it reports is shorter on a scaled display, so that is not used.
    """
    user32 = _user32()
    if user32 is None:
        return DEFAULT_TITLE_HEIGHT
    hwnd = int(window.internalWinId())
    dpi = (
        user32.GetDpiForWindow(ctypes.c_void_p(hwnd))
        if hwnd
        else user32.GetDpiForSystem()
    )
    if not dpi:
        return DEFAULT_TITLE_HEIGHT
    physical = sum(
        int(user32.GetSystemMetricsForDpi(metric, dpi))
        for metric in (SM_CYCAPTION, SM_CXSIZEFRAME, SM_CXPADDEDBORDER)
    )
    return physical / max(window.devicePixelRatioF(), 1.0)


def caption_buttons_width(window: QWidget) -> int:
    """Width the minimise, maximise and close buttons cover at the right end."""
    return math.ceil(
        CAPTION_BUTTON_COUNT * CAPTION_BUTTON_ASPECT * title_bar_height(window)
    )


def set_native_caption(window: QWidget, text: str) -> None:
    """Name the window for the taskbar and Alt+Tab without drawing the name."""
    user32 = _user32()
    hwnd = int(window.internalWinId())
    if user32 is None or not hwnd:
        return
    user32.SetWindowTextW(ctypes.c_void_p(hwnd), ctypes.c_wchar_p(text))


class _IconSpace(QWidget):
    """Keeps the menus clear of the window icon Qt draws over the bar."""

    def sizeHint(self) -> QSize:
        return QSize(ICON_SPACE, 1)

    def minimumSizeHint(self) -> QSize:
        return self.sizeHint()


class TitleMenuBar(QMenuBar):
    """A menu bar that fills the title bar and can be dragged by its empty part."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._item_padding = 0
        self.setCornerWidget(_IconSpace(self), Qt.Corner.TopLeftCorner)
        self._match_title_height()

    def caption_buttons_width(self) -> int:
        """Width to keep clear at the right end for the caption buttons."""
        return caption_buttons_width(self.window())

    def row_height(self) -> int:
        """Height of the menus; a corner widget this tall sits level with them."""
        return self.fontMetrics().height() + 2 * self._item_padding

    def _match_title_height(self) -> None:
        """Pad the items until the bar is as tall as the caption buttons."""
        target = round(title_bar_height(self.window()))
        # Full height from the start, before the menus are added.
        self.setMinimumHeight(target)
        spare = target - BAR_BORDER - self.fontMetrics().height()
        padding = max(ITEM_PADDING, spare // 2)
        if padding != self._item_padding:
            self._item_padding = padding
            self.setStyleSheet(
                f"QMenuBar::item {{ padding: {padding}px {ITEM_SIDE_PADDING}px; }}"
            )
        corner = self.cornerWidget(Qt.Corner.TopRightCorner)
        if corner is not None:
            corner.setMinimumHeight(self.row_height())

    def changeEvent(self, event: QEvent) -> None:
        super().changeEvent(event)
        if event.type() == QEvent.Type.FontChange:
            self._match_title_height()

    def showEvent(self, event: QShowEvent) -> None:
        super().showEvent(event)
        # Only a window that exists can say which display's scale it uses.
        self._match_title_height()

    def _on_empty_stretch(self, event: QMouseEvent) -> bool:
        return self.actionAt(event.position().toPoint()) is None

    def mousePressEvent(self, event: QMouseEvent) -> None:
        # Left unhandled, a press here lets Windows drag the window.
        if self._on_empty_stretch(event):
            event.ignore()
            return
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        # Left unhandled, a double-click here maximises or restores the window.
        if self._on_empty_stretch(event):
            event.ignore()
            return
        super().mouseDoubleClickEvent(event)
