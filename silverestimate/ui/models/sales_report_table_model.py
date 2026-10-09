"""Sortable weight-only tables for period, item and voucher sales reports."""

from datetime import datetime

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt
from PySide6.QtGui import QColor

from silverestimate.domain.sales_report import ReportLevel, SalesReportRow
from silverestimate.ui.display_formatting import format_display_date
from silverestimate.ui.estimate_table_formatting import format_indian_number
from silverestimate.ui.models.table_sorting import sort_model_rows
from silverestimate.ui.theme_tokens import INFO_TEXT, WARNING_TEXT

ZERO_TEXT = "#94a3b8"


def format_day(value: str) -> str:
    """Return ``Fri 09/10/2026`` for an ISO date, or the plain display date."""
    try:
        day = datetime.strptime(str(value)[:10], "%Y-%m-%d")
    except ValueError:
        return format_display_date(value)
    return f"{day:%a} {day:%d/%m/%Y}"


def format_period(key: str) -> str:
    """Return a day (``Fri 09/10/2026``) or month (``October 2026``) label."""
    if len(key) == 10:
        return format_day(key)
    try:
        return datetime.strptime(key + "-01", "%Y-%m-%d").strftime("%B %Y")
    except ValueError:
        return key


class SalesReportTableModel(QAbstractTableModel):
    WEIGHT_HEADERS = (
        "Sale\nNet (g)",
        "Sale\nFine (g)",
        "Return\nNet (g)",
        "Return\nFine (g)",
    )

    def __init__(self, parent=None):
        super().__init__(parent)
        self.rows: list[SalesReportRow] = []
        self.level: ReportLevel = "period"
        self._headers: tuple[str, ...] = ("Date", *self.WEIGHT_HEADERS)

    def set_report(self, level: ReportLevel, rows: tuple[SalesReportRow, ...]) -> None:
        self.beginResetModel()
        self.level = level
        self.rows = list(rows)
        labels = {
            "period": ("Date / month",),
            "item": ("Item code", "Item name"),
            "voucher": ("Voucher", "Date"),
        }
        self._headers = (*labels[level], *self.WEIGHT_HEADERS)
        self.endResetModel()

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.rows)

    def columnCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self._headers)

    @property
    def weight_offset(self) -> int:
        return len(self._headers) - 4

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if orientation != Qt.Orientation.Horizontal:
            return None
        if not 0 <= section < len(self._headers):
            return None
        if role == Qt.ItemDataRole.DisplayRole:
            return self._headers[section]
        if role == Qt.ItemDataRole.ForegroundRole and section >= self.weight_offset:
            sale = section - self.weight_offset < 2
            return QColor(INFO_TEXT if sale else WARNING_TEXT)
        if role == Qt.ItemDataRole.TextAlignmentRole and section >= self.weight_offset:
            return Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        return None

    def weight_at(self, row: int, slot: int) -> float:
        """Return one of a row's four weights as a float, for drawing."""
        return float(self.rows[row].weights.values()[slot])

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or not 0 <= index.row() < len(self.rows):
            return None
        row = self.rows[index.row()]
        column = index.column()
        offset = len(self._headers) - 4
        if role == Qt.ItemDataRole.TextAlignmentRole and column >= offset:
            return Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        if role == Qt.ItemDataRole.ForegroundRole and column >= offset:
            zero = not row.weights.values()[column - offset]
            return QColor(ZERO_TEXT) if zero else None
        if role not in (Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.ToolTipRole):
            return None
        if column >= offset:
            return format_indian_number(row.weights.values()[column - offset], 2)
        if column == 1:
            return format_day(row.detail) if self.level == "voucher" else row.detail
        if self.level == "period":
            return format_period(row.key)
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
