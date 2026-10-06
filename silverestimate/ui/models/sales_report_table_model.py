"""Sortable weight-only tables for period, item and voucher sales reports."""

from PySide6.QtCore import QAbstractTableModel, QDate, QModelIndex, Qt

from silverestimate.domain.sales_report import ReportLevel, SalesReportRow
from silverestimate.ui.display_formatting import format_display_date
from silverestimate.ui.estimate_table_formatting import format_indian_number
from silverestimate.ui.models.table_sorting import sort_model_rows


class SalesReportTableModel(QAbstractTableModel):
    WEIGHT_HEADERS = (
        "Sale\nNet Wt (g)",
        "Sale\nFine Wt (g)",
        "Return\nNet Wt (g)",
        "Return\nFine Wt (g)",
    )

    def __init__(self, parent=None):
        super().__init__(parent)
        self.rows: list[SalesReportRow] = []
        self.level: ReportLevel = "period"
        self._headers: tuple[str, ...] = ("Date / Month", *self.WEIGHT_HEADERS)

    def set_report(self, level: ReportLevel, rows: tuple[SalesReportRow, ...]) -> None:
        self.beginResetModel()
        self.level = level
        self.rows = list(rows)
        labels = {
            "period": ("Date / Month",),
            "item": ("Item Code", "Item Name"),
            "voucher": ("Voucher No", "Date"),
        }
        self._headers = (*labels[level], *self.WEIGHT_HEADERS)
        self.endResetModel()

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.rows)

    def columnCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self._headers)

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if (
            role == Qt.ItemDataRole.DisplayRole
            and orientation == Qt.Orientation.Horizontal
        ):
            return self._headers[section] if 0 <= section < len(self._headers) else None
        return None

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or not 0 <= index.row() < len(self.rows):
            return None
        row = self.rows[index.row()]
        column = index.column()
        offset = len(self._headers) - 4
        if role == Qt.ItemDataRole.TextAlignmentRole and column >= offset:
            return Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        if role not in (Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.ToolTipRole):
            return None
        if column >= offset:
            return format_indian_number(row.weights.values()[column - offset], 2)
        if column == 1:
            return (
                format_display_date(row.detail)
                if self.level == "voucher"
                else row.detail
            )
        if self.level == "period":
            return (
                format_display_date(row.key)
                if len(row.key) == 10
                else QDate.fromString(row.key + "-01", "yyyy-MM-dd").toString(
                    "MMM yyyy"
                )
            )
        return row.key or "(No item code)"

    def sort(self, column, order=Qt.SortOrder.AscendingOrder):
        if not 0 <= column < len(self._headers):
            return
        offset = len(self._headers) - 4

        def key(row):
            if column >= offset:
                return row.weights.values()[column - offset]
            return row.key if column == 0 else row.detail

        sort_model_rows(
            self, self.rows, key=key, reverse=order == Qt.SortOrder.DescendingOrder
        )
