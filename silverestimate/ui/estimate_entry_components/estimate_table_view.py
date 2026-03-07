"""Table view component for estimate entry."""

from __future__ import annotations

from dataclasses import replace
from typing import Any, Optional

from PyQt5.QtCore import QItemSelection, QModelIndex, Qt, pyqtSignal
from PyQt5.QtGui import QColor, QPalette
from PyQt5.QtWidgets import QAction, QHeaderView, QMenu, QTableView

from silverestimate.domain.estimate_models import EstimateLineCategory
from silverestimate.ui.models.estimate_table_model import EstimateTableModel
from silverestimate.ui.view_models.estimate_entry_view_model import (
    EstimateEntryRowState,
)


class EstimateTableView(QTableView):
    """Table view for displaying and editing estimate entries.

    This component displays estimate data using the EstimateTableModel and
    provides keyboard shortcuts, context menus, and cell editing capabilities.

    Exposes model-first helper APIs consumed by estimate-entry runtime code.
    """

    item_lookup_requested = pyqtSignal(int, str)  # row, code
    row_deleted = pyqtSignal(int)  # row index
    cell_edited = pyqtSignal(int, int)  # row, column
    history_requested = pyqtSignal()
    column_layout_reset_requested = pyqtSignal()

    # Retained for existing signal wiring in EstimateEntryWidget.
    cellChanged = pyqtSignal(int, int)  # row, column
    cellClicked = pyqtSignal(int, int)  # row, column
    itemSelectionChanged = pyqtSignal()  # no args
    currentCellChanged = pyqtSignal(
        int, int, int, int
    )  # currentRow, currentCol, prevRow, prevCol

    host_widget: QTableView | None

    def __init__(self, parent=None):
        super().__init__(parent)
        self.host_widget = None
        self._table_model = EstimateTableModel(self)
        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self) -> None:
        self.setObjectName("EstimateTableView")
        self.setModel(self._table_model)

        self.setAlternatingRowColors(True)
        self.setSelectionBehavior(QTableView.SelectRows)
        self.setSelectionMode(QTableView.SingleSelection)
        self.setShowGrid(True)
        self.setCornerButtonEnabled(False)
        self.setSortingEnabled(False)

        horizontal_header = self.horizontalHeader()
        horizontal_header.setStretchLastSection(False)
        horizontal_header.setSectionResizeMode(QHeaderView.Interactive)
        horizontal_header.setDefaultAlignment(Qt.AlignLeft)

        vertical_header = self.verticalHeader()
        vertical_header.setVisible(True)
        vertical_header.setDefaultSectionSize(30)
        vertical_header.setMinimumSectionSize(28)

        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)

        palette = self.palette()
        palette.setColor(QPalette.Base, QColor("#ffffff"))
        palette.setColor(QPalette.AlternateBase, QColor("#f4f6f8"))
        palette.setColor(QPalette.Highlight, QColor("#dbeafe"))
        palette.setColor(QPalette.HighlightedText, QColor("#111827"))
        self.setPalette(palette)

    def _connect_signals(self) -> None:
        self._table_model.data_changed_detailed.connect(self._on_data_changed_detailed)
        self.clicked.connect(self._on_cell_clicked)

        selection_model = self.selectionModel()
        if selection_model:
            selection_model.selectionChanged.connect(self._on_selection_changed)
            selection_model.currentChanged.connect(self._on_current_changed)

    def _on_data_changed_detailed(
        self, row: int, col: int, old_value: object, new_value: object
    ) -> None:
        self.cell_edited.emit(row, col)
        self.cellChanged.emit(row, col)

    def _on_cell_clicked(self, index: QModelIndex) -> None:
        if index.isValid():
            self.cellClicked.emit(index.row(), index.column())

    def _on_selection_changed(
        self, selected: QItemSelection, deselected: QItemSelection
    ) -> None:
        del selected, deselected
        self.itemSelectionChanged.emit()

    def _on_current_changed(self, current: QModelIndex, previous: QModelIndex) -> None:
        current_row = current.row() if current.isValid() else -1
        current_col = current.column() if current.isValid() else -1
        prev_row = previous.row() if previous.isValid() else -1
        prev_col = previous.column() if previous.isValid() else -1
        self.currentCellChanged.emit(current_row, current_col, prev_row, prev_col)

    def _show_context_menu(self, position) -> None:
        menu = QMenu(self)

        reset_action = QAction("Reset Column Layout", self)
        reset_action.triggered.connect(self.column_layout_reset_requested.emit)
        menu.addAction(reset_action)

        menu.addSeparator()

        delete_action = QAction("Delete Current Row", self)
        delete_action.triggered.connect(self._delete_current_row)
        menu.addAction(delete_action)

        history_action = QAction("Open Estimate History", self)
        history_action.triggered.connect(self.history_requested.emit)
        menu.addAction(history_action)

        menu.exec_(self.viewport().mapToGlobal(position))

    def _delete_current_row(self) -> None:
        current_index = self.currentIndex()
        if current_index.isValid():
            self.row_deleted.emit(current_index.row())

    def add_row(self, row_data: Optional[EstimateEntryRowState] = None) -> int:
        return self._table_model.add_row(row_data)

    def append_empty_row(self) -> int:
        row_data = EstimateEntryRowState(
            row_index=self._table_model.rowCount() + 1,
            pieces=0,
            wage_type="WT",
            category=EstimateLineCategory.REGULAR,
        )
        return self.add_row(row_data)

    def append_row_state(self, row_state: EstimateEntryRowState) -> int:
        if row_state.row_index <= 0:
            row_state = replace(row_state, row_index=self._table_model.rowCount() + 1)
        return self.add_row(row_state)

    def delete_row(self, row_idx: int) -> bool:
        return self._table_model.remove_row(row_idx)

    def clear_rows(self) -> None:
        self._table_model.clear_rows()

    def get_row(self, row_idx: int) -> Optional[EstimateEntryRowState]:
        return self._table_model.get_row(row_idx)

    def get_row_state(self, row_idx: int) -> Optional[EstimateEntryRowState]:
        return self.get_row(row_idx)

    def set_row(self, row_idx: int, row_data: EstimateEntryRowState) -> bool:
        return self._table_model.set_row(row_idx, row_data)

    def rowCount(self) -> int:
        return self._table_model.rowCount()

    def columnCount(self) -> int:
        return self._table_model.columnCount()

    def get_all_rows(self) -> list[EstimateEntryRowState]:
        return self._table_model.get_all_rows()

    def set_all_rows(self, rows: list[EstimateEntryRowState]) -> None:
        self._table_model.set_all_rows(rows)

    def replace_all_rows(self, rows: list[EstimateEntryRowState]) -> None:
        self.set_all_rows(rows)

    def get_model(self) -> EstimateTableModel:
        return self._table_model

    def get_cell_value(self, row: int, column: int, role: int = Qt.DisplayRole) -> Any:
        if not (0 <= row < self._table_model.rowCount()):
            return None
        if not (0 <= column < self._table_model.columnCount()):
            return None
        index = self._table_model.index(row, column)
        if not index.isValid():
            return None
        return self._table_model.data(index, role)

    def get_cell_text(self, row: int, column: int) -> str:
        value = self.get_cell_value(row, column, Qt.DisplayRole)
        if value is None:
            return ""
        return str(value)

    def set_cell_value(self, row: int, column: int, value: Any) -> bool:
        if not (0 <= row < self._table_model.rowCount()):
            return False
        if not (0 <= column < self._table_model.columnCount()):
            return False
        index = self._table_model.index(row, column)
        if not index.isValid():
            return False
        return bool(self._table_model.setData(index, value, Qt.EditRole))

    def set_cell_text(self, row: int, column: int, value: str) -> bool:
        return self.set_cell_value(row, column, str(value))

    def set_row_category(self, row: int, category: EstimateLineCategory) -> bool:
        row_state = self.get_row_state(row)
        if row_state is None:
            return False
        return self.set_row(row, replace(row_state, category=category))

    def set_row_wage_type(self, row: int, wage_type: str) -> bool:
        return bool(self._table_model.set_row_wage_type(row, wage_type))

    def is_cell_editable(self, row: int, column: int) -> bool:
        if not (0 <= row < self._table_model.rowCount()):
            return False
        if not (0 <= column < self._table_model.columnCount()):
            return False
        index = self._table_model.index(row, column)
        if not index.isValid():
            return False
        return bool(self._table_model.flags(index) & Qt.ItemIsEditable)

    def focus_cell(self, row: int, column: int, *, start_edit: bool = False) -> None:
        if not (0 <= row < self._table_model.rowCount()):
            return
        index = self._table_model.index(row, column)
        if not index.isValid():
            return
        self.setCurrentIndex(index)
        if start_edit and (self._table_model.flags(index) & Qt.ItemIsEditable):
            self.edit(index)

    def begin_cell_edit(self, row: int, column: int) -> bool:
        if not self.is_cell_editable(row, column):
            return False
        index = self._table_model.index(row, column)
        if not index.isValid():
            return False
        self.setCurrentIndex(index)
        self.edit(index)
        return True

    def get_current_row(self) -> int:
        current_index = self.currentIndex()
        return current_index.row() if current_index.isValid() else -1

    def get_current_column(self) -> int:
        current_index = self.currentIndex()
        return current_index.column() if current_index.isValid() else -1

    def currentRow(self) -> int:
        return self.get_current_row()

    def currentColumn(self) -> int:
        return self.get_current_column()

    def setCurrentCell(self, row: int, column: int) -> None:
        index = self._table_model.index(row, column)
        self.setCurrentIndex(index)

    def save_column_widths(self) -> dict[int, int]:
        widths = {}
        for col in range(self._table_model.columnCount()):
            widths[col] = self.columnWidth(col)
        return widths

    def restore_column_widths(self, widths: dict[int, int]) -> None:
        for col, width in widths.items():
            if col < self._table_model.columnCount():
                self.setColumnWidth(col, width)

    def reset_column_widths(self) -> None:
        default_widths = {
            0: 100,
            1: 200,
            2: 80,
            3: 80,
            4: 80,
            5: 80,
            6: 80,
            7: 80,
            8: 80,
            9: 80,
            10: 80,
        }
        self.restore_column_widths(default_widths)

    def set_column_stretch(self, column: int, stretch: bool = True) -> None:
        header = self.horizontalHeader()
        if stretch:
            header.setSectionResizeMode(column, QHeaderView.Stretch)
        else:
            header.setSectionResizeMode(column, QHeaderView.Interactive)
