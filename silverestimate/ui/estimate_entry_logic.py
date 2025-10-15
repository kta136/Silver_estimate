#!/usr/bin/env python
from PyQt5.QtWidgets import (QTableWidgetItem, QMessageBox, QDialog, QApplication)
from PyQt5.QtCore import Qt, QDate, QTimer, QLocale # Import QLocale
from PyQt5.QtGui import QColor

from datetime import datetime
import traceback # For detailed error reporting
import logging # Import logging module
from typing import Optional

from .item_selection_dialog import ItemSelectionDialog

from silverestimate.domain.estimate_models import EstimateLine, EstimateLineCategory, TotalsResult
from silverestimate.services.estimate_calculator import (
    compute_fine_weight,
    compute_net_weight,
    compute_totals,
    compute_wage_amount,
)
from silverestimate.presenter import (
    EstimateEntryPresenter,
    EstimateEntryViewState,
    SaveItem,
    SaveOutcome,
    SavePayload,
    LoadedEstimate,
)

# --- Column Constants ---
COL_CODE = 0
COL_ITEM_NAME = 1
COL_GROSS = 2
COL_POLY = 3
COL_NET_WT = 4
COL_PURITY = 5
COL_WAGE_RATE = 6
COL_PIECES = 7
COL_WAGE_AMT = 8
COL_FINE_WT = 9
COL_TYPE = 10
# --- End Constants ---

