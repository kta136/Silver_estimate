"""Compact saved-list and inventory views for the unified history window."""

from typing import Any

from PySide6.QtCore import Qt

from silverestimate.domain.numeric_policy import fixed_decimal

from .silver_bar_table_models import (
    HistorySilverBarsTableModel,
    _BaseSilverBarTableModel,
)


class SilverBarHistoryModel(HistorySilverBarsTableModel):
    HEADERS = [
        "Bar #",
        "Voucher / note",
        "Weight (g)",
        "Purity (%)",
        "Fine (g)",
        "Status",
        "List",
        "Added",
    ]

    def background_brush(self, row: int):
        # The status column draws a coloured label, so rows stay plain.
        return None

    def display_value(self, row: int, column: int) -> str:
        payload = self.row_payload(row)
        if payload and column == 3:
            return fixed_decimal(payload.get("purity", 0), 2)
        text = super().display_value(row, column)
        if column == 5:
            return {"In Stock": "Available", "Assigned": "In active list"}.get(
                text, text
            )
        return text

    def tooltip_value(self, row: int, column: int) -> str:
        if column == 5:
            return self.display_value(row, column)
        return super().tooltip_value(row, column)


class SilverBarListsHistoryModel(_BaseSilverBarTableModel):
    HEADERS = [
        "List",
        "Note",
        "State",
        "Bars",
        "Weight (g)",
        "Fine (g)",
        "Created",
        "Issued",
    ]
    KEYS = [
        "list_identifier",
        "list_note",
        "state",
        "bar_count",
        "weight",
        "fine_weight",
        "creation_date",
        "issued_date",
    ]

    def value_key(self, column: int) -> str:
        return self.KEYS[column]

    def display_value(self, row: int, column: int) -> str:
        payload = self.row_payload(row)
        if payload is None:
            return ""
        if column == 2:
            return "Issued" if payload.get("issued_date") else "Active"
        if column in (4, 5):
            return fixed_decimal(payload.get(self.KEYS[column], 0), 2)
        if column in (6, 7):
            return self._format_date(payload.get(self.KEYS[column])) or "—"
        return str(payload.get(self.KEYS[column]) or (0 if column == 3 else ""))

    def sort_key_value(self, row: dict[str, Any], column: int) -> Any:
        if column in (3, 4, 5):
            return float(row.get(self.KEYS[column]) or 0)
        if column == 2:
            return bool(row.get("issued_date"))
        return str(row.get(self.KEYS[column]) or "").casefold()

    def text_alignment(self, column: int) -> Qt.AlignmentFlag | None:
        if column in (3, 4, 5):
            return Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        return None
