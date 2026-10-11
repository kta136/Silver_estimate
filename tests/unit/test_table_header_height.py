"""Table headers stay tall enough for their bold labels."""

import pytest
from PySide6.QtGui import QFont, QFontMetrics, QStandardItemModel
from PySide6.QtWidgets import QTableView

from silverestimate.ui.appearance import header_height, set_table_font


@pytest.mark.parametrize("size", [8, 9, 11, 14, 16])
def test_header_height_leaves_room_for_bold_text_and_its_padding(qtbot, size):
    table = QTableView()
    qtbot.addWidget(table)
    table.setModel(QStandardItemModel(1, 2))
    set_table_font(table, QFont("Segoe UI", size))

    bold = QFont(table.horizontalHeader().font())
    bold.setBold(True)
    # 4 px of padding above and below, and the bottom border.
    assert header_height(table) >= QFontMetrics(bold).height() + 9


def test_header_height_never_goes_below_the_asked_minimum(qtbot):
    table = QTableView()
    qtbot.addWidget(table)
    table.setModel(QStandardItemModel(1, 2))
    set_table_font(table, QFont("Segoe UI", 8))

    assert header_height(table, minimum=60) == 60
