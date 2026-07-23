"""Table model for the item master catalog."""

from __future__ import annotations

from typing import Any, cast

from PySide6.QtCore import (
    QAbstractTableModel,
    QModelIndex,
    QPersistentModelIndex,
    Qt,
)


class ItemMasterTableModel(QAbstractTableModel):
    """Expose catalog items to the item-master table view."""

    HEADERS = ["Code", "Name", "Tunch", "Purity (%)", "Wage Type", "Wage Rate"]
    HEADER_TOOLTIPS = [
        "Item Code",
        "Item Name",
        "Optional Tunch text",
        "Default Purity",
        "Default Wage Calc Type",
        "Default Wage Rate",
    ]
    _NUMERIC_COLUMNS = {3, 5}

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._rows: list[dict[str, Any]] = []
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
        if orientation != Qt.Orientation.Horizontal:
            return None
        if not (0 <= section < len(self.HEADERS)):
            return None
        if role == Qt.ItemDataRole.DisplayRole:
            return self.HEADERS[section]
        if role == Qt.ItemDataRole.ToolTipRole:
            return self.HEADER_TOOLTIPS[section]
        return None

    def data(
        self,
        index: QModelIndex | QPersistentModelIndex,
        role: int = Qt.ItemDataRole.DisplayRole,
    ) -> Any:
        if not index.isValid():
            return None
        payload = self.row_payload(index.row())
        if payload is None:
            return None

        if role == Qt.ItemDataRole.DisplayRole:
            return self.display_value(payload, index.column())
        if role == Qt.ItemDataRole.EditRole:
            return self.sort_key_value(payload, index.column())
        if (
            role == Qt.ItemDataRole.TextAlignmentRole
            and index.column() in self._NUMERIC_COLUMNS
        ):
            return Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        return None

    def sort(
        self, column: int, order: Qt.SortOrder = Qt.SortOrder.AscendingOrder
    ) -> None:
        if not (0 <= column < self.columnCount()):
            return
        self.layoutAboutToBeChanged.emit()
        self._sort_column = int(column)
        self._sort_order = order
        self._sort_rows()
        self.layoutChanged.emit()

    def set_rows(self, rows: list[object]) -> None:
        self.beginResetModel()
        self._rows = [self._normalize_row(row) for row in list(rows or [])]
        if self._sort_column is not None and self._rows:
            self._sort_rows()
        self.endResetModel()

    def row_payload(self, row: int) -> dict[str, Any] | None:
        if 0 <= row < len(self._rows):
            return self._rows[row]
        return None

    def display_value(self, payload: dict[str, Any], column: int) -> str:
        key = self._column_key(column)
        value = payload.get(key)
        if value is None:
            return ""
        return str(value)

    def sort_key_value(self, payload: dict[str, Any], column: int) -> Any:
        key = self._column_key(column)
        value = payload.get(key)
        if column in self._NUMERIC_COLUMNS:
            try:
                return float(value or 0.0)
            except TypeError, ValueError:
                return 0.0
        if isinstance(value, str):
            return value.casefold()
        return value

    def _sort_rows(self) -> None:
        if self._sort_column is None:
            return
        reverse = self._sort_order == Qt.SortOrder.DescendingOrder
        self._rows.sort(
            key=lambda row: self._sort_key_for_row(row, self._sort_column or 0),
            reverse=reverse,
        )

    def _sort_key_for_row(
        self, payload: dict[str, Any], column: int
    ) -> tuple[Any, ...]:
        value = self.sort_key_value(payload, column)
        return (value is None, value)

    @staticmethod
    def _column_key(column: int) -> str:
        mapping = {
            0: "code",
            1: "name",
            2: "tunch",
            3: "purity",
            4: "wage_type",
            5: "wage_rate",
        }
        return mapping.get(column, "")

    def _normalize_row(self, row: object) -> dict[str, Any]:
        if hasattr(row, "keys"):
            row_mapping = cast(Any, row)
            keys = getattr(row_mapping, "keys", None)
            if callable(keys):
                available_keys = set(keys())
                required_keys = {"code", "name", "purity", "wage_type", "wage_rate"}
                if required_keys.issubset(available_keys):
                    return {
                        "code": row_mapping["code"],
                        "name": row_mapping["name"],
                        "tunch": (
                            row_mapping["tunch"] if "tunch" in available_keys else None
                        ),
                        "purity": row_mapping["purity"],
                        "wage_type": row_mapping["wage_type"],
                        "wage_rate": row_mapping["wage_rate"],
                    }
        if isinstance(row, dict):
            return {
                "code": row.get("code"),
                "name": row.get("name"),
                "tunch": row.get("tunch"),
                "purity": row.get("purity"),
                "wage_type": row.get("wage_type"),
                "wage_rate": row.get("wage_rate"),
            }
        return {
            "code": "",
            "name": "",
            "tunch": None,
            "purity": 0.0,
            "wage_type": "WT",
            "wage_rate": 0.0,
        }


__all__ = ["ItemMasterTableModel"]
