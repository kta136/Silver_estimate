"""Table and context-menu helpers for silver-bar management."""

from __future__ import annotations

import time
import traceback

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QApplication, QMenu, QMessageBox

from ._host_proxy import HostProxy


class SilverBarTableController(HostProxy):
    """Own table utilities, totals refresh, and context menus."""

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
            clearer = getattr(model, "clear_rows", None)
            if callable(clearer):
                clearer()
                return
            setter = getattr(model, "set_rows", None)
            if callable(setter):
                setter([], total_count=0)
        except Exception as exc:
            self.logger.debug("Could not clear management table: %s", exc)

    def _populate_table(self, table, bars_data, *, total_rows=None):
        start = time.perf_counter()
        try:
            model = table.model()
            setter = getattr(model, "set_rows", None)
            if callable(setter):
                setter(list(bars_data or []), total_count=total_rows)

            loaded_count_getter = getattr(model, "loaded_count", None)
            total_count_getter = getattr(model, "total_count", None)
            total_weight_getter = getattr(model, "total_weight", None)
            total_fine_getter = getattr(model, "total_fine_weight", None)

            bar_count = (
                int(loaded_count_getter())
                if callable(loaded_count_getter)
                else len(list(bars_data or []))
            )
            total_weight = (
                float(total_weight_getter()) if callable(total_weight_getter) else 0.0
            )
            total_fine_weight = (
                float(total_fine_getter()) if callable(total_fine_getter) else 0.0
            )
            effective_total_rows = (
                int(total_count_getter())
                if callable(total_count_getter)
                else total_rows
            )

            loaded_text = f"{bar_count}"
            if isinstance(effective_total_rows, int) and effective_total_rows >= 0:
                loaded_text = f"{bar_count}/{effective_total_rows}"
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
