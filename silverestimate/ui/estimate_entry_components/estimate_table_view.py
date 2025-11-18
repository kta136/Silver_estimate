"""Table view component for estimate entry."""

from __future__ import annotations

from typing import Optional

from PyQt5.QtCore import Qt, pyqtSignal, QModelIndex, QItemSelection
from PyQt5.QtWidgets import QAction, QHeaderView, QMenu, QTableView, QTableWidgetItem

from silverestimate.ui.models.estimate_table_model import EstimateTableModel
from silverestimate.ui.view_models.estimate_entry_view_model import (
    EstimateEntryRowState,
)


class ModelBackedTableItem(QTableWidgetItem):
    """QTableWidgetItem that's backed by a Model/View model.

    This class acts as a bridge between QTableWidget API and Model/View architecture.
    When you call setText(), setData(), etc., it updates the underlying model.
    """

    def __init__(self, model: EstimateTableModel, row: int, column: int):
        """Initialize the item.

        Args:
            model: The table model
            row: The row index
            column: The column index
        """
        super().__init__()
        self._model = model
        self._row = row
        self._column = column
        self._user_data = {}  # Store user data separately

        # Load initial data from model
        index = self._model.index(row, column)
        data = self._model.data(index, Qt.DisplayRole)
        if data is not None:
            super().setText(str(data))

        # Set flags from model
        model_flags = self._model.flags(index)
        self.setFlags(model_flags)

    def setText(self, text: str) -> None:
        """Set the text of this item and update the model.

        Args:
            text: The new text
        """
        super().setText(text)
        index = self._model.index(self._row, self._column)
        self._model.setData(index, text, Qt.EditRole)

    def text(self) -> str:
        """Get the text from the model.

        Returns:
            The current text
        """
        index = self._model.index(self._row, self._column)
        data = self._model.data(index, Qt.DisplayRole)
        return str(data) if data is not None else ""

    def setData(self, role: int, value) -> None:
        """Set data for this item.

        Args:
            role: The data role
            value: The value to set
        """
        if role == Qt.UserRole:
            # Store user data separately (not in the model)
            self._user_data[role] = value
        else:
            super().setData(role, value)

    def data(self, role: int):
        """Get data for this item.

        Args:
            role: The data role

        Returns:
            The data for the role
        """
        if role == Qt.UserRole and role in self._user_data:
            return self._user_data[role]
        return super().data(role)


