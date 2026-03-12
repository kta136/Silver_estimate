"""Model/view table models for silver-bar management and history."""

from __future__ import annotations

from typing import Any, Optional

from PyQt5.QtCore import QAbstractTableModel, QModelIndex, Qt
from PyQt5.QtGui import QBrush, QColor


class _BaseSilverBarTableModel(QAbstractTableModel):
    HEADERS: list[str] = []

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._rows: list[dict[str, Any]] = []
        self._total_count = 0
        self._sort_column: Optional[int] = None
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
            return self.display_value(index.row(), index.column())
        if role == Qt.EditRole:
            return self.sort_value(index.row(), index.column())
        if role == Qt.TextAlignmentRole:
            return self.text_alignment(index.column())
        if role == Qt.BackgroundRole:
            return self.background_brush(index.row())
        return None

    def sort(self, column: int, order: Qt.SortOrder = Qt.AscendingOrder) -> None:
        if not (0 <= column < self.columnCount()):
            return
        self.layoutAboutToBeChanged.emit()
        self._sort_column = int(column)
        self._sort_order = order
        reverse = order == Qt.DescendingOrder
        self._rows.sort(
            key=lambda row: self.sort_key_for_row(row, column), reverse=reverse
        )
        self.layoutChanged.emit()

    def set_rows(
        self, rows: list[dict[str, Any]], total_count: int | None = None
    ) -> None:
        self.beginResetModel()
        self._rows = [dict(row) for row in list(rows or [])]
        self._total_count = (
            int(total_count)
            if isinstance(total_count, int) and total_count >= 0
            else len(self._rows)
        )
        if self._sort_column is not None and self._rows:
            reverse = self._sort_order == Qt.DescendingOrder
            self._rows.sort(
                key=lambda row: self.sort_key_for_row(row, self._sort_column or 0),
                reverse=reverse,
            )
        self.endResetModel()

    def total_count(self) -> int:
        return self._total_count

    def loaded_count(self) -> int:
        return len(self._rows)

    def clear_rows(self) -> None:
        self.set_rows([], total_count=0)

    def row_payload(self, row: int) -> Optional[dict[str, Any]]:
        if 0 <= row < len(self._rows):
            return self._rows[row]
        return None

    def bar_id_at(self, row: int) -> Optional[int]:
        payload = self.row_payload(row)
        if not payload:
            return None
        try:
            value = payload.get("bar_id")
            return int(value) if value is not None else None
        except (TypeError, ValueError):
            return None

    def display_value(self, row: int, column: int) -> str:
        value = self.sort_value(row, column)
        if value is None:
            return ""
        return str(value)

    def sort_value(self, row: int, column: int) -> Any:
        payload = self.row_payload(row)
        if payload is None:
            return None
        return payload.get(self.value_key(column))

    def sort_key_for_row(self, row: dict[str, Any], column: int) -> tuple[Any, ...]:
        value = self.sort_key_value(row, column)
        return (value is None, value)

    def sort_key_value(self, row: dict[str, Any], column: int) -> Any:
        key = self.value_key(column)
        value = row.get(key)
        if isinstance(value, str):
            return value.casefold()
        return value

    def value_key(self, column: int) -> str:
        raise NotImplementedError

    def text_alignment(self, column: int) -> Optional[int]:
        del column
        return None

    def background_brush(self, row: int) -> Optional[QBrush]:
        del row
        return None

    def total_weight(self) -> float:
        return self._sum_numeric_field("weight")

    def total_fine_weight(self) -> float:
        return self._sum_numeric_field("fine_weight")

    @staticmethod
    def _format_float(value: Any, places: int) -> str:
        try:
            return f"{float(value or 0.0):.{places}f}"
        except (TypeError, ValueError):
            return f"{0.0:.{places}f}"

    @staticmethod
    def _bar_id_sort_value(row: dict[str, Any]) -> int:
        try:
            return int(row.get("bar_id") or 0)
        except (TypeError, ValueError):
            return 0

    @staticmethod
    def _voucher_sort_value(row: dict[str, Any]) -> tuple[int, Any, str]:
        voucher_no = str(row.get("estimate_voucher_no") or "").strip()
        if not voucher_no:
            return (2, "", "")
        try:
            return (0, int(voucher_no), voucher_no.casefold())
        except (TypeError, ValueError):
            return (1, voucher_no.casefold(), voucher_no.casefold())

    @staticmethod
    def _status_brush(status: str | None) -> Optional[QBrush]:
        normalized = str(status or "").strip()
        if normalized == "In Stock":
            return QBrush(QColor("#f0f9f0"))
        if normalized == "Assigned":
            return QBrush(QColor("#f0f4f8"))
        if normalized == "Issued":
            return QBrush(QColor("#fdf2f2"))
        if normalized == "Sold":
            return QBrush(QColor("#f7f0ff"))
        return None

    def _sum_numeric_field(self, key: str) -> float:
        total = 0.0
        for row in self._rows:
            try:
                total += float(row.get(key) or 0.0)
            except (TypeError, ValueError):
                continue
        return total


