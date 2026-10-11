"""Weight-first rows for keyboard suggestions and the current list."""

from typing import Any

from PySide6.QtCore import Qt

from silverestimate.domain.numeric_policy import fixed_decimal
from silverestimate.ui.models.silver_bar_table_models import _BaseSilverBarTableModel


class SilverBarEntryModel(_BaseSilverBarTableModel):
    HEADERS = [
        "Weight (g)",
        "Purity (%)",
        "Fine (g)",
        "Voucher / note",
        "Bar #",
    ]
    KEYS = ["weight", "purity", "fine_weight", "estimate_voucher_no", "bar_id"]

    def value_key(self, column: int) -> str:
        return self.KEYS[column]

    def display_value(self, row: int, column: int) -> str:
        bar = self.row_payload(row)
        if bar is None:
            return ""
        if column < 3:
            return fixed_decimal(bar[self.KEYS[column]], 2)
        if column == 3:
            note = str(bar.get("estimate_note") or "")
            return str(bar["estimate_voucher_no"]) + (f" · {note}" if note else "")
        return str(bar["bar_id"])

    def tooltip_value(self, row: int, column: int) -> str:
        return self.display_value(row, column)

    def text_alignment(self, column: int) -> Qt.AlignmentFlag:
        horizontal = (
            Qt.AlignmentFlag.AlignLeft if column == 3 else Qt.AlignmentFlag.AlignRight
        )
        return horizontal | Qt.AlignmentFlag.AlignVCenter

    def sort_key_value(self, row: dict[str, Any], column: int) -> Any:
        return row.get(self.KEYS[column])
