"""The menu bar that sits in the window's title bar on Windows."""

from PySide6.QtCore import QEvent, QPoint, QPointF, Qt
from PySide6.QtGui import QFont, QMouseEvent
from PySide6.QtWidgets import QMainWindow, QPushButton, QWidget

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


def test_menus_move_into_the_title_bar_on_windows(qt_app, monkeypatch):
    # Windows 10 and 11 alike: Qt draws the buttons on both.
    _on_windows(monkeypatch)
    assert title_bar.supported()


def test_environment_switch_keeps_the_ordinary_title_bar(qt_app, monkeypatch):
    _on_windows(monkeypatch)
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
