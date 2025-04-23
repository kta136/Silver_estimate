#!/usr/bin/env python
from PyQt5.QtWidgets import (QTableWidgetItem, QMessageBox, QDialog)
from PyQt5.QtCore import Qt, QDate, QTimer, QLocale # Import QLocale
from PyQt5.QtGui import QColor

from item_selection_dialog import ItemSelectionDialog
from datetime import datetime
import traceback # For detailed error reporting

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

    # --- Helper to show status messages (assumes self has show_status method) ---
    def _status(self, message, timeout=3000):
        if hasattr(self, 'show_status') and callable(self.show_status):
            self.show_status(message, timeout)
        else: # Fallback if show_status isn't available (e.g. testing)
            print(f"Status: {message}")
    # --------------------------------------------------------------------------

    def connect_signals(self):
        """Connect UI signals to their handlers."""
        # Connect header signals
        self.voucher_edit.editingFinished.connect(self.load_estimate)
        self.generate_button.clicked.connect(self.generate_voucher)
        self.silver_rate_spin.valueChanged.connect(self.calculate_totals)

        # Connect table signals
        self.item_table.cellClicked.connect(self.cell_clicked)
        self.item_table.itemSelectionChanged.connect(self.selection_changed)
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

        # Removed connection for table_font_size_spinbox as it's moved to menu
        # if hasattr(self, 'table_font_size_spinbox'):
        #     self.table_font_size_spinbox.valueChanged.connect(self._apply_table_font_size)

        # Connect Delete This Estimate button
        if hasattr(self, 'delete_estimate_button'):
            self.delete_estimate_button.clicked.connect(self.delete_current_estimate)

    def print_estimate(self):
        """Print the current estimate."""
        from print_manager import PrintManager

        voucher_no = self.voucher_edit.text().strip()
        if not voucher_no:
            QMessageBox.warning(self, "Print Error", "Please save the estimate or generate a voucher number before printing.")
            self._status("Print Error: Voucher number missing", 4000)
            return

        self._status(f"Generating print preview for {voucher_no}...")
        # Pass the stored main window font setting
        current_print_font = getattr(self.main_window, 'print_font', None)
        print_manager = PrintManager(self.db_manager, print_font=current_print_font)
        success = print_manager.print_estimate(voucher_no, self)
        if success:
             self._status(f"Print preview for {voucher_no} generated.", 3000)
        else:
             self._status(f"Failed to generate print preview for {voucher_no}.", 4000)


    def add_empty_row(self):
        """Add an empty row to the item table."""
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

    # Helper to set item visuals based on mode (used in add_empty_row)
    def _update_row_type_visuals_direct(self, type_item):
         if self.return_mode:
             type_item.setText("Return")
             type_item.setBackground(QColor(255, 200, 200))
         elif self.silver_bar_mode:
             type_item.setText("Silver Bar")
             type_item.setBackground(QColor(200, 255, 200))
         else:
             type_item.setText("No")
             type_item.setBackground(QColor(255, 255, 255))

    def cell_clicked(self, row, column):
        """Update current position when a cell is clicked."""
        self.current_row = row
        self.current_column = column
        # Use constants for editable columns check
        editable_cols = [COL_CODE, COL_GROSS, COL_POLY, COL_PURITY, COL_WAGE_RATE, COL_PIECES]
        if column in editable_cols:
            item = self.item_table.item(row, column)
            if item and (item.flags() & Qt.ItemIsEditable):
                self.item_table.editItem(item)

    def selection_changed(self):
        """Update current position when selection changes."""
        selected_items = self.item_table.selectedItems()
        if selected_items:
            item = selected_items[0]
            self.current_row = self.item_table.row(item)
            self.current_column = self.item_table.column(item)

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
                # Potentially update totals if other columns could change? Unlikely now.
                 self.calculate_totals()

        except Exception as e:
            err_msg = f"Calculation Error: {e}"
            self._status(err_msg, 5000)
            QMessageBox.critical(self, "Calculation Error", f"{err_msg}\n{traceback.format_exc()}")
        finally:
            self.item_table.blockSignals(False)

    def move_to_next_cell(self):
        """Navigate to the next editable cell in the logical order."""
        if self.processing_cell: return

        current_col = self.current_column
        current_row = self.current_row
        next_col = -1
        next_row = current_row

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
        if 0 <= row < self.item_table.rowCount():
            self._ensure_cell_exists(row, COL_CODE) # Use constant
            self.item_table.setCurrentCell(row, COL_CODE) # Use constant
            item_to_edit = self.item_table.item(row, COL_CODE) # Use constant
            if item_to_edit:
                QTimer.singleShot(10, lambda: self.item_table.editItem(item_to_edit))


    def process_item_code(self):
        """Look up item code, populate row, or show selection dialog. Moves focus."""
        if self.processing_cell: return
        # Use constant
        if self.current_row < 0 or not self.item_table.item(self.current_row, COL_CODE): return

        code_item = self.item_table.item(self.current_row, COL_CODE)
        code = code_item.text().strip().upper() # Convert to uppercase
        code_item.setText(code) # Update cell visually

        if not code:
            QTimer.singleShot(0, self.move_to_next_cell)
            return

        item_data = self.db_manager.get_item_by_code(code)
        if item_data:
            self._status(f"Item '{code}' found.", 2000)
            self.populate_item_row(dict(item_data))
            # Use constant for target column
            QTimer.singleShot(0, lambda: self.item_table.setCurrentCell(self.current_row, COL_GROSS))
            QTimer.singleShot(10, lambda: self.item_table.editItem(self.item_table.item(self.current_row, COL_GROSS)))
        else:
            self._status(f"Item '{code}' not found, opening selection...", 3000)
            dialog = ItemSelectionDialog(self.db_manager, code, self)
            if dialog.exec_() == QDialog.Accepted:
                selected_item = dialog.get_selected_item()
                if selected_item:
                    self._status(f"Item '{selected_item['code']}' selected.", 2000)
                    self.item_table.blockSignals(True)
                    try:
                        self.item_table.item(self.current_row, COL_CODE).setText(selected_item['code']) # Use constant
                    finally:
                        self.item_table.blockSignals(False)
                    self.populate_item_row(selected_item)
                    # Use constant for target column
                    QTimer.singleShot(0, lambda: self.item_table.setCurrentCell(self.current_row, COL_GROSS))
                    QTimer.singleShot(10, lambda: self.item_table.editItem(self.item_table.item(self.current_row, COL_GROSS)))
            else:
                 self._status(f"Item selection cancelled.", 2000)
                 # Clear the invalid code? Use constant
                 # self.item_table.item(self.current_row, COL_CODE).setText("")
                 # QTimer.singleShot(0, lambda: self.item_table.setCurrentCell(self.current_row, COL_CODE))
                 # QTimer.singleShot(10, lambda: self.item_table.editItem(self.item_table.item(self.current_row, COL_CODE)))


    def populate_item_row(self, item_data):
        """Fill in item details in the current row based on item data dictionary."""
        if self.current_row < 0: return

        self.item_table.blockSignals(True)
        try:
            # Use constants for columns
            non_editable_calc_cols = [COL_NET_WT, COL_WAGE_AMT, COL_FINE_WT, COL_TYPE]
            for col in range(1, self.item_table.columnCount()):
                self._ensure_cell_exists(self.current_row, col, editable=(col not in non_editable_calc_cols))

            self.item_table.item(self.current_row, COL_ITEM_NAME).setText(item_data.get('name', ''))
            self.item_table.item(self.current_row, COL_PURITY).setText(str(item_data.get('purity', 0.0)))
            self.item_table.item(self.current_row, COL_WAGE_RATE).setText(str(item_data.get('wage_rate', 0.0)))

            pcs_item = self.item_table.item(self.current_row, COL_PIECES)
            if not pcs_item.text().strip():
                pcs_item.setText("1")

            type_item = self.item_table.item(self.current_row, COL_TYPE)
            self._update_row_type_visuals_direct(type_item)
            type_item.setTextAlignment(Qt.AlignCenter)

            self.calculate_net_weight()

        except Exception as e:
             QMessageBox.critical(self, "Error", f"Error populating row: {e}\n{traceback.format_exc()}")
             self._status(f"Error populating row {self.current_row+1}", 4000)
        finally:
            self.item_table.blockSignals(False)

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
         item = self.item_table.item(row, col)
         if not item:
             item = QTableWidgetItem("")
             self.item_table.setItem(row, col, item)
             if not editable:
                 item.setFlags(item.flags() & ~Qt.ItemIsEditable)
             else:
                 item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsEditable)
         return item


    def calculate_net_weight(self):
        """Calculate net weight (Gross - Poly) for current row and update dependents."""
        if self.current_row < 0: return
        try:
            # Use constants
            gross = self._get_cell_float(self.current_row, COL_GROSS)
            poly = self._get_cell_float(self.current_row, COL_POLY)
            net = max(0, gross - poly)
            net_item = self._ensure_cell_exists(self.current_row, COL_NET_WT, editable=False)
            net_item.setText(f"{net:.3f}")
            self.calculate_fine()
            self.calculate_wage()
        except Exception as e:
            err_msg = f"Error calculating Net Weight: {e}"
            self._status(err_msg, 5000)
            QMessageBox.critical(self, "Calculation Error", f"{err_msg}\n{traceback.format_exc()}")


    def calculate_fine(self):
        """Calculate fine weight (Net * Purity/100) for current row and update totals."""
        if self.current_row < 0: return
        try:
            # Use constants
            net = self._get_cell_float(self.current_row, COL_NET_WT)
            purity = self._get_cell_float(self.current_row, COL_PURITY)
            fine = net * (purity / 100.0) if purity > 0 else 0.0
            fine_item = self._ensure_cell_exists(self.current_row, COL_FINE_WT, editable=False)
            fine_item.setText(f"{fine:.3f}")
            self.calculate_totals()
        except Exception as e:
            err_msg = f"Error calculating Fine Weight: {e}"
            self._status(err_msg, 5000)
            QMessageBox.critical(self, "Calculation Error", f"{err_msg}\n{traceback.format_exc()}")

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
            wage_type = "WT"
            if code:
                item_data = self.db_manager.get_item_by_code(code)
                if item_data and item_data['wage_type'] is not None:
                    wage_type = item_data['wage_type'].strip().upper()
            wage = 0.0
            if wage_type == "PC":
                wage = pieces * wage_rate
            else:
                wage = net * wage_rate
            wage_item = self._ensure_cell_exists(self.current_row, COL_WAGE_AMT, editable=False)
            wage_item.setText(f"{wage:.2f}")
            self.calculate_totals()
        except Exception as e:
            err_msg = f"Error calculating Wage: {e}"
            self._status(err_msg, 5000)
            QMessageBox.critical(self, "Calculation Error", f"{err_msg}\n{traceback.format_exc()}")


    def calculate_totals(self):
        """Calculate and update totals for all columns, separating categories."""
        reg_gross, reg_net, reg_fine, reg_wage = 0.0, 0.0, 0.0, 0.0
        return_gross, return_net, return_fine, return_wage = 0.0, 0.0, 0.0, 0.0
        bar_gross, bar_net, bar_fine, bar_wage = 0.0, 0.0, 0.0, 0.0

        for row in range(self.item_table.rowCount()):
            # Use constant
            code_item = self.item_table.item(row, COL_CODE)
            if not code_item or not code_item.text().strip(): continue
            try:
                # Use constant
                type_item = self.item_table.item(row, COL_TYPE)
                item_type = type_item.text() if type_item else "No"
                # Use constants for reading values
                gross = self._get_cell_float(row, COL_GROSS)
                net = self._get_cell_float(row, COL_NET_WT)
                fine = self._get_cell_float(row, COL_FINE_WT)
                wage = self._get_cell_float(row, COL_WAGE_AMT)

                if item_type == "Return":
                    return_gross += gross; return_net += net; return_fine += fine; return_wage += wage
                elif item_type == "Silver Bar":
                    bar_gross += gross; bar_net += net; bar_fine += fine; bar_wage += wage
                else: # Regular ("No")
                    reg_gross += gross; reg_net += net; reg_fine += fine; reg_wage += wage
            except Exception as e:
                print(f"Warning: Skipping row {row+1} in total calculation due to error: {e}")
                continue

        # ... (rest of total calculations and label updates remain the same) ...
        silver_rate = self.silver_rate_spin.value()
        reg_fine_value = reg_fine * silver_rate
        return_value = return_fine * silver_rate
        bar_value = bar_fine * silver_rate
        # Subtract both Silver Bars and Returns from Regular items
        net_fine_calc = reg_fine - bar_fine - return_fine
        net_wage_calc = reg_wage - bar_wage - return_wage # Note: bar_wage is usually 0
        net_value_calc = net_fine_calc * silver_rate
        grand_total_calc = net_value_calc + net_wage_calc # Calculate Grand Total

        # Update UI labels
        self.total_gross_label.setText(f"{reg_gross:.3f}")
        self.total_net_label.setText(f"{reg_net:.3f}")
        self.total_fine_label.setText(f"{reg_fine:.3f}")
        self.fine_value_label.setText(f"{reg_fine_value:.2f}")
        self.total_wage_label.setText(f"{reg_wage:.2f}")
        self.return_gross_label.setText(f"{return_gross:.3f}")
        self.return_net_label.setText(f"{return_net:.3f}")
        self.return_fine_label.setText(f"{return_fine:.3f}")
        self.return_value_label.setText(f"{return_value:.2f}")
        self.return_wage_label.setText(f"{return_wage:.2f}")
        self.bar_gross_label.setText(f"{bar_gross:.3f}")
        self.bar_net_label.setText(f"{bar_net:.3f}")
        self.bar_fine_label.setText(f"{bar_fine:.3f}")
        self.bar_value_label.setText(f"{bar_value:.2f}")
        self.net_fine_label.setText(f"{net_fine_calc:.3f}")
        self.net_value_label.setText(f"{net_value_calc:.2f}")
        self.net_wage_label.setText(f"{net_wage_calc:.2f}")
        self.grand_total_label.setText(f"{grand_total_calc:.2f}") # Update Grand Total label


    def generate_voucher(self):
        """Generate a new voucher number from the database."""
        voucher_no = self.db_manager.generate_voucher_no()
        self.voucher_edit.setText(voucher_no)
        self._status(f"Generated new voucher: {voucher_no}", 3000)

    def load_estimate(self):
        """Load an existing estimate by voucher number."""
        voucher_no = self.voucher_edit.text().strip()
        if not voucher_no:
            return # No warning if field just cleared

        self._status(f"Loading estimate {voucher_no}...", 2000)
        estimate_data = self.db_manager.get_estimate_by_voucher(voucher_no)
        if not estimate_data:
            QMessageBox.warning(self, "Load Error", f"Estimate voucher '{voucher_no}' not found.")
            self._status(f"Estimate {voucher_no} not found.", 4000)
            return

        self.item_table.blockSignals(True)
        self.processing_cell = True
        try:
            while self.item_table.rowCount() > 0:
                self.item_table.removeRow(0)

            header = estimate_data['header']
            try:
                load_date = QDate.fromString(header.get('date', QDate.currentDate().toString("yyyy-MM-dd")), "yyyy-MM-dd")
                self.date_edit.setDate(load_date)
            except Exception as e:
                print(f"Error parsing date during load: {e}")
                self.date_edit.setDate(QDate.currentDate())

            self.silver_rate_spin.setValue(header.get('silver_rate', 0.0))

            for item in estimate_data['items']:
                row = self.item_table.rowCount()
                self.item_table.insertRow(row)
                is_return = item.get('is_return', 0) == 1
                is_silver_bar = item.get('is_silver_bar', 0) == 1

                # Populate cells using constants
                self.item_table.setItem(row, COL_CODE, QTableWidgetItem(item.get('item_code', '')))
                self.item_table.setItem(row, COL_ITEM_NAME, QTableWidgetItem(item.get('item_name', '')))
                self.item_table.setItem(row, COL_GROSS, QTableWidgetItem(str(item.get('gross', 0.0))))
                self.item_table.setItem(row, COL_POLY, QTableWidgetItem(str(item.get('poly', 0.0))))
                self.item_table.setItem(row, COL_NET_WT, QTableWidgetItem(str(item.get('net_wt', 0.0))))
                self.item_table.setItem(row, COL_PURITY, QTableWidgetItem(str(item.get('purity', 0.0))))
                self.item_table.setItem(row, COL_WAGE_RATE, QTableWidgetItem(str(item.get('wage_rate', 0.0))))
                self.item_table.setItem(row, COL_PIECES, QTableWidgetItem(str(item.get('pieces', 1))))
                self.item_table.setItem(row, COL_WAGE_AMT, QTableWidgetItem(str(item.get('wage', 0.0))))
                self.item_table.setItem(row, COL_FINE_WT, QTableWidgetItem(str(item.get('fine', 0.0))))

                # Set Type column visuals
                if is_return: type_text, bg_color = "Return", QColor(255, 200, 200)
                elif is_silver_bar: type_text, bg_color = "Silver Bar", QColor(200, 255, 200)
                else: type_text, bg_color = "No", QColor(255, 255, 255)
                type_item = QTableWidgetItem(type_text)
                type_item.setBackground(bg_color)
                type_item.setTextAlignment(Qt.AlignCenter)
                type_item.setFlags(type_item.flags() & ~Qt.ItemIsEditable)
                self.item_table.setItem(row, COL_TYPE, type_item) # Use constant

                # Ensure calculated fields non-editable using constants
                for col in [COL_NET_WT, COL_WAGE_AMT, COL_FINE_WT]:
                    cell = self.item_table.item(row, col)
                    if cell: cell.setFlags(cell.flags() & ~Qt.ItemIsEditable)

            self.add_empty_row()
            self.calculate_totals()
            self._status(f"Estimate {voucher_no} loaded successfully.", 3000)

        except Exception as e:
             QMessageBox.critical(self, "Load Error", f"An error occurred loading estimate: {e}\n{traceback.format_exc()}")
             self._status(f"Error loading estimate {voucher_no}", 5000)
        finally:
            self.processing_cell = False
            self.item_table.blockSignals(False)
            if self.item_table.rowCount() > 1:
                self.focus_on_code_column(0)
            elif self.item_table.rowCount() == 1:
                self.focus_on_code_column(0)


    def save_estimate(self):
        """Save the current estimate, recalculating totals before saving."""
        voucher_no = self.voucher_edit.text().strip()
        if not voucher_no:
            QMessageBox.warning(self, "Input Error", "Voucher number is required to save.")
            self._status("Save Error: Voucher number missing", 4000)
            return

        self._status(f"Saving estimate {voucher_no}...", 2000)
        date = self.date_edit.date().toString("yyyy-MM-dd")
        silver_rate = self.silver_rate_spin.value()

        items_to_save = []
        silver_bars_for_inventory = []
        rows_with_errors = []

        for row in range(self.item_table.rowCount()):
            # Use constant
            code_item = self.item_table.item(row, COL_CODE)
            code = code_item.text().strip() if code_item else ""
            if not code: continue

            # Use constant
            type_item = self.item_table.item(row, COL_TYPE)
            item_type_str = type_item.text() if type_item else "No"
            is_return = (item_type_str == "Return")
            is_silver_bar = (item_type_str == "Silver Bar")

            try:
                # Use constants when accessing cell data
                item_dict = {
                    'code': code,
                    'name': self.item_table.item(row, COL_ITEM_NAME).text() if self.item_table.item(row, COL_ITEM_NAME) else '',
                    'gross': self._get_cell_float(row, COL_GROSS),
                    'poly': self._get_cell_float(row, COL_POLY),
                    'net_wt': self._get_cell_float(row, COL_NET_WT),
                    'purity': self._get_cell_float(row, COL_PURITY),
                    'wage_rate': self._get_cell_float(row, COL_WAGE_RATE),
                    'pieces': self._get_cell_int(row, COL_PIECES),
                    'wage': self._get_cell_float(row, COL_WAGE_AMT),
                    'fine': self._get_cell_float(row, COL_FINE_WT),
                    'is_return': is_return,
                    'is_silver_bar': is_silver_bar
                }
                if item_dict['net_wt'] < 0 or item_dict['fine'] < 0 or item_dict['wage'] < 0:
                     raise ValueError("Calculated values (Net, Fine, Wage) cannot be negative.")

                items_to_save.append(item_dict)
                if is_silver_bar and not is_return:
                    silver_bars_for_inventory.append(item_dict)
            except Exception as e:
                rows_with_errors.append(row + 1)
                print(f"Error processing row {row+1} for saving: {e}")
                continue

        if rows_with_errors:
             QMessageBox.warning(self, "Data Error", f"Could not process data in row(s): {', '.join(map(str, rows_with_errors))}. These rows were skipped.")
             self._status(f"Save Error: Invalid data in row(s) {', '.join(map(str, rows_with_errors))}", 5000)

        if not items_to_save:
            QMessageBox.warning(self, "Input Error", "No valid items found to save.")
            self._status("Save Error: No valid items to save", 4000)
            return

        # --- Recalculate Totals ---
        # (Calculation logic itself doesn't need constants, it uses dict keys)
        calc_total_gross, calc_total_net = 0.0, 0.0
        calc_net_fine, calc_net_wage = 0.0, 0.0
        calc_reg_fine, calc_reg_wage = 0.0, 0.0
        calc_bar_fine, calc_bar_wage = 0.0, 0.0
        calc_ret_fine, calc_ret_wage = 0.0, 0.0

        for item in items_to_save:
            calc_total_gross += item['gross']
            calc_total_net += item['net_wt']
            if item['is_return']:
                calc_ret_fine += item['fine']
                calc_ret_wage += item['wage']
            elif item['is_silver_bar']:
                calc_bar_fine += item['fine']
                calc_bar_wage += item['wage']
            else:
                calc_reg_fine += item['fine']
                calc_reg_wage += item['wage']

        # Corrected net calculation: Subtract both Bars and Returns from Regular
        calc_net_fine = calc_reg_fine - calc_bar_fine - calc_ret_fine
        calc_net_wage = calc_reg_wage - calc_bar_wage - calc_ret_wage # Note: bar_wage usually 0
        recalculated_totals = {
            'total_gross': calc_total_gross, # This still represents overall gross
            'total_net': calc_total_net,     # This still represents overall net
            'net_fine': calc_net_fine,
            'net_wage': calc_net_wage
        }

        # --- Add Silver Bars to Inventory ---
        bars_added_count = 0
        bars_failed_count = 0
        if silver_bars_for_inventory:
            for bar_item in silver_bars_for_inventory:
                bar_inventory_no = bar_item['code']
                weight = bar_item['net_wt']
                purity = bar_item['purity']
                if not bar_inventory_no:
                     print(f"Skipping bar addition for item '{bar_item.get('name', 'N/A')}' due to missing code.")
                     bars_failed_count += 1
                     continue
                if self.db_manager.add_silver_bar(bar_inventory_no, weight, purity):
                    bars_added_count += 1
                else:
                    bars_failed_count += 1

        # --- Save Estimate Data ---
        regular_items_for_db = [item for item in items_to_save if not item['is_return']]
        return_items_for_db = [item for item in items_to_save if item['is_return']]
        save_success = self.db_manager.save_estimate_with_returns(
            voucher_no, date, silver_rate,
            regular_items_for_db, return_items_for_db, recalculated_totals
        )

        # --- Show Result Message ---
        if save_success:
            message_parts = [f"Estimate '{voucher_no}' saved successfully."]
            if bars_added_count > 0: message_parts.append(f"{bars_added_count} silver bar(s) added.")
            if bars_failed_count > 0: message_parts.append(f"{bars_failed_count} bar add(s) failed (check code/dupes).")
            final_message = " ".join(message_parts)
            self._status(final_message, 5000)
            QMessageBox.information(self, "Success", final_message)

            # --- Open print preview and clear form for new estimate ---
            self.print_estimate()
            self.clear_form(confirm=False) # Clear without asking confirmation
            # ---------------------------------------------------------
        else:
            err_msg = f"Failed to save estimate '{voucher_no}'. Check logs."
            QMessageBox.critical(self, "Error", err_msg)
            self._status(err_msg, 5000)


    def clear_form(self, confirm=True):
        """Reset the form to create a new estimate."""
        reply = QMessageBox.No # Default if confirm is False
        if confirm:
            reply = QMessageBox.question(self, "Confirm New Estimate",
                                         "Start a new estimate? Unsaved changes will be lost.",
                                         QMessageBox.Yes | QMessageBox.No, QMessageBox.No)

        if reply == QMessageBox.Yes or not confirm:
            self.item_table.blockSignals(True)
            self.processing_cell = True
            try:
                self.voucher_edit.clear()
                self.generate_voucher()
                self.date_edit.setDate(QDate.currentDate())
                self.silver_rate_spin.setValue(0)
                if self.return_mode: self.toggle_return_mode()
                if self.silver_bar_mode: self.toggle_silver_bar_mode()
                self.mode_indicator_label.setText("Mode: Regular")
                self.mode_indicator_label.setStyleSheet("font-weight: bold; color: #333; margin-top: 5px; margin-bottom: 5px;")

                while self.item_table.rowCount() > 0:
                    self.item_table.removeRow(0)
                self.add_empty_row()
                self.calculate_totals()
                self._status("New estimate form cleared.", 3000)
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Error clearing form: {e}\n{traceback.format_exc()}")
                self._status("Error clearing form.", 4000)
            finally:
                 self.processing_cell = False
                 self.item_table.blockSignals(False)
                 QTimer.singleShot(50, lambda: self.focus_on_code_column(0))


    def show_history(self):
        """Show the estimate history dialog."""
        from estimate_history import EstimateHistoryDialog
        # Pass the stored main_window reference, not self (EstimateEntryWidget)
        history_dialog = EstimateHistoryDialog(self.db_manager, main_window_ref=self.main_window, parent=self)
        if history_dialog.exec_() == QDialog.Accepted:
            voucher_no = history_dialog.selected_voucher
            if voucher_no:
                self.voucher_edit.setText(voucher_no)
                self.load_estimate()
                self._status(f"Loaded estimate {voucher_no} from history.", 3000)
            else:
                 self._status("No estimate selected from history.", 2000)


    def show_silver_bars(self):
        """Show the silver bar management dialog."""
        from silver_bar_management import SilverBarDialog
        silver_dialog = SilverBarDialog(self.db_manager, self)
        silver_dialog.exec_()
        self._status("Closed Silver Bar Management.", 2000)


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

    # toggle_return_mode and toggle_silver_bar_mode are now in EstimateEntryWidget

    # focus_on_empty_row is now in EstimateEntryWidget


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

            new_row_count = self.item_table.rowCount()
            if new_row_count == 0:
                 self.add_empty_row()
            else:
                 focus_row = min(current_row, new_row_count - 1)
                 QTimer.singleShot(0, lambda: self.focus_on_code_column(focus_row))


    def confirm_exit(self):
        """Placeholder for exit confirmation logic."""
        # Usually called from MainWindow's closeEvent
        # Check for unsaved changes here if needed.
        # For now, assume MainWindow handles it or there's no unsaved check.
        print("Confirm exit requested (logic likely in MainWindow)")
        # Example check (needs has_unsaved_changes method):
        # if self.has_unsaved_changes():
        #    # ... ask user ...
        #    pass
        pass

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

        # Check if the estimate actually exists before confirming deletion
        # (Optional but good practice)
        # estimate_exists = self.db_manager.get_estimate_by_voucher(voucher_no)
        # if not estimate_exists:
        #     QMessageBox.warning(self, "Delete Error", f"Estimate '{voucher_no}' not found in the database.")
        #     self._status(f"Delete Error: Estimate {voucher_no} not found", 4000)
        #     return

        reply = QMessageBox.warning(self, "Confirm Delete Estimate",
                                     f"Are you sure you want to permanently delete estimate '{voucher_no}'?\n"
                                     "This action cannot be undone.",
                                     QMessageBox.Yes | QMessageBox.Cancel, QMessageBox.Cancel)

        if reply == QMessageBox.Yes:
            try:
                success = self.db_manager.delete_single_estimate(voucher_no)
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
