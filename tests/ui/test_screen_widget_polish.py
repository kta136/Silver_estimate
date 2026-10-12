"""Small drawing details that only show up at the real row heights."""

from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import (
    QColor,
    QFont,
    QImage,
    QPainter,
    QStandardItem,
    QStandardItemModel,
)
from PySide6.QtWidgets import QLabel, QStyleOptionViewItem

from silverestimate.ui.screen_widgets import StatusPillDelegate
from silverestimate.ui.shortcuts_dialog import ShortcutsDialog


def _pill_image(row_height: int) -> QImage:
    model = QStandardItemModel(1, 1)
    model.setItem(0, 0, QStandardItem("In active list"))
    delegate = StatusPillDelegate({"In active list": "active"})
    image = QImage(220, row_height, QImage.Format.Format_ARGB32)
    image.fill(QColor("#ffffff"))
    painter = QPainter(image)
    option = QStyleOptionViewItem()
    option.rect = QRect(0, 0, 220, row_height)
    option.font = QFont("Segoe UI", 11)
    delegate.paint(painter, option, model.index(0, 0))
    painter.end()
    return image


def test_status_pill_leaves_a_clear_line_above_and_below_it(qt_app):
    del qt_app
    # The pill used to be as tall as a 24 px row, so its outline touched the
    # row above and below and the pills of neighbouring rows ran together.
    for row_height in (22, 24):
        image = _pill_image(row_height)
        middle = 40
        assert image.pixelColor(middle, 0) == QColor("#ffffff"), row_height
        assert image.pixelColor(middle, row_height - 1) == QColor("#ffffff")
        # ...and as much room above it as below, with the pill in the middle.
        above = next(
            y
            for y in range(row_height)
            if image.pixelColor(middle, y) != QColor("#ffffff")
        )
        below = next(
            row_height - 1 - y
            for y in range(row_height - 1, -1, -1)
            if image.pixelColor(middle, y) != QColor("#ffffff")
        )
        assert above >= 1 and below >= 1
        assert abs(above - below) <= 1, (row_height, above, below)


def test_shortcut_group_headings_line_up_across_columns(qtbot):
    dialog = ShortcutsDialog()
    qtbot.addWidget(dialog)
    # Taller than the groups need, as on a screen that gives it room: the
    # shorter group in each row used to centre itself in the extra height.
    dialog.resize(776, 620)
    dialog.show()
    qtbot.waitUntil(dialog.isVisible)

    grid = dialog.layout().itemAt(1).layout()
    cells = [grid.itemAt(index) for index in range(grid.count())]
    assert len(cells) >= 4
    for cell in cells:
        assert cell.alignment() & Qt.AlignmentFlag.AlignTop

    headings = [
        label
        for label in dialog.findChildren(QLabel)
        if label.objectName() == "Eyebrow"
    ]
    assert len(headings) >= 4
    rows: dict[int, list[int]] = {}
    for heading in headings:
        top = heading.mapTo(dialog, heading.rect().topLeft()).y()
        column = heading.mapTo(dialog, heading.rect().topLeft()).x()
        rows.setdefault(0 if top < dialog.height() // 2 else 1, []).append(top)
        assert column >= 0
    for tops in rows.values():
        assert max(tops) - min(tops) <= 1, tops
