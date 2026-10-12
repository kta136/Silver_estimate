"""The estimate screen on a 1280x720 screen, such as a remote desktop session."""

import pytest
from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QScrollArea

from silverestimate.infrastructure.settings import SettingsKey
from silverestimate.ui.application_theme import apply_light_application_theme
from silverestimate.ui.estimate_entry_logic.constants import (
    COL_CODE,
    COL_FINE_WT,
    COL_GROSS,
    COL_ITEM_NAME,
    COL_NET_WT,
    COL_PIECES,
    COL_POLY,
    COL_PURITY,
    COL_TYPE,
    COL_WAGE_AMT,
    COL_WAGE_RATE,
)
from tests.factories import regular_item
from tests.smoke.test_full_startup_smoke import _configure_smoke_font
from tests.ui.test_estimate_entry_widget import _set_row

# Height the side panel gets: a maximized window on a 1280x720 screen is 649
# px high (less the taskbar and title bar), and the panel has 595 of it. The
# smallest window the app allows there leaves 586.
PANEL_HEIGHTS = [595, 586]

# The columns that show numbers, and every column but the two that give way.
NUMBER_COLUMNS = (
    COL_GROSS,
    COL_POLY,
    COL_NET_WT,
    COL_PURITY,
    COL_WAGE_RATE,
    COL_PIECES,
    COL_WAGE_AMT,
    COL_FINE_WT,
)
OTHER_COLUMNS = (COL_CODE, *NUMBER_COLUMNS)


@pytest.fixture
def small_screen_widget(qtbot, qt_application_state, make_estimate_widget, fake_db):
    _configure_smoke_font(qt_application_state)
    apply_light_application_theme(qt_application_state)
    widget = make_estimate_widget(fake_db)
    for row in range(4):
        _set_row(widget, row, regular_item(gross=1239.567, poly=0, purity=92.5))
    widget.layout_controller.grow_columns_to_content()
    return widget


def _show_with_panel_height(qtbot, widget, width: int, panel_height: int) -> None:
    widget.resize(width, 700)
    widget.show()
    qtbot.wait(60)
    # The widget is taller than the panel by the strip above the table.
    chrome = widget.height() - widget.totals_panel.height()
    widget.resize(width, panel_height + chrome)
    qtbot.wait(120)
    assert widget.totals_panel.height() == panel_height


@pytest.mark.parametrize("panel_height", PANEL_HEIGHTS)
def test_side_panel_needs_no_scrollbar_on_a_1280x720_screen(
    qtbot, small_screen_widget, panel_height
):
    widget = small_screen_widget
    _show_with_panel_height(qtbot, widget, 1280, panel_height)

    scroll = widget.totals_panel.findChild(QScrollArea)
    assert scroll.verticalScrollBar().maximum() == 0
    # Everything down to Delete Estimate is in view.
    bottom = widget.delete_estimate_button.mapTo(
        widget.totals_panel, widget.delete_estimate_button.rect().bottomLeft()
    ).y()
    assert bottom < widget.totals_panel.height()
    # Not by a hair: fonts differ from one PC to the next.
    assert scroll.widget().layout().minimumSize().height() <= panel_height - 5


def test_load_button_is_as_tall_as_the_voucher_field_beside_it(
    qtbot, small_screen_widget
):
    widget = small_screen_widget
    _show_with_panel_height(qtbot, widget, 1280, 595)

    # A taller button made the whole row, and so the panel, taller.
    assert widget.load_button.height() == widget.voucher_edit.height()


def test_status_line_sits_under_the_table_not_in_the_side_panel(
    qtbot, small_screen_widget
):
    widget = small_screen_widget
    _show_with_panel_height(qtbot, widget, 1280, 595)

    status = widget.status_line_label
    assert not widget.totals_panel.isAncestorOf(status)
    assert status.parentWidget() is widget.item_table.parentWidget()
    assert status.geometry().top() >= widget.item_table.geometry().bottom()
    assert f"Rows: {widget.item_table.rowCount()}" in status.text()
    assert "F1 Shortcuts" in status.text()
    # One line, so it costs the table little.
    assert status.height() <= 24


