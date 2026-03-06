"""Table model for the item selection dialog."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from PyQt5.QtCore import QAbstractTableModel, QModelIndex, Qt
from PyQt5.QtGui import QColor


@dataclass(frozen=True)
class ItemSelectionRecord:
    code: str
    name: str
    purity: float
    wage_type: str
    wage_rate: float
    code_upper: str
    name_upper: str


class ItemSelectionTableModel(QAbstractTableModel):
    """Expose ranked item-selection results through a Qt table model."""

    HEADERS = ["Code", "Name", "Purity"]

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._rows: list[ItemSelectionRecord] = []
        self._query_upper = ""
        self._highlight = QColor(255, 246, 196)

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
        record = self.row_payload(index.row())
        if record is None:
            return None

        if role == Qt.DisplayRole:
            if index.column() == 0:
                return record.code
            if index.column() == 1:
                return record.name
            if index.column() == 2:
                return f"{record.purity:.2f}"
            return None

        if role == Qt.TextAlignmentRole and index.column() == 2:
            return Qt.AlignRight | Qt.AlignVCenter

        if role == Qt.BackgroundRole and self._query_upper:
            if index.column() == 0 and self._query_upper in record.code_upper:
                return self._highlight
            if index.column() == 1 and self._query_upper in record.name_upper:
                return self._highlight

        return None

    def set_rows(self, rows: list[ItemSelectionRecord], *, query: str = "") -> None:
        self.beginResetModel()
        self._rows = list(rows or [])
        self._query_upper = (query or "").strip().upper()
        self.endResetModel()

    def row_payload(self, row: int) -> ItemSelectionRecord | None:
        if 0 <= row < len(self._rows):
            return self._rows[row]
        return None


__all__ = ["ItemSelectionRecord", "ItemSelectionTableModel"]