class EstimateTableView(QTableView):
    """Table view for displaying and editing estimate entries.

    This component displays estimate data using the EstimateTableModel and
    provides keyboard shortcuts, context menus, and cell editing capabilities.

    Provides QTableWidget-compatible signals for backward compatibility with mixins.
    """

    # Modern signals
    item_lookup_requested = pyqtSignal(int, str)  # row, code
    row_deleted = pyqtSignal(int)  # row index
    cell_edited = pyqtSignal(int, int)  # row, column
    history_requested = pyqtSignal()
    column_layout_reset_requested = pyqtSignal()

    # QTableWidget-compatible signals (for mixin compatibility)
    cellChanged = pyqtSignal(int, int)  # row, column
    cellClicked = pyqtSignal(int, int)  # row, column
    itemSelectionChanged = pyqtSignal()  # no args
    currentCellChanged = pyqtSignal(int, int, int, int)  # currentRow, currentCol, prevRow, prevCol

    def __init__(self, parent=None):
        """Initialize the estimate table view.

        Args:
            parent: Optional parent widget
        """
        super().__init__(parent)
        self._table_model = EstimateTableModel(self)
        self._item_cache = {}  # Cache for ModelBackedTableItem instances
        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self) -> None:
        """Set up the user interface."""
        # Set the model
        self.setModel(self._table_model)

        # Table appearance
        self.setAlternatingRowColors(True)
        self.setSelectionBehavior(QTableView.SelectRows)
        self.setSelectionMode(QTableView.SingleSelection)
        self.setShowGrid(True)
        self.setCornerButtonEnabled(False)

        # Enable sorting
        self.setSortingEnabled(False)  # Disable for now to maintain order

        # Header configuration
        horizontal_header = self.horizontalHeader()
        horizontal_header.setStretchLastSection(False)
        horizontal_header.setSectionResizeMode(QHeaderView.Interactive)
        horizontal_header.setDefaultAlignment(Qt.AlignLeft)

        # Vertical header
        vertical_header = self.verticalHeader()
        vertical_header.setVisible(True)
        vertical_header.setDefaultSectionSize(30)

        # Context menu
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)

    def _connect_signals(self) -> None:
        """Connect internal signals."""
        # Store previous cell for currentCellChanged signal
        self._prev_row = -1
        self._prev_col = -1

        # Connect model data changed signal to both modern and compatibility signals
        self._table_model.data_changed_detailed.connect(self._on_data_changed_detailed)

        # Connect view's clicked signal to cellClicked compatibility signal
        self.clicked.connect(self._on_cell_clicked)

        # Connect selection model signals to compatibility signals
        selection_model = self.selectionModel()
        if selection_model:
            selection_model.selectionChanged.connect(self._on_selection_changed)
            selection_model.currentChanged.connect(self._on_current_changed)

    def _on_data_changed_detailed(self, row: int, col: int, old_value, new_value) -> None:
        """Handle detailed data changed from model.

        Emits both modern cell_edited and QTableWidget-compatible cellChanged signals.
        """
        self.cell_edited.emit(row, col)
        self.cellChanged.emit(row, col)

    def _on_cell_clicked(self, index: QModelIndex) -> None:
        """Handle cell clicked.

        Emits QTableWidget-compatible cellClicked signal.
        """
        if index.isValid():
            self.cellClicked.emit(index.row(), index.column())

    def _on_selection_changed(self, selected: QItemSelection, deselected: QItemSelection) -> None:
        """Handle selection changed.

        Emits QTableWidget-compatible itemSelectionChanged signal.
        """
        self.itemSelectionChanged.emit()

    def _on_current_changed(self, current: QModelIndex, previous: QModelIndex) -> None:
        """Handle current cell changed.

        Emits QTableWidget-compatible currentCellChanged signal.
        """
        current_row = current.row() if current.isValid() else -1
        current_col = current.column() if current.isValid() else -1
        prev_row = previous.row() if previous.isValid() else -1
        prev_col = previous.column() if previous.isValid() else -1

        self.currentCellChanged.emit(current_row, current_col, prev_row, prev_col)

    def _show_context_menu(self, position) -> None:
        """Show context menu at the given position.

        Args:
            position: The position where to show the menu
        """
        menu = QMenu(self)

        # Reset column layout action
        reset_action = QAction("Reset Column Layout", self)
        reset_action.triggered.connect(self.column_layout_reset_requested.emit)
        menu.addAction(reset_action)

        menu.addSeparator()

        # Delete row action
        delete_action = QAction("Delete Current Row", self)
        delete_action.triggered.connect(self._delete_current_row)
        menu.addAction(delete_action)

        # Estimate history action
        history_action = QAction("Open Estimate History", self)
        history_action.triggered.connect(self.history_requested.emit)
        menu.addAction(history_action)

        menu.exec_(self.viewport().mapToGlobal(position))

    def _delete_current_row(self) -> None:
        """Delete the currently selected row."""
        current_index = self.currentIndex()
        if current_index.isValid():
            row = current_index.row()
            self.row_deleted.emit(row)

    # Public methods for managing rows

    def add_row(self, row_data: Optional[EstimateEntryRowState] = None) -> int:
        """Add a new row to the table.

        Args:
            row_data: Optional row data. If None, adds an empty row.

        Returns:
            The index of the newly added row
        """
        result = self._table_model.add_row(row_data)
        # Clear cache when rows change
        self._item_cache.clear()
        return result

    def delete_row(self, row_idx: int) -> bool:
        """Delete a row from the table.

        Args:
            row_idx: The index of the row to delete

        Returns:
            True if the row was deleted, False otherwise
        """
        result = self._table_model.remove_row(row_idx)
        # Clear cache when rows change
        self._item_cache.clear()
        return result

    def clear_rows(self) -> None:
        """Remove all rows from the table."""
        self._table_model.clear_rows()
        # Clear cache when rows change
        self._item_cache.clear()

    def get_row(self, row_idx: int) -> Optional[EstimateEntryRowState]:
        """Get the row data at the given index.

        Args:
            row_idx: The row index

        Returns:
            The row data, or None if the index is invalid
        """
        return self._table_model.get_row(row_idx)

    def set_row(self, row_idx: int, row_data: EstimateEntryRowState) -> bool:
        """Set the row data at the given index.

        Args:
            row_idx: The row index
            row_data: The new row data

        Returns:
            True if the row was set, False otherwise
        """
        return self._table_model.set_row(row_idx, row_data)

    def rowCount(self) -> int:
        """Get the number of rows (QTableWidget compatibility adapter).

        Returns:
            The number of rows in the table
        """
        return self._table_model.rowCount()

    def columnCount(self) -> int:
        """Get the number of columns (QTableWidget compatibility adapter).

        Returns:
            The number of columns in the table
        """
        return self._table_model.columnCount()

    def get_all_rows(self) -> list[EstimateEntryRowState]:
        """Get all row data.

        Returns:
            A list of all rows
        """
        return self._table_model.get_all_rows()

    def set_all_rows(self, rows: list[EstimateEntryRowState]) -> None:
        """Set all rows at once.

        Args:
            rows: The new list of rows
        """
        self._table_model.set_all_rows(rows)
        # Clear cache when rows change
        self._item_cache.clear()

    def focus_cell(self, row: int, column: int) -> None:
        """Set focus to a specific cell.

        Args:
            row: The row index
            column: The column index
        """
        if 0 <= row < self._table_model.rowCount():
            index = self._table_model.index(row, column)
            self.setCurrentIndex(index)
            self.edit(index)

    def get_current_row(self) -> int:
        """Get the current row index.

        Returns:
            The current row index, or -1 if no row is selected
        """
        current_index = self.currentIndex()
        return current_index.row() if current_index.isValid() else -1

    def get_current_column(self) -> int:
        """Get the current column index.

        Returns:
            The current column index, or -1 if no column is selected
        """
        current_index = self.currentIndex()
        return current_index.column() if current_index.isValid() else -1

    # QTableWidget compatibility helpers
    def currentRow(self) -> int:
        """QTableWidget-compatible accessor for current row."""
        return self.get_current_row()

    def currentColumn(self) -> int:
        """QTableWidget-compatible accessor for current column."""
        return self.get_current_column()

    def get_model(self) -> EstimateTableModel:
        """Get the underlying table model.

        Returns:
            The EstimateTableModel instance
        """
        return self._table_model

    def save_column_widths(self) -> dict[int, int]:
        """Save the current column widths.

        Returns:
            A dictionary mapping column index to width
        """
        widths = {}
        for col in range(self._table_model.columnCount()):
            widths[col] = self.columnWidth(col)
        return widths

    def restore_column_widths(self, widths: dict[int, int]) -> None:
        """Restore column widths from saved data.

        Args:
            widths: A dictionary mapping column index to width
        """
        for col, width in widths.items():
            if col < self._table_model.columnCount():
                self.setColumnWidth(col, width)

    def reset_column_widths(self) -> None:
        """Reset column widths to default values."""
        # Default widths for each column
        default_widths = {
            0: 100,  # Code
            1: 200,  # Item Name
            2: 80,   # Gross
            3: 80,   # Poly
            4: 80,   # Net Wt
            5: 80,   # Purity
            6: 80,   # Wage Rate
            7: 80,   # Pieces
            8: 80,   # Wage Amt
            9: 80,   # Fine Wt
            10: 80,  # Type
        }
        self.restore_column_widths(default_widths)

    def set_column_stretch(self, column: int, stretch: bool = True) -> None:
        """Set whether a column should stretch to fill available space.

        Args:
            column: The column index
            stretch: True to stretch, False to use fixed width
        """
        header = self.horizontalHeader()
        if stretch:
            header.setSectionResizeMode(column, QHeaderView.Stretch)
        else:
            header.setSectionResizeMode(column, QHeaderView.Interactive)

    # QTableWidget compatibility methods for adapter
    def insertRow(self, row: int) -> None:
        """Insert a new row at the specified position (QTableWidget compatibility).

        Args:
            row: The row index where the new row should be inserted
        """
        self._table_model.add_row()

    def removeRow(self, row: int) -> None:
        """Remove a row at the specified position (QTableWidget compatibility).

        Args:
            row: The row index to remove
        """
        self._table_model.remove_row(row)
        # Clear cache when rows change
        self._item_cache.clear()

    def setCurrentCell(self, row: int, column: int) -> None:
        """Set the current cell (QTableWidget compatibility).

        Args:
            row: The row index
            column: The column index
        """
        index = self._table_model.index(row, column)
        self.setCurrentIndex(index)

    def editItem(self, item) -> None:
        """Start editing an item (QTableWidget compatibility).

        Args:
            item: The QTableWidgetItem to edit (ModelBackedTableItem)
        """
        if isinstance(item, ModelBackedTableItem):
            # Get the index from the item and start editing
            index = self._table_model.index(item._row, item._column)
            self.setCurrentIndex(index)
            self.edit(index)

    def item(self, row: int, column: int):
        """Get the item at the specified row and column (QTableWidget compatibility).

        For Model/View architecture, we create a model-backed QTableWidgetItem that
        synchronizes with the underlying model.

        Args:
            row: The row index
            column: The column index

        Returns:
            A ModelBackedTableItem with the cell data, or None if invalid
        """
        if not (0 <= row < self._table_model.rowCount() and 0 <= column < self._table_model.columnCount()):
            return None

        # Use cached item if available, otherwise create new one
        cache_key = (row, column)
        if cache_key not in self._item_cache:
            self._item_cache[cache_key] = ModelBackedTableItem(self._table_model, row, column)

        return self._item_cache[cache_key]

    def setItem(self, row: int, column: int, item) -> None:
        """Set the item at the specified row and column (QTableWidget compatibility).

        Args:
            row: The row index
            column: The column index
            item: The QTableWidgetItem to set
        """
        if item is None:
            return

        index = self._table_model.index(row, column)
        self._table_model.setData(index, item.text(), Qt.EditRole)

        # Copy flags to the model if needed
        # Note: In Model/View, flags are typically handled by the model's flags() method
