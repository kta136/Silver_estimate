"""The menu bar that sits in the window's title bar on Windows."""

import ctypes

from PySide6.QtCore import QEvent, QPoint, QPointF, Qt
from PySide6.QtGui import QFont, QMouseEvent
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QWidget,
)

from silverestimate.ui import title_bar
from silverestimate.ui.title_bar import TitleMenuBar

EXPANDED = Qt.WindowType.ExpandedClientAreaHint
NO_BACKGROUND = Qt.WindowType.NoTitleBarBackgroundHint
SAFE_AREA = Qt.WidgetAttribute.WA_ContentsMarginsRespectsSafeArea


def _on_windows(monkeypatch) -> None:
    monkeypatch.delenv(title_bar.CLASSIC_TITLE_BAR_ENV, raising=False)
    monkeypatch.setattr(
        title_bar.QGuiApplication, "platformName", staticmethod(lambda: "windows")
    )


def _mouse(bar: TitleMenuBar, kind: QEvent.Type, point: QPoint) -> QMouseEvent:
    return QMouseEvent(
        kind,
        QPointF(point),
        QPointF(bar.mapToGlobal(point)),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )


def test_ordinary_title_bar_is_kept_where_qt_cannot_draw_the_buttons(qt_app, qtbot):
    # The tests run on Qt's offscreen platform, which has no title bar.
    window = QWidget()
    qtbot.addWidget(window)
    flags = window.windowFlags()

    assert not title_bar.supported()
    assert not title_bar.merge_menu_into_title_bar(window)
    assert window.windowFlags() == flags


def test_environment_switch_keeps_the_ordinary_title_bar(qt_app, monkeypatch):
    _on_windows(monkeypatch)
    # Windows 10 and 11 alike: Qt draws the buttons on both.
    assert title_bar.supported()
    for value in ("true", "1", "YES"):
        monkeypatch.setenv(title_bar.CLASSIC_TITLE_BAR_ENV, value)
        assert not title_bar.supported()
    monkeypatch.setenv(title_bar.CLASSIC_TITLE_BAR_ENV, "false")
    assert title_bar.supported()


def test_merging_runs_the_window_content_under_the_title_bar(
    qt_app, qtbot, monkeypatch
):
    monkeypatch.setattr(title_bar, "supported", lambda: True)
    window = QWidget()
    qtbot.addWidget(window)
    window.setAttribute(SAFE_AREA, True)

    assert title_bar.merge_menu_into_title_bar(window)
    assert window.windowFlags() & EXPANDED
    assert window.windowFlags() & NO_BACKGROUND
    assert not window.testAttribute(SAFE_AREA)


def test_caption_buttons_take_four_and_a_half_title_heights(qt_app, qtbot, monkeypatch):
    window = QMainWindow()
    qtbot.addWidget(window)
    # Off Windows there is no title bar to measure.
    assert title_bar.title_bar_height(window) == title_bar.DEFAULT_TITLE_HEIGHT

    monkeypatch.setattr(title_bar, "title_bar_height", lambda _window: 30.4)
    assert title_bar.caption_buttons_width(window) == 137


def test_menus_start_after_the_window_icon(qt_app, qtbot):
    bar = TitleMenuBar()
    qtbot.addWidget(bar)
    menu = bar.addMenu("&File")
    bar.resize(600, bar.sizeHint().height())
    bar.show()

    assert bar.actionGeometry(menu.menuAction()).left() >= title_bar.ICON_SPACE


