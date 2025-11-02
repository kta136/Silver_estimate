from __future__ import annotations

from typing import Mapping

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import QMessageBox, QTableWidget, QTableWidgetItem

from ..estimate_entry_logic.constants import (
    COL_CODE,
    COL_FINE_WT,
    COL_GROSS,
    COL_ITEM_NAME,
    COL_NET_WT,
    COL_PIECES,
    COL_POLY,
    COL_PURITY,
    COL_TYPE,
    COL_WAGE_AMT,
    COL_WAGE_RATE,
)


class EstimateTableAdapter:
    """Encapsulate table manipulation for EstimateEntryWidget.

    The adapter operates on the `QTableWidget` while delegating callbacks back
    to the owning widget/mixin for calculations and status updates.
    """

    def __init__(self, owner, table: QTableWidget) -> None:
        self._owner = owner
        self._table = table

    # ------------------------------------------------------------------ #
    # Row population helpers
    # ------------------------------------------------------------------ #
    def populate_row(self, row_index: int, item_data: Mapping[str, object]) -> None:
        if row_index < 0 or row_index >= self._table.rowCount():
            return

        table = self._table
        owner = self._owner
        table.blockSignals(True)
        previous_row = getattr(owner, "current_row", -1)
        try:
            non_editable_calc_cols = [COL_NET_WT, COL_WAGE_AMT, COL_FINE_WT, COL_TYPE]
            for col in range(table.columnCount()):
                owner._ensure_cell_exists(
                    row_index,
                    col,
                    editable=(col not in non_editable_calc_cols),
                )

            canonical_code = (item_data.get("code", "") or "").strip()  # type: ignore[arg-type]
            display_code = canonical_code.upper() if canonical_code else ""
            code_item = table.item(row_index, COL_CODE)
            if code_item is not None:
                code_item.setText(display_code)
                code_item.setData(Qt.UserRole, canonical_code or None)

            table.item(row_index, COL_ITEM_NAME).setText(
                str(item_data.get("name", ""))  # type: ignore[arg-type]
            )
            table.item(row_index, COL_PURITY).setText(
                str(item_data.get("purity", 0.0))  # type: ignore[arg-type]
            )
            table.item(row_index, COL_WAGE_RATE).setText(
                str(item_data.get("wage_rate", 0.0))  # type: ignore[arg-type]
            )

            pcs_item = table.item(row_index, COL_PIECES)
            if pcs_item is not None and not pcs_item.text().strip():
                pcs_item.setText("1")

            type_item = table.item(row_index, COL_TYPE)
            owner._update_row_type_visuals_direct(type_item)
            if type_item is not None:
                type_item.setTextAlignment(Qt.AlignCenter)

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
                last_code_item = table.item(last_row, COL_CODE)
                if not last_code_item or not last_code_item.text().strip():
                    QTimer.singleShot(0, lambda: owner.focus_on_code_column(last_row))
                    return

            owner.processing_cell = True
            row = table.rowCount()
            table.insertRow(row)

            for col in range(table.columnCount()):
                item = QTableWidgetItem("")
                if col in [COL_NET_WT, COL_WAGE_AMT, COL_FINE_WT]:
                    item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                elif col == COL_TYPE:
                    owner._update_row_type_visuals_direct(item)
                    item.setTextAlignment(Qt.AlignCenter)
                    item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                else:
                    item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsEditable)
                table.setItem(row, col, item)

            QTimer.singleShot(50, lambda: owner.focus_on_code_column(row))
        except Exception as exc:  # pragma: no cover
            owner.logger.error("Error adding empty row: %s", exc, exc_info=True)
            owner._status("Unable to add new row", 3500)
        finally:
            owner.processing_cell = False

    # ------------------------------------------------------------------ #
    # Mode / visuals helpers
    # ------------------------------------------------------------------ #
    def refresh_empty_row_type(self) -> None:
        table = self._table
        owner = self._owner
        owner.logger.info(f"EstimateTableAdapter.refresh_empty_row_type() called, rowCount={table.rowCount()}")
        try:
            for row in range(table.rowCount()):
                code_item = table.item(row, COL_CODE)
                code_text = code_item.text() if code_item else ""
                owner.logger.info(f"Row {row}: code='{code_text}'")
                if code_item and code_item.text().strip():
                    owner.logger.info(f"Row {row} has code, skipping")
                    continue
                owner.logger.info(f"Row {row} is empty, updating type")
                type_item = table.item(row, COL_TYPE)
                owner.logger.info(f"Got type_item: {type_item}, type={type(type_item).__name__ if type_item else 'None'}")
                if type_item is None:
                    owner.logger.info("type_item is None, creating new QTableWidgetItem")
                    type_item = QTableWidgetItem("")
                    type_item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
                    table.setItem(row, COL_TYPE, type_item)
                table.blockSignals(True)
                try:
                    owner.logger.info(f"Calling owner._update_row_type_visuals_direct()")
                    owner._update_row_type_visuals_direct(type_item)
                    type_item.setTextAlignment(Qt.AlignCenter)
                finally:
                    table.blockSignals(False)
        except Exception as exc:  # pragma: no cover
            owner.logger.error(f"Failed to refresh empty row type: {exc}", exc_info=True)

    def focus_on_empty_row(self, *, update_visuals: bool = False) -> None:
        table = self._table
        owner = self._owner
        empty_row_index = -1
        for row in range(table.rowCount()):
            code_item = table.item(row, COL_CODE)
            if not code_item or not code_item.text().strip():
                empty_row_index = row
                break

        if empty_row_index != -1:
            if update_visuals:
                self.refresh_empty_row_type()
                owner.calculate_totals()
            owner.focus_on_code_column(empty_row_index)
        else:
            self.add_empty_row()
