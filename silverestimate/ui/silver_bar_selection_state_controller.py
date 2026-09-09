"""Selection and button-state bookkeeping for silver-bar management."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from PySide6.QtCore import Qt

from silverestimate.domain.numeric_policy import WEIGHT_PLACES, fixed_decimal

if TYPE_CHECKING:
    from .silver_bar_management import SilverBarDialog


class SilverBarSelectionStateController:
    """Keep selection summaries and transfer button state in sync."""

    def __init__(self, host: SilverBarDialog) -> None:
        self.host = host

    def _update_transfer_buttons_state(self) -> None:
        try:
            list_selected = self.host.current_list_id is not None
            available_selection = self.host.available_bars_table.selectionModel()
            list_selection = self.host.list_bars_table.selectionModel()
            has_available_selection = bool(
                available_selection and available_selection.selectedRows()
            )
            has_list_selection = bool(list_selection and list_selection.selectedRows())

            if hasattr(self.host, "add_to_list_button"):
                self.host.add_to_list_button.setEnabled(
                    list_selected and has_available_selection
                )
            if hasattr(self.host, "remove_from_list_button"):
                self.host.remove_from_list_button.setEnabled(
                    list_selected and has_list_selection
                )
            if hasattr(self.host, "add_all_button"):
                self.host.add_all_button.setEnabled(
                    list_selected
                    and self.host.available_bars_table.model().rowCount() > 0
                )
            if hasattr(self.host, "remove_all_button"):
                self.host.remove_all_button.setEnabled(
                    list_selected and self.host.list_bars_table.model().rowCount() > 0
                )
        except Exception as exc:
            self.host.logger.debug("Failed to update transfer button state: %s", exc)

    def _on_selection_changed(self, *args, **kwargs) -> None:
        del args, kwargs
        try:
            self._update_transfer_buttons_state()
            self._update_selection_summaries()
        except Exception as exc:
            self.host.logger.debug("Failed to refresh selection summaries: %s", exc)

    def _update_selection_summaries(self) -> None:
        try:
            available_count, available_weight, available_fine = (
                self._selection_totals_for_table(self.host.available_bars_table)
            )
            list_count, list_weight, list_fine = self._selection_totals_for_table(
                self.host.list_bars_table
            )
            if hasattr(self.host, "available_selection_label"):
                self.host.available_selection_label.setText(
                    f"Selected: {available_count} | Weight: {fixed_decimal(available_weight, WEIGHT_PLACES)} g | Fine: {fixed_decimal(available_fine, WEIGHT_PLACES)} g"
                )
            if hasattr(self.host, "list_selection_label"):
                self.host.list_selection_label.setText(
                    f"Selected: {list_count} | Weight: {fixed_decimal(list_weight, WEIGHT_PLACES)} g | Fine: {fixed_decimal(list_fine, WEIGHT_PLACES)} g"
                )
        except Exception as exc:
            self.host.logger.debug("Failed to update selection summary labels: %s", exc)

    def _selection_totals_for_table(self, table) -> Any:
        selection_model = table.selectionModel()
        selected = selection_model.selectedRows() if selection_model else []
        count = len(selected)
        weight_sum = 0.0
        fine_sum = 0.0
        for index in selected:
            row = index.row()
            try:
                weight_val = self.host._table_cell_value(
                    table, row, 1, Qt.ItemDataRole.EditRole
                )
                fine_val = self.host._table_cell_value(
                    table, row, 3, Qt.ItemDataRole.EditRole
                )
                weight_sum += float(weight_val or 0.0)
                fine_sum += float(fine_val or 0.0)
            except TypeError, ValueError:
                continue
        return count, weight_sum, fine_sum
