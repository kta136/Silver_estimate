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

from PySide6.QtCore import (
    QAbstractNativeEventFilter,
    QCoreApplication,
    QEvent,
    QPoint,
    QSize,
    Qt,
)
from PySide6.QtGui import QGuiApplication, QMouseEvent, QShowEvent
from PySide6.QtWidgets import QAbstractButton, QMenuBar, QWidget
from shiboken6 import isValid

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

# The question Windows asks before every mouse message, and two answers.
WM_NCHITTEST = 0x0084
HTCLIENT = 1
HTTOP = 12


class _NativeMessage(ctypes.Structure):
    """The start of a Windows MSG: the window, the message and its values."""

    _fields_ = (
        ("hwnd", ctypes.c_void_p),
        ("message", ctypes.c_uint),
        ("wParam", ctypes.c_size_t),
        ("lParam", ctypes.c_ssize_t),
    )


class _NativePoint(ctypes.Structure):
    _fields_ = (("x", ctypes.c_long), ("y", ctypes.c_long))


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


def resize_border(window: QWidget) -> int:
    """Thickness, in device pixels, of the edge that resizes the window."""
    user32 = _user32()
    hwnd = int(window.internalWinId())
    if user32 is None or not hwnd:
        return 0
    dpi = user32.GetDpiForWindow(ctypes.c_void_p(hwnd))
    if not dpi:
        return 0
    return sum(
        int(user32.GetSystemMetricsForDpi(metric, dpi))
        for metric in (SM_CXSIZEFRAME, SM_CXPADDEDBORDER)
    )


class _ClickHitTest(QAbstractNativeEventFilter):
    """Tells Windows which parts of the bar take a click themselves.

    Qt 6.11 asks the window about a press in the title bar by delivering
    the press once as a question (accept it, or the window is dragged) and
    then again as the click. A menu opens on the first and closes on the
    second. Answering for the menus and buttons before Qt asks leaves one
    press per click; Qt still decides for the stretch that drags the window.
    """

    def __init__(self, bar: TitleMenuBar) -> None:
        super().__init__()
        self._bar = bar

    def nativeEventFilter(self, _event_type: Any, message: Any) -> Any:
        try:
            native = _NativeMessage.from_address(int(message))
            if native.message != WM_NCHITTEST or not isValid(self._bar):
                return False, 0
            answer = self._bar.native_hit_test(native.hwnd or 0, native.lParam)
        except Exception:
            # A mistake here must never stop the window's own messages.
            return False, 0
        if answer is None:
            return False, 0
        return True, answer


def _stop_answering(hit_test: _ClickHitTest) -> None:
    application = QCoreApplication.instance()
    if application is not None:
        application.removeNativeEventFilter(hit_test)


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
        hit_test = _ClickHitTest(self)
        self._click_hit_test = hit_test
        application = QCoreApplication.instance()
        if application is not None:
            application.installNativeEventFilter(hit_test)
            # Not a method of the bar: it runs while the bar is going away.
            self.destroyed.connect(lambda *_: _stop_answering(hit_test))

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

    def takes_click_at(self, position: QPoint) -> bool:
        """True over a menu or a button; False where a press drags the window."""
        if self.actionAt(position) is not None:
            return True
        child = self.childAt(position)
        while child is not None and child is not self:
            if isinstance(child, QAbstractButton):
                return child.isEnabled()
            child = child.parentWidget()
        return False

    def native_hit_test(self, hwnd: int, screen_position: int) -> int | None:
        """Answer Windows for a point over a menu or button; None asks Qt."""
        user32 = _user32()
        window = self.window()
        if (
            user32 is None
            or not self.isVisible()
            or hwnd != int(window.internalWinId())
        ):
            return None
        point = _NativePoint(
            ctypes.c_short(screen_position & 0xFFFF).value,
            ctypes.c_short((screen_position >> 16) & 0xFFFF).value,
        )
        if not user32.ScreenToClient(ctypes.c_void_p(hwnd), ctypes.byref(point)):
            return None
        scale = max(window.devicePixelRatioF(), 1.0)
        position = self.mapFrom(
            window, QPoint(int(point.x // scale), int(point.y // scale))
        )
        if not self.rect().contains(position) or not self.takes_click_at(position):
            return None
        # The top edge still resizes a window that is not maximised.
        if not (
            window.isMaximized() or window.isFullScreen()
        ) and point.y < resize_border(window):
            return HTTOP
        return HTCLIENT

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
