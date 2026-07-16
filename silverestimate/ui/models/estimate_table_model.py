"""QAbstractTableModel implementation for estimate entry table."""

from __future__ import annotations

from dataclasses import replace
from typing import Any, Optional
from uuid import uuid4

from PyQt6.QtCore import QAbstractTableModel, QModelIndex, Qt, pyqtSignal
from PyQt6.QtGui import QBrush, QColor, QFont

from silverestimate.domain.estimate_models import EstimateLineCategory
from silverestimate.ui.estimate_entry_logic.column_specs import (
    NUMERIC_COLUMNS,
    column_count,
    header_for_column,
    is_editable_column,
    precision_for_column,
)
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
from silverestimate.ui.estimate_table_formatting import format_indian_number
from silverestimate.ui.numeric_font import numeric_table_font
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

    _NUMERIC_COLUMNS = NUMERIC_COLUMNS
    _TYPE_BACKGROUND_BRUSHES = {
        EstimateLineCategory.RETURN: QBrush(QColor("#dbeafe")),
        EstimateLineCategory.SILVER_BAR: QBrush(QColor("#fff7ed")),
        EstimateLineCategory.REGULAR: QBrush(QColor("#f8fafc")),
    }
    _TYPE_FOREGROUND_BRUSHES = {
        EstimateLineCategory.RETURN: QBrush(QColor("#1d4ed8")),
        EstimateLineCategory.SILVER_BAR: QBrush(QColor("#b45309")),
        EstimateLineCategory.REGULAR: QBrush(QColor("#334155")),
    }
    _CALCULATED_BACKGROUND_BRUSH = QBrush(QColor("#f1f5f9"))
    _CALCULATED_FOREGROUND_BRUSH = QBrush(QColor("#0f172a"))

    def __init__(self, parent=None):
        """Initialize the table model.

        Args:
            parent: Optional parent QObject
        """
        super().__init__(parent)
        self._rows: list[EstimateEntryRowState] = []
        self._numeric_font_cache: QFont | None = None
        self._numeric_font_cache_key: str | None = None

    def _numeric_display_font(self) -> QFont:
        parent = self.parent()
        base_font = (
            parent.font() if parent is not None and hasattr(parent, "font") else None
        )
        cache_key = base_font.toString() if base_font is not None else ""
        if (
            self._numeric_font_cache is None
            or cache_key != self._numeric_font_cache_key
        ):
            self._numeric_font_cache = numeric_table_font(base_font)
            self._numeric_font_cache_key = cache_key
        return self._numeric_font_cache

    def invalidate_style_cache(self) -> None:
        """Invalidate role values derived from the parent view's font."""

        self._numeric_font_cache = None
        self._numeric_font_cache_key = None

    @staticmethod
    def _raw_cell_value(row_data: EstimateEntryRowState, col: int) -> Any:
        if col == COL_CODE:
            return row_data.code
        if col == COL_ITEM_NAME:
            return row_data.name
        if col == COL_GROSS:
            return row_data.gross
        if col == COL_POLY:
            return row_data.poly
        if col == COL_NET_WT:
            return row_data.net_weight
        if col == COL_PURITY:
            return row_data.purity
        if col == COL_WAGE_RATE:
            return row_data.wage_rate
        if col == COL_PIECES:
            return row_data.pieces
        if col == COL_WAGE_AMT:
            return row_data.wage_amount
        if col == COL_FINE_WT:
            return row_data.fine_weight
        if col == COL_TYPE:
            return row_data.category.display_name() if row_data.category else ""
        return None

    def _display_cell_value(self, row_data: EstimateEntryRowState, col: int) -> Any:
        raw_value = self._raw_cell_value(row_data, col)
        precision = precision_for_column(col)
        if precision is not None:
            return format_indian_number(raw_value, precision)
        return raw_value

    @staticmethod
    def _normalize_wage_type(value: Any) -> str:
        normalized = str(value or "").strip().upper()
        return "PC" if normalized == "PC" else "WT"

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        """Return the number of rows in the model."""
        if parent.isValid():
            return 0
        return len(self._rows)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        """Return the number of columns in the model."""
        if parent.isValid():
            return 0
        return column_count()

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        """Return data for the given index and role.

        Args:
            index: The model index
            role: The data role (DisplayRole, EditRole, etc.)

        Returns:
            The data for the given role, or None if not available
        """
        if not index.isValid() or not (0 <= index.row() < len(self._rows)):
            return None

        row_data = self._rows[index.row()]
        col = index.column()

        if role == Qt.ItemDataRole.DisplayRole:
            return self._display_cell_value(row_data, col)

        if role == Qt.ItemDataRole.EditRole:
            return self._raw_cell_value(row_data, col)

        if role == Qt.ItemDataRole.FontRole and col in self._NUMERIC_COLUMNS:
            return self._numeric_display_font()

        if role == Qt.ItemDataRole.BackgroundRole and col == COL_TYPE:
            return self._TYPE_BACKGROUND_BRUSHES.get(
                row_data.category,
                self._TYPE_BACKGROUND_BRUSHES[EstimateLineCategory.REGULAR],
            )

        if role == Qt.ItemDataRole.ForegroundRole and col == COL_TYPE:
            return self._TYPE_FOREGROUND_BRUSHES.get(
                row_data.category,
                self._TYPE_FOREGROUND_BRUSHES[EstimateLineCategory.REGULAR],
            )

        if role == Qt.ItemDataRole.BackgroundRole and col in (
            COL_NET_WT,
            COL_WAGE_AMT,
            COL_FINE_WT,
        ):
            return self._CALCULATED_BACKGROUND_BRUSH

        if role == Qt.ItemDataRole.ForegroundRole and col in (
            COL_NET_WT,
            COL_WAGE_AMT,
            COL_FINE_WT,
        ):
            return self._CALCULATED_FOREGROUND_BRUSH

        if role == Qt.ItemDataRole.TextAlignmentRole:
            if col in self._NUMERIC_COLUMNS:
                return Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            if col == COL_TYPE:
                return Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter

        return None

    def setData(
        self, index: QModelIndex, value: Any, role: int = Qt.ItemDataRole.EditRole
    ) -> bool:
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

        if role != Qt.ItemDataRole.EditRole:
            return False

        row_idx = index.row()
        col = index.column()
        old_row = self._rows[row_idx]

        # Create a new row with the updated value using dataclass replace
        try:
            if col == COL_CODE:
                new_code = str(value) if value is not None else ""
                new_row = replace(
                    old_row,
                    code=new_code,
                    line_key=old_row.line_key if new_code.strip() else "",
                )
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
                if value is None or str(value).strip() == "":
                    pieces = 1 if old_row.wage_type == "PC" else 0
                else:
                    pieces = int(value)
                new_row = replace(old_row, pieces=pieces)
            elif col == COL_WAGE_AMT:
                new_row = replace(old_row, wage_amount=float(value) if value else 0.0)
            elif col == COL_FINE_WT:
                new_row = replace(old_row, fine_weight=float(value) if value else 0.0)
            elif col == COL_TYPE:
                # Handle EstimateLineCategory
                if isinstance(value, EstimateLineCategory):
                    new_row = replace(old_row, category=value)
                else:
                    # Use from_label to convert display name or enum value to category
                    category = (
                        EstimateLineCategory.from_label(str(value))
                        if value
                        else EstimateLineCategory.REGULAR
                    )
                    new_row = replace(old_row, category=category)
            else:
                return False

            # For unchanged Code cells, skip emitting change signals to avoid
            # retriggering item lookup and overwriting manual row overrides.
            # Other unchanged editable cells still emit signals so Enter/Tab
            # navigation keeps moving forward through the row.
            if col == COL_CODE and new_row == old_row:
                return True

            # Store old value for detailed signal
            old_value = self.data(index, Qt.ItemDataRole.DisplayRole)

            # Update the row
            self._rows[row_idx] = new_row

            # Emit standard signal
            self.dataChanged.emit(
                index, index, [Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole]
            )

            # Emit detailed signal with row, column, old and new values
            self.data_changed_detailed.emit(row_idx, col, old_value, value)

            return True

        except ValueError, TypeError:
            return False

    def headerData(
        self,
        section: int,
        orientation: Qt.Orientation,
        role: int = Qt.ItemDataRole.DisplayRole,
    ) -> Any:
        """Return header data for the given section.

        Args:
            section: The section (row or column index)
            orientation: Horizontal or vertical
            role: The data role

        Returns:
            The header data, or None if not available
        """
        if role != Qt.ItemDataRole.DisplayRole:
            return None

        if orientation == Qt.Orientation.Horizontal:
            return header_for_column(section)
        elif orientation == Qt.Orientation.Vertical:
            return section + 1  # Row numbers starting from 1

    def flags(self, index: QModelIndex) -> Qt.ItemFlag:
        """Return the item flags for the given index.

        Args:
            index: The model index

        Returns:
            The item flags
        """
        if not index.isValid():
            return Qt.ItemFlag(Qt.ItemFlag.NoItemFlags)

        col = index.column()
        if not is_editable_column(col):
            return Qt.ItemFlag(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
        if col == COL_PIECES:
            row_data = self.get_row(index.row())
            if row_data and row_data.wage_type != "PC":
                return Qt.ItemFlag(
                    Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
                )

        # All other columns are editable
        return Qt.ItemFlag(
            Qt.ItemFlag.ItemIsEnabled
            | Qt.ItemFlag.ItemIsSelectable
            | Qt.ItemFlag.ItemIsEditable
        )

    def set_row_wage_type(self, row_idx: int, wage_type: str) -> bool:
        """Update a row's wage type and refresh pieces editability."""
        if not (0 <= row_idx < len(self._rows)):
            return False

        normalized = self._normalize_wage_type(wage_type)
        row_data = self._rows[row_idx]
        if row_data.wage_type == normalized:
            return True

        self._rows[row_idx] = replace(row_data, wage_type=normalized)
        pieces_index = self.index(row_idx, COL_PIECES)
        self.dataChanged.emit(
            pieces_index,
            pieces_index,
            [Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole],
        )
        return True

    # Custom methods for managing rows

    def add_row(self, row_data: Optional[EstimateEntryRowState] = None) -> int:
        """Add a new row to the model.

        Args:
            row_data: Optional row data. If None, adds an empty row.

        Returns:
            The index of the newly added row
        """
        row_idx = len(self._rows)
        if row_data is None:
            row_data = EstimateEntryRowState(
                row_index=row_idx + 1,
                pieces=0,
                wage_type="WT",
            )
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
        self.dataChanged.emit(
            left_index,
            right_index,
            [Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole],
        )

        return True

    def get_all_rows(self) -> list[EstimateEntryRowState]:
        """Get all row data.

        Returns:
            A list of all rows
        """
        return list(self._rows)

    def ensure_line_keys(self) -> None:
        """Assign stable line keys to active rows missing one."""
        changed_rows: list[int] = []
        for row_idx, row_data in enumerate(self._rows):
            if row_data.is_empty() or str(row_data.line_key or "").strip():
                continue
            self._rows[row_idx] = replace(row_data, line_key=uuid4().hex)
            changed_rows.append(row_idx)

        for row_idx in changed_rows:
            left_index = self.index(row_idx, 0)
            right_index = self.index(row_idx, self.columnCount() - 1)
            self.dataChanged.emit(
                left_index,
                right_index,
                [Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole],
            )

    def set_all_rows(self, rows: list[EstimateEntryRowState]) -> None:
        """Set all rows at once.

        Args:
            rows: The new list of rows
        """
        self.beginResetModel()
        self._rows = list(rows)
        self.endResetModel()