class EstimateLogic:
    """Business logic for the estimate entry widget."""

    def __init__(self):
        """Initialize the logger for this class."""
        self.logger = logging.getLogger(__name__)
        # Track whether an existing estimate is loaded
        self._estimate_loaded = False
        self._unsaved_changes = False
        self._unsaved_block = 0
        # Guard flag to prevent recursive selection handling
        self._enforcing_code_nav = False
        self.presenter: Optional[EstimateEntryPresenter] = None

    # --- Helper to show status messages (assumes self has show_status method) ---
    def _status(self, message, timeout=3000):
        if hasattr(self, 'show_status') and callable(self.show_status):
            self.show_status(message, timeout)
        else:  # Fallback if show_status isn't available (e.g. testing)
            self.logger.info(f"Status: {message}")

    # --- Unsaved-change tracking helpers ---
    def _push_unsaved_block(self) -> None:
        self._unsaved_block = getattr(self, "_unsaved_block", 0) + 1

    def _pop_unsaved_block(self) -> None:
        if getattr(self, "_unsaved_block", 0) > 0:
            self._unsaved_block -= 1

    def _set_unsaved(self, dirty: bool, *, force: bool = False) -> None:
        if not force and dirty and getattr(self, "_unsaved_block", 0) > 0:
            return
        previous = getattr(self, "_unsaved_changes", False)
        self._unsaved_changes = dirty
        if previous != dirty or force:
            callback = getattr(self, "_on_unsaved_state_changed", None)
            if callable(callback):
                try:
                    callback(dirty)
                except Exception:
                    pass

    def _mark_unsaved(self, *_, **__) -> None:
        self._set_unsaved(True)

    # --------------------------------------------------------------------------

    def set_voucher_number(self, voucher_no: str) -> None:
        """Update the voucher field without triggering recursive loads."""
        editor = getattr(self, 'voucher_edit', None)
        if editor is None:
            return
        try:
            editor.blockSignals(True)
            editor.setText(voucher_no)
        finally:
            editor.blockSignals(False)

    def populate_row(self, row_index: int, item_data):
        """Fill in item details for the specified row based on item data dictionary."""
        if row_index < 0 or row_index >= self.item_table.rowCount():
            return
        self.item_table.blockSignals(True)
        previous_row = getattr(self, "current_row", -1)
        try:
            non_editable_calc_cols = [COL_NET_WT, COL_WAGE_AMT, COL_FINE_WT, COL_TYPE]
            for col in range(self.item_table.columnCount()):
                self._ensure_cell_exists(row_index, col, editable=(col not in non_editable_calc_cols))

            code_text = (item_data.get('code', '') or '').strip()
            if code_text:
                code_text = code_text.upper()
            code_item = self.item_table.item(row_index, COL_CODE)
            if code_item is not None:
                code_item.setText(code_text)

            self.item_table.item(row_index, COL_ITEM_NAME).setText(item_data.get('name', ''))
            self.item_table.item(row_index, COL_PURITY).setText(str(item_data.get('purity', 0.0)))
            self.item_table.item(row_index, COL_WAGE_RATE).setText(str(item_data.get('wage_rate', 0.0)))

            pcs_item = self.item_table.item(row_index, COL_PIECES)
            if not pcs_item.text().strip():
                pcs_item.setText("1")

            type_item = self.item_table.item(row_index, COL_TYPE)
            self._update_row_type_visuals_direct(type_item)
            type_item.setTextAlignment(Qt.AlignCenter)

            self.current_row = row_index
            self.calculate_net_weight()
        except Exception as e:
            self.logger.error(f"Error populating row {row_index + 1}: {str(e)}", exc_info=True)
            QMessageBox.critical(self, "Error", f"Error populating row: {str(e)}")
            self._status(f"Error populating row {row_index + 1}", 4000)
        finally:
            self.item_table.blockSignals(False)
            self.current_row = previous_row

    def populate_item_row(self, item_data):
        """Backward-compatible wrapper for legacy calls using current_row."""
        if getattr(self, "current_row", -1) < 0:
            return
        self.populate_row(self.current_row, item_data)

    def prompt_item_selection(self, code: str):
        """Open the item selection dialog and return the chosen item."""
        try:
            dialog = ItemSelectionDialog(self.db_manager, code, self)
            if dialog.exec_() == QDialog.Accepted:
                selected_item = dialog.get_selected_item()
                if selected_item:
                    return selected_item
        except Exception as exc:
            self.logger.error(f"Error during item selection for code {code}: {exc}", exc_info=True)
            QMessageBox.critical(self, "Selection Error", f"Could not open selection dialog: {exc}")
        return None

    def focus_after_item_lookup(self, row_index: int) -> None:
        """Move focus to the Gross column after an item lookup."""
        if row_index < 0 or row_index >= self.item_table.rowCount():
            return
        try:
            self.item_table.setCurrentCell(row_index, COL_GROSS)
            QTimer.singleShot(0, lambda: self.item_table.setCurrentCell(row_index, COL_GROSS))
            QTimer.singleShot(
                10,
                lambda: self.item_table.editItem(self.item_table.item(row_index, COL_GROSS)),
            )
        except Exception:
            pass

    def apply_loaded_estimate(self, loaded: LoadedEstimate) -> bool:
        """Populate the form using the presenter-provided loaded estimate."""
        success = False
        self._push_unsaved_block()
        self.item_table.blockSignals(True)
        self.processing_cell = True
        try:
            while self.item_table.rowCount() > 0:
                self.item_table.removeRow(0)

            try:
                load_date = QDate.fromString(loaded.date, "yyyy-MM-dd")
                if load_date and load_date.isValid():
                    self.date_edit.setDate(load_date)
                else:
                    self.date_edit.setDate(QDate.currentDate())
            except Exception:
                self.date_edit.setDate(QDate.currentDate())

            self.silver_rate_spin.setValue(loaded.silver_rate)

            if hasattr(self, 'note_edit'):
                try:
                    self.note_edit.setText(loaded.note or "")
                except Exception:
                    self.note_edit.setText("")

            self.last_balance_silver = loaded.last_balance_silver
            self.last_balance_amount = loaded.last_balance_amount

            for item in loaded.items:
                row = self.item_table.rowCount()
                self.item_table.insertRow(row)
                self.item_table.setItem(row, COL_CODE, QTableWidgetItem(item.code))
                self.item_table.setItem(row, COL_ITEM_NAME, QTableWidgetItem(item.name))
                self.item_table.setItem(row, COL_GROSS, QTableWidgetItem(f"{item.gross:.2f}"))
                self.item_table.setItem(row, COL_POLY, QTableWidgetItem(f"{item.poly:.2f}"))
                self.item_table.setItem(row, COL_NET_WT, QTableWidgetItem(f"{item.net_wt:.2f}"))
                self.item_table.setItem(row, COL_PURITY, QTableWidgetItem(f"{item.purity:.2f}"))
                self.item_table.setItem(row, COL_WAGE_RATE, QTableWidgetItem(f"{item.wage_rate:.2f}"))
                self.item_table.setItem(row, COL_PIECES, QTableWidgetItem(str(item.pieces)))
                self.item_table.setItem(row, COL_WAGE_AMT, QTableWidgetItem(f"{item.wage:.0f}"))
                self.item_table.setItem(row, COL_FINE_WT, QTableWidgetItem(f"{item.fine:.2f}"))

                if item.is_return:
                    type_text, bg_color = "Return", QColor(255, 200, 200)
                elif item.is_silver_bar:
                    type_text, bg_color = "Silver Bar", QColor(200, 255, 200)
                else:
                    type_text, bg_color = "No", QColor(255, 255, 255)
                type_item = QTableWidgetItem(type_text)
                type_item.setBackground(bg_color)
                type_item.setTextAlignment(Qt.AlignCenter)
                type_item.setFlags(type_item.flags() & ~Qt.ItemIsEditable)
                self.item_table.setItem(row, COL_TYPE, type_item)

                for col in [COL_NET_WT, COL_WAGE_AMT, COL_FINE_WT]:
                    cell = self.item_table.item(row, col)
                    if cell:
                        cell.setFlags(cell.flags() & ~Qt.ItemIsEditable)

            self.add_empty_row()
            self.calculate_totals()

            self._estimate_loaded = True
            success = True
            try:
                if hasattr(self, 'delete_estimate_button'):
                    self.delete_estimate_button.setEnabled(True)
            except Exception:
                pass
        finally:
            self.processing_cell = False
            self.item_table.blockSignals(False)
            self._pop_unsaved_block()
            try:
                self.focus_on_code_column(0)
            except Exception:
                pass

        if success:
            self.set_voucher_number(loaded.voucher_no)
            self._set_unsaved(False, force=True)
        return success

    def open_history_dialog(self) -> Optional[str]:
        """Open the estimate history dialog and return the selected voucher."""
        try:
            from .estimate_history import EstimateHistoryDialog

            history_dialog = EstimateHistoryDialog(
                self.db_manager,
                main_window_ref=self.main_window,
                parent=self,
            )
            if history_dialog.exec_() == QDialog.Accepted:
                return history_dialog.selected_voucher or None
            return None
        except Exception as exc:
            QMessageBox.critical(
                self,
                "History Error",
                f"Failed to open estimate history: {exc}",
            )
            self._status("History Error: Unable to open history dialog.", 5000)
            return None

    def show_silver_bar_management(self) -> None:
        """Open Silver Bar Management embedded in the main window when available."""
        try:
            if hasattr(self, 'main_window') and hasattr(self.main_window, 'show_silver_bars'):
                self.main_window.show_silver_bars()
                self._status("Opened Silver Bar Management.", 1500)
                return
        except Exception:
            pass
        from .silver_bar_management import SilverBarDialog

        silver_dialog = SilverBarDialog(self.db_manager, self)
        silver_dialog.exec_()
        self._status("Closed Silver Bar Management.", 2000)

    def connect_signals(self, skip_load_estimate=False):
        """Connect UI signals to their handlers."""
        # Connect header signals - use safe_load_estimate if available
        if not skip_load_estimate:
            if hasattr(self, 'safe_load_estimate'):
                self.voucher_edit.editingFinished.connect(self.safe_load_estimate)
            else:
                # Fallback to direct connection if safe method not available
                self.voucher_edit.editingFinished.connect(self.load_estimate)

        # Remove connection to generate button as it's been removed
        self.silver_rate_spin.valueChanged.connect(self._handle_silver_rate_changed)

        # Connect Last Balance button
        if hasattr(self, 'last_balance_button'):
            self.last_balance_button.clicked.connect(self.show_last_balance_dialog)
        if hasattr(self, 'note_edit'):
            self.note_edit.textEdited.connect(self._mark_unsaved)

        if hasattr(self, 'date_edit'):
            self.date_edit.dateChanged.connect(self._mark_unsaved)

        # Connect table signals
        self.item_table.cellClicked.connect(self.cell_clicked)
        self.item_table.itemSelectionChanged.connect(self.selection_changed)
        # Always edit on navigation/selection changes
        self.item_table.currentCellChanged.connect(self.current_cell_changed)
        self.item_table.cellChanged.connect(self.handle_cell_changed)

        # Connect button signals
        self.save_button.clicked.connect(self.save_estimate)
        self.clear_button.clicked.connect(self.clear_form)
        self.print_button.clicked.connect(self.print_estimate)
        # Connect delete row button - handled in EstimateUI setup / EstimateEntryWidget

        # Connect the return toggle button
        self.return_toggle_button.clicked.connect(self.toggle_return_mode)

        # Connect the silver bar toggle button
        self.silver_bar_toggle_button.clicked.connect(self.toggle_silver_bar_mode)

        # Connect the new buttons if they exist
        if hasattr(self, 'history_button'):
            self.history_button.clicked.connect(self.show_history)

        if hasattr(self, 'silver_bars_button'):
            self.silver_bars_button.clicked.connect(self.show_silver_bars)

        # Manual refresh for silver rate
        if hasattr(self, 'refresh_rate_button'):
            self.refresh_rate_button.clicked.connect(self.refresh_silver_rate)

        # Removed connection for table_font_size_spinbox as it's moved to menu
        # if hasattr(self, 'table_font_size_spinbox'):
        #     self.table_font_size_spinbox.valueChanged.connect(self._apply_table_font_size)

        # Connect Delete This Estimate button
        if hasattr(self, 'delete_estimate_button'):
            self.delete_estimate_button.clicked.connect(self.delete_current_estimate)
            # Ensure disabled initially; enable only when an estimate is loaded
            try:
                self.delete_estimate_button.setEnabled(False)
            except Exception:
                pass

    def _handle_silver_rate_changed(self, *_):
        """React to manual silver-rate changes by recalculating totals and marking unsaved state."""
        try:
            self.calculate_totals()
        except Exception:
            pass
        self._mark_unsaved()
        self._mark_unsaved()

    # --- Currency formatting helper ---
    def _format_currency(self, value):
        """Format currency using system locale; fallback to INR symbol with grouping."""
        try:
            locale = QLocale.system()
            # Round to whole currency units for display
            return locale.toCurrencyString(float(round(value)))
        except Exception:
            try:
                return f"₹ {int(round(value)):,}"
            except Exception:
                return str(value)

    def print_estimate(self):
        """Print the current estimate."""
        from .print_manager import PrintManager

        voucher_no = self.voucher_edit.text().strip()
        if not voucher_no:
            QMessageBox.warning(self, "Print Error", "Please save the estimate or generate a voucher number before printing.")
            self._status("Print Error: Voucher number missing", 4000)
            return

        self.logger.info(f"Generating print preview for {voucher_no}...")
        self._status(f"Generating print preview for {voucher_no}...")
        # Disable initiating button while preparing preview
        try:
            if hasattr(self, 'print_button'):
                self.print_button.setEnabled(False)
        except Exception:
            pass
        # Pass the stored main window font setting
        current_print_font = getattr(self.main_window, 'print_font', None)
        print_manager = PrintManager(self.db_manager, print_font=current_print_font)
        success = print_manager.print_estimate(voucher_no, self)
        if success:
             self._status(f"Print preview for {voucher_no} generated.", 3000)
        else:
             self._status(f"Failed to generate print preview for {voucher_no}.", 4000)
        # Re-enable button
        try:
            if hasattr(self, 'print_button'):
                self.print_button.setEnabled(True)
        except Exception:
            pass

    def add_empty_row(self):
        """Add an empty row to the item table."""
        try:
            if self.item_table.rowCount() > 0:
                last_row = self.item_table.rowCount() - 1
                is_last_row_empty = True
                last_code_item = self.item_table.item(last_row, COL_CODE) # Use constant
                if last_code_item and last_code_item.text().strip():
                    is_last_row_empty = False

                if is_last_row_empty:
                    QTimer.singleShot(0, lambda: self.focus_on_code_column(last_row))
                    return

            self.processing_cell = True
            row = self.item_table.rowCount()
            self.item_table.insertRow(row)

            for col in range(self.item_table.columnCount()):
                item = QTableWidgetItem("")
                # Use constants for column checks
                if col in [COL_NET_WT, COL_WAGE_AMT, COL_FINE_WT]:
                    item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                elif col == COL_TYPE:
                    self._update_row_type_visuals_direct(item)
                    item.setTextAlignment(Qt.AlignCenter)
                    item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                else:
                    item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsEditable)
                self.item_table.setItem(row, col, item)

            self.processing_cell = False
            QTimer.singleShot(50, lambda: self.focus_on_code_column(row))

        except Exception as e:
            # Log the error but don't crash the application
            self.logger.error(f"Error adding empty row: {str(e)}", exc_info=True)
            self._status("Warning: Could not add empty row", 3000)
            # Make sure processing_cell is reset even if an error occurs
            self.processing_cell = False

    # Helper to set item visuals based on mode (used in add_empty_row)
    def _update_row_type_visuals_direct(self, type_item):
         try:
             if not type_item:
                 self.logger.warning("Null type_item passed to _update_row_type_visuals_direct")
                 return

             if self.return_mode:
                 type_item.setText("Return")
                 type_item.setBackground(QColor(255, 200, 200))
             elif self.silver_bar_mode:
                 type_item.setText("Silver Bar")
                 type_item.setBackground(QColor(200, 255, 200))
             else:
                 type_item.setText("No")
                 type_item.setBackground(QColor(255, 255, 255))
         except Exception as e:
             # Log the error but don't crash the application
             self.logger.error(f"Error updating row type visuals: {str(e)}", exc_info=True)

    def _is_code_empty(self, row):
        try:
            itm = self.item_table.item(row, COL_CODE)
            return (not itm) or (not itm.text().strip())
        except Exception:
            return True

    def _enforce_code_required(self, target_row, target_col, show_hint=True):
        """Ensure code is filled before allowing navigation away from code column.

        Returns True if navigation is allowed, False if blocked (and focus reset).
        """
        if self._enforcing_code_nav:
            return True
        try:
            # If current row has empty code, only allow focus on its code cell
            if 0 <= getattr(self, 'current_row', -1) < self.item_table.rowCount():
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
        except Exception:
            # On any error, do not block
            return True
        return True

    def cell_clicked(self, row, column):
        """Update current position when a cell is clicked.

        Allow changing selection with the mouse even if the current row's
        code is empty. Code enforcement will be handled for keyboard
        navigation in current_cell_changed.
        """
        prev_row = getattr(self, 'current_row', -1)
        prev_empty_code = self._is_code_empty(prev_row) if 0 <= prev_row < self.item_table.rowCount() else False
        self.current_row = row
        self.current_column = column
        # Use constants for editable columns check
        editable_cols = [COL_CODE, COL_GROSS, COL_POLY, COL_PURITY, COL_WAGE_RATE, COL_PIECES]
        if column in editable_cols:
            item = self.item_table.item(row, column)
            if item and (item.flags() & Qt.ItemIsEditable):
                # If we are switching away from a row with empty code, allow selection
                # but avoid immediately entering edit mode in the new row.
                if not (prev_empty_code and row != prev_row):
                    self.item_table.editItem(item)

    def selection_changed(self):
        """Update current position when selection changes.

        Do not block mouse-driven selection changes here; keyboard
        enforcement is handled in current_cell_changed.
        """
        selected_items = self.item_table.selectedItems()
        if not selected_items:
            return
        item = selected_items[0]
        row = self.item_table.row(item)
        col = self.item_table.column(item)
        prev_row = getattr(self, 'current_row', -1)
        prev_empty_code = self._is_code_empty(prev_row) if 0 <= prev_row < self.item_table.rowCount() else False
        self.current_row = row
        self.current_column = col
        # Open editor when a new selection is made on an editable cell
        editable_cols = [COL_CODE, COL_GROSS, COL_POLY, COL_PURITY, COL_WAGE_RATE, COL_PIECES]
        if col in editable_cols:
            cell = self._ensure_cell_exists(row, col)
            if cell and (cell.flags() & Qt.ItemIsEditable):
                # Same behavior: if switching from an empty-code row, don't auto-edit
                if not (prev_empty_code and row != prev_row):
                    from PyQt5.QtCore import QTimer
                    QTimer.singleShot(0, lambda c=cell: self.item_table.editItem(c))

    def current_cell_changed(self, currentRow, currentCol, previousRow, previousCol):
        """Ensure the newly focused cell enters edit mode immediately if editable.

        Enforce the "code required" rule only for keyboard/navigation-driven
        focus changes. Mouse-driven selection changes should be allowed so that
        users can click to select another row.
        """
        try:
            mouse_pressed = QApplication.mouseButtons() != Qt.NoButton
        except Exception:
            mouse_pressed = False
        if not mouse_pressed:
            if not self._enforce_code_required(currentRow, currentCol):
                return
        self.current_row = currentRow
        self.current_column = currentCol
        editable_cols = [COL_CODE, COL_GROSS, COL_POLY, COL_PURITY, COL_WAGE_RATE, COL_PIECES]
        if currentCol in editable_cols and 0 <= currentRow < self.item_table.rowCount():
            cell = self._ensure_cell_exists(currentRow, currentCol)
            if cell and (cell.flags() & Qt.ItemIsEditable):
                from PyQt5.QtCore import QTimer
                QTimer.singleShot(0, lambda c=cell: self.item_table.editItem(c))

    def handle_cell_changed(self, row, column):
        """Handle cell value changes with direct calculation for weight fields and purity."""
        if self.processing_cell:
            return

        self.current_row = row
        self.current_column = column

        self.item_table.blockSignals(True)
        try:
            # Use constants for column checks
            if column == COL_CODE:
                self.process_item_code()
            elif column in [COL_GROSS, COL_POLY]:
                self.calculate_net_weight()
                QTimer.singleShot(0, self.move_to_next_cell)
            elif column == COL_PURITY:
                self.calculate_fine()
                QTimer.singleShot(0, self.move_to_next_cell)
            elif column == COL_WAGE_RATE:
                self.calculate_wage()
                QTimer.singleShot(0, self.move_to_next_cell)
            elif column == COL_PIECES:
                self.calculate_wage()
                if row == self.item_table.rowCount() - 1:
                    code_item = self.item_table.item(row, COL_CODE) # Use constant
                    if code_item and code_item.text().strip():
                        QTimer.singleShot(10, self.add_empty_row)
                else:
                    QTimer.singleShot(10, lambda: self.focus_on_code_column(row + 1))
            else:
                # Potentially update totals; use debounced recalculation to reduce churn
                if hasattr(self, 'request_totals_recalc'):
                    self.request_totals_recalc()
                else:
                    self.calculate_totals()

        except ValueError as e:
            err_msg = f"Value Error in calculation: {str(e)}"
            self.logger.error(err_msg, exc_info=True)
            self._status(err_msg, 5000)
            QMessageBox.critical(self, "Calculation Error", f"{err_msg}")
        except TypeError as e:
            err_msg = f"Type Error in calculation: {str(e)}"
            self.logger.error(err_msg, exc_info=True)
            self._status(err_msg, 5000)
            QMessageBox.critical(self, "Calculation Error", f"{err_msg}")
        except Exception as e:
            err_msg = f"Unexpected Error in calculation: {str(e)}"
            self.logger.error(err_msg, exc_info=True)
            self._status(err_msg, 5000)
            QMessageBox.critical(self, "Calculation Error", f"{err_msg}")
        finally:
            self.item_table.blockSignals(False)
        self._mark_unsaved()

    def move_to_next_cell(self):
        """Navigate to the next editable cell in the logical order."""
        if self.processing_cell: return

        current_col = self.current_column
        current_row = self.current_row
        next_col = -1
        next_row = current_row

        # Block leaving Code if empty
        if current_col == COL_CODE and self._is_code_empty(current_row):
            self._status("Enter item code first", 1500)
            self.focus_on_code_column(current_row)
            return

        # Use constants for navigation logic
        if current_col == COL_CODE: next_col = COL_GROSS
        elif current_col == COL_GROSS: next_col = COL_POLY
        elif current_col == COL_POLY: next_col = COL_PURITY
        elif current_col == COL_PURITY: next_col = COL_WAGE_RATE
        elif current_col == COL_WAGE_RATE: next_col = COL_PIECES
        elif current_col == COL_PIECES:
            next_row = current_row + 1
            next_col = COL_CODE
        else: # Fallback
            next_col = COL_CODE
            next_row = current_row # Stay on same row, go to code?

        # Handle row wrapping/adding new row
        if next_row >= self.item_table.rowCount():
             last_code_item = self.item_table.item(current_row, COL_CODE) # Use constant
             if last_code_item and last_code_item.text().strip():
                 self.add_empty_row()
                 return
             else:
                 next_row = current_row
                 next_col = current_col # Stay put

        # Focus the calculated next cell
        editable_cols = [COL_CODE, COL_GROSS, COL_POLY, COL_PURITY, COL_WAGE_RATE, COL_PIECES]
        if 0 <= next_row < self.item_table.rowCount() and 0 <= next_col < self.item_table.columnCount():
            self.item_table.setCurrentCell(next_row, next_col)
            if next_col in editable_cols:
                 item_to_edit = self.item_table.item(next_row, next_col)
                 if item_to_edit:
                     QTimer.singleShot(10, lambda: self.item_table.editItem(item_to_edit))

    def focus_on_code_column(self, row):
        """Focus on the code column (first column) of the specified row and start editing."""
        try:
            if 0 <= row < self.item_table.rowCount():
                self._ensure_cell_exists(row, COL_CODE) # Use constant
                self.item_table.setCurrentCell(row, COL_CODE) # Use constant
                # Capture row and col instead of the item object for the timer
                target_row, target_col = row, COL_CODE
                QTimer.singleShot(10, lambda: self._safe_edit_item(target_row, target_col))
            else:
                self.logger.warning(f"Invalid row {row} in focus_on_code_column (rowCount: {self.item_table.rowCount()})")
        except Exception as e:
            # Log the error but don't crash the application
            self.logger.error(f"Error focusing on code column for row {row}: {str(e)}", exc_info=True)

    def _safe_edit_item(self, row, col):
        """Safely fetches item at row/col and calls editItem if it exists."""
        try:
            # Check if row and column are valid
            if row < 0 or row >= self.item_table.rowCount() or col < 0 or col >= self.item_table.columnCount():
                self.logger.warning(f"Invalid row/col in _safe_edit_item: {row}/{col}")
                return

            item = self.item_table.item(row, col)
            if item:
                self.item_table.editItem(item)
        except Exception as e:
            # Log the error but don't crash the application
            self.logger.error(f"Error in _safe_edit_item({row}, {col}): {str(e)}", exc_info=True)
    def process_item_code(self):
        """Look up item code, populate row, or show selection dialog. Moves focus."""
        if self.processing_cell: return
        # Use constant
        if self.current_row < 0 or not self.item_table.item(self.current_row, COL_CODE): return

        code_item = self.item_table.item(self.current_row, COL_CODE)
        code = code_item.text().strip().upper() # Convert to uppercase
        code_item.setText(code) # Update cell visually

        if not code:
            # Keep focus on code; do not move forward
            self._status("Enter item code first", 1500)
            QTimer.singleShot(0, lambda: self.focus_on_code_column(self.current_row))
            return

        presenter = getattr(self, 'presenter', None)
        if presenter is None:
            self.logger.error("Presenter unavailable for item code processing.")
            self._status("Item lookup unavailable; presenter not initialised.", 4000)
            return

        try:
            if presenter.handle_item_code(self.current_row, code):
                self._mark_unsaved()
        except Exception as exc:
            self.logger.error(
                "Presenter handle_item_code failed for %s: %s", code, exc, exc_info=True
            )
            self._status("Warning: Item lookup failed via presenter.", 4000)

    def _get_cell_float(self, row, col, default=0.0):
        """Safely get float value from a cell."""
        item = self.item_table.item(row, col)
        text = item.text().strip() if item else ""
        value = default
        ok = False
        # 1. Try parsing using system locale
        try:
            locale = QLocale.system()
            f_val, ok = locale.toDouble(text)
            if ok:
                value = f_val
        except Exception:
            ok = False # Ensure ok is false if exception occurs

        # 2. If locale parsing failed or returned not ok, try standard float conversion
        if not ok and text:
            try:
                # Replace comma with period for standard float conversion
                text_for_float = text.replace(',', '.')
                value = float(text_for_float)
                ok = True
            except ValueError:
                ok = False # Explicitly set ok to False on error
            except Exception: # Catch other potential errors
                 ok = False

        return value if ok else default

    def _get_cell_int(self, row, col, default=1):
        """Safely get integer value from a cell."""
        item = self.item_table.item(row, col)
        text = item.text().strip() if item else ""
        try:
            return int(text) if text else default
        except ValueError:
            return default

    def _ensure_cell_exists(self, row, col, editable=True):
         """Ensure a QTableWidgetItem exists at row, col."""
         try:
             # Validate row and column indices
             if row < 0 or row >= self.item_table.rowCount() or col < 0 or col >= self.item_table.columnCount():
                 self.logger.warning(f"Invalid row/col in _ensure_cell_exists: {row}/{col}")
                 return None

             item = self.item_table.item(row, col)
             if not item:
                 item = QTableWidgetItem("")
                 self.item_table.setItem(row, col, item)
                 if not editable:
                     item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                 else:
                     item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsEditable)
             return item
         except Exception as e:
             # Log the error but don't crash the application
             self.logger.error(f"Error ensuring cell exists at {row}/{col}: {str(e)}", exc_info=True)
             return None

    def calculate_net_weight(self):
        """Calculate net weight (Gross - Poly) for current row and update dependents."""
        if self.current_row < 0: return
        try:
            # Use constants
            gross = self._get_cell_float(self.current_row, COL_GROSS)
            poly = self._get_cell_float(self.current_row, COL_POLY)
            net = compute_net_weight(gross, poly)
            net_item = self._ensure_cell_exists(self.current_row, COL_NET_WT, editable=False)
            net_item.setText(f"{net:.2f}")
            self.calculate_fine()
            self.calculate_wage()
        except Exception as e:
            err_msg = f"Error calculating Net Weight: {str(e)}"
            self.logger.error(err_msg, exc_info=True)
            self._status(err_msg, 5000)
            QMessageBox.critical(self, "Calculation Error", f"{err_msg}")

    def calculate_fine(self):
        """Calculate fine weight (Net * Purity/100) for current row and update totals."""
        if self.current_row < 0: return
        try:
            # Use constants
            net = self._get_cell_float(self.current_row, COL_NET_WT)
            purity = self._get_cell_float(self.current_row, COL_PURITY)
            fine = compute_fine_weight(net, purity)
            fine_item = self._ensure_cell_exists(self.current_row, COL_FINE_WT, editable=False)
            fine_item.setText(f"{fine:.2f}")
            if hasattr(self, 'request_totals_recalc'):
                self.request_totals_recalc()
            else:
                self.calculate_totals()
        except Exception as e:
            err_msg = f"Error calculating Fine Weight: {str(e)}"
            self.logger.error(err_msg, exc_info=True)
            self._status(err_msg, 5000)
            QMessageBox.critical(self, "Calculation Error", f"{err_msg}")

    def calculate_wage(self):
        """Calculate wage based on wage type, net weight/pieces, and rate for current row."""
        if self.current_row < 0: return
        try:
            # Use constants
            net = self._get_cell_float(self.current_row, COL_NET_WT)
            wage_rate = self._get_cell_float(self.current_row, COL_WAGE_RATE)
            pieces = self._get_cell_int(self.current_row, COL_PIECES)
            code_item = self.item_table.item(self.current_row, COL_CODE)
            code = code_item.text().strip() if code_item else ""
            wage_basis = "WT"
            if code:
                repo = getattr(self.presenter, "repository", None)
                item_data = repo.fetch_item(code) if repo else None
                if item_data and item_data.get('wage_type') is not None:
                    wage_basis = item_data['wage_type']
            wage = compute_wage_amount(
                wage_basis,
                net_weight=net,
                wage_rate=wage_rate,
                pieces=pieces,
            )
            wage_item = self._ensure_cell_exists(self.current_row, COL_WAGE_AMT, editable=False)
            wage_item.setText(f"{wage:.0f}")
            if hasattr(self, 'request_totals_recalc'):
                self.request_totals_recalc()
            else:
                self.calculate_totals()
        except Exception as e:
            err_msg = f"Error calculating Wage: {str(e)}"
            self.logger.error(err_msg, exc_info=True)
            self._status(err_msg, 5000)
            QMessageBox.critical(self, "Calculation Error", f"{err_msg}")

    def show_last_balance_dialog(self):
        """Show dialog to enter last balance values."""
        from PyQt5.QtWidgets import QDialog, QVBoxLayout, QFormLayout, QDoubleSpinBox, QDialogButtonBox, QLabel

        dialog = QDialog(self)
        dialog.setWindowTitle("Enter Last Balance")
        layout = QVBoxLayout(dialog)

        form_layout = QFormLayout()

        # Silver weight input
        self.lb_silver_spin = QDoubleSpinBox()
        self.lb_silver_spin.setRange(0, 1000000)
        self.lb_silver_spin.setDecimals(2)
        self.lb_silver_spin.setSuffix(" g")
        if hasattr(self, 'last_balance_silver'):
            self.lb_silver_spin.setValue(self.last_balance_silver)
        form_layout.addRow("Silver Weight:", self.lb_silver_spin)

        # Amount input
        self.lb_amount_spin = QDoubleSpinBox()
        self.lb_amount_spin.setRange(0, 10000000)
        self.lb_amount_spin.setDecimals(0)
        self.lb_amount_spin.setPrefix("₹ ")
        if hasattr(self, 'last_balance_amount'):
            self.lb_amount_spin.setValue(self.last_balance_amount)
        form_layout.addRow("Amount:", self.lb_amount_spin)

        layout.addLayout(form_layout)

        # Add buttons
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(dialog.accept)
        button_box.rejected.connect(dialog.reject)
        layout.addWidget(button_box)

        # Show dialog
        if dialog.exec_():
            self.last_balance_silver = self.lb_silver_spin.value()
            self.last_balance_amount = self.lb_amount_spin.value()
            self.logger.info(f"Last balance set: {self.last_balance_silver:.2f} g, ₹ {self.last_balance_amount:.0f}")
            self._status(f"Last balance set: {self.last_balance_silver:.2f} g, ₹ {self.last_balance_amount:.0f}", 3000)
            self.calculate_totals()
            self._mark_unsaved()
        else:
            self._status("Last balance not changed", 2000)

    def capture_state(self) -> EstimateEntryViewState:
        """Collect the current view state for presenter computations."""
        lines = []
        for row in range(self.item_table.rowCount()):
            code_item = self.item_table.item(row, COL_CODE)
            code = code_item.text().strip() if code_item else ""
            if not code:
                continue
            try:
                type_item = self.item_table.item(row, COL_TYPE)
                category = EstimateLineCategory.from_label(type_item.text() if type_item else None)
                line = EstimateLine(
                    code=code,
                    category=category,
                    gross=self._get_cell_float(row, COL_GROSS),
                    poly=self._get_cell_float(row, COL_POLY),
                    net_weight=self._get_cell_float(row, COL_NET_WT),
                    fine_weight=self._get_cell_float(row, COL_FINE_WT),
                    wage_amount=self._get_cell_float(row, COL_WAGE_AMT),
                )
                lines.append(line)
            except Exception as row_error:
                self.logger.warning(
                    "Skipping row %s in state capture due to error: %s",
                    row + 1,
                    row_error,
                )
                continue

        try:
            silver_rate = float(self.silver_rate_spin.value())
        except Exception:
            silver_rate = 0.0

        last_balance_silver = getattr(self, 'last_balance_silver', 0.0)
        last_balance_amount = getattr(self, 'last_balance_amount', 0.0)

        return EstimateEntryViewState(
            lines=lines,
            silver_rate=silver_rate,
            last_balance_silver=last_balance_silver,
            last_balance_amount=last_balance_amount,
        )

    def apply_totals(self, totals: TotalsResult) -> None:
        """Update UI totals based on presenter computation results."""
        try:
            if hasattr(self, 'overall_gross_label'):
                self.overall_gross_label.setText(f"{totals.overall_gross:.1f}")
            if hasattr(self, 'overall_poly_label'):
                self.overall_poly_label.setText(f"{totals.overall_poly:.1f}")

            if hasattr(self, 'total_gross_label'):
                self.total_gross_label.setText(f"{totals.regular.gross:.1f}")
            if hasattr(self, 'total_net_label'):
                self.total_net_label.setText(f"{totals.regular.net:.1f}")
            if hasattr(self, 'total_fine_label'):
                self.total_fine_label.setText(f"{totals.regular.fine:.1f}")

            if hasattr(self, 'return_gross_label'):
                self.return_gross_label.setText(f"{totals.returns.gross:.1f}")
            if hasattr(self, 'return_net_label'):
                self.return_net_label.setText(f"{totals.returns.net:.1f}")
            if hasattr(self, 'return_fine_label'):
                self.return_fine_label.setText(f"{totals.returns.fine:.1f}")

            if hasattr(self, 'bar_gross_label'):
                self.bar_gross_label.setText(f"{totals.silver_bars.gross:.1f}")
            if hasattr(self, 'bar_net_label'):
                self.bar_net_label.setText(f"{totals.silver_bars.net:.1f}")
            if hasattr(self, 'bar_fine_label'):
                self.bar_fine_label.setText(f"{totals.silver_bars.fine:.1f}")

            if hasattr(self, 'net_fine_label'):
                if totals.last_balance_silver > 0:
                    self.net_fine_label.setText(
                        f"{totals.net_fine_core:.1f} + {totals.last_balance_silver:.1f} = {totals.net_fine:.1f}"
                    )
                else:
                    self.net_fine_label.setText(f"{totals.net_fine_core:.1f}")

            if hasattr(self, 'net_wage_label'):
                base_wage = self._format_currency(totals.net_wage_core)
                if totals.last_balance_amount > 0:
                    lb_wage = self._format_currency(totals.last_balance_amount)
                    total_wage = self._format_currency(totals.net_wage)
                    self.net_wage_label.setText(f"{base_wage} + {lb_wage} = {total_wage}")
                else:
                    self.net_wage_label.setText(base_wage)

            if hasattr(self, 'grand_total_label'):
                if totals.silver_rate > 0:
                    self.grand_total_label.setText(self._format_currency(totals.grand_total))
                    if hasattr(self, 'net_value_label'):
                        self.net_value_label.setText(self._format_currency(totals.net_value))
                else:
                    wage_str = self._format_currency(totals.net_wage)
                    grand_total_text = f"{totals.net_fine:.1f} g | {wage_str}"
                    self.grand_total_label.setText(grand_total_text)
                    if hasattr(self, 'net_value_label'):
                        self.net_value_label.setText("")
        except Exception as e:
            self.logger.error(
                "Error updating UI labels in apply_totals: %s", e, exc_info=True
            )
            self._status("Warning: Some UI elements could not be updated", 3000)

    def calculate_totals(self):
        """Calculate and update totals for all columns, separating categories."""
        presenter = getattr(self, 'presenter', None)
        if presenter is not None:
            try:
                presenter.refresh_totals()
                return
            except Exception as exc:
                self.logger.error(
                    "Presenter totals computation failed: %s", exc, exc_info=True
                )
                self._status("Warning: presenter totals failed, falling back.", 3500)

        state = self.capture_state()
        totals = compute_totals(
            state.lines,
            silver_rate=state.silver_rate,
            last_balance_silver=state.last_balance_silver,
            last_balance_amount=state.last_balance_amount,
        )
        self.apply_totals(totals)

    def generate_voucher(self):
        """Generate a new voucher number from the database."""
        try:
            # Temporarily disconnect the editingFinished signal to prevent triggering load_estimate
            try:
                if hasattr(self, 'safe_load_estimate'):
                    self.voucher_edit.editingFinished.disconnect(self.safe_load_estimate)
                else:
                    self.voucher_edit.editingFinished.disconnect(self.load_estimate)
            except TypeError:
                pass  # Signal wasn't connected, which is fine

            presenter = getattr(self, 'presenter', None)
            if presenter is None:
                raise RuntimeError("Estimate presenter is not available.")

            voucher_no = presenter.generate_voucher()
            if not voucher_no:
                raise RuntimeError("No voucher number could be generated.")

            self.logger.info(f"Generated new voucher: {voucher_no}")
            try:
                if hasattr(self, 'delete_estimate_button'):
                    self.delete_estimate_button.setEnabled(False)
            except Exception:
                pass
            self._estimate_loaded = False

        except Exception as e:
            self.logger.error(f"Error generating voucher number: {str(e)}", exc_info=True)
            self._status(f"Error generating voucher number", 3000)
            QMessageBox.critical(self, "Error", f"Failed to generate voucher number: {str(e)}")
        finally:
            # Reconnect the signal
            try:
                # Ensure it's not connected multiple times
                if hasattr(self, 'safe_load_estimate'):
                    self.voucher_edit.editingFinished.connect(self.safe_load_estimate)
                else:
                    self.voucher_edit.editingFinished.connect(self.load_estimate)
            except Exception as e:
                self.logger.error(f"Error reconnecting signal: {str(e)}", exc_info=True)

    def load_estimate(self):
        """Load an existing estimate by voucher number."""
        # Skip loading during initialization to prevent startup crashes
        if hasattr(self, 'initializing') and self.initializing:
            self.logger.debug("Skipping load_estimate during initialization")
            return

        presenter = getattr(self, 'presenter', None)
        if presenter is None:
            self.logger.error("Cannot load estimate: presenter is not available")
            QMessageBox.critical(
                self,
                "Error",
                "Estimate presenter is not available. Please restart the application.",
            )
            return

        try:
            voucher_no = self.voucher_edit.text().strip()
        except Exception as exc:
            self.logger.error(f"Error getting voucher number: {exc}", exc_info=True)
            QMessageBox.critical(self, "Error", f"Error accessing voucher field: {exc}")
            return

        if not voucher_no:
            return

        self.logger.info(f"Loading estimate {voucher_no}...")
        self._status(f"Loading estimate {voucher_no}...", 2000)

        try:
            loaded_estimate = presenter.load_estimate(voucher_no)
        except Exception as exc:
            self.logger.error(f"Error retrieving estimate {voucher_no}: {exc}", exc_info=True)
            QMessageBox.critical(
                self,
                "Load Error",
                f"Error retrieving estimate {voucher_no}: {exc}",
            )
            self._status(f"Error retrieving estimate {voucher_no}", 4000)
            return

        if loaded_estimate is None:
            self.logger.warning(f"Estimate voucher '{voucher_no}' not found")
            QMessageBox.warning(self, "Load Error", f"Estimate voucher '{voucher_no}' not found.")
            self._status(f"Estimate {voucher_no} not found.", 4000)
            self._estimate_loaded = False
            try:
                if hasattr(self, 'delete_estimate_button'):
                    self.delete_estimate_button.setEnabled(False)
            except Exception:
                pass
            return

        if self.apply_loaded_estimate(loaded_estimate):
            self.logger.info(f"Estimate {loaded_estimate.voucher_no} loaded successfully")
            self._status(f"Estimate {loaded_estimate.voucher_no} loaded successfully.", 3000)
        else:
            self._status(f"Estimate {voucher_no} could not be loaded.", 4000)

    def save_estimate(self):
        """Save the current estimate, handling silver bar creation/deletion."""
        voucher_no = self.voucher_edit.text().strip()
        if not voucher_no:
            self.logger.warning("Save Error: Voucher number missing")
            QMessageBox.warning(self, "Input Error", "Voucher number is required to save.")
            self._status("Save Error: Voucher number missing", 4000)
            return

        self.logger.info(f"Saving estimate {voucher_no}...")
        self._status(f"Saving estimate {voucher_no}...", 2000)
        date = self.date_edit.date().toString("yyyy-MM-dd")
        silver_rate = self.silver_rate_spin.value()

        presenter = getattr(self, 'presenter', None)
        if presenter is None:
            self.logger.error("Cannot save estimate: presenter is not available")
            QMessageBox.critical(
                self,
                "Save Error",
                "Estimate presenter is not available. Please restart the application.",
            )
            return

        items_to_save: list[SaveItem] = []
        rows_with_errors = []

        # --- Collect Item Data ---
        for row in range(self.item_table.rowCount()):
            code_item = self.item_table.item(row, COL_CODE)
            code = code_item.text().strip() if code_item else ""
            if not code:
                continue

            type_item = self.item_table.item(row, COL_TYPE)
            item_type_str = type_item.text() if type_item else "No"
            is_return = (item_type_str == "Return")
            is_silver_bar = (item_type_str == "Silver Bar")

            try:
                name_item = self.item_table.item(row, COL_ITEM_NAME)
                save_item = SaveItem(
                    code=code,
                    row_number=row + 1,
                    name=name_item.text() if name_item else "",
                    gross=self._get_cell_float(row, COL_GROSS),
                    poly=self._get_cell_float(row, COL_POLY),
                    net_wt=self._get_cell_float(row, COL_NET_WT),
                    purity=self._get_cell_float(row, COL_PURITY),
                    wage_rate=self._get_cell_float(row, COL_WAGE_RATE),
                    pieces=self._get_cell_int(row, COL_PIECES),
                    wage=self._get_cell_float(row, COL_WAGE_AMT),
                    fine=self._get_cell_float(row, COL_FINE_WT),
                    is_return=is_return,
                    is_silver_bar=is_silver_bar,
                )
                if save_item.net_wt < 0 or save_item.fine < 0 or save_item.wage < 0:
                    raise ValueError("Calculated values (Net, Fine, Wage) cannot be negative.")
                items_to_save.append(save_item)
            except Exception as e:
                rows_with_errors.append(row + 1)
                self.logger.error(f"Error processing row {row+1} for saving: {str(e)}", exc_info=True)
                continue

        if rows_with_errors:
             error_msg = f"Could not process data in row(s): {', '.join(map(str, rows_with_errors))}. These rows were skipped."
             self.logger.warning(error_msg)
             QMessageBox.warning(self, "Data Error", error_msg)
             self._status(f"Save Error: Invalid data in row(s) {', '.join(map(str, rows_with_errors))}", 5000)

        if not items_to_save:
            self.logger.warning("Save Error: No valid items to save")
            QMessageBox.warning(self, "Input Error", "No valid items found to save.")
            self._status("Save Error: No valid items to save", 4000)
            return

        # --- Recalculate Totals ---
        calc_total_gross, calc_total_net = 0.0, 0.0
        calc_net_fine, calc_net_wage = 0.0, 0.0
        calc_reg_fine, calc_reg_wage = 0.0, 0.0
        calc_bar_fine, calc_bar_wage = 0.0, 0.0
        calc_ret_fine, calc_ret_wage = 0.0, 0.0
        for item in items_to_save:
            calc_total_gross += item.gross
            calc_total_net += item.net_wt
            if item.is_return:
                calc_ret_fine += item.fine
                calc_ret_wage += item.wage
            elif item.is_silver_bar:
                calc_bar_fine += item.fine
                calc_bar_wage += item.wage
            else:
                calc_reg_fine += item.fine
                calc_reg_wage += item.wage
        calc_net_fine = calc_reg_fine - calc_bar_fine - calc_ret_fine
        calc_net_wage = calc_reg_wage - calc_bar_wage - calc_ret_wage
        # Get note from the note_edit field
        note = self.note_edit.text().strip() if hasattr(self, 'note_edit') else ''

        # Get last balance values
        last_balance_silver = getattr(self, 'last_balance_silver', 0.0)
        last_balance_amount = getattr(self, 'last_balance_amount', 0.0)

        recalculated_totals = {
            'total_gross': calc_total_gross, 'total_net': calc_total_net,
            'net_fine': calc_net_fine, 'net_wage': calc_net_wage,
            'note': note,
            'last_balance_silver': last_balance_silver,
            'last_balance_amount': last_balance_amount
        }

        regular_items = [
            item for item in items_to_save if not item.is_return and not item.is_silver_bar
        ]
        return_items = [
            item for item in items_to_save if item.is_return or item.is_silver_bar
        ]

        payload = SavePayload(
            voucher_no=voucher_no,
            date=date,
            silver_rate=silver_rate,
            note=note,
            last_balance_silver=last_balance_silver,
            last_balance_amount=last_balance_amount,
            items=tuple(items_to_save),
            regular_items=tuple(regular_items),
            return_items=tuple(return_items),
            totals=recalculated_totals,
        )

        try:
            outcome = presenter.save_estimate(payload)
        except Exception as exc:
            self.logger.error("Unexpected error saving estimate %s: %s", voucher_no, exc, exc_info=True)
            QMessageBox.critical(
                self,
                "Save Error",
                f"An unexpected error occurred while saving estimate '{voucher_no}': {exc}",
            )
            self._status("Save Error: Unexpected exception during save", 5000)
            return

        if outcome.success:
            self._status(outcome.message, 5000)
            QMessageBox.information(self, "Success", outcome.message)
            self.print_estimate()
            self.clear_form(confirm=False)
        else:
            error_detail = outcome.error_detail
            if error_detail:
                dialog_message = f"Estimate '{voucher_no}' could not be saved.\n\n{error_detail}"
                status_message = f"Save Error: {error_detail}"
            else:
                dialog_message = outcome.message
                status_message = outcome.message
            self.logger.error(
                "Save estimate %s failed: %s",
                voucher_no,
                error_detail or outcome.message,
            )
            QMessageBox.critical(self, "Save Error", dialog_message)
            self._status(status_message.replace('\n', ' ').strip(), 5000)

    def refresh_silver_rate(self):
        """Fetch the live silver rate and apply it to the field and live label."""
        btn = getattr(self, 'refresh_rate_button', None)
        try:
            if btn:
                btn.setEnabled(False)
        except Exception:
            pass
        self._status("Refreshing live silver rate…", 2000)

        def worker():
            rate = None
            try:
                from silverestimate.services.dda_rate_fetcher import fetch_broadcast_rate_exact, fetch_silver_agra_local_mohar_rate
                # Prefer broadcast for exact screen number
                try:
                    rate, market_open, _ = fetch_broadcast_rate_exact(timeout=7)
                except Exception:
                    rate = None
                if rate is None:
                    try:
                        rate, _meta = fetch_silver_agra_local_mohar_rate(timeout=7)
                    except Exception:
                        rate = None
            except Exception:
                rate = None

            from PyQt5.QtCore import QTimer
            def apply():
                try:
                    if btn:
                        btn.setEnabled(True)
                except Exception:
                    pass
                if rate is None:
                    try:
                        QMessageBox.warning(self, "Rate Refresh", "Could not fetch live silver rate. Please try again.")
                    except Exception:
                        pass
                    if hasattr(self, 'live_rate_value_label'):
                        try:
                            self.live_rate_value_label.setText("N/A /g")
                        except Exception:
                            pass
                    self._status("Live rate refresh failed", 3000)
                    return
                gram_rate = None
                try:
                    gram_rate = float(rate) / 1000.0
                except Exception:
                    gram_rate = None

                if gram_rate is None:
                    if hasattr(self, 'live_rate_value_label'):
                        try:
                            self.live_rate_value_label.setText("N/A /g")
                        except Exception:
                            pass
                    self._status("Live rate unavailable", 3000)
                    return

                # Update live badge if present (per gram display)
                if hasattr(self, 'live_rate_value_label'):
                    try:
                        locale = QLocale.system()
                        display = locale.toCurrencyString(gram_rate)
                        display = f"{display} /g"
                    except Exception:
                        try:
                            display = f"₹ {round(gram_rate, 2)} /g"
                        except Exception:
                            display = str(gram_rate)
                    try:
                        self.live_rate_value_label.setText(display)
                    except Exception:
                        pass

                self._status("Live rate refreshed (per-gram display)", 2000)

            QTimer.singleShot(0, apply)

        import threading
        threading.Thread(target=worker, daemon=True).start()

    def clear_form(self, confirm=True):
        """Reset the form to create a new estimate."""
        reply = QMessageBox.No # Default if confirm is False
        if confirm:
            reply = QMessageBox.question(self, "Confirm New Estimate",
                                         "Start a new estimate? Unsaved changes will be lost.",
                                         QMessageBox.Yes | QMessageBox.No, QMessageBox.No)

        if reply == QMessageBox.Yes or not confirm:
            self._push_unsaved_block()
            self.item_table.blockSignals(True)
            self.processing_cell = True
            cleared = False
            try:
                self.voucher_edit.clear()
                self.generate_voucher()
                self.date_edit.setDate(QDate.currentDate())
                self.silver_rate_spin.setValue(0)
                if hasattr(self, 'note_edit'):
                    self.note_edit.clear()
                # Reset last balance
                self.last_balance_silver = 0.0
                self.last_balance_amount = 0.0
                if self.return_mode:
                    self.toggle_return_mode()
                if self.silver_bar_mode:
                    self.toggle_silver_bar_mode()
                self.mode_indicator_label.setText("Mode: Regular")
                self.mode_indicator_label.setStyleSheet("font-weight: bold;")
                self._update_mode_tooltip()

                while self.item_table.rowCount() > 0:
                    self.item_table.removeRow(0)
                self.add_empty_row()
                self.calculate_totals()
                self._status("New estimate form cleared.", 3000)
                cleared = True
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Error clearing form: {e}\n{traceback.format_exc()}")
                self._status("Error clearing form.", 4000)
            finally:
                self.processing_cell = False
                self.item_table.blockSignals(False)
                QTimer.singleShot(50, lambda: self.focus_on_code_column(0))
                # Disable delete button when starting a new/unsaved estimate
                self._estimate_loaded = False
                try:
                    if hasattr(self, 'delete_estimate_button'):
                        self.delete_estimate_button.setEnabled(False)
                except Exception:
                    pass
                self._pop_unsaved_block()
            if cleared:
                self._set_unsaved(False, force=True)

    def show_history(self):
        """Show the estimate history dialog."""
        presenter = getattr(self, 'presenter', None)
        if presenter is None:
            QMessageBox.critical(
                self,
                "History Error",
                "Estimate presenter is not available. Please restart the application.",
            )
            return
        try:
            presenter.open_history()
        except Exception as exc:
            self.logger.error("Error opening estimate history: %s", exc, exc_info=True)
            QMessageBox.critical(
                self,
                "History Error",
                f"Failed to open estimate history: {exc}",
            )
            self._status("History Error: Unable to open history dialog.", 5000)

    def show_silver_bars(self):
        """Open Silver Bar Management embedded in the main window when available."""
        presenter = getattr(self, 'presenter', None)
        if presenter is None:
            QMessageBox.critical(
                self,
                "Error",
                "Estimate presenter is not available. Please restart the application.",
            )
            return
        try:
            presenter.open_silver_bar_management()
        except Exception as exc:
            self.logger.error("Error opening Silver Bar Management: %s", exc, exc_info=True)
            QMessageBox.critical(
                self,
                "Error",
                f"Failed to open Silver Bar Management: {exc}",
            )
            self._status("Error: Unable to open Silver Bar Management.", 5000)

    def _update_row_type_visuals(self, row):
        """Update the visual style of the Type column for a specific row."""
        if 0 <= row < self.item_table.rowCount():
             # Use constant
             type_item = self._ensure_cell_exists(row, COL_TYPE, editable=False)
             self.item_table.blockSignals(True)
             try:
                 self._update_row_type_visuals_direct(type_item)
                 type_item.setTextAlignment(Qt.AlignCenter)
             finally:
                 self.item_table.blockSignals(False)

    def toggle_return_mode(self):
        """Toggle return item entry mode and update UI."""
        # If switching TO return mode, ensure silver bar mode is OFF
        if not self.return_mode and self.silver_bar_mode:
            self.silver_bar_mode = False
            self.silver_bar_toggle_button.setChecked(False)
            self.silver_bar_toggle_button.setText("?? Silver Bars (Ctrl+B)")
            self.silver_bar_toggle_button.setStyleSheet(
                """
                QPushButton {
                    background-color: palette(button);
                    border: 1px solid palette(mid);
                    border-radius: 4px;
                    font-weight: normal;
                    color: palette(buttonText);
                    padding: 4px 8px;
                }
                QPushButton:hover {
                    background-color: palette(light);
                }
            """
            )

        # Toggle the mode
        self.return_mode = not self.return_mode
        self.return_toggle_button.setChecked(self.return_mode)

        # Update button appearance and Mode Label
        if self.return_mode:
            self.return_toggle_button.setText("? Return Items Mode ACTIVE (Ctrl+R)")
            self.return_toggle_button.setStyleSheet(
                """
                QPushButton {
                    background-color: #e8f4fd;
                    border: 2px solid #0066cc;
                    border-radius: 4px;
                    font-weight: bold;
                    color: #003d7a;
                    padding: 4px 8px;
                }
                QPushButton:hover {
                    background-color: #d6eafc;
                }
            """
            )
            self.mode_indicator_label.setText("Mode: Return Items")
            self.mode_indicator_label.setStyleSheet("font-weight: bold; color: #0066cc;")
            self._status("Return Items mode activated", 2000)
        else:
            self.return_toggle_button.setText("? Return Items (Ctrl+R)")
            self.return_toggle_button.setStyleSheet(
                """
                QPushButton {
                    background-color: palette(button);
                    border: 1px solid palette(mid);
                    border-radius: 4px;
                    font-weight: normal;
                    color: palette(buttonText);
                    padding: 4px 8px;
                }
                QPushButton:hover {
                    background-color: palette(light);
                }
            """
            )
            if not self.silver_bar_mode:
                self.mode_indicator_label.setText("Mode: Regular")
                self.mode_indicator_label.setStyleSheet(
                    """
                    font-weight: bold;
                    color: palette(windowText);
                    background-color: palette(window);
                    border: 1px solid palette(mid);
                    border-radius: 3px;
                    padding: 2px 6px;
                """
                )
            self._status("Return Items mode deactivated", 2000)

        # Update the current or next empty row's type column visually
        self._refresh_empty_row_type()
        self.focus_on_empty_row(update_visuals=True)
        self._update_mode_tooltip()
        self._mark_unsaved()

    def toggle_silver_bar_mode(self):
        """Toggle silver bar entry mode and update UI."""
        # If switching TO silver bar mode, ensure return mode is OFF
        if not self.silver_bar_mode and self.return_mode:
            self.return_mode = False
            self.return_toggle_button.setChecked(False)
            self.return_toggle_button.setText("? Return Items (Ctrl+R)")
            self.return_toggle_button.setStyleSheet(
                """
                QPushButton {
                    background-color: palette(button);
                    border: 1px solid palette(mid);
                    border-radius: 4px;
                    font-weight: normal;
                    color: palette(buttonText);
                    padding: 4px 8px;
                }
                QPushButton:hover {
                    background-color: palette(light);
                }
            """
            )
            # Mode label updated below

        # Toggle the mode
        self.silver_bar_mode = not self.silver_bar_mode
        self.silver_bar_toggle_button.setChecked(self.silver_bar_mode)

        # Update button appearance and Mode Label
        if self.silver_bar_mode:
            self.silver_bar_toggle_button.setText("?? Silver Bar Mode ACTIVE (Ctrl+B)")
            self.silver_bar_toggle_button.setStyleSheet(
                """
                QPushButton {
                    background-color: #fff4e6;
                    border: 2px solid #cc6600;
                    border-radius: 4px;
                    font-weight: bold;
                    color: #994d00;
                    padding: 4px 8px;
                }
                QPushButton:hover {
                    background-color: #ffe6cc;
                }
            """
            )
            self.mode_indicator_label.setText("Mode: Silver Bars")
            self.mode_indicator_label.setStyleSheet("font-weight: bold; color: #cc6600;")
            self._status("Silver Bars mode activated", 2000)
        else:
            self.silver_bar_toggle_button.setText("?? Silver Bars (Ctrl+B)")
            self.silver_bar_toggle_button.setStyleSheet(
                """
                QPushButton {
                    background-color: palette(button);
                    border: 1px solid palette(mid);
                    border-radius: 4px;
                    font-weight: normal;
                    color: palette(buttonText);
                    padding: 4px 8px;
                }
                QPushButton:hover {
                    background-color: palette(light);
                }
            """
            )
            if not self.return_mode:
                self.mode_indicator_label.setText("Mode: Regular")
                self.mode_indicator_label.setStyleSheet(
                    """
                    font-weight: bold;
                    color: palette(windowText);
                    background-color: palette(window);
                    border: 1px solid palette(mid);
                    border-radius: 3px;
                    padding: 2px 6px;
                """
                )
            self._status("Silver Bars mode deactivated", 2000)

        # Update the current or next empty row's type column visually
        self._refresh_empty_row_type()
        self.focus_on_empty_row(update_visuals=True)
        self._update_mode_tooltip()
        self._mark_unsaved()

    def _refresh_empty_row_type(self):
        """Ensure the empty row reflects the active mode."""
        try:
            table = self.item_table
            for row in range(table.rowCount()):
                code_item = table.item(row, COL_CODE)
                if code_item and code_item.text().strip():
                    continue
                type_item = table.item(row, COL_TYPE)
                if type_item is None:
                    type_item = QTableWidgetItem("")
                    type_item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
                    table.setItem(row, COL_TYPE, type_item)
                table.blockSignals(True)
                try:
                    self._update_row_type_visuals_direct(type_item)
                    type_item.setTextAlignment(Qt.AlignCenter)
                finally:
                    table.blockSignals(False)
        except Exception:
            self.logger.debug("Failed to refresh empty row type", exc_info=True)

    def focus_on_empty_row(self, update_visuals=False):
        """Find and focus the first empty row's code column. Optionally update its type visuals."""
        empty_row_index = -1
        for row in range(self.item_table.rowCount()):
            code_item = self.item_table.item(row, COL_CODE)
            if not code_item or not code_item.text().strip():
                empty_row_index = row
                break

        if empty_row_index != -1:
            if update_visuals:
                self._update_row_type_visuals(empty_row_index)
                self.calculate_totals()
            self.focus_on_code_column(empty_row_index)
        else:
            self.add_empty_row()

    def delete_current_row(self):
        """Delete the currently selected row from the table."""
        current_row = self.item_table.currentRow()
        if current_row < 0:
            self._status("Delete Row: No row selected", 3000)
            # QMessageBox.information(self, "Delete Row", "Please select a row to delete.") # Redundant if using status bar
            return

        if self.item_table.rowCount() <= 1:
            self._status("Delete Row: Cannot delete the only row", 3000)
            QMessageBox.warning(self, "Delete Row", "Cannot delete the only row.")
            return

        reply = QMessageBox.question(self, "Confirm Delete",
                                     f"Delete row {current_row + 1}?",
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)

        if reply == QMessageBox.Yes:
            self.item_table.removeRow(current_row)
            self.calculate_totals()
            self._status(f"Row {current_row + 1} deleted.", 2000)
            self._mark_unsaved()

            new_row_count = self.item_table.rowCount()
            if new_row_count == 0:
                 self.add_empty_row()
            else:
                 focus_row = min(current_row, new_row_count - 1)
                 QTimer.singleShot(0, lambda: self.focus_on_code_column(focus_row))

    def confirm_exit(self) -> bool:
        """Ask the user whether to discard unsaved changes before exiting."""
        has_changes = getattr(self, "has_unsaved_changes", None)
        if callable(has_changes):
            if not has_changes():
                return True
        elif not getattr(self, "_unsaved_changes", False):
            return True

        reply = QMessageBox.question(
            self,
            "Discard Unsaved Changes?",
            "You have unsaved changes that will be lost. Exit anyway?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            return True
        self._status("Close cancelled; current estimate still unsaved.", 2000)
        return False

    def move_to_previous_cell(self):
        """Navigate to the previous editable cell in the logical order."""
        if self.processing_cell: return

        current_col = self.current_column
        current_row = self.current_row
        prev_col = -1
        prev_row = current_row

        # Use constants
        editable_cols = [COL_CODE, COL_GROSS, COL_POLY, COL_PURITY, COL_WAGE_RATE, COL_PIECES]

        if current_col == COL_PIECES: prev_col = COL_WAGE_RATE
        elif current_col == COL_WAGE_RATE: prev_col = COL_PURITY
        elif current_col == COL_PURITY: prev_col = COL_POLY
        elif current_col == COL_POLY: prev_col = COL_GROSS
        elif current_col == COL_GROSS: prev_col = COL_CODE
        elif current_col == COL_CODE:
            if current_row > 0:
                 prev_row = current_row - 1
                 prev_col = COL_PIECES
            else:
                 prev_col = COL_CODE
                 prev_row = 0
        else: # Find nearest previous editable column in current row
             temp_col = current_col - 1
             while temp_col >= 0:
                 if temp_col in editable_cols:
                     prev_col = temp_col
                     break
                 temp_col -= 1
             if prev_col == -1: # If none found, go to previous row's last editable
                 if current_row > 0:
                     prev_row = current_row - 1
                     prev_col = COL_PIECES
                 else: # Already at start
                     prev_col = COL_CODE
                     prev_row = 0

        # Focus the calculated previous cell
        if 0 <= prev_row < self.item_table.rowCount() and 0 <= prev_col < self.item_table.columnCount():
            self.item_table.setCurrentCell(prev_row, prev_col)
            if prev_col in editable_cols:
                 item_to_edit = self.item_table.item(prev_row, prev_col)
                 if item_to_edit:
                     QTimer.singleShot(10, lambda: self.item_table.editItem(item_to_edit)) # Delay edit

    def delete_current_estimate(self):
        """Handle deletion of the currently loaded estimate."""
        voucher_no = self.voucher_edit.text().strip()
        if not voucher_no:
            QMessageBox.warning(self, "Delete Error", "No estimate voucher number entered/loaded.")
            self._status("Delete Error: No voucher number", 3000)
            return

        reply = QMessageBox.warning(self, "Confirm Delete Estimate",
                                     f"Are you sure you want to permanently delete estimate '{voucher_no}'?\n"
                                     "This action cannot be undone.",
                                     QMessageBox.Yes | QMessageBox.Cancel, QMessageBox.Cancel)

        if reply == QMessageBox.Yes:
            try:
                presenter = getattr(self, 'presenter', None)
                if presenter is None:
                    raise RuntimeError("Estimate presenter is not available.")
                success = presenter.delete_estimate(voucher_no)
                if success:
                    QMessageBox.information(self, "Success", f"Estimate '{voucher_no}' deleted successfully.")
                    self._status(f"Estimate {voucher_no} deleted.", 3000)
                    self.clear_form(confirm=False) # Clear form after deletion
                else:
                    # This might happen if the estimate was deleted between load and delete click
                    QMessageBox.warning(self, "Delete Error", f"Estimate '{voucher_no}' could not be deleted (might already be deleted).")
                    self._status(f"Delete Error: Failed for {voucher_no}", 4000)
            except Exception as e:
                QMessageBox.critical(self, "Error", f"An unexpected error occurred during deletion: {str(e)}")
                self._status(f"Delete Error: Unexpected error for {voucher_no}", 5000)

