"""Action/controller layer for silver-bar management."""

from __future__ import annotations

import csv
import logging
import time
import traceback

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QApplication,
    QFileDialog,
    QInputDialog,
    QLineEdit,
    QMenu,
    QMessageBox,
)

from ._host_proxy import HostProxy
from .silver_bar_optimization import find_optimal_combination


class SilverBarListActions(HostProxy):
    """Handle list actions, table updates, context menus, and exports."""

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

    def create_new_list(self):
        logging.getLogger(__name__).info("Creating new list...")
        note, ok = QInputDialog.getText(
            self.host,
            "Create New List",
            "Enter a note for the new list:",
            QLineEdit.Normal,
        )
        if ok:
            new_list_id = self.db_manager.create_silver_bar_list(note if note else None)
            if new_list_id:
                QMessageBox.information(self.host, "Success", "New list created.")
                self.load_lists()
                index = self.list_combo.findData(new_list_id)
                if index >= 0:
                    self.list_combo.setCurrentIndex(index)
            else:
                QMessageBox.critical(self.host, "Error", "Failed to create new list.")

    def _create_list_from_selection(self):
        selected = (
            self.available_bars_table.selectionModel().selectedRows()
            if self.available_bars_table.selectionModel()
            else []
        )
        if not selected:
            QMessageBox.warning(
                self.host, "Selection", "Select one or more available bars first."
            )
            return
        note, ok = QInputDialog.getText(
            self.host,
            "Create List from Selection",
            "Enter a note for the new list:",
            QLineEdit.Normal,
        )
        if not ok:
            return
        new_list_id = self.db_manager.create_silver_bar_list(note if note else None)
        if not new_list_id:
            QMessageBox.critical(self.host, "Error", "Failed to create new list.")
            return
        self.load_lists()
        idx = self.list_combo.findData(new_list_id)
        if idx >= 0:
            self.list_combo.setCurrentIndex(idx)
        bar_ids = []
        for index in selected:
            bar_id = self._bar_id_from_table(self.available_bars_table, index.row())
            if bar_id is not None:
                bar_ids.append(bar_id)
        try:
            QApplication.setOverrideCursor(Qt.WaitCursor)
        except Exception as exc:
            self.logger.debug("Could not enable wait cursor for list creation: %s", exc)
        added_count, failed = self._bulk_assign_to_list(bar_ids, new_list_id)
        try:
            QApplication.restoreOverrideCursor()
        except Exception as exc:
            self.logger.debug("Could not restore cursor after list creation: %s", exc)
        self.load_available_bars()
        self.load_bars_in_selected_list()
        if added_count:
            QMessageBox.information(
                self.host, "Success", f"Created list and added {added_count} bar(s)."
            )
        if failed:
            QMessageBox.warning(
                self.host, "Partial", f"Failed to add bars: {', '.join(failed)}"
            )

    def add_selected_to_list(self):
        if self.current_list_id is None:
            QMessageBox.warning(
                self.host, "Selection Error", "Please select a list first."
            )
            return

        selected_rows = self.available_bars_table.selectionModel().selectedRows()
        if not selected_rows:
            QMessageBox.warning(
                self.host,
                "Selection Error",
                "Please select one or more available bars to add.",
            )
            return

        bar_ids_to_add = []
        for index in selected_rows:
            bar_id = self._bar_id_from_table(self.available_bars_table, index.row())
            if bar_id is not None:
                bar_ids_to_add.append(bar_id)

        if not bar_ids_to_add:
            QMessageBox.warning(
                self.host, "Error", "Could not get IDs for selected bars."
            )
            return

        reply = QMessageBox.question(
            self.host,
            "Confirm Add",
            f"Add {len(bar_ids_to_add)} selected bar(s) to list '{self.list_combo.currentText()}'?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )

        if reply == QMessageBox.Yes:
            try:
                QApplication.setOverrideCursor(Qt.WaitCursor)
            except Exception as exc:
                self.logger.debug(
                    "Could not enable wait cursor while adding bars: %s", exc
                )
            added_count, failed_ids = self._bulk_assign_to_list(
                bar_ids_to_add,
                self.current_list_id,
            )

            if added_count > 0:
                QMessageBox.information(
                    self.host, "Success", f"{added_count} bar(s) added to the list."
                )
            if failed_ids:
                QMessageBox.warning(
                    self.host,
                    "Error",
                    f"Failed to add bars with IDs: {', '.join(failed_ids)}",
                )

            self.load_available_bars()
            self.load_bars_in_selected_list()
            self._update_transfer_buttons_state()
            try:
                QApplication.restoreOverrideCursor()
            except Exception as exc:
                self.logger.debug("Could not restore cursor after adding bars: %s", exc)

    def remove_selected_from_list(self):
        if self.current_list_id is None:
            QMessageBox.warning(self.host, "Error", "No list selected.")
            return

        selected_rows = self.list_bars_table.selectionModel().selectedRows()
        if not selected_rows:
            QMessageBox.warning(
                self.host,
                "Selection Error",
                "Please select one or more bars from the list to remove.",
            )
            return

        bar_ids_to_remove = []
        for index in selected_rows:
            bar_id = self._bar_id_from_table(self.list_bars_table, index.row())
            if bar_id is not None:
                bar_ids_to_remove.append(bar_id)

        if not bar_ids_to_remove:
            QMessageBox.warning(
                self.host, "Error", "Could not get IDs for selected bars."
            )
            return

        reply = QMessageBox.question(
            self.host,
            "Confirm Remove",
            f"Remove {len(bar_ids_to_remove)} selected bar(s) from list '{self.list_combo.currentText()}'?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )

        if reply == QMessageBox.Yes:
            try:
                QApplication.setOverrideCursor(Qt.WaitCursor)
            except Exception as exc:
                self.logger.debug(
                    "Could not enable wait cursor while removing bars: %s", exc
                )
            removed_count, failed_ids = self._bulk_remove_from_list(bar_ids_to_remove)

            if removed_count > 0:
                QMessageBox.information(
                    self.host,
                    "Success",
                    f"{removed_count} bar(s) removed from the list.",
                )
            if failed_ids:
                QMessageBox.warning(
                    self.host,
                    "Error",
                    f"Failed to remove bars with IDs: {', '.join(failed_ids)}",
                )

            self.load_available_bars()
            self.load_bars_in_selected_list()
            self._update_transfer_buttons_state()
            try:
                QApplication.restoreOverrideCursor()
            except Exception as exc:
                self.logger.debug(
                    "Could not restore cursor after removing bars: %s", exc
                )

    def edit_list_note(self):
        if self.current_list_id is None:
            QMessageBox.warning(self.host, "Error", "No list selected.")
            return
        details = self.db_manager.get_silver_bar_list_details(self.current_list_id)
        if not details:
            QMessageBox.warning(
                self.host, "Error", "Could not retrieve current list details."
            )
            return

        current_note = details["list_note"] or ""
        new_note, ok = QInputDialog.getText(
            self.host,
            "Edit List Note",
            f"Enter new note for list '{details['list_identifier']}':",
            QLineEdit.Normal,
            current_note,
        )

        if ok and new_note != current_note:
            if self.db_manager.update_silver_bar_list_note(
                self.current_list_id, new_note
            ):
                QMessageBox.information(self.host, "Success", "List note updated.")
                details_label = getattr(self, "list_details_label", None)
                if details_label is not None:
                    details_label.setText(
                        f"Selected List: {details['list_identifier']} (Note: {new_note or 'N/A'})"
                    )
                index = self.list_combo.findData(self.current_list_id)
                if index >= 0:
                    list_date = (
                        details["creation_date"].split()[0]
                        if "creation_date" in details.keys()
                        and details["creation_date"]
                        else ""
                    )
                    display_text = f"{details['list_identifier']} ({list_date})"
                    if new_note:
                        display_text += f" - {new_note}"
                    self.list_combo.setItemText(index, display_text)
            else:
                QMessageBox.critical(self.host, "Error", "Failed to update list note.")

    def delete_selected_list(self):
        if self.current_list_id is None:
            QMessageBox.warning(self.host, "Error", "No list selected.")
            return
        details = self.db_manager.get_silver_bar_list_details(self.current_list_id)
        list_name = (
            details["list_identifier"] if details else f"ID {self.current_list_id}"
        )

        reply = QMessageBox.warning(
            self.host,
            "Confirm Delete",
            f"Are you sure you want to delete list '{list_name}'?\n"
            "All bars currently assigned to this list will be unassigned (status set to 'In Stock').\n"
            "This action cannot be undone.",
            QMessageBox.Yes | QMessageBox.Cancel,
            QMessageBox.Cancel,
        )

        if reply == QMessageBox.Yes:
            success, message = self.db_manager.delete_silver_bar_list(
                self.current_list_id
            )
            if success:
                QMessageBox.information(
                    self.host, "Success", f"List '{list_name}' deleted successfully."
                )
                self.load_lists()
            else:
                QMessageBox.critical(
                    self.host, "Error", f"Failed to delete list: {message}"
                )

    def mark_list_as_issued(self):
        if self.current_list_id is None:
            QMessageBox.warning(self.host, "Error", "No list selected.")
            return

        details = self.db_manager.get_silver_bar_list_details(self.current_list_id)
        list_name = (
            details["list_identifier"] if details else f"ID {self.current_list_id}"
        )

        reply = QMessageBox.question(
            self.host,
            "Mark as Issued",
            f"Are you sure you want to mark list '{list_name}' as issued?\n\n"
            "This will:\n"
            "• Remove the list from the active lists menu\n"
            "• Move it to Silver Bar History\n"
            "• Set all bars in the list to 'Issued' status\n\n"
            "This action can be reversed from the History window.",
            QMessageBox.Yes | QMessageBox.Cancel,
            QMessageBox.Cancel,
        )

        if reply == QMessageBox.Yes:
            try:
                success = self.db_manager.mark_silver_bar_list_as_issued(
                    self.current_list_id
                )
                if not success:
                    raise RuntimeError("Failed to mark the selected list as issued.")

                QMessageBox.information(
                    self.host,
                    "Success",
                    f"List '{list_name}' has been marked as issued.\n"
                    "It has been moved to Silver Bar History.",
                )

                self.load_lists()
                self.load_available_bars()

            except Exception as exc:
                self.logger.warning(
                    "Failed to mark list %s as issued: %s",
                    self.current_list_id,
                    exc,
                    exc_info=True,
                )
                QMessageBox.critical(
                    self.host, "Error", f"Failed to mark list as issued: {exc}"
                )

    def print_selected_list(self):
        if self.current_list_id is None:
            QMessageBox.warning(self.host, "Error", "No list selected.")
            return
        details = self.db_manager.get_silver_bar_list_details(self.current_list_id)
        if not details:
            QMessageBox.warning(
                self.host, "Error", "Could not retrieve list details for printing."
            )
            return

        bars_in_list = self.db_manager.get_bars_in_list(self.current_list_id)
        logging.getLogger(__name__).info(
            "Printing list %s (ID: %s) with %s bars.",
            details["list_identifier"],
            self.current_list_id,
            len(bars_in_list),
        )

        try:
            from .print_manager import PrintManager

            parent_context = self.host.parent()
            current_print_font = (
                getattr(parent_context, "print_font", None) if parent_context else None
            )

            print_manager = PrintManager(self.db_manager, print_font=current_print_font)
            success = print_manager.print_silver_bar_list_details(
                details, bars_in_list, self.host
            )

            if not success:
                QMessageBox.warning(
                    self.host,
                    "Print Error",
                    "Failed to generate print preview for the list.",
                )

        except ImportError:
            QMessageBox.critical(self.host, "Error", "Could not import PrintManager.")
        except AttributeError as exc:
            QMessageBox.critical(
                self.host,
                "Error",
                f"Print function not found or incorrect in PrintManager: {exc}",
            )
        except Exception as exc:
            QMessageBox.critical(
                self.host,
                "Print Error",
                f"An unexpected error occurred during printing: {exc}\n{traceback.format_exc()}",
            )

    def generate_optimal_list(self, dialog_cls):
        dialog = dialog_cls(self.host)
        if dialog.exec_() != dialog_cls.Accepted:
            return

        min_target = dialog.min_target
        max_target = dialog.max_target
        list_name = dialog.list_name
        optimization_type = dialog.optimization_type

        try:
            available_bars = self.db_manager.get_silver_bars(
                status="In Stock",
                unassigned_only=True,
            )

            if not available_bars:
                QMessageBox.information(
                    self.host,
                    "No Bars Available",
                    "No silver bars are available for list generation.",
                )
                return

            selected_bars = find_optimal_combination(
                available_bars, min_target, max_target, optimization_type
            )

            if not selected_bars:
                QMessageBox.information(
                    self.host,
                    "No Solution",
                    f"Could not find a combination of bars within the range {min_target:.1f}g - {max_target:.1f}g.",
                )
                return

            new_list_id = self.db_manager.create_silver_bar_list(list_name)
            if not new_list_id:
                QMessageBox.critical(self.host, "Error", "Failed to create new list.")
                return

            selected_ids = [bar["bar_id"] for bar in selected_bars]
            added_count, failed_bars = self._bulk_assign_to_list(
                selected_ids,
                new_list_id,
            )

            actual_fine_weight = sum(bar["fine_weight"] for bar in selected_bars)

            message = "Optimal list created successfully!\n\n"
            message += f"List Name: {list_name}\n"
            message += f"Target Range: {min_target:.1f}g - {max_target:.1f}g\n"
            message += f"Actual Fine Weight: {actual_fine_weight:.1f}g\n"
            message += f"Bars Added: {added_count}\n"
            message += (
                "Optimization: Minimum bars"
                if optimization_type == "min_bars"
                else "Optimization: Maximum bars"
            )

            if failed_bars:
                message += (
                    "\n\nWarning: Failed to add "
                    f"{len(failed_bars)} bars: {', '.join(failed_bars)}"
                )

            QMessageBox.information(self.host, "List Generated", message)

            self.load_lists()
            self.load_available_bars()

            index = self.list_combo.findData(new_list_id)
            if index >= 0:
                self.list_combo.setCurrentIndex(index)

        except Exception as exc:
            self.logger.error("Failed to generate optimal list: %s", exc, exc_info=True)
            QMessageBox.critical(
                self.host,
                "Error",
                f"Failed to generate optimal list: {exc}\n{traceback.format_exc()}",
            )

    @staticmethod
    def _table_cell_value(table, row: int, column: int, role: int = Qt.DisplayRole):
        try:
            model = table.model()
            if model is None:
                return None
            index = model.index(row, column)
            if not index.isValid():
                return None
            return model.data(index, role)
        except (AttributeError, RuntimeError, TypeError):
            return None

    @classmethod
    def _table_cell_text(cls, table, row: int, column: int) -> str:
        value = cls._table_cell_value(table, row, column, Qt.DisplayRole)
        return "" if value is None else str(value)

    @staticmethod
    def _bar_id_from_table(table, row: int):
        try:
            model = table.model()
            getter = getattr(model, "bar_id_at", None)
            if callable(getter):
                return getter(row)
        except (AttributeError, RuntimeError, TypeError, ValueError):
            return None
        return None

    def _clear_management_table(self, table) -> None:
        try:
            model = table.model()
            setter = getattr(model, "set_rows", None)
            if callable(setter):
                setter([], total_count=0)
        except Exception as exc:
            self.logger.debug("Could not clear management table: %s", exc)

    def _populate_table(self, table, bars_data, *, total_rows=None):
        start = time.perf_counter()
        total_weight = 0.0
        total_fine_weight = 0.0
        bar_count = 0
        try:
            normalized_rows = [
                dict(bar_row) if not isinstance(bar_row, dict) else dict(bar_row)
                for bar_row in list(bars_data or [])
            ]
            model = table.model()
            setter = getattr(model, "set_rows", None)
            if callable(setter):
                setter(normalized_rows, total_count=total_rows)

            for bar_row in normalized_rows:
                try:
                    total_weight += float(bar_row.get("weight") or 0.0)
                except (TypeError, ValueError):
                    pass
                try:
                    total_fine_weight += float(bar_row.get("fine_weight") or 0.0)
                except (TypeError, ValueError):
                    pass
                bar_count += 1

            loaded_text = f"{bar_count}"
            if isinstance(total_rows, int) and total_rows >= 0:
                loaded_text = f"{bar_count}/{total_rows}"
            totals_text = (
                f"Bars: {bar_count} | Total Weight: {total_weight:.3f} g | "
                f"Total Fine Wt: {total_fine_weight:.3f} g | Loaded: {loaded_text}"
            )
            if table == self.available_bars_table:
                self.available_totals_label.setText(f"Available {totals_text}")
                badge = getattr(self, "available_header_badge", None)
                if badge is not None:
                    badge.setText(f"Available: {bar_count}")
            elif table == self.list_bars_table:
                self.list_totals_label.setText(f"List {totals_text}")
                badge = getattr(self, "list_header_badge", None)
                if badge is not None:
                    badge.setText(f"List: {bar_count}")
        except Exception as exc:
            QMessageBox.critical(
                self.host,
                "Table Error",
                f"Error populating table: {exc}\n{traceback.format_exc()}",
            )
        finally:
            try:
                table.viewport().update()
            except Exception as exc:
                self.logger.debug("Failed to refresh table viewport: %s", exc)
            self._update_selection_summaries()
            elapsed_ms = (time.perf_counter() - start) * 1000.0
            if elapsed_ms >= 20.0:
                self.logger.debug(
                    "[perf] silver_bars.populate_table=%.2fms rows=%s",
                    elapsed_ms,
                    len(bars_data or []),
                )

    def _show_available_context_menu(self, pos):
        try:
            menu = QMenu(self.host)
            add_action = menu.addAction("Add Selected Bars to List")
            add_all_action = menu.addAction("Add All Filtered to List")
            create_list_sel_action = menu.addAction("Create New List from Selection…")
            refresh_action = menu.addAction("Refresh Available")
            copy_action = menu.addAction("Copy Selected Rows")
            action = menu.exec_(self.available_bars_table.viewport().mapToGlobal(pos))
            if action == add_action:
                self.add_selected_to_list()
            elif action == add_all_action:
                self.add_all_filtered_to_list()
            elif action == create_list_sel_action:
                self._create_list_from_selection()
            elif action == refresh_action:
                self.load_available_bars()
            elif action == copy_action:
                self._copy_selected_rows(self.available_bars_table)
        except Exception as exc:
            self.logger.debug("Failed to show available-bars context menu: %s", exc)

    def _show_list_context_menu(self, pos):
        try:
            menu = QMenu(self.host)
            remove_action = menu.addAction("Remove Selected Bars from List")
            remove_all_action = menu.addAction("Remove All Bars from List")
            print_action = menu.addAction("Print List")
            export_action = menu.addAction("Export List to CSV…")
            copy_action = menu.addAction("Copy Selected Rows")
            action = menu.exec_(self.list_bars_table.viewport().mapToGlobal(pos))
            if action == remove_action:
                self.remove_selected_from_list()
            elif action == remove_all_action:
                self.remove_all_from_list()
            elif action == print_action:
                self.print_selected_list()
            elif action == export_action:
                self.export_current_list_to_csv()
            elif action == copy_action:
                self._copy_selected_rows(self.list_bars_table)
        except Exception as exc:
            self.logger.debug("Failed to show list context menu: %s", exc)

    def _copy_selected_rows(self, table):
        try:
            selected = table.selectionModel().selectedRows()
            if not selected:
                return
            rows = []
            for idx in selected:
                row = idx.row()
                values = []
                for column in range(table.model().columnCount()):
                    values.append(self._table_cell_text(table, row, column))
                rows.append("\t".join(values))
            QApplication.clipboard().setText("\n".join(rows))
        except Exception as exc:
            self.logger.debug("Failed to copy selected silver bar rows: %s", exc)

    def _update_transfer_buttons_state(self):
        try:
            list_selected = self.current_list_id is not None
            has_avail_sel = False
            has_list_sel = False
            selection_model = self.available_bars_table.selectionModel()
            if selection_model is not None:
                has_avail_sel = bool(selection_model.selectedRows())
            selection_model = self.list_bars_table.selectionModel()
            if selection_model is not None:
                has_list_sel = bool(selection_model.selectedRows())
            if hasattr(self, "add_to_list_button"):
                self.add_to_list_button.setEnabled(list_selected and has_avail_sel)
            if hasattr(self, "remove_from_list_button"):
                self.remove_from_list_button.setEnabled(list_selected and has_list_sel)
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

            def compute(table):
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
                        pass
                return count, weight_sum, fine_sum

            ac, aw, af = compute(self.available_bars_table)
            lc, lw, lf = compute(self.list_bars_table)
            if hasattr(self, "available_selection_label"):
                self.available_selection_label.setText(
                    f"Selected: {ac} | Weight: {aw:.3f} g | Fine: {af:.3f} g"
                )
            if hasattr(self, "list_selection_label"):
                self.list_selection_label.setText(
                    f"Selected: {lc} | Weight: {lw:.3f} g | Fine: {lf:.3f} g"
                )
        except Exception as exc:
            self.logger.debug("Failed to update selection summary labels: %s", exc)

    def _clear_filters(self):
        try:
            self._filter_reload_timer.stop()
        except Exception as exc:
            self.logger.debug("Failed to stop filter reload timer: %s", exc)
        try:
            inputs = [
                self.weight_search_edit,
                self.weight_tol_spin,
                self.purity_min_spin,
                self.purity_max_spin,
                getattr(self, "date_range_combo", None),
            ]
            for widget in inputs:
                if widget is not None:
                    widget.blockSignals(True)
            self.weight_search_edit.clear()
            self.weight_tol_spin.setValue(0.001)
            self.purity_min_spin.setValue(0.0)
            self.purity_max_spin.setValue(100.0)
            date_combo = getattr(self, "date_range_combo", None)
            if date_combo is not None:
                idx = date_combo.findText("Any")
                if idx >= 0:
                    date_combo.setCurrentIndex(idx)
            for widget in inputs:
                if widget is not None:
                    widget.blockSignals(False)
            self.load_available_bars()
        except Exception as exc:
            self.logger.warning("Failed to clear silver bar filters: %s", exc)

    def add_all_filtered_to_list(self):
        if self.current_list_id is None:
            QMessageBox.warning(
                self.host, "Selection Error", "Please select a list first."
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
        bar_ids = []
        for row in range(row_count):
            bar_id = self._bar_id_from_table(self.available_bars_table, row)
            if bar_id is not None:
                bar_ids.append(bar_id)
        try:
            QApplication.setOverrideCursor(Qt.WaitCursor)
        except Exception as exc:
            self.logger.debug(
                "Could not enable wait cursor while adding all bars: %s", exc
            )
        added, failed = self._bulk_assign_to_list(bar_ids, self.current_list_id)
        try:
            QApplication.restoreOverrideCursor()
        except Exception as exc:
            self.logger.debug("Could not restore cursor after add-all: %s", exc)
        self.load_available_bars()
        self.load_bars_in_selected_list()
        self._update_transfer_buttons_state()
        if added:
            QMessageBox.information(
                self.host, "Success", f"{added} bar(s) added to the list."
            )
        if failed:
            QMessageBox.warning(
                self.host, "Partial", f"Failed to add bars: {', '.join(failed)}"
            )

    def remove_all_from_list(self):
        if self.current_list_id is None:
            QMessageBox.warning(
                self.host, "Selection Error", "Please select a list first."
            )
            return
        row_count = self.list_bars_table.model().rowCount()
        if row_count == 0:
            QMessageBox.information(
                self.host, "No Bars", "No bars in the selected list."
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
        bar_ids = []
        for row in range(row_count):
            bar_id = self._bar_id_from_table(self.list_bars_table, row)
            if bar_id is not None:
                bar_ids.append(bar_id)
        try:
            QApplication.setOverrideCursor(Qt.WaitCursor)
        except Exception as exc:
            self.logger.debug(
                "Could not enable wait cursor while removing all bars: %s", exc
            )
        removed, failed = self._bulk_remove_from_list(bar_ids)
        try:
            QApplication.restoreOverrideCursor()
        except Exception as exc:
            self.logger.debug("Could not restore cursor after remove-all: %s", exc)
        self.load_available_bars()
        self.load_bars_in_selected_list()
        self._update_transfer_buttons_state()
        if removed:
            QMessageBox.information(
                self.host, "Success", f"{removed} bar(s) removed from the list."
            )
        if failed:
            QMessageBox.warning(
                self.host, "Partial", f"Failed to remove bars: {', '.join(failed)}"
            )

    def export_current_list_to_csv(self):
        if self.current_list_id is None:
            QMessageBox.warning(self.host, "Error", "No list selected.")
            return
        path, _ = QFileDialog.getSaveFileName(
            self.host, "Export List to CSV", "silver_bars.csv", "CSV Files (*.csv)"
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
                self.host, "Export Complete", f"List exported to\n{path}"
            )
        except Exception as exc:
            QMessageBox.critical(
                self.host, "Export Error", f"Failed to export CSV: {exc}"
            )
