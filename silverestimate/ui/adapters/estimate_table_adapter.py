from __future__ import annotations

import weakref
from typing import Mapping

from PyQt5 import sip
from PyQt5.QtCore import QTimer
from PyQt5.QtWidgets import QMessageBox

from silverestimate.domain.estimate_models import EstimateLineCategory

from ..estimate_entry_components import EstimateTableView
from ..estimate_entry_logic.constants import (
    COL_CODE,
    COL_ITEM_NAME,
    COL_PIECES,
    COL_PURITY,
    COL_WAGE_RATE,
)


class EstimateTableAdapter:
    """Encapsulate table manipulation for EstimateEntryWidget."""

    def __init__(self, owner, table: EstimateTableView) -> None:
        self._owner = owner
        self._table = table

    @staticmethod
    def _normalize_wage_type(value: object) -> str:
        return "PC" if str(value or "").strip().upper() == "PC" else "WT"

    @staticmethod
    def _safe_focus_owner_code(owner_ref: "weakref.ReferenceType", row: int) -> None:
        owner = owner_ref()
        if owner is None:
            return
        try:
            if sip.isdeleted(owner):
                return
            owner.focus_on_code_column(row)
        except RuntimeError:
            return

    @staticmethod
    def _category_for_mode(owner) -> EstimateLineCategory:
        if getattr(owner, "return_mode", False):
            return EstimateLineCategory.RETURN
        if getattr(owner, "silver_bar_mode", False):
            return EstimateLineCategory.SILVER_BAR
        return EstimateLineCategory.REGULAR

    def _apply_mode_category(self, row: int) -> None:
        self._table.set_row_category(row, self._category_for_mode(self._owner))

    def populate_row(self, row_index: int, item_data: Mapping[str, object]) -> None:
        if row_index < 0 or row_index >= self._table.rowCount():
            return

        table = self._table
        owner = self._owner
        table.blockSignals(True)
        previous_row = getattr(owner, "current_row", -1)
        try:
            canonical_code = (item_data.get("code", "") or "").strip()  # type: ignore[arg-type]
            display_code = canonical_code.upper() if canonical_code else ""

            table.set_cell_text(row_index, COL_CODE, display_code)
            table.set_cell_text(
                row_index,
                COL_ITEM_NAME,
                str(item_data.get("name", "")),  # type: ignore[arg-type]
            )
            table.set_cell_text(
                row_index,
                COL_PURITY,
                str(item_data.get("purity", 0.0)),  # type: ignore[arg-type]
            )
            table.set_cell_text(
                row_index,
                COL_WAGE_RATE,
                str(item_data.get("wage_rate", 0.0)),  # type: ignore[arg-type]
            )

            wage_type = self._normalize_wage_type(item_data.get("wage_type"))
            table.set_row_wage_type(row_index, wage_type)

            current_pieces = table.get_cell_text(row_index, COL_PIECES).strip()
            if wage_type == "WT":
                table.set_cell_text(row_index, COL_PIECES, "0")
            elif not current_pieces or current_pieces == "0":
                table.set_cell_text(row_index, COL_PIECES, "1")

            self._apply_mode_category(row_index)

            owner.current_row = row_index
            owner.calculate_net_weight()
        except Exception as exc:  # pragma: no cover - UI failure reporting
            owner.logger.error(
                "Error populating row %s: %s", row_index + 1, exc, exc_info=True
            )
            QMessageBox.critical(owner, "Error", f"Error populating row: {exc}")
            owner._status(f"Error populating row {row_index + 1}", 4000)
        finally:
            table.blockSignals(False)
            owner.current_row = previous_row

    def add_empty_row(self) -> None:
        table = self._table
        owner = self._owner

        try:
            if table.rowCount() > 0:
                last_row = table.rowCount() - 1
                last_code = table.get_cell_text(last_row, COL_CODE).strip()
                if not last_code:
                    owner_ref = weakref.ref(owner)
                    QTimer.singleShot(
                        0,
                        lambda: self._safe_focus_owner_code(owner_ref, last_row),
                    )
                    return

            owner.processing_cell = True
            row = table.append_empty_row()
            self._apply_mode_category(row)

            owner_ref = weakref.ref(owner)
            QTimer.singleShot(
                50,
                lambda: self._safe_focus_owner_code(owner_ref, row),
            )
        except Exception as exc:  # pragma: no cover
            owner.logger.error("Error adding empty row: %s", exc, exc_info=True)
            owner._status("Unable to add new row", 3500)
        finally:
            owner.processing_cell = False

    def refresh_empty_row_type(self) -> None:
        table = self._table
        owner = self._owner
        owner.logger.debug(
            "EstimateTableAdapter.refresh_empty_row_type rowCount=%s",
            table.rowCount(),
        )
        try:
            category = self._category_for_mode(owner)
            table.blockSignals(True)
            try:
                for row in range(table.rowCount()):
                    if table.get_cell_text(row, COL_CODE).strip():
                        continue
                    table.set_row_category(row, category)
            finally:
                table.blockSignals(False)
        except Exception as exc:  # pragma: no cover
            owner.logger.error(
                "Failed to refresh empty row type: %s", exc, exc_info=True
            )

    def focus_on_empty_row(self, *, update_visuals: bool = False) -> None:
        table = self._table
        owner = self._owner
        empty_row_index = -1
        for row in range(table.rowCount()):
            if not table.get_cell_text(row, COL_CODE).strip():
                empty_row_index = row
                break

        if empty_row_index != -1:
            if update_visuals:
                self.refresh_empty_row_type()
                owner.calculate_totals()
            owner.focus_on_code_column(empty_row_index)
        else:
            self.add_empty_row()
