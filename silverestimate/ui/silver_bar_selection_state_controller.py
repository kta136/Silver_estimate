"""Selection and button-state bookkeeping for silver-bar management."""

from __future__ import annotations

from PyQt5.QtCore import Qt

from ._host_proxy import HostProxy


class SilverBarSelectionStateController(HostProxy):
    """Keep selection summaries and transfer button state in sync."""

    def _update_transfer_buttons_state(self):
        try:
            list_selected = self.current_list_id is not None
            available_selection = self.available_bars_table.selectionModel()
            list_selection = self.list_bars_table.selectionModel()
            has_available_selection = bool(
                available_selection and available_selection.selectedRows()
            )
            has_list_selection = bool(list_selection and list_selection.selectedRows())

            if hasattr(self, "add_to_list_button"):
                self.add_to_list_button.setEnabled(
                    list_selected and has_available_selection
                )
            if hasattr(self, "remove_from_list_button"):
                self.remove_from_list_button.setEnabled(
                    list_selected and has_list_selection
                )
            if hasattr(self, "add_all_button"):
                self.add_all_button.setEnabled(
                    list_selected and self.available_bars_table.model().rowCount() > 0
                )
            if hasattr(self, "remove_all_button"):
                self.remove_all_button.setEnabled(
                    list_selected and self.list_bars_table.model().rowCount() > 0
                )
        except Exception as exc:
            self.logger.debug("Failed to update transfer button state: %s", exc)

    def _on_selection_changed(self, *args, **kwargs):
        del args, kwargs
        try:
            self._update_transfer_buttons_state()
            self._update_selection_summaries()
        except Exception as exc:
            self.logger.debug("Failed to refresh selection summaries: %s", exc)

    def _update_selection_summaries(self):
        try:
            available_count, available_weight, available_fine = (
                self._selection_totals_for_table(self.available_bars_table)
            )
            list_count, list_weight, list_fine = self._selection_totals_for_table(
                self.list_bars_table
            )
            if hasattr(self, "available_selection_label"):
                self.available_selection_label.setText(
                    f"Selected: {available_count} | Weight: {available_weight:.3f} g | Fine: {available_fine:.3f} g"
                )
            if hasattr(self, "list_selection_label"):
                self.list_selection_label.setText(
                    f"Selected: {list_count} | Weight: {list_weight:.3f} g | Fine: {list_fine:.3f} g"
                )
        except Exception as exc:
            self.logger.debug("Failed to update selection summary labels: %s", exc)

    def _selection_totals_for_table(self, table):
        selection_model = table.selectionModel()
        selected = selection_model.selectedRows() if selection_model else []
        count = len(selected)
        weight_sum = 0.0
        fine_sum = 0.0
        for index in selected:
            row = index.row()
            try:
                weight_val = self._table_cell_value(table, row, 1, Qt.EditRole)
                fine_val = self._table_cell_value(table, row, 3, Qt.EditRole)
                weight_sum += float(weight_val or 0.0)
                fine_sum += float(fine_val or 0.0)
            except (TypeError, ValueError):
                continue
        return count, weight_sum, fine_sum