def _drag_divider(widget, dx: int) -> None:
    splitter = widget._content_splitter
    handle = splitter.handle(1)
    start = handle.rect().center()
    end = QPoint(start.x() + dx, start.y())
    QTest.mousePress(
        handle, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, start
    )
    QTest.mouseMove(handle, end)
    QTest.mouseRelease(
        handle, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, end
    )


def _table_shows_every_column(widget) -> bool:
    table = widget.item_table
    columns = sum(
        table.columnWidth(column)
        for column in range(table.columnCount())
        if not table.isColumnHidden(column)
    )
    return table.horizontalScrollBar().maximum() == 0 and (
        table.viewport().width() >= columns
    )


def _numbers_are_whole(widget) -> bool:
    """Every number in the first row fits its column, with its full text."""
    table = widget.item_table
    metrics = table.fontMetrics()
    return all(
        metrics.horizontalAdvance(table.get_cell_text(0, column))
        <= table.columnWidth(column) - 4
        for column in NUMBER_COLUMNS
    )


def _widths(widget, columns) -> dict[int, int]:
    return {column: widget.item_table.columnWidth(column) for column in columns}


def test_widening_the_side_panel_takes_the_room_from_item_name_and_type_only(
    qtbot, small_screen_widget
):
    widget = small_screen_widget
    _show_with_panel_height(qtbot, widget, 1280, 595)
    table = widget.item_table
    panel_before = widget.totals_panel.width()
    name_before = table.columnWidth(COL_ITEM_NAME)
    type_before = table.columnWidth(COL_TYPE)
    others_before = _widths(widget, OTHER_COLUMNS)
    assert _table_shows_every_column(widget)

    _drag_divider(widget, -120)
    qtbot.wait(120)

    # The panel grew, as far as the two columns could give.
    assert widget.totals_panel.width() > panel_before + 40
    limits = widget.layout_controller._column_width_limits()
    assert table.columnWidth(COL_ITEM_NAME) == limits[COL_ITEM_NAME][0]
    assert table.columnWidth(COL_TYPE) == limits[COL_TYPE][0]
    assert table.columnWidth(COL_ITEM_NAME) < name_before
    assert table.columnWidth(COL_TYPE) < type_before
    # Gross, Net and the rest kept their width, were never cut, and the table
    # does not scroll.
    assert _widths(widget, OTHER_COLUMNS) == others_before
    assert _numbers_are_whole(widget)
    assert _table_shows_every_column(widget)


def test_item_name_gives_up_room_before_type_does(qtbot, small_screen_widget):
    widget = small_screen_widget
    _show_with_panel_height(qtbot, widget, 1280, 595)
    table = widget.item_table
    name_before = table.columnWidth(COL_ITEM_NAME)
    type_before = table.columnWidth(COL_TYPE)

    _drag_divider(widget, -25)
    qtbot.wait(120)

    assert table.columnWidth(COL_ITEM_NAME) < name_before
    assert table.columnWidth(COL_TYPE) == type_before
    assert _table_shows_every_column(widget)


def test_type_goes_back_to_its_width_when_there_is_room_again(
    qtbot, small_screen_widget
):
    widget = small_screen_widget
    _show_with_panel_height(qtbot, widget, 1280, 595)
    table = widget.item_table
    type_before = table.columnWidth(COL_TYPE)

    _drag_divider(widget, -120)
    qtbot.wait(120)
    assert table.columnWidth(COL_TYPE) < type_before
    # What is saved is the width Type prefers, not the one it is squeezed to.
    widget.layout_controller._save_column_widths_setting()
    saved = widget.layout_controller._settings().value(
        "ui/estimate_table_column_widths", type=str
    )
    assert int(saved.split(",")[COL_TYPE]) == type_before

    _drag_divider(widget, 200)
    qtbot.wait(120)
    assert table.columnWidth(COL_TYPE) == type_before


