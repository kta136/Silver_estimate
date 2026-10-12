"""The estimate table's number editor must always show what was typed."""

from PySide6.QtGui import QFont
from PySide6.QtWidgets import QLineEdit, QTableWidget, QTableWidgetItem

from silverestimate.ui.estimate_entry_logic.constants import COL_GROSS, COL_POLY
from silverestimate.ui.estimate_entry_ui import NumericDelegate


def _open_editor(qtbot, text, *, column_width=72):
    table = QTableWidget(1, COL_POLY + 1)
    qtbot.addWidget(table)
    # The size the app uses; at a smaller font the digits would fit anyway.
    table.setFont(QFont("Segoe UI", 11))
    table.setItemDelegateForColumn(COL_GROSS, NumericDelegate(table))
    table.setColumnWidth(COL_GROSS, column_width)
    table.setItem(0, COL_GROSS, QTableWidgetItem(text))
    table.resize(700, 120)
    table.show()
    qtbot.waitUntil(table.isVisible)
    index = table.model().index(0, COL_GROSS)
    table.setCurrentIndex(index)
    table.edit(index)
    editor = table.indexWidget(index)
    assert isinstance(editor, QLineEdit)
    qtbot.wait(20)
    return table, index, editor


def test_editor_is_wide_enough_for_a_weight_of_a_kilo_or_more(qtbot):
    # 1239.567 g used to read 239.567 while editing: the leading digit
    # scrolled out of a 72 px cell.
    table, index, editor = _open_editor(qtbot, "1239.567")
    cell = table.visualRect(index)

    needed = editor.fontMetrics().horizontalAdvance("1239.567")
    assert editor.width() >= needed + 16
    # Numbers are right aligned, so it grows to the left and keeps the cell's
    # right edge.
    assert editor.geometry().right() == cell.right()
    assert editor.geometry().left() >= 0
    assert editor.text() == "1239.567"


def test_editor_keeps_the_cell_size_when_the_number_is_short(qtbot):
    table, index, editor = _open_editor(qtbot, "12.5")

    assert editor.geometry() == table.visualRect(index)


def test_editor_grows_while_digits_are_typed(qtbot):
    table, index, editor = _open_editor(qtbot, "1.5")
    cell = table.visualRect(index)
    assert editor.width() == cell.width()

    editor.setText("123456.789")

    needed = editor.fontMetrics().horizontalAdvance("123456.789")
    assert editor.width() >= needed + 16
    assert editor.geometry().right() == cell.right()
