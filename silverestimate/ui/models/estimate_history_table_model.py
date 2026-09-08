"""Table model for the estimate history dialog."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from PySide6.QtCore import (
    QAbstractTableModel,
    QModelIndex,
    QPersistentModelIndex,
    Qt,
)

from silverestimate.domain.numeric_policy import WEIGHT_PLACES
from silverestimate.ui.display_formatting import format_display_date, format_rupees
from silverestimate.ui.estimate_table_formatting import format_indian_number
from silverestimate.ui.models.table_sorting import insert_model_rows, sort_model_rows


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
        self._sort_order = Qt.SortOrder.AscendingOrder

    def rowCount(
        self, parent: QModelIndex | QPersistentModelIndex = QModelIndex()
    ) -> int:
        if parent.isValid():
            return 0
        return len(self._rows)

    def columnCount(
        self, parent: QModelIndex | QPersistentModelIndex = QModelIndex()
    ) -> int:
        if parent.isValid():
            return 0
        return len(self.HEADERS)

    def headerData(
        self,
        section: int,
        orientation: Qt.Orientation,
        role: int = Qt.ItemDataRole.DisplayRole,
    ) -> Any:
        if role != Qt.ItemDataRole.DisplayRole:
            return None
        if orientation == Qt.Orientation.Horizontal and 0 <= section < len(
            self.HEADERS
        ):
            return self.HEADERS[section]
        return None

    def data(
        self,
        index: QModelIndex | QPersistentModelIndex,
        role: int = Qt.ItemDataRole.DisplayRole,
    ) -> Any:
        if not index.isValid():
            return None
        row = self.row_payload(index.row())
        if row is None:
            return None

        if role == Qt.ItemDataRole.DisplayRole:
            return self._display_value(row, index.column())
        if role == Qt.ItemDataRole.EditRole:
            return self._sort_value(row, index.column())
        if role == Qt.ItemDataRole.ToolTipRole:
            return self._display_value(row, index.column())
        if (
            role == Qt.ItemDataRole.TextAlignmentRole
            and index.column() in self._RIGHT_ALIGN_COLUMNS
        ):
            return Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        return None

    def sort(
        self, column: int, order: Qt.SortOrder = Qt.SortOrder.AscendingOrder
    ) -> None:
        if not (0 <= column < self.columnCount()):
            return
        self._sort_column = int(column)
        self._sort_order = order
        sort_model_rows(
            self,
            self._rows,
            key=lambda row: self._sort_key_for_row(row, column),
            reverse=order == Qt.SortOrder.DescendingOrder,
        )

    def set_rows(self, rows: list[EstimateHistoryRow]) -> None:
        self.beginResetModel()
        self._rows = list(rows or [])
        if self._sort_column is not None and self._rows:
            self._sort_rows()
        self.endResetModel()

    def append_rows(self, rows: list[EstimateHistoryRow]) -> None:
        column = self._sort_column
        insert_model_rows(
            self,
            self._rows,
            list(rows or []),
            key=(lambda row: self._sort_key_for_row(row, column))
            if column is not None
            else None,
            reverse=self._sort_order == Qt.SortOrder.DescendingOrder,
        )

    def row_payload(self, row: int) -> EstimateHistoryRow | None:
        if 0 <= row < len(self._rows):
            return self._rows[row]
        return None

    def _display_value(self, row: EstimateHistoryRow, column: int) -> str:
        if column == 0:
            return row.voucher_no
        if column == 1:
            return format_display_date(row.date)
        if column == 2:
            return row.note
        if column == 3:
            return format_rupees(row.silver_rate)
        if column == 4:
            return format_indian_number(row.total_gross, WEIGHT_PLACES)
        if column == 5:
            return format_indian_number(row.total_net, WEIGHT_PLACES)
        if column == 6:
            return format_indian_number(row.net_fine, WEIGHT_PLACES)
        if column == 7:
            return format_rupees(row.net_wage)
        if column == 8:
            return format_rupees(row.grand_total)
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
        reverse = self._sort_order == Qt.SortOrder.DescendingOrder
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
        if column == 0:
            try:
                return (0, int(row.voucher_no), row.voucher_no)
            except ValueError:
                return (1, value, row.voucher_no)
        return (value is None, value)


__all__ = ["EstimateHistoryRow", "EstimateHistoryTableModel"]
