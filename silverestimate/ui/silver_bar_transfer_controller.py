"""Transfer and export workflows for silver-bar management."""

from __future__ import annotations

import csv

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QApplication, QFileDialog, QMessageBox

from ._host_proxy import HostProxy


class SilverBarTransferController(HostProxy):
    """Handle moving bars between lists and exporting list contents."""

    def _bulk_assign_to_list(self, bar_ids, list_id):
        assign_bulk = getattr(self.db_manager, "assign_bars_to_list_bulk", None)
        if callable(assign_bulk):
            added, failed_ids = assign_bulk(bar_ids, list_id)
            return int(added or 0), [str(bar_id) for bar_id in (failed_ids or [])]

        added = 0
        failed = []
        for bar_id in list(bar_ids or []):
            if self.db_manager.assign_bar_to_list(bar_id, list_id):
                added += 1
            else:
                failed.append(str(bar_id))
        return added, failed

    def _bulk_remove_from_list(self, bar_ids):
        remove_bulk = getattr(self.db_manager, "remove_bars_from_list_bulk", None)
        if callable(remove_bulk):
            removed, failed_ids = remove_bulk(bar_ids)
            return int(removed or 0), [str(bar_id) for bar_id in (failed_ids or [])]

        removed = 0
        failed = []
        for bar_id in list(bar_ids or []):
            if self.db_manager.remove_bar_from_list(bar_id):
                removed += 1
            else:
                failed.append(str(bar_id))
        return removed, failed

    def add_selected_to_list(self):
        if self.current_list_id is None:
            QMessageBox.warning(
                self.host,
                "Selection Error",
                "Please select a list first.",
            )
            return

        selected_rows = self._selected_rows(self.available_bars_table)
        if not selected_rows:
            QMessageBox.warning(
                self.host,
                "Selection Error",
                "Please select one or more available bars to add.",
            )
            return

        bar_ids_to_add = self._bar_ids_from_indexes(
            self.available_bars_table,
            selected_rows,
        )
        if not bar_ids_to_add:
            QMessageBox.warning(
                self.host,
                "Error",
                "Could not get IDs for selected bars.",
            )
            return

        reply = QMessageBox.question(
            self.host,
            "Confirm Add",
            f"Add {len(bar_ids_to_add)} selected bar(s) to list '{self.list_combo.currentText()}'?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return

        added_count, failed_ids = self._run_with_wait_cursor(
            lambda: self._bulk_assign_to_list(bar_ids_to_add, self.current_list_id),
            enable_log="Could not enable wait cursor while adding bars: %s",
            restore_log="Could not restore cursor after adding bars: %s",
        )
        self._show_transfer_result(
            added_count,
            failed_ids,
            success_message=f"{added_count} bar(s) added to the list.",
            failure_prefix="Failed to add bars with IDs",
        )
        self._refresh_after_transfer()

    def remove_selected_from_list(self):
        if self.current_list_id is None:
            QMessageBox.warning(self.host, "Error", "No list selected.")
            return

        selected_rows = self._selected_rows(self.list_bars_table)
        if not selected_rows:
            QMessageBox.warning(
                self.host,
                "Selection Error",
                "Please select one or more bars from the list to remove.",
            )
            return

        bar_ids_to_remove = self._bar_ids_from_indexes(
            self.list_bars_table, selected_rows
        )
        if not bar_ids_to_remove:
            QMessageBox.warning(
                self.host,
                "Error",
                "Could not get IDs for selected bars.",
            )
            return

        reply = QMessageBox.question(
            self.host,
            "Confirm Remove",
            f"Remove {len(bar_ids_to_remove)} selected bar(s) from list '{self.list_combo.currentText()}'?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return

        removed_count, failed_ids = self._run_with_wait_cursor(
            lambda: self._bulk_remove_from_list(bar_ids_to_remove),
            enable_log="Could not enable wait cursor while removing bars: %s",
            restore_log="Could not restore cursor after removing bars: %s",
        )
        self._show_transfer_result(
            removed_count,
            failed_ids,
            success_message=f"{removed_count} bar(s) removed from the list.",
            failure_prefix="Failed to remove bars with IDs",
        )
        self._refresh_after_transfer()

    def add_all_filtered_to_list(self):
        if self.current_list_id is None:
            QMessageBox.warning(
                self.host,
                "Selection Error",
                "Please select a list first.",
            )
            return
        row_count = self.available_bars_table.model().rowCount()
        if row_count == 0:
            QMessageBox.information(self.host, "No Bars", "No available bars to add.")
            return
        reply = QMessageBox.question(
            self.host,
            "Confirm Add All",
            f"Add all {row_count} available bar(s) to list '{self.list_combo.currentText()}'?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return
        bar_ids = self._all_bar_ids(self.available_bars_table)
        added, failed = self._run_with_wait_cursor(
            lambda: self._bulk_assign_to_list(bar_ids, self.current_list_id),
            enable_log="Could not enable wait cursor while adding all bars: %s",
            restore_log="Could not restore cursor after add-all: %s",
        )
        self._refresh_after_transfer()
        self._show_transfer_result(
            added,
            failed,
            success_message=f"{added} bar(s) added to the list.",
            failure_prefix="Failed to add bars",
            partial_title="Partial",
        )

    def remove_all_from_list(self):
        if self.current_list_id is None:
            QMessageBox.warning(
                self.host,
                "Selection Error",
                "Please select a list first.",
            )
            return
        row_count = self.list_bars_table.model().rowCount()
        if row_count == 0:
            QMessageBox.information(
                self.host,
                "No Bars",
                "No bars in the selected list.",
            )
            return
        reply = QMessageBox.warning(
            self.host,
            "Confirm Remove All",
            f"Remove all {row_count} bar(s) from list '{self.list_combo.currentText()}'?\nThis will set their status to 'In Stock'.",
            QMessageBox.Yes | QMessageBox.Cancel,
            QMessageBox.Cancel,
        )
        if reply != QMessageBox.Yes:
            return
        bar_ids = self._all_bar_ids(self.list_bars_table)
        removed, failed = self._run_with_wait_cursor(
            lambda: self._bulk_remove_from_list(bar_ids),
            enable_log="Could not enable wait cursor while removing all bars: %s",
            restore_log="Could not restore cursor after remove-all: %s",
        )
        self._refresh_after_transfer()
        self._show_transfer_result(
            removed,
            failed,
            success_message=f"{removed} bar(s) removed from the list.",
            failure_prefix="Failed to remove bars",
            partial_title="Partial",
        )

    def export_current_list_to_csv(self):
        if self.current_list_id is None:
            QMessageBox.warning(self.host, "Error", "No list selected.")
            return
        path, _ = QFileDialog.getSaveFileName(
            self.host,
            "Export List to CSV",
            "silver_bars.csv",
            "CSV Files (*.csv)",
        )
        if not path:
            return
        try:
            with open(path, "w", newline="", encoding="utf-8") as handle:
                writer = csv.writer(handle)
                writer.writerow(
                    [
                        "bar_id",
                        "estimate_voucher_no",
                        "weight_g",
                        "purity_pct",
                        "fine_weight_g",
                        "date_added",
                        "status",
                    ]
                )
                model = self.list_bars_table.model()
                for row in range(model.rowCount()):
                    output_row = [
                        self._bar_id_from_table(self.list_bars_table, row) or ""
                    ]
                    for column in range(model.columnCount()):
                        output_row.append(
                            self._table_cell_text(self.list_bars_table, row, column)
                        )
                    writer.writerow(output_row)
            QMessageBox.information(
                self.host,
                "Export Complete",
                f"List exported to\n{path}",
            )
        except Exception as exc:
            QMessageBox.critical(
                self.host,
                "Export Error",
                f"Failed to export CSV: {exc}",
            )

    def _selected_rows(self, table):
        selection_model = table.selectionModel()
        return selection_model.selectedRows() if selection_model is not None else []

    def _bar_ids_from_indexes(self, table, indexes):
        bar_ids = []
        for index in indexes:
            bar_id = self._bar_id_from_table(table, index.row())
            if bar_id is not None:
                bar_ids.append(bar_id)
        return bar_ids

    def _all_bar_ids(self, table):
        bar_ids = []
        row_count = table.model().rowCount()
        for row in range(row_count):
            bar_id = self._bar_id_from_table(table, row)
            if bar_id is not None:
                bar_ids.append(bar_id)
        return bar_ids

    def _run_with_wait_cursor(self, operation, *, enable_log: str, restore_log: str):
        try:
            QApplication.setOverrideCursor(Qt.WaitCursor)
        except Exception as exc:
            self.logger.debug(enable_log, exc)
        try:
            return operation()
        finally:
            try:
                QApplication.restoreOverrideCursor()
            except Exception as exc:
                self.logger.debug(restore_log, exc)

    def _refresh_after_transfer(self) -> None:
        self.load_available_bars()
        self.load_bars_in_selected_list()
        self._update_transfer_buttons_state()

    def _show_transfer_result(
        self,
        success_count: int,
        failed_ids,
        *,
        success_message: str,
        failure_prefix: str,
        partial_title: str = "Error",
    ) -> None:
        if success_count > 0:
            QMessageBox.information(self.host, "Success", success_message)
        if failed_ids:
            QMessageBox.warning(
                self.host,
                partial_title,
                f"{failure_prefix}: {', '.join(failed_ids)}",
            )