class _ManagementSilverBarsTableModel(_BaseSilverBarTableModel):
    HEADERS = [
        "Voucher/Note",
        "Weight (g)",
        "Purity (%)",
        "Fine Wt (g)",
        "Date Added",
        "Status",
    ]

    def value_key(self, column: int) -> str:
        mapping = {
            0: "voucher_display",
            1: "weight",
            2: "purity",
            3: "fine_weight",
            4: "date_added",
            5: "status",
        }
        return mapping.get(column, "")

    def display_value(self, row: int, column: int) -> str:
        payload = self.row_payload(row)
        if payload is None:
            return ""
        if column == 0:
            voucher_no = payload.get("estimate_voucher_no") or "N/A"
            note = payload.get("estimate_note") or ""
            return f"{voucher_no} ({note})" if note else str(voucher_no)
        if column == 1:
            return self._format_float(payload.get("weight"), 3)
        if column == 2:
            return self._format_float(payload.get("purity"), 2)
        if column == 3:
            return self._format_float(payload.get("fine_weight"), 3)
        if column == 4:
            return str(payload.get("date_added") or "")
        if column == 5:
            return str(payload.get("status") or "")
        return ""

    def sort_key_value(self, row: dict[str, Any], column: int) -> Any:
        if column == 0:
            return self._voucher_sort_value(row)
        if column in (1, 2, 3):
            try:
                return float(row.get(self.value_key(column)) or 0.0)
            except (TypeError, ValueError):
                return 0.0
        if column == 4:
            return str(row.get("date_added") or "")
        if column == 5:
            return str(row.get("status") or "").casefold()
        return super().sort_key_value(row, column)

    def sort_key_for_row(self, row: dict[str, Any], column: int) -> tuple[Any, ...]:
        if column == 0:
            return (*self._voucher_sort_value(row), self._bar_id_sort_value(row))
        primary = self.sort_key_value(row, column)
        if column == 4:
            return (primary is None, primary, self._bar_id_sort_value(row))
        return (primary is None, primary)

    def text_alignment(self, column: int) -> Optional[int]:
        if column in (1, 2, 3):
            return int(Qt.AlignRight | Qt.AlignVCenter)
        return None

    def background_brush(self, row: int) -> Optional[QBrush]:
        payload = self.row_payload(row)
        if payload is None:
            return None
        return self._status_brush(payload.get("status"))

    def display_value_from_row(self, row: dict[str, Any], column: int) -> str:
        if column == 0:
            voucher_no = row.get("estimate_voucher_no") or "N/A"
            note = row.get("estimate_note") or ""
            return f"{voucher_no} ({note})" if note else str(voucher_no)
        if column == 1:
            return self._format_float(row.get("weight"), 3)
        if column == 2:
            return self._format_float(row.get("purity"), 2)
        if column == 3:
            return self._format_float(row.get("fine_weight"), 3)
        if column == 4:
            return str(row.get("date_added") or "")
        if column == 5:
            return str(row.get("status") or "")
        return ""


class AvailableSilverBarsTableModel(_ManagementSilverBarsTableModel):
    """Model for the available bars pane in silver-bar management."""


class SelectedListSilverBarsTableModel(_ManagementSilverBarsTableModel):
    """Model for the selected-list bars pane in silver-bar management."""


