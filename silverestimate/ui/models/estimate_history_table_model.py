"""Table model for the estimate history dialog."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from PyQt5.QtCore import QAbstractTableModel, QModelIndex, Qt


@dataclass(frozen=True)
class EstimateHistoryRow:
    voucher_no: str
    date: str
    note: str
    silver_rate: float
    total_gross: float
    total_net: float
    net_fine: float
    net_wage: float
    grand_total: float


class EstimateHistoryTableModel(QAbstractTableModel):
    """Expose estimate-history rows through a sortable Qt table model."""

    HEADERS = [
        "Voucher No",
        "Date",
        "Note",
        "Silver Rate",
        "Total Gross",
        "Total Net",
        "Net Fine",
        "Net Wage",
        "Grand Total",
    ]
    _RIGHT_ALIGN_COLUMNS = {3, 4, 5, 6, 7, 8}

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._rows: list[EstimateHistoryRow] = []
        self._sort_column: int | None = None
        self._sort_order = Qt.AscendingOrder

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        if parent.isValid():
            return 0
        return len(self._rows)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        if parent.isValid():
            return 0
        return len(self.HEADERS)

    def headerData(
        self,
        section: int,
        orientation: Qt.Orientation,
        role: int = Qt.DisplayRole,
    ) -> Any:
        if role != Qt.DisplayRole:
            return None
        if orientation == Qt.Horizontal and 0 <= section < len(self.HEADERS):
            return self.HEADERS[section]
        return None

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole) -> Any:
        if not index.isValid():
            return None
        row = self.row_payload(index.row())
        if row is None:
            return None

        if role == Qt.DisplayRole:
            return self._display_value(row, index.column())
        if role == Qt.EditRole:
            return self._sort_value(row, index.column())
        if role == Qt.TextAlignmentRole and index.column() in self._RIGHT_ALIGN_COLUMNS:
            return Qt.AlignRight | Qt.AlignVCenter
        return None

    def sort(self, column: int, order: Qt.SortOrder = Qt.AscendingOrder) -> None:
        if not (0 <= column < self.columnCount()):
            return
        self.layoutAboutToBeChanged.emit()
        self._sort_column = int(column)
        self._sort_order = order
        self._sort_rows()
        self.layoutChanged.emit()

    def set_rows(self, rows: list[EstimateHistoryRow]) -> None:
        self.beginResetModel()
        self._rows = list(rows or [])
        if self._sort_column is not None and self._rows:
            self._sort_rows()
        self.endResetModel()

    def row_payload(self, row: int) -> EstimateHistoryRow | None:
        if 0 <= row < len(self._rows):
            return self._rows[row]
        return None

    def _display_value(self, row: EstimateHistoryRow, column: int) -> str:
        if column == 0:
            return row.voucher_no
        if column == 1:
            return row.date
        if column == 2:
            return row.note
        if column == 3:
            return f"{row.silver_rate:.2f}"
        if column == 4:
            return f"{row.total_gross:.3f}"
        if column == 5:
            return f"{row.total_net:.3f}"
        if column == 6:
            return f"{row.net_fine:.3f}"
        if column == 7:
            return f"{row.net_wage:.2f}"
        if column == 8:
            return f"{row.grand_total:.2f}"
        return ""

    def _sort_value(self, row: EstimateHistoryRow, column: int) -> Any:
        if column == 0:
            return row.voucher_no.casefold()
        if column == 1:
            return row.date
        if column == 2:
            return row.note.casefold()
        if column == 3:
            return row.silver_rate
        if column == 4:
            return row.total_gross
        if column == 5:
            return row.total_net
        if column == 6:
            return row.net_fine
        if column == 7:
            return row.net_wage
        if column == 8:
            return row.grand_total
        return None

    def _sort_rows(self) -> None:
        if self._sort_column is None:
            return
        reverse = self._sort_order == Qt.DescendingOrder
        self._rows.sort(
            key=lambda row: self._sort_key_for_row(row, self._sort_column or 0),
            reverse=reverse,
        )

    def _sort_key_for_row(
        self,
        row: EstimateHistoryRow,
        column: int,
    ) -> tuple[Any, ...]:
        value = self._sort_value(row, column)
        return (value is None, value)


__all__ = ["EstimateHistoryRow", "EstimateHistoryTableModel"]
