"""Table model for the item import preview dialog."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from PyQt5.QtCore import QAbstractTableModel, QModelIndex, Qt


@dataclass(frozen=True)
class ItemImportPreviewRow:
    code: str
    name: str
    wage_type: str
    wage_rate: str
    purity: str


class ItemImportPreviewTableModel(QAbstractTableModel):
    """Expose preview rows for the import dialog."""

    HEADERS = ["Item Code", "Item Name", "Wage Type", "Wage Rate", "Purity %"]

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._rows: list[ItemImportPreviewRow] = []

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
        return None

    def set_rows(self, rows: list[ItemImportPreviewRow]) -> None:
        self.beginResetModel()
        self._rows = list(rows or [])
        self.endResetModel()

    def row_payload(self, row: int) -> ItemImportPreviewRow | None:
        if 0 <= row < len(self._rows):
            return self._rows[row]
        return None

    def _display_value(self, row: ItemImportPreviewRow, column: int) -> str:
        if column == 0:
            return row.code
        if column == 1:
            return row.name
        if column == 2:
            return row.wage_type
        if column == 3:
            return row.wage_rate
        if column == 4:
            return row.purity
        return ""


__all__ = ["ItemImportPreviewRow", "ItemImportPreviewTableModel"]