class HistorySilverBarsTableModel(_BaseSilverBarTableModel):
    HEADERS = [
        "Bar ID",
        "Voucher/Note",
        "Weight (g)",
        "Purity (%)",
        "Fine Wt (g)",
        "Status",
        "List",
        "Date Added",
        "List Status",
    ]

    def value_key(self, column: int) -> str:
        mapping = {
            0: "bar_id",
            1: "voucher_display",
            2: "weight",
            3: "purity",
            4: "fine_weight",
            5: "status",
            6: "list_display",
            7: "date_added",
            8: "list_status",
        }
        return mapping.get(column, "")

    def display_value(self, row: int, column: int) -> str:
        payload = self.row_payload(row)
        if payload is None:
            return ""
        if column == 0:
            return str(payload.get("bar_id") or "")
        if column == 1:
            voucher_no = payload.get("estimate_voucher_no") or "N/A"
            note = payload.get("estimate_note") or ""
            return f"{voucher_no} ({note})" if note else str(voucher_no)
        if column == 2:
            return self._format_float(payload.get("weight"), 1)
        if column == 3:
            return self._format_float(payload.get("purity"), 1)
        if column == 4:
            return self._format_float(payload.get("fine_weight"), 1)
        if column == 5:
            return str(payload.get("status") or "Unknown")
        if column == 6:
            if payload.get("list_id"):
                return str(
                    payload.get("list_identifier") or f"List {payload['list_id']}"
                )
            return "None"
        if column == 7:
            return str(payload.get("date_added") or "")
        if column == 8:
            if payload.get("list_id"):
                return "Issued" if payload.get("issued_date") else "Active"
            return "N/A"
        return ""

    def sort_key_value(self, row: dict[str, Any], column: int) -> Any:
        if column == 0:
            try:
                return int(row.get("bar_id") or 0)
            except (TypeError, ValueError):
                return 0
        if column == 1:
            return self._voucher_sort_value(row)
        if column in (2, 3, 4):
            try:
                return float(row.get(self.value_key(column)) or 0.0)
            except (TypeError, ValueError):
                return 0.0
        return self.display_value_from_row(row, column).casefold()

    def sort_key_for_row(self, row: dict[str, Any], column: int) -> tuple[Any, ...]:
        if column == 1:
            return (*self._voucher_sort_value(row), self._bar_id_sort_value(row))
        primary = self.sort_key_value(row, column)
        if column == 7:
            return (primary is None, primary, self._bar_id_sort_value(row))
        return (primary is None, primary)

    def text_alignment(self, column: int) -> Optional[int]:
        if column in (0, 2, 3, 4):
            return int(Qt.AlignRight | Qt.AlignVCenter)
        return None

    def background_brush(self, row: int) -> Optional[QBrush]:
        payload = self.row_payload(row)
        if payload is None:
            return None
        return self._status_brush(payload.get("status"))

    def display_value_from_row(self, row: dict[str, Any], column: int) -> str:
        if column == 0:
            return str(row.get("bar_id") or "")
        if column == 1:
            voucher_no = row.get("estimate_voucher_no") or "N/A"
            note = row.get("estimate_note") or ""
            return f"{voucher_no} ({note})" if note else str(voucher_no)
        if column == 2:
            return self._format_float(row.get("weight"), 1)
        if column == 3:
            return self._format_float(row.get("purity"), 1)
        if column == 4:
            return self._format_float(row.get("fine_weight"), 1)
        if column == 5:
            return str(row.get("status") or "Unknown")
        if column == 6:
            if row.get("list_id"):
                return str(row.get("list_identifier") or f"List {row['list_id']}")
            return "None"
        if column == 7:
            return str(row.get("date_added") or "")
        if column == 8:
            if row.get("list_id"):
                return "Issued" if row.get("issued_date") else "Active"
            return "N/A"
        return ""