def test_empty_part_of_the_bar_is_left_for_windows_to_drag(qt_app, qtbot):
    bar = TitleMenuBar()
    qtbot.addWidget(bar)
    menu = bar.addMenu("&File")
    menu.addAction("Example")
    bar.resize(600, bar.sizeHint().height())
    bar.show()
    empty = QPoint(400, bar.height() // 2)
    assert bar.actionAt(empty) is None

    press = _mouse(bar, QEvent.Type.MouseButtonPress, empty)
    bar.mousePressEvent(press)
    assert not press.isAccepted()

    double_click = _mouse(bar, QEvent.Type.MouseButtonDblClick, empty)
    bar.mouseDoubleClickEvent(double_click)
    assert not double_click.isAccepted()

    # The icon's corner is part of the title bar too.
    assert bar.actionAt(QPoint(title_bar.ICON_SPACE // 2, bar.height() // 2)) is None


def test_a_press_on_a_menu_still_opens_it(qt_app, qtbot):
    bar = TitleMenuBar()
    qtbot.addWidget(bar)
    menu = bar.addMenu("&File")
    menu.addAction("Example")
    bar.resize(600, bar.sizeHint().height())
    bar.show()
    try:
        qtbot.mouseClick(
            bar,
            Qt.MouseButton.LeftButton,
            pos=bar.actionGeometry(menu.menuAction()).center(),
        )
        assert menu.isVisible()
    finally:
        menu.close()


def test_bar_and_its_corner_widget_match_the_caption_buttons(
    qt_app, qtbot, monkeypatch
):
    monkeypatch.setattr(title_bar, "title_bar_height", lambda _window: 30.4)
    bar = TitleMenuBar()
    qtbot.addWidget(bar)
    font = QFont(bar.font())
    font.setPixelSize(16)
    bar.setFont(font)
    text_height = bar.fontMetrics().height()

    # Never shorter than the buttons, even before it has menus.
    assert bar.minimumHeight() == 30
    assert bar.row_height() == text_height + 2 * bar._item_padding
    assert 30 - 2 <= bar.row_height() + title_bar.BAR_BORDER <= 30

    button = QPushButton("Save")
    bar.setCornerWidget(button, Qt.Corner.TopRightCorner)
    font.setPixelSize(12)
    bar.setFont(font)
    assert bar.fontMetrics().height() < text_height
    assert button.minimumHeight() == bar.row_height()

    # Large text makes the bar taller; it is never squeezed to fit.
    font.setPixelSize(40)
    bar.setFont(font)
    assert bar._item_padding == title_bar.ITEM_PADDING


class _FakeUser32:
    """Windows calls the hit test makes; screen and window coordinates agree."""

    def ScreenToClient(self, _hwnd, _point) -> int:  # noqa: N802
        return 1

    def GetDpiForWindow(self, _hwnd) -> int:  # noqa: N802
        return 96

    def GetSystemMetricsForDpi(self, _metric, _dpi) -> int:  # noqa: N802
        return 4


def _window_with_menus_and_buttons(qtbot):
    window = QMainWindow()
    qtbot.addWidget(window)
    bar = TitleMenuBar(window)
    window.setMenuBar(bar)
    menu = bar.addMenu("&File")
    menu.addAction("Example")
    strip = QWidget()
    row = QHBoxLayout(strip)
    row.setContentsMargins(0, 0, 0, 0)
    status = QLabel("Ready")
    save = QPushButton("Save")
    locked = QPushButton("Print")
    locked.setEnabled(False)
    for widget in (status, save, locked):
        row.addWidget(widget)
    bar.setCornerWidget(strip, Qt.Corner.TopRightCorner)
    window.resize(900, 500)
    window.show()
    qtbot.waitExposed(window)
    return window, bar, menu, status, save, locked


def _centre(bar: TitleMenuBar, widget: QWidget) -> QPoint:
    return widget.mapTo(bar, widget.rect().center())


def _screen_position(point: QPoint) -> int:
    return (point.y() << 16) | point.x()


def test_menus_and_buttons_take_the_click_and_the_rest_drags_the_window(qt_app, qtbot):
    _, bar, menu, status, save, locked = _window_with_menus_and_buttons(qtbot)
    item = bar.actionGeometry(menu.menuAction())

    assert bar.takes_click_at(item.center())
    assert bar.takes_click_at(_centre(bar, save))
    # A button that is switched off, a label and the empty stretch all drag.
    assert not bar.takes_click_at(_centre(bar, locked))
    assert not bar.takes_click_at(_centre(bar, status))
    assert not bar.takes_click_at(QPoint(item.right() + 60, bar.height() // 2))
    assert not bar.takes_click_at(QPoint(title_bar.ICON_SPACE // 2, bar.height() // 2))


def test_windows_is_answered_for_menus_and_buttons_only(qt_app, qtbot, monkeypatch):
    # Qt 6.11 would deliver a press here twice; the second closes the menu.
    window, bar, menu, _, save, _ = _window_with_menus_and_buttons(qtbot)
    monkeypatch.setattr(title_bar, "_user32", _FakeUser32)
    hwnd = int(window.internalWinId())
    item = bar.actionGeometry(menu.menuAction())
    on_item = _screen_position(item.center())
    assert item.center().y() >= title_bar.resize_border(window) == 8

    assert bar.native_hit_test(hwnd, on_item) == title_bar.HTCLIENT
    assert (
        bar.native_hit_test(hwnd, _screen_position(_centre(bar, save)))
        == title_bar.HTCLIENT
    )
    # Qt decides for the stretch that drags the window, and for other windows.
    empty = QPoint(item.right() + 60, bar.height() // 2)
    assert bar.native_hit_test(hwnd, _screen_position(empty)) is None
    assert bar.native_hit_test(hwnd + 1, on_item) is None

    # The top edge resizes the window until it is maximised.
    top_edge = _screen_position(QPoint(item.center().x(), 2))
    assert bar.native_hit_test(hwnd, top_edge) == title_bar.HTTOP
    window.showMaximized()
    qtbot.waitUntil(window.isMaximized)
    edge_item = bar.actionGeometry(menu.menuAction())
    top_edge = _screen_position(QPoint(edge_item.center().x(), 2))
    assert bar.native_hit_test(hwnd, top_edge) == title_bar.HTCLIENT


def test_only_the_hit_test_message_is_answered(qt_app, qtbot, monkeypatch):
    window, bar, menu, _, _, _ = _window_with_menus_and_buttons(qtbot)
    monkeypatch.setattr(title_bar, "_user32", _FakeUser32)
    centre = bar.actionGeometry(menu.menuAction()).center()
    message = title_bar._NativeMessage(
        int(window.internalWinId()),
        title_bar.WM_NCHITTEST,
        0,
        _screen_position(centre),
    )
    address = ctypes.addressof(message)
    hit_test = bar._click_hit_test

    assert hit_test.nativeEventFilter(b"windows_generic_MSG", address) == (
        True,
        title_bar.HTCLIENT,
    )
    message.message = 0x0200  # a mouse move
    assert hit_test.nativeEventFilter(b"windows_generic_MSG", address) == (False, 0)