def test_a_narrow_window_narrows_the_side_panel_before_the_table_scrolls(
    qtbot, small_screen_widget
):
    widget = small_screen_widget
    _show_with_panel_height(qtbot, widget, 1280, 595)
    panel = widget.totals_panel
    assert panel.width() == 320

    # 1280 - 12 margins - 10 handle leaves 1258; with the panel at 320 the
    # table has 938. Here it has 790 and needs 872 even with both columns at
    # their minimum, so the panel gives up what it can.
    widget.resize(1130, widget.height())
    qtbot.wait(150)
    assert panel.width() == panel.minimumWidth()
    # Never narrower than its fields and buttons need, or they are cut off.
    assert panel.width() >= panel.content_minimum_width()

    # And it goes back to the width it had as soon as the room is there.
    widget.resize(1280, widget.height())
    qtbot.wait(150)
    assert panel.width() == 320
    assert _table_shows_every_column(widget)


def test_a_wider_window_lets_the_side_panel_grow_up_to_its_maximum(
    qtbot, small_screen_widget
):
    widget = small_screen_widget
    _show_with_panel_height(qtbot, widget, 1700, 595)

    _drag_divider(widget, -300)
    qtbot.wait(120)

    assert widget.totals_panel.width() == widget.totals_panel.maximumWidth()
    assert _table_shows_every_column(widget)


def test_the_side_panel_can_still_be_narrowed_to_give_the_table_room(
    qtbot, small_screen_widget
):
    widget = small_screen_widget
    _show_with_panel_height(qtbot, widget, 1280, 595)

    _drag_divider(widget, 120)
    qtbot.wait(120)

    assert widget.totals_panel.width() == widget.totals_panel.minimumWidth()
    assert widget.totals_panel.width() >= widget.totals_panel.content_minimum_width()


def test_the_side_panel_width_is_remembered(
    qtbot, small_screen_widget, make_estimate_widget, fake_db
):
    widget = small_screen_widget
    _show_with_panel_height(qtbot, widget, 1700, 595)
    assert widget.totals_panel.width() == 320

    _drag_divider(widget, -60)
    qtbot.wait(500)  # saved shortly after the drag, as the column widths are

    chosen = widget.totals_panel.width()
    assert chosen == 380
    settings = widget.layout_controller._settings()
    assert settings.get_int(SettingsKey.UI_ESTIMATE_PANEL_WIDTH, 0) == chosen

    reopened = make_estimate_widget(fake_db)
    _show_with_panel_height(qtbot, reopened, 1700, 595)
    assert reopened.totals_panel.width() == chosen


def test_a_remembered_width_too_big_for_the_window_comes_back_when_it_fits(
    qtbot, small_screen_widget, make_estimate_widget, fake_db
):
    widget = small_screen_widget
    widget.layout_controller._settings().set(SettingsKey.UI_ESTIMATE_PANEL_WIDTH, 440)
    reopened = make_estimate_widget(fake_db)

    _show_with_panel_height(qtbot, reopened, 1150, 595)
    # On 1150 the item name and Type cannot give 440 px, so it is narrower...
    panel = reopened.totals_panel
    assert panel.content_minimum_width() <= panel.width() < 440
    assert _table_shows_every_column(reopened)

    reopened.resize(1700, reopened.height())
    qtbot.wait(150)
    # ...but the choice itself was kept.
    assert reopened.totals_panel.width() == 440


def test_estimate_table_headings_are_short_and_keep_their_meaning_in_tooltips(
    small_screen_widget,
):
    model = small_screen_widget.item_table.model()
    headings = [
        model.headerData(column, Qt.Orientation.Horizontal)
        for column in range(model.columnCount())
    ]
    assert headings == [
        "Code",
        "Item Name",
        "Gross",
        "Poly",
        "Net",
        "%",
        "Lbr",
        "Pc",
        "Lbr",
        "Fine",
        "Type",
    ]

    def tooltip(column):
        return model.headerData(
            column, Qt.Orientation.Horizontal, Qt.ItemDataRole.ToolTipRole
        )

    # Told apart by the tooltip: the two Lbr columns, and the short names.
    assert tooltip(COL_PURITY) == "Purity (%)"
    assert tooltip(COL_PIECES) == "Pieces"
    assert "rate" in tooltip(COL_WAGE_RATE)
    assert "amount" in tooltip(COL_WAGE_AMT)
