"""QAbstractTableModel implementation for estimate entry table."""

from __future__ import annotations

from typing import Any, Optional

from PyQt5.QtCore import QAbstractTableModel, QModelIndex, Qt, pyqtSignal

from silverestimate.domain.estimate_models import EstimateLineCategory
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
from silverestimate.ui.view_models.estimate_entry_view_model import (
    EstimateEntryRowState,
)


class EstimateTableModel(QAbstractTableModel):
    """Table model for estimate entry data.

    This model manages the rows of estimate data and provides the interface
    for the QTableView to display and edit the data.
    """

    # Signal emitted when data changes (row, column, old_value, new_value)
    data_changed_detailed = pyqtSignal(int, int, object, object)

    # Column headers
    HEADERS = [
        "Code",
        "Item Name",
        "Gross",
        "Poly",
        "Net Wt",
        "Purity",
        "Wage Rate",
        "Pieces",
        "Wage Amt",
        "Fine Wt",
        "Type",
    ]

    def __init__(self, parent=None):
        """Initialize the table model.

        Args:
            parent: Optional parent QObject
        """
        super().__init__(parent)
        self._rows: list[EstimateEntryRowState] = []

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        """Return the number of rows in the model."""
        if parent.isValid():
            return 0
        return len(self._rows)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        """Return the number of columns in the model."""
        if parent.isValid():
            return 0
        return len(self.HEADERS)

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole) -> Any:
        """Return data for the given index and role.

        Args:
            index: The model index
            role: The data role (DisplayRole, EditRole, etc.)

        Returns:
            The data for the given role, or None if not available
        """
        if not index.isValid() or not (0 <= index.row() < len(self._rows)):
            return None

        if role not in (Qt.DisplayRole, Qt.EditRole):
            return None

        row_data = self._rows[index.row()]
        col = index.column()

        if col == COL_CODE:
            return row_data.code
        elif col == COL_ITEM_NAME:
            return row_data.name
        elif col == COL_GROSS:
            return row_data.gross
        elif col == COL_POLY:
            return row_data.poly
        elif col == COL_NET_WT:
            return row_data.net_weight
        elif col == COL_PURITY:
            return row_data.purity
        elif col == COL_WAGE_RATE:
            return row_data.wage_rate
        elif col == COL_PIECES:
            return row_data.pieces
        elif col == COL_WAGE_AMT:
            return row_data.wage_amount
        elif col == COL_FINE_WT:
            return row_data.fine_weight
        elif col == COL_TYPE:
            return row_data.category.value if row_data.category else ""

        return None

    def setData(self, index: QModelIndex, value: Any, role: int = Qt.EditRole) -> bool:
        """Set data for the given index.

        Args:
            index: The model index
            value: The new value
            role: The data role

        Returns:
            True if the data was set successfully, False otherwise
        """
        if not index.isValid() or not (0 <= index.row() < len(self._rows)):
            return False

        if role != Qt.EditRole:
            return False

        row_idx = index.row()
        col = index.column()
        old_row = self._rows[row_idx]

        # Create a new row with the updated value using dataclass replace
        from dataclasses import replace

        try:
            if col == COL_CODE:
                new_row = replace(old_row, code=str(value) if value is not None else "")
            elif col == COL_ITEM_NAME:
                new_row = replace(old_row, name=str(value) if value is not None else "")
            elif col == COL_GROSS:
                new_row = replace(old_row, gross=float(value) if value else 0.0)
            elif col == COL_POLY:
                new_row = replace(old_row, poly=float(value) if value else 0.0)
            elif col == COL_NET_WT:
                new_row = replace(old_row, net_weight=float(value) if value else 0.0)
            elif col == COL_PURITY:
                new_row = replace(old_row, purity=float(value) if value else 0.0)
            elif col == COL_WAGE_RATE:
                new_row = replace(old_row, wage_rate=float(value) if value else 0.0)
            elif col == COL_PIECES:
                new_row = replace(old_row, pieces=int(value) if value else 1)
            elif col == COL_WAGE_AMT:
                new_row = replace(old_row, wage_amount=float(value) if value else 0.0)
            elif col == COL_FINE_WT:
                new_row = replace(old_row, fine_weight=float(value) if value else 0.0)
            elif col == COL_TYPE:
                # Handle EstimateLineCategory
                if isinstance(value, EstimateLineCategory):
                    new_row = replace(old_row, category=value)
                else:
                    # Try to convert string to category
                    category = EstimateLineCategory(str(value)) if value else EstimateLineCategory.REGULAR
                    new_row = replace(old_row, category=category)
            else:
                return False

            # Store old value for detailed signal
            old_value = self.data(index, Qt.DisplayRole)

            # Update the row
            self._rows[row_idx] = new_row

            # Emit standard signal
            self.dataChanged.emit(index, index, [Qt.DisplayRole, Qt.EditRole])

            # Emit detailed signal with row, column, old and new values
            self.data_changed_detailed.emit(row_idx, col, old_value, value)

            return True

        except (ValueError, TypeError):
            return False

    def headerData(
        self, section: int, orientation: Qt.Orientation, role: int = Qt.DisplayRole
    ) -> Any:
        """Return header data for the given section.

        Args:
            section: The section (row or column index)
            orientation: Horizontal or vertical
            role: The data role

        Returns:
            The header data, or None if not available
        """
        if role != Qt.DisplayRole:
            return None

        if orientation == Qt.Horizontal and 0 <= section < len(self.HEADERS):
            return self.HEADERS[section]
        elif orientation == Qt.Vertical:
            return section + 1  # Row numbers starting from 1

        return None

    def flags(self, index: QModelIndex) -> Qt.ItemFlags:
        """Return the item flags for the given index.

        Args:
            index: The model index

        Returns:
            The item flags
        """
        if not index.isValid():
            return Qt.NoItemFlags

        # Calculated columns are read-only
        col = index.column()
        if col in (COL_NET_WT, COL_WAGE_AMT, COL_FINE_WT, COL_TYPE):
            return Qt.ItemIsEnabled | Qt.ItemIsSelectable

        # All other columns are editable
        return Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsEditable

    # Custom methods for managing rows

    def add_row(self, row_data: Optional[EstimateEntryRowState] = None) -> int:
        """Add a new row to the model.

        Args:
            row_data: Optional row data. If None, adds an empty row.

        Returns:
            The index of the newly added row
        """
        if row_data is None:
            row_data = EstimateEntryRowState(row_index=len(self._rows))

        row_idx = len(self._rows)
        self.beginInsertRows(QModelIndex(), row_idx, row_idx)
        self._rows.append(row_data)
        self.endInsertRows()

        return row_idx

    def remove_row(self, row_idx: int) -> bool:
        """Remove a row from the model.

        Args:
            row_idx: The index of the row to remove

        Returns:
            True if the row was removed, False otherwise
        """
        if not (0 <= row_idx < len(self._rows)):
            return False

        self.beginRemoveRows(QModelIndex(), row_idx, row_idx)
        self._rows.pop(row_idx)
        self.endRemoveRows()

        # Update row indices for remaining rows
        for i in range(row_idx, len(self._rows)):
            from dataclasses import replace
            self._rows[i] = replace(self._rows[i], row_index=i)

        return True

    def clear_rows(self) -> None:
        """Remove all rows from the model."""
        if not self._rows:
            return

        self.beginRemoveRows(QModelIndex(), 0, len(self._rows) - 1)
        self._rows.clear()
        self.endRemoveRows()

    def get_row(self, row_idx: int) -> Optional[EstimateEntryRowState]:
        """Get the row data at the given index.

        Args:
            row_idx: The row index

        Returns:
            The row data, or None if the index is invalid
        """
        if 0 <= row_idx < len(self._rows):
            return self._rows[row_idx]
        return None

    def set_row(self, row_idx: int, row_data: EstimateEntryRowState) -> bool:
        """Set the row data at the given index.

        Args:
            row_idx: The row index
            row_data: The new row data

        Returns:
            True if the row was set, False otherwise
        """
        if not (0 <= row_idx < len(self._rows)):
            return False

        self._rows[row_idx] = row_data

        # Emit dataChanged for the entire row
        left_index = self.index(row_idx, 0)
        right_index = self.index(row_idx, self.columnCount() - 1)
        self.dataChanged.emit(left_index, right_index, [Qt.DisplayRole, Qt.EditRole])

        return True

    def get_all_rows(self) -> list[EstimateEntryRowState]:
        """Get all row data.

        Returns:
            A list of all rows
        """
        return list(self._rows)

    def set_all_rows(self, rows: list[EstimateEntryRowState]) -> None:
        """Set all rows at once.

        Args:
            rows: The new list of rows
        """
        self.beginResetModel()
        self._rows = list(rows)
        self.endResetModel()
