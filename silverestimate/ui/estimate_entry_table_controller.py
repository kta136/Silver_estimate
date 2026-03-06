"""Table and navigation controller for estimate entry."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any

from PyQt5 import sip
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import QAbstractItemView, QApplication

from ._host_proxy import HostProxy
from .adapters import EstimateTableAdapter
from .estimate_entry_ui import (
    COL_CODE,
    COL_GROSS,
    COL_PIECES,
    COL_POLY,
    COL_PURITY,
    COL_WAGE_RATE,
)


class EstimateEntryTableController(HostProxy):
    """Handle row management, focus, editing, and cell navigation."""

    if TYPE_CHECKING:
        _enforcing_code_nav: bool
        _loading_estimate: bool
        _table_adapter: EstimateTableAdapter | None

    def _get_table_adapter(self) -> EstimateTableAdapter:
        if (
            self._table_adapter is None
            or getattr(self._table_adapter, "_table", None) is not self.item_table
        ):
            self._table_adapter = EstimateTableAdapter(self.host, self.item_table)
        return self._table_adapter

    @staticmethod
    def _qt_object_available(obj: Any) -> bool:
        try:
            return not sip.isdeleted(obj)
        except TypeError:
            return obj is not None
        except RuntimeError:
            return False

    def _table_runtime_available(self) -> bool:
        table = getattr(self, "item_table", None)
        if not self._qt_object_available(self.host) or not self._qt_object_available(
            table
        ):
            return False
        model = getattr(table, "_table_model", None)
        return model is not None and self._qt_object_available(model)

    def populate_item_row(self, item_data):
        if self.current_row < 0:
            return
        self.populate_row(self.current_row, item_data)

    def add_empty_row(self):
        if not self._table_runtime_available():
            return
        self._get_table_adapter().add_empty_row()
        if not self._table_runtime_available():
            return
        if self._totals_incremental_is_active():
            try:
                row_index = self.item_table.rowCount() - 1
                if row_index >= 0:
                    self._row_contrib_cache[row_index] = (
                        self._inactive_row_contribution()
                    )
            except (AttributeError, RuntimeError, TypeError, ValueError) as exc:
                self._disable_incremental_totals_and_fallback(exc)
        self._schedule_columns_autofit()

    def clear_all_rows(self):
        self.item_table.blockSignals(True)
        try:
            self.item_table.clear_rows()
        finally:
            self.item_table.blockSignals(False)
        if self._totals_incremental_is_active():
            try:
                self._reset_incremental_aggregates()
            except (AttributeError, RuntimeError, TypeError, ValueError) as exc:
                self._disable_incremental_totals_and_fallback(exc)
        self.current_row = -1
        self.current_column = -1
        self._schedule_columns_autofit()

    def _on_table_cell_edited(self, row: int, column: int):
        start = time.perf_counter()
        if self._is_continuous_column_autofit_enabled():
            self._schedule_columns_autofit(columns=[column])
        self.handle_cell_changed(row, column)
        self._log_perf_metric(
            "estimate_entry.cell_edit",
            start,
            threshold_ms=25.0,
            row=row,
            column=column,
        )

    def _on_table_row_delete_requested(self, row: int):
        if row < 0 or row >= self.item_table.rowCount():
            return
        target_col = self.current_column
        if (
            target_col is None
            or target_col < 0
            or target_col >= self.item_table.columnCount()
        ):
            target_col = COL_CODE
        try:
            self.item_table.setCurrentCell(row, target_col)
        except (AttributeError, RuntimeError, TypeError, ValueError):
            pass
        self.current_row = row
        self.current_column = target_col
        self.delete_current_row()

    def cell_clicked(self, row, column):
        self.current_row = row
        self.current_column = column
        if column in self.EDITABLE_ENTRY_COLS:
            self._request_edit_cell(row, column, delay_ms=0)

    def selection_changed(self):
        index = self.item_table.currentIndex()
        if not index.isValid():
            selected_indexes = self.item_table.selectedIndexes()
            if not selected_indexes:
                return
            index = selected_indexes[0]
        if not index.isValid():
            return
        self.current_row = index.row()
        self.current_column = index.column()

    def current_cell_changed(self, currentRow, currentCol, previousRow, previousCol):
        try:
            mouse_pressed = bool(QApplication.mouseButtons())
        except (AttributeError, RuntimeError):
            mouse_pressed = False
        row_changed = (
            previousRow is not None
            and previousRow >= 0
            and currentRow is not None
            and currentRow >= 0
            and currentRow != previousRow
        )
        if row_changed and not mouse_pressed:
            self._mark_manual_row_navigation()
        if not mouse_pressed:
            if not self._enforce_code_required(currentRow, currentCol):
                return
        self.current_row = currentRow
        self.current_column = currentCol
        if (
            currentCol in self.EDITABLE_ENTRY_COLS
            and 0 <= currentRow < self.item_table.rowCount()
        ):
            if row_changed and self._manual_row_nav_recent():
                self._request_edit_cell(
                    currentRow,
                    currentCol,
                    delay_ms=self._manual_row_nav_edit_delay_ms,
                )
                return
            self._request_edit_cell(currentRow, currentCol, delay_ms=0)

    def handle_cell_changed(self, row, column):
        if self.processing_cell:
            return

        self.current_row = row
        self.current_column = column

        self.item_table.blockSignals(True)
        try:
            if column == COL_CODE:
                self.process_item_code()
            elif column in [COL_GROSS, COL_POLY, COL_PURITY, COL_WAGE_RATE]:
                self._recompute_row_derived_values(row)
                self._schedule_auto_advance_from(row, column)
            elif column == COL_PIECES:
                self._recompute_row_derived_values(row)
                if row == self.item_table.rowCount() - 1:
                    code_text = self.item_table.get_cell_text(row, COL_CODE).strip()
                    if code_text:
                        QTimer.singleShot(10, self.add_empty_row)
                else:
                    self._schedule_focus_code_from(row, column, row + 1, delay_ms=10)
            else:
                self._schedule_totals_recalc()

        except Exception as exc:
            self.logger.error("Error in calculation: %s", exc, exc_info=True)
            self._status(f"Error: {exc}", 5000)
        finally:
            self.item_table.blockSignals(False)
        self._mark_unsaved()

    def _schedule_auto_advance_from(self, row: int, col: int) -> None:
        QTimer.singleShot(0, lambda: self._auto_advance_if_origin_unchanged(row, col))

    def _auto_advance_if_origin_unchanged(self, row: int, col: int) -> None:
        if self._manual_row_nav_recent():
            return
        if self.current_row != row or self.current_column != col:
            return
        self.move_to_next_cell()

    def _schedule_focus_code_from(
        self, origin_row: int, origin_col: int, target_row: int, *, delay_ms: int
    ) -> None:
        QTimer.singleShot(
            delay_ms,
            lambda: self._focus_code_if_origin_unchanged(
                origin_row, origin_col, target_row
            ),
        )

    def _focus_code_if_origin_unchanged(
        self, origin_row: int, origin_col: int, target_row: int
    ) -> None:
        if self._manual_row_nav_recent():
            return
        if self.current_row != origin_row or self.current_column != origin_col:
            return
        self.focus_on_code_column(target_row)

    def _mark_manual_row_navigation(self) -> None:
        self._last_manual_row_nav_ts = time.monotonic()

    def _manual_row_nav_recent(self, *, threshold_seconds: float = 0.25) -> bool:
        return (time.monotonic() - self._last_manual_row_nav_ts) <= threshold_seconds

    def process_item_code(self):
        if self.processing_cell:
            return
        if self.current_row < 0:
            return

        code = self.item_table.get_cell_text(self.current_row, COL_CODE).strip().upper()
        self.item_table.set_cell_text(self.current_row, COL_CODE, code)

        if not code:
            self._status("Enter item code first", 1500)
            self._update_incremental_for_row(self.current_row)
            self._schedule_totals_recalc()
            if self._should_force_code_focus():
                QTimer.singleShot(
                    0, lambda: self.focus_on_code_column(self.current_row)
                )
            return

        if self.presenter is None:
            self._status("Item lookup unavailable; presenter not initialised.", 4000)
            return

        try:
            if self.presenter.handle_item_code(self.current_row, code):
                self._mark_unsaved()
        except Exception as exc:
            self.logger.error(
                "Presenter handle_item_code failed: %s", exc, exc_info=True
            )

    def _is_code_empty(self, row):
        try:
            return not self.item_table.get_cell_text(row, COL_CODE).strip()
        except (AttributeError, RuntimeError, TypeError):
            return True

    def _enforce_code_required(self, target_row, target_col, show_hint=True):
        if self._enforcing_code_nav:
            return True
        try:
            if not self._is_table_valid():
                return True
            if (
                target_row is None
                or target_col is None
                or target_row < 0
                or target_col < 0
            ):
                return True

            if 0 <= self.current_row < self.item_table.rowCount():
                if self._is_code_empty(self.current_row):
                    if target_row != self.current_row or target_col != COL_CODE:
                        if show_hint:
                            self._status("Enter item code first", 1500)
                        self._enforcing_code_nav = True
                        try:
                            self.focus_on_code_column(self.current_row)
                        finally:
                            self._enforcing_code_nav = False
                        return False
        except (AttributeError, RuntimeError, TypeError, ValueError):
            return True
        return True

    def move_to_next_cell(self):
        if self.processing_cell:
            return

        current_col = self.current_column
        current_row = self.current_row

        if current_row is None or current_row < 0:
            self.focus_on_code_column(0)
            return

        if current_col == COL_CODE and self._is_code_empty(current_row):
            self._status("Enter item code first", 1500)
            self.focus_on_code_column(current_row)
            return

        next_row, next_col = self._next_edit_target(current_row, current_col)

        if next_row >= self.item_table.rowCount():
            last_code_text = self.item_table.get_cell_text(
                current_row, COL_CODE
            ).strip()
            if last_code_text:
                self.add_empty_row()
                return
            next_row = current_row
            next_col = current_col

        if self._is_table_valid() and 0 <= next_row < self.item_table.rowCount():
            self.item_table.blockSignals(True)
            try:
                self.item_table.setCurrentCell(next_row, next_col)
            finally:
                self.item_table.blockSignals(False)
            if next_col in self.EDITABLE_ENTRY_COLS:
                QTimer.singleShot(10, lambda: self._safe_edit_item(next_row, next_col))

    def move_to_previous_cell(self):
        if self.processing_cell:
            return
        current_col = self.current_column
        current_row = self.current_row

        if current_row is None or current_row < 0:
            self.focus_on_code_column(0)
            return

        prev_row, prev_col = self._previous_edit_target(current_row, current_col)

        if 0 <= prev_row < self.item_table.rowCount():
            self.item_table.setCurrentCell(prev_row, prev_col)
            QTimer.singleShot(10, lambda: self._safe_edit_item(prev_row, prev_col))

    def _next_edit_target(self, row: int, col: int) -> tuple[int, int]:
        if col == COL_CODE:
            return row, COL_GROSS
        if col == COL_GROSS:
            return row, COL_POLY
        if col == COL_POLY:
            return row, COL_PURITY
        if col == COL_PURITY:
            return row, COL_WAGE_RATE
        if col == COL_WAGE_RATE:
            if self._is_pieces_editable_for_row(row):
                return row, COL_PIECES
            return row + 1, COL_CODE
        if col == COL_PIECES:
            return row + 1, COL_CODE
        return row, COL_CODE

    def _previous_edit_target(self, row: int, col: int) -> tuple[int, int]:
        if col == COL_PIECES:
            return row, COL_WAGE_RATE
        if col == COL_WAGE_RATE:
            return row, COL_PURITY
        if col == COL_PURITY:
            return row, COL_POLY
        if col == COL_POLY:
            return row, COL_GROSS
        if col == COL_GROSS:
            return row, COL_CODE
        if col == COL_CODE:
            if row > 0:
                prev_row = row - 1
                if self._is_pieces_editable_for_row(prev_row):
                    return prev_row, COL_PIECES
                return prev_row, COL_WAGE_RATE
            return 0, COL_CODE
        return row, COL_CODE

    def focus_on_code_column(self, row):
        try:
            if sip.isdeleted(self.host):
                return
        except RuntimeError:
            return

        def _apply_focus(target_row):
            try:
                if not self._is_table_valid():
                    return
                if 0 <= target_row < self.item_table.rowCount():
                    self.item_table.blockSignals(True)
                    try:
                        self.item_table.setCurrentCell(target_row, COL_CODE)
                    finally:
                        self.item_table.blockSignals(False)
                    QTimer.singleShot(
                        10, lambda: self._safe_edit_item(target_row, COL_CODE)
                    )
            except (AttributeError, RuntimeError, TypeError, ValueError) as exc:
                self.logger.debug("Failed to focus code column: %s", exc)

        timer = getattr(self, "_code_focus_timer", None)
        if timer is None or sip.isdeleted(timer):
            timer = QTimer(self.host)
            timer.setSingleShot(True)
            timer.timeout.connect(
                lambda: _apply_focus(getattr(self, "_pending_focus_row", 0))
            )
            self._code_focus_timer = timer
        try:
            timer.stop()
        except RuntimeError:
            return
        self._pending_focus_row = row
        timer.start(0)

    def _safe_edit_item(self, row, col):
        try:
            table = self.item_table
            if not table or sip.isdeleted(table) or not table.isVisible():
                return
            if self._loading_estimate:
                return
            if table.state() == QAbstractItemView.EditingState:
                current = table.currentIndex()
                if (
                    current.isValid()
                    and current.row() == row
                    and current.column() == col
                ):
                    return

            model = table.model()
            if model and not sip.isdeleted(model):
                index = model.index(row, col)
                if index.isValid() and (model.flags(index) & Qt.ItemIsEditable):
                    table.setCurrentIndex(index)
                    table.edit(index)
        except (AttributeError, RuntimeError, TypeError, ValueError) as exc:
            self.logger.debug(
                "Could not open inline editor for row=%s col=%s: %s",
                row,
                col,
                exc,
            )

    def _is_table_valid(self) -> bool:
        try:
            return self.item_table is not None and not sip.isdeleted(self.item_table)
        except RuntimeError:
            return False

    def _is_pieces_editable_for_row(self, row: int) -> bool:
        if not self._is_table_valid():
            return False
        table = self.item_table
        model = table.model() if table is not None else None
        if model is None:
            return True
        try:
            index = model.index(row, COL_PIECES)
            if not index.isValid():
                return True
            return bool(model.flags(index) & Qt.ItemIsEditable)
        except (AttributeError, RuntimeError, TypeError):
            return True

    def _should_force_code_focus(self) -> bool:
        try:
            table = self.item_table
            if not self._is_table_valid():
                return False
            app = QApplication.instance()
            if not app:
                return True
            focus_widget = QApplication.focusWidget()
            if not focus_widget:
                return True
            if focus_widget is table:
                return True
            if hasattr(table, "isAncestorOf") and table.isAncestorOf(focus_widget):
                return True
            return False
        except (AttributeError, RuntimeError, TypeError):
            return False

    def _get_cell_float(self, row, col, default=0.0):
        text = self.item_table.get_cell_text(row, col).strip()
        try:
            return float(text.replace(",", ".")) if text else default
        except (AttributeError, TypeError, ValueError):
            return default

    def _get_cell_int(self, row, col, default=1):
        text = self.item_table.get_cell_text(row, col).strip()
        try:
            return int(text) if text else default
        except (AttributeError, TypeError, ValueError):
            return default

    def _schedule_cell_edit(self, row, col):
        self._request_edit_cell(row, col, delay_ms=0)

    def _request_edit_cell(self, row: int, col: int, *, delay_ms: int = 0) -> None:
        self._edit_request_token += 1
        token = self._edit_request_token
        QTimer.singleShot(delay_ms, lambda: self._run_edit_request(token, row, col))

    def _run_edit_request(self, token: int, row: int, col: int) -> None:
        if token != self._edit_request_token:
            return
        if self.processing_cell or self._loading_estimate:
            return
        if not self._is_table_valid():
            return
        if row < 0 or col < 0 or row >= self.item_table.rowCount():
            return
        if col not in self.EDITABLE_ENTRY_COLS:
            return
        if self.item_table.is_cell_editable(row, col):
            self._safe_edit_item(row, col)