class IssuedSilverBarListsTableModel(_BaseSilverBarTableModel):
    HEADERS = ["List ID", "Identifier", "Note", "Created", "Issued", "Bar Count"]

    def value_key(self, column: int) -> str:
        mapping = {
            0: "list_id",
            1: "list_identifier",
            2: "list_note",
            3: "creation_date",
            4: "issued_date",
            5: "bar_count",
        }
        return mapping.get(column, "")

    def display_value(self, row: int, column: int) -> str:
        payload = self.row_payload(row)
        if payload is None:
            return ""
        if column == 0:
            return str(payload.get("list_id") or "")
        if column == 5:
            return str(payload.get("bar_count") or 0)
        return str(payload.get(self.value_key(column)) or "")

    def sort_key_value(self, row: dict[str, Any], column: int) -> Any:
        if column in (0, 5):
            try:
                return int(row.get(self.value_key(column)) or 0)
            except (TypeError, ValueError):
                return 0
        return str(row.get(self.value_key(column)) or "").casefold()

    def text_alignment(self, column: int) -> Optional[int]:
        if column in (0, 5):
            return int(Qt.AlignCenter | Qt.AlignVCenter)
        return None


class HistoryListBarsTableModel(_BaseSilverBarTableModel):
    HEADERS = [
        "Bar ID",
        "Voucher/Note",
        "Weight (g)",
        "Purity (%)",
        "Fine Wt (g)",
        "Status",
        "Date Added",
    ]

    def value_key(self, column: int) -> str:
        mapping = {
            0: "bar_id",
            1: "voucher_display",
            2: "weight",
            3: "purity",
            4: "fine_weight",
            5: "status",
            6: "date_added",
        }
        return mapping.get(column, "")

    def display_value(self, row: int, column: int) -> str:
        payload = self.row_payload(row)
        if payload is None:
            return ""
        if column == 0:
            return str(payload.get("bar_id") or "")
        if column == 1:
            voucher_no = payload.get("estimate_voucher_no") or "N/A"
            note = payload.get("estimate_note") or ""
            return f"{voucher_no} ({note})" if note else str(voucher_no)
        if column == 2:
            return self._format_float(payload.get("weight"), 1)
        if column == 3:
            return self._format_float(payload.get("purity"), 1)
        if column == 4:
            return self._format_float(payload.get("fine_weight"), 1)
        if column == 5:
            return str(payload.get("status") or "Unknown")
        if column == 6:
            return str(payload.get("date_added") or "")
        return ""

    def sort_key_value(self, row: dict[str, Any], column: int) -> Any:
        if column == 0:
            try:
                return int(row.get("bar_id") or 0)
            except (TypeError, ValueError):
                return 0
        if column == 1:
            return self._voucher_sort_value(row)
        if column in (2, 3, 4):
            try:
                return float(row.get(self.value_key(column)) or 0.0)
            except (TypeError, ValueError):
                return 0.0
        return self.display_value_from_row(row, column).casefold()

    def sort_key_for_row(self, row: dict[str, Any], column: int) -> tuple[Any, ...]:
        if column == 1:
            return (*self._voucher_sort_value(row), self._bar_id_sort_value(row))
        primary = self.sort_key_value(row, column)
        if column == 6:
            return (primary is None, primary, self._bar_id_sort_value(row))
        return (primary is None, primary)

    def text_alignment(self, column: int) -> Optional[int]:
        if column in (0, 2, 3, 4):
            return int(Qt.AlignRight | Qt.AlignVCenter)
        return None

    def background_brush(self, row: int) -> Optional[QBrush]:
        payload = self.row_payload(row)
        if payload is None:
            return None
        return self._status_brush(payload.get("status"))

    def display_value_from_row(self, row: dict[str, Any], column: int) -> str:
        if column == 0:
            return str(row.get("bar_id") or "")
        if column == 1:
            voucher_no = row.get("estimate_voucher_no") or "N/A"
            note = row.get("estimate_note") or ""
            return f"{voucher_no} ({note})" if note else str(voucher_no)
        if column == 2:
            return self._format_float(row.get("weight"), 1)
        if column == 3:
            return self._format_float(row.get("purity"), 1)
        if column == 4:
            return self._format_float(row.get("fine_weight"), 1)
        if column == 5:
            return str(row.get("status") or "Unknown")
        if column == 6:
            return str(row.get("date_added") or "")
        return ""
