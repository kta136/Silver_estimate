"""Checkbox gutter backed by the table's existing row selection."""

from PySide6.QtCore import QItemSelectionModel, Qt
from PySide6.QtWidgets import QHeaderView, QStyle, QStyleOptionButton


class SelectionCheckHeader(QHeaderView):
    def __init__(self, table):
        super().__init__(Qt.Orientation.Vertical, table)
        self.table = table
        self.setSectionsClickable(True)
        self.setFixedWidth(28)
        self.setDefaultSectionSize(table.verticalHeader().defaultSectionSize())
        self.sectionClicked.connect(self._toggle)
        table.selectionModel().selectionChanged.connect(self.viewport().update)
        table.setVerticalHeader(self)
        self.show()

    def _toggle(self, row):
        self.table.selectionModel().select(
            self.table.model().index(row, 0),
            QItemSelectionModel.SelectionFlag.Toggle
            | QItemSelectionModel.SelectionFlag.Rows,
        )

    def paintSection(self, painter, rect, logical_index):
        painter.fillRect(rect, self.palette().base())
        option = QStyleOptionButton()
        option.rect = rect.adjusted(6, 4, -4, -4)
        option.state = QStyle.StateFlag.State_Enabled
        selected = self.table.selectionModel().isRowSelected(logical_index)
        option.state |= (
            QStyle.StateFlag.State_On if selected else QStyle.StateFlag.State_Off
        )
        self.style().drawControl(QStyle.ControlElement.CE_CheckBox, option, painter)
