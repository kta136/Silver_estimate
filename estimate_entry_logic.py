#!/usr/bin/env python
from PyQt5.QtWidgets import (QTableWidgetItem, QMessageBox, QDialog)
from PyQt5.QtCore import Qt, QDate, QTimer
from PyQt5.QtGui import QColor

from item_selection_dialog import ItemSelectionDialog
from datetime import datetime
import traceback # For detailed error reporting


class EstimateLogic:
    """Business logic for the estimate entry widget."""

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
        self.print_button.clicked.connect(self.print_estimate)  # Connect print button
        # Connect delete row button - handled in EstimateUI setup

        # Connect the return toggle button
        self.return_toggle_button.clicked.connect(self.toggle_return_mode)

        # Connect the silver bar toggle button
        self.silver_bar_toggle_button.clicked.connect(self.toggle_silver_bar_mode)

        # Connect the new buttons if they exist
        if hasattr(self, 'history_button'):
            self.history_button.clicked.connect(self.show_history)

        if hasattr(self, 'silver_bars_button'):
            self.silver_bars_button.clicked.connect(self.show_silver_bars)

    def print_estimate(self):
        """Print the current estimate."""
        from print_manager import PrintManager

        # Check if voucher number exists
        voucher_no = self.voucher_edit.text().strip()
        if not voucher_no:
            QMessageBox.warning(self, "Print Error", "Please save the estimate before printing or generate a voucher number.")
            return

        # Ensure estimate exists in DB before printing (optional but good practice)
        # if not self.db_manager.get_estimate_by_voucher(voucher_no):
        #     QMessageBox.warning(self, "Print Error", f"Estimate {voucher_no} not found in the database. Please save it first.")
        #     return

        # Create print manager instance and print estimate
        print_manager = PrintManager(self.db_manager)
        # Pass the estimate data directly if already loaded or fetch it
        # For simplicity, we let the print manager fetch it using the voucher_no
        print_manager.print_estimate(voucher_no, self)

    def add_empty_row(self):
        """Add an empty row to the item table."""
        # Prevent adding more than one empty row at the end
        if self.item_table.rowCount() > 0:
            last_row = self.item_table.rowCount() - 1
            is_last_row_empty = True

            # Check if the Code cell in the last row is empty or non-existent
            last_code_item = self.item_table.item(last_row, 0)
            if last_code_item and last_code_item.text().strip():
                is_last_row_empty = False

            if is_last_row_empty:
                # If the last row is already empty, just focus it
                QTimer.singleShot(0, lambda: self.focus_on_code_column(last_row))
                return

        # Stop processing to prevent unexpected focus changes
        self.processing_cell = True

        row = self.item_table.rowCount()
        self.item_table.insertRow(row)

        # Create a new item for each cell with appropriate flags
        for col in range(self.item_table.columnCount()):
            item = QTableWidgetItem("")

            # Make calculated columns non-editable (Net Wt, Wage, Fine)
            if col in [4, 8, 9]:
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)
            # For the Type column, set based on current mode
            elif col == 10: # Type column
                if self.return_mode:
                    item.setText("Return")
                    item.setBackground(QColor(255, 200, 200))
                elif self.silver_bar_mode:
                    item.setText("Silver Bar")
                    item.setBackground(QColor(200, 255, 200))
                else:
                    item.setText("No") # Default is regular item
                item.setTextAlignment(Qt.AlignCenter)
                item.setFlags(item.flags() & ~Qt.ItemIsEditable) # Type column is not directly editable
            else:
                # Ensure all other necessary columns are editable
                item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsEditable)

            self.item_table.setItem(row, col, item)

        # Reset processing flag
        self.processing_cell = False

        # Use a timer to ensure UI has updated before setting focus
        QTimer.singleShot(50, lambda: self.focus_on_code_column(row))

    def cell_clicked(self, row, column):
        """Update current position when a cell is clicked."""
        self.current_row = row
        self.current_column = column

        # Auto-start editing for editable cells on click
        # Editable columns: Code(0), Gross(2), Poly(3), Purity(5), W.Rate(6), Pieces(7)
        if column in [0, 2, 3, 5, 6, 7]:
            item = self.item_table.item(row, column)
            if item and (item.flags() & Qt.ItemIsEditable): # Check if item exists and is editable
                self.item_table.editItem(item)

    def selection_changed(self):
        """Update current position when selection changes."""
        selected_items = self.item_table.selectedItems()
        if selected_items:
            # If multiple cells are selected (e.g., by dragging), use the first one
            item = selected_items[0]
            self.current_row = self.item_table.row(item)
            self.current_column = self.item_table.column(item)

    def handle_cell_changed(self, row, column):
        """Handle cell value changes with direct calculation for weight fields and purity."""
        if self.processing_cell:
            return

        # Update current position just in case
        self.current_row = row
        self.current_column = column

        # Block signals temporarily to prevent recursion during calculations
        self.item_table.blockSignals(True)
        try:
            # Process based on column
            if column == 0: # Code column
                self.process_item_code() # This handles its own navigation
            elif column in [2, 3]: # Gross or Poly
                self.calculate_net_weight() # Calculates net, fine, wage, totals
                QTimer.singleShot(0, self.move_to_next_cell)
            elif column == 5: # P% (Purity)
                self.calculate_fine() # Calculates fine, totals
                QTimer.singleShot(0, self.move_to_next_cell)
            elif column == 6: # W.Rate
                self.calculate_wage() # Calculates wage, totals
                QTimer.singleShot(0, self.move_to_next_cell)
            elif column == 7: # P/Q (Pieces)
                self.calculate_wage() # Calculates wage, totals
                # If this is the last row, add a new one automatically
                if row == self.item_table.rowCount() - 1:
                     # Add row only if Code field is filled
                    code_item = self.item_table.item(row, 0)
                    if code_item and code_item.text().strip():
                        QTimer.singleShot(10, self.add_empty_row) # Use timer to ensure wage calc finishes
                    else:
                         # If code is empty, maybe just move to next cell in same row? Or stay put?
                         # Let's stay put for now, user needs to enter code first.
                         pass
                else:
                    # Move to the first column (Code) of the next row
                    QTimer.singleShot(10, lambda: self.focus_on_code_column(row + 1))
            else:
                # For other columns, just update totals if necessary (though shouldn't happen for non-editable)
                self.calculate_totals()

        except Exception as e:
            QMessageBox.critical(self, "Calculation Error", f"An error occurred processing the cell change: {e}\n{traceback.format_exc()}")
        finally:
            # Ensure signals are unblocked
            self.item_table.blockSignals(False)

    # --- OBSOLETE Methods - Replaced by direct calls in handle_cell_changed ---
    # def process_weight_change(self, row, column): ...
    # def process_cell_change(self, row, column): ...
    # def set_cell_next_row(self, current_row): ...
    # -----------------------------------------------------------------------

    def move_to_next_cell(self):
        """Navigate to the next editable cell in the logical order."""
        if self.processing_cell: # Should not happen if called correctly
            return

        # Logical order of editable cells: 0 -> 2 -> 3 -> 5 -> 6 -> 7 -> next row's 0
        current_col = self.current_column
        current_row = self.current_row
        next_col = -1
        next_row = current_row

        if current_col == 0: next_col = 2 # Code -> Gross
        elif current_col == 2: next_col = 3 # Gross -> Poly
        elif current_col == 3: next_col = 5 # Poly -> Purity
        elif current_col == 5: next_col = 6 # Purity -> W.Rate
        elif current_col == 6: next_col = 7 # W.Rate -> Pieces
        elif current_col == 7: # Pieces -> Next row's Code
            next_row = current_row + 1
            next_col = 0
        else:
             # Should not happen from an editable cell change, but as fallback:
             next_col = (current_col + 1) % self.item_table.columnCount()
             if next_col == 0:
                 next_row = current_row + 1


        # Check if next row needs to be added
        if next_row >= self.item_table.rowCount():
             # Add row only if Code field of current last row is filled
            last_code_item = self.item_table.item(current_row, 0)
            if last_code_item and last_code_item.text().strip():
                self.add_empty_row() # This will focus the new row's code column
                return # Add_empty_row handles focus
            else:
                # Don't add row if code is missing, stay in last cell
                next_row = current_row
                next_col = current_col # Stay put


        # Focus the calculated next cell
        if 0 <= next_row < self.item_table.rowCount() and 0 <= next_col < self.item_table.columnCount():
            self.item_table.setCurrentCell(next_row, next_col)
            # Start editing if it's an editable column
            if next_col in [0, 2, 3, 5, 6, 7]:
                 item_to_edit = self.item_table.item(next_row, next_col)
                 if item_to_edit: # Check item exists
                     self.item_table.editItem(item_to_edit)


    def focus_on_code_column(self, row):
        """Focus on the code column (first column) of the specified row and start editing."""
        if 0 <= row < self.item_table.rowCount():
            self.item_table.setCurrentCell(row, 0)
            self.current_row = row
            self.current_column = 0
            item_to_edit = self.item_table.item(row, 0)
            if item_to_edit: # Check item exists
                self.item_table.editItem(item_to_edit)


    def process_item_code(self):
        """Look up item code, populate row, or show selection dialog. Moves focus."""
        if self.processing_cell: return
        if self.current_row < 0 or not self.item_table.item(self.current_row, 0): return

        code = self.item_table.item(self.current_row, 0).text().strip()
        if not code:
            # If code is cleared, maybe clear the rest of the row? Or just move?
            # For now, let's just try to move to the next cell (Gross)
            QTimer.singleShot(0, self.move_to_next_cell)
            return

        item_data = self.db_manager.get_item_by_code(code)
        if item_data:
            # Item found - populate row
            self.populate_item_row(dict(item_data)) # Convert Row object to dict
            # Move focus to Gross column (col 2)
            QTimer.singleShot(0, lambda: self.item_table.setCurrentCell(self.current_row, 2))
            item_to_edit = self.item_table.item(self.current_row, 2)
            if item_to_edit:
                QTimer.singleShot(10, lambda: self.item_table.editItem(item_to_edit))
        else:
            # Item not found - open selection dialog
            dialog = ItemSelectionDialog(self.db_manager, code, self)
            if dialog.exec_() == QDialog.Accepted:
                selected_item = dialog.get_selected_item()
                if selected_item:
                    # Block signals while setting code to prevent re-triggering
                    self.item_table.blockSignals(True)
                    try:
                        self.item_table.item(self.current_row, 0).setText(selected_item['code'])
                    finally:
                        self.item_table.blockSignals(False)

                    # Populate row with selected item data
                    self.populate_item_row(selected_item)
                    # Move focus to Gross column (col 2)
                    QTimer.singleShot(0, lambda: self.item_table.setCurrentCell(self.current_row, 2))
                    item_to_edit = self.item_table.item(self.current_row, 2)
                    if item_to_edit:
                        QTimer.singleShot(10, lambda: self.item_table.editItem(item_to_edit))
            else:
                 # Dialog cancelled - maybe clear the entered code or stay? Let's clear.
                 self.item_table.item(self.current_row, 0).setText("")
                 # Stay in the code cell for re-entry
                 QTimer.singleShot(0, lambda: self.item_table.setCurrentCell(self.current_row, 0))
                 item_to_edit = self.item_table.item(self.current_row, 0)
                 if item_to_edit:
                     QTimer.singleShot(10, lambda: self.item_table.editItem(item_to_edit))

    def populate_item_row(self, item_data):
        """Fill in item details in the current row based on item data dictionary."""
        # Assumes item_data is a dictionary-like object with keys: name, purity, wage_rate, etc.
        # This should only be called when an item is successfully found or selected.
        if self.current_row < 0: return

        self.item_table.blockSignals(True) # Block signals during population
        try:
            # Ensure cells exist (should be handled by add_empty_row)
            for col in range(1, self.item_table.columnCount()): # Start from 1 (Name)
                if not self.item_table.item(self.current_row, col):
                    cell_item = QTableWidgetItem("")
                    # Set non-editable flags for calculated/display fields
                    if col in [4, 8, 9]: item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                    if col == 10: item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                    self.item_table.setItem(self.current_row, col, cell_item)

            # Populate cells from item_data
            self.item_table.item(self.current_row, 1).setText(item_data.get('name', ''))
            self.item_table.item(self.current_row, 5).setText(str(item_data.get('purity', 0.0)))
            self.item_table.item(self.current_row, 6).setText(str(item_data.get('wage_rate', 0.0)))

            # Set default piece count if empty (or maybe always set to 1?)
            pcs_item = self.item_table.item(self.current_row, 7)
            if not pcs_item.text().strip():
                pcs_item.setText("1")

            # Set type column based on current mode (Return or Silver Bar)
            type_item = self.item_table.item(self.current_row, 10)
            if self.return_mode:
                type_item.setText("Return")
                type_item.setBackground(QColor(255, 200, 200))
            elif self.silver_bar_mode:
                type_item.setText("Silver Bar")
                type_item.setBackground(QColor(200, 255, 200))
            else:
                type_item.setText("No")
                type_item.setBackground(QColor(255, 255, 255)) # Default white BG
            type_item.setTextAlignment(Qt.AlignCenter)

            # Trigger calculations based on populated data (e.g., if default pieces=1)
            self.calculate_net_weight() # This will cascade to fine, wage, totals

        except Exception as e:
             QMessageBox.critical(self, "Error", f"Error populating row: {e}\n{traceback.format_exc()}")
        finally:
            self.item_table.blockSignals(False) # Unblock signals

    def _get_cell_float(self, row, col, default=0.0):
        """Safely get float value from a cell."""
        item = self.item_table.item(row, col)
        text = item.text().strip() if item else ""
        try:
            return float(text) if text else default
        except ValueError:
            # Optionally show a warning for invalid number format
            # QMessageBox.warning(self, "Input Error", f"Invalid number in row {row+1}, column {col+1}: '{text}'")
            return default # Return default if conversion fails

    def _get_cell_int(self, row, col, default=1):
        """Safely get integer value from a cell."""
        item = self.item_table.item(row, col)
        text = item.text().strip() if item else ""
        try:
            # Handle empty string for pieces specifically, default to 1
            return int(text) if text else default
        except ValueError:
            # Optionally show a warning
            # QMessageBox.warning(self, "Input Error", f"Invalid integer in row {row+1}, column {col+1}: '{text}'")
            return default

    def _ensure_cell_exists(self, row, col, editable=True):
         """Ensure a QTableWidgetItem exists at row, col."""
         if not self.item_table.item(row, col):
             item = QTableWidgetItem("")
             if not editable:
                 item.setFlags(item.flags() & ~Qt.ItemIsEditable)
             else:
                 # Ensure default editable flags are set if cell was missing
                 item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsEditable)
             self.item_table.setItem(row, col, item)
         return self.item_table.item(row, col)


    def calculate_net_weight(self):
        """Calculate net weight (Gross - Poly) for current row and update dependents."""
        if self.current_row < 0: return

        # No need for self.processing_cell check here if signals are blocked by caller
        try:
            gross = self._get_cell_float(self.current_row, 2) # Gross Wt
            poly = self._get_cell_float(self.current_row, 3)  # Poly Wt
            net = max(0, gross - poly)

            # Ensure Net Wt cell exists and set value
            net_item = self._ensure_cell_exists(self.current_row, 4, editable=False)
            net_item.setText(f"{net:.3f}")

            # Update dependent calculations (Fine depends on Net, Wage depends on Net or Pieces)
            self.calculate_fine() # Fine depends on Net Wt
            # Wage calculation depends on wage type (from DB) which might involve Net Wt
            self.calculate_wage()
            # No need to call calculate_totals here, as calculate_wage calls it

        except Exception as e:
            QMessageBox.critical(self, "Calculation Error", f"Error calculating Net Weight: {e}\n{traceback.format_exc()}")


    def calculate_fine(self):
        """Calculate fine weight (Net * Purity/100) for current row and update totals."""
        if self.current_row < 0: return

        try:
            net = self._get_cell_float(self.current_row, 4)    # Net Wt (already calculated)
            purity = self._get_cell_float(self.current_row, 5) # Purity %

            fine = net * (purity / 100.0) if purity > 0 else 0.0

            # Ensure Fine cell exists and set value
            fine_item = self._ensure_cell_exists(self.current_row, 9, editable=False)
            fine_item.setText(f"{fine:.3f}")

            # Update totals (Fine affects overall totals)
            self.calculate_totals()

        except Exception as e:
            QMessageBox.critical(self, "Calculation Error", f"Error calculating Fine Weight: {e}\n{traceback.format_exc()}")

    def calculate_wage(self):
        """Calculate wage based on wage type, net weight/pieces, and rate for current row."""
        if self.current_row < 0: return

        try:
            # Get potentially needed values
            net = self._get_cell_float(self.current_row, 4)       # Net Wt
            wage_rate = self._get_cell_float(self.current_row, 6) # Wage Rate
            pieces = self._get_cell_int(self.current_row, 7)      # Pieces

            # Determine Wage Type (requires DB lookup based on item code)
            code_item = self.item_table.item(self.current_row, 0)
            code = code_item.text().strip() if code_item else ""
            wage_type = "WT" # Default to Weight based

            if code:
                item_data = self.db_manager.get_item_by_code(code)
                if item_data and 'wage_type' in item_data:
                    wage_type = item_data['wage_type'].strip().upper()

            # Calculate wage based on type
            wage = 0.0
            if wage_type == "PC": # Piece based
                wage = pieces * wage_rate
            else: # Weight based (WT or any other type)
                wage = net * wage_rate

             # Ensure Wage cell exists and set value
            wage_item = self._ensure_cell_exists(self.current_row, 8, editable=False)
            wage_item.setText(f"{wage:.2f}")

            # Update totals (Wage affects overall totals)
            self.calculate_totals()

        except Exception as e:
            QMessageBox.critical(self, "Calculation Error", f"Error calculating Wage: {e}\n{traceback.format_exc()}")


    def calculate_totals(self):
        """Calculate and update totals for all columns, separating regular, return items, and silver bars."""
        # No need for processing_cell check if called correctly after changes
        # Initialize totals
        total_gross, total_net, total_fine, total_wage = 0.0, 0.0, 0.0, 0.0
        return_gross, return_net, return_fine, return_wage = 0.0, 0.0, 0.0, 0.0
        bar_gross, bar_net, bar_fine, bar_wage = 0.0, 0.0, 0.0, 0.0 # Bar wage is usually 0

        # Sum up values from all rows
        for row in range(self.item_table.rowCount()):
            # Skip truly empty rows (check code)
            code_item = self.item_table.item(row, 0)
            if not code_item or not code_item.text().strip():
                continue

            try:
                # Determine item type from the 'Type' column (column 10)
                type_item = self.item_table.item(row, 10)
                item_type = type_item.text() if type_item else "No" # Default to regular

                # Get calculated values safely
                gross = self._get_cell_float(row, 2)
                net = self._get_cell_float(row, 4)
                fine = self._get_cell_float(row, 9)
                wage = self._get_cell_float(row, 8)

                # Add to the appropriate totals
                if item_type == "Return":
                    return_gross += gross
                    return_net += net
                    return_fine += fine
                    return_wage += wage
                elif item_type == "Silver Bar":
                    bar_gross += gross
                    bar_net += net
                    bar_fine += fine
                    bar_wage += wage # Add wage here, even if typically 0
                else: # Regular item ("No" or unrecognized type)
                    total_gross += gross
                    total_net += net
                    total_fine += fine
                    total_wage += wage
            except Exception as e:
                # Log or show error for the specific row?
                print(f"Warning: Skipping row {row+1} in total calculation due to error: {e}")
                continue # Skip problematic row

        # Get silver rate
        silver_rate = self.silver_rate_spin.value()

        # Calculate fine values
        fine_value = total_fine * silver_rate
        return_value = return_fine * silver_rate
        bar_value = bar_fine * silver_rate

        # Calculate NET totals (Regular + Bars - Returns)
        # Note: Regular totals (total_*) now implicitly include non-return silver bars
        #       if we categorize based on 'Type' column only. Let's refine this.

        # Re-calculate totals by category based on Type column:
        reg_gross, reg_net, reg_fine, reg_wage = 0.0, 0.0, 0.0, 0.0 # Pure Regular
        # We already have return_gross, return_net, return_fine, return_wage
        # We already have bar_gross, bar_net, bar_fine, bar_wage (for non-return bars)

        for row in range(self.item_table.rowCount()):
            code_item = self.item_table.item(row, 0)
            if not code_item or not code_item.text().strip(): continue
            try:
                type_item = self.item_table.item(row, 10)
                item_type = type_item.text() if type_item else "No"
                gross = self._get_cell_float(row, 2)
                net = self._get_cell_float(row, 4)
                fine = self._get_cell_float(row, 9)
                wage = self._get_cell_float(row, 8)

                if item_type == "Return":
                    # Already calculated above
                    pass
                elif item_type == "Silver Bar":
                    # Already calculated above
                     pass
                else: # Regular ("No")
                    reg_gross += gross
                    reg_net += net
                    reg_fine += fine
                    reg_wage += wage
            except Exception:
                 continue # Skip row on error

        # Calculate display values based on these refined categories
        reg_fine_value = reg_fine * silver_rate
        # return_value = return_fine * silver_rate (already calculated)
        # bar_value = bar_fine * silver_rate (already calculated)

        # Calculate Net = (Regular + Bars) - Returns
        net_fine_calc = (reg_fine + bar_fine) - return_fine
        net_wage_calc = (reg_wage + bar_wage) - return_wage
        net_value_calc = net_fine_calc * silver_rate

        # Update UI labels
        # Regular Item Totals (Pure Regular)
        self.total_gross_label.setText(f"{reg_gross:.3f}")
        self.total_net_label.setText(f"{reg_net:.3f}")
        self.total_fine_label.setText(f"{reg_fine:.3f}")
        self.fine_value_label.setText(f"{reg_fine_value:.2f}") # Value of regular fine
        self.total_wage_label.setText(f"{reg_wage:.2f}")

        # Return Item Totals
        self.return_gross_label.setText(f"{return_gross:.3f}")
        self.return_net_label.setText(f"{return_net:.3f}")
        self.return_fine_label.setText(f"{return_fine:.3f}")
        self.return_value_label.setText(f"{return_value:.2f}") # Value of return fine
        self.return_wage_label.setText(f"{return_wage:.2f}")

        # Silver Bar Totals (Non-Return Bars)
        self.bar_gross_label.setText(f"{bar_gross:.3f}")
        self.bar_net_label.setText(f"{bar_net:.3f}")
        self.bar_fine_label.setText(f"{bar_fine:.3f}")
        self.bar_value_label.setText(f"{bar_value:.2f}") # Value of bar fine
        # No separate wage label for bars needed in UI usually

        # Net Totals (Overall Calculation)
        self.net_fine_label.setText(f"{net_fine_calc:.3f}")
        self.net_value_label.setText(f"{net_value_calc:.2f}")
        self.net_wage_label.setText(f"{net_wage_calc:.2f}")


    def generate_voucher(self):
        """Generate a new voucher number from the database."""
        voucher_no = self.db_manager.generate_voucher_no()
        self.voucher_edit.setText(voucher_no)
        # Optionally clear the form when generating a new voucher?
        # self.clear_form(confirm=False) # Maybe not, user might want to keep date/rate

    def load_estimate(self):
        """Load an existing estimate by voucher number."""
        voucher_no = self.voucher_edit.text().strip()
        if not voucher_no:
            # Don't clear if voucher number is simply removed
            # Maybe show a message?
            return

        estimate_data = self.db_manager.get_estimate_by_voucher(voucher_no)
        if not estimate_data:
            # If voucher doesn't exist, maybe clear the form or show warning?
            QMessageBox.warning(self, "Load Error", f"Estimate voucher '{voucher_no}' not found.")
            # Decide whether to clear:
            # self.clear_form(confirm=False)
            return

        # --- Estimate Found - Proceed to Load ---
        # Block signals during load
        self.item_table.blockSignals(True)
        self.processing_cell = True # Use flag during programmatic changes

        try:
            # Clear current table content ONLY
            while self.item_table.rowCount() > 0:
                self.item_table.removeRow(0)

            # Set header information from loaded data
            header = estimate_data['header']
            try:
                load_date = QDate.fromString(header.get('date', QDate.currentDate().toString("yyyy-MM-dd")), "yyyy-MM-dd")
                self.date_edit.setDate(load_date)
            except Exception as e:
                print(f"Error parsing date during load: {e}")
                self.date_edit.setDate(QDate.currentDate()) # Fallback

            self.silver_rate_spin.setValue(header.get('silver_rate', 0.0))

            # Add items from the estimate
            for item in estimate_data['items']:
                row = self.item_table.rowCount()
                self.item_table.insertRow(row)

                # Determine type based on loaded flags
                is_return = item.get('is_return', 0) == 1
                is_silver_bar = item.get('is_silver_bar', 0) == 1

                # Populate all cells for the row
                self.item_table.setItem(row, 0, QTableWidgetItem(item.get('item_code', '')))
                self.item_table.setItem(row, 1, QTableWidgetItem(item.get('item_name', '')))
                self.item_table.setItem(row, 2, QTableWidgetItem(str(item.get('gross', 0.0))))
                self.item_table.setItem(row, 3, QTableWidgetItem(str(item.get('poly', 0.0))))
                self.item_table.setItem(row, 4, QTableWidgetItem(str(item.get('net_wt', 0.0))))
                self.item_table.setItem(row, 5, QTableWidgetItem(str(item.get('purity', 0.0))))
                self.item_table.setItem(row, 6, QTableWidgetItem(str(item.get('wage_rate', 0.0))))
                self.item_table.setItem(row, 7, QTableWidgetItem(str(item.get('pieces', 1))))
                self.item_table.setItem(row, 8, QTableWidgetItem(str(item.get('wage', 0.0))))
                self.item_table.setItem(row, 9, QTableWidgetItem(str(item.get('fine', 0.0))))

                # Set type status and appearance based on flags
                if is_return:
                    type_text = "Return"
                    bg_color = QColor(255, 200, 200)
                elif is_silver_bar:
                    type_text = "Silver Bar"
                    bg_color = QColor(200, 255, 200)
                else:
                    type_text = "No"
                    bg_color = QColor(255, 255, 255) # Default white

                type_item = QTableWidgetItem(type_text)
                type_item.setBackground(bg_color)
                type_item.setTextAlignment(Qt.AlignCenter)
                type_item.setFlags(type_item.flags() & ~Qt.ItemIsEditable) # Type not editable
                self.item_table.setItem(row, 10, type_item)

                # Mark calculated fields as non-editable explicitly
                for col in [4, 8, 9]: # Net Wt, Wage, Fine
                    cell = self.item_table.item(row, col)
                    if cell:
                        cell.setFlags(cell.flags() & ~Qt.ItemIsEditable)

            # Add ONE empty row at the end for new entries
            self.add_empty_row() # This function handles its own flags/signals

            # Calculate totals based on loaded data
            self.calculate_totals()

        except Exception as e:
             QMessageBox.critical(self, "Load Error", f"An error occurred while loading the estimate: {e}\n{traceback.format_exc()}")
        finally:
            # Ensure flags/signals are reset
            self.processing_cell = False
            self.item_table.blockSignals(False)
            # Optional: Focus first cell of first loaded item? Or first empty row?
            if self.item_table.rowCount() > 1: # If more than just the empty row
                self.focus_on_code_column(0)
            elif self.item_table.rowCount() == 1: # Only the empty row exists
                self.focus_on_code_column(0)


    def save_estimate(self):
        """Save the current estimate, recalculating totals before saving."""
        voucher_no = self.voucher_edit.text().strip()
        if not voucher_no:
            QMessageBox.warning(self, "Input Error", "Voucher number is required to save.")
            return

        # Get header data
        date = self.date_edit.date().toString("yyyy-MM-dd")
        silver_rate = self.silver_rate_spin.value()

        # --- Collect items and flags from the table ---
        items_to_save = []
        silver_bars_for_inventory = [] # Separate list for bars to add/update in inventory

        for row in range(self.item_table.rowCount()):
            code_item = self.item_table.item(row, 0)
            code = code_item.text().strip() if code_item else ""
            if not code:  # Skip rows without a code (likely empty or incomplete)
                continue

            # Determine item type and flags
            type_item = self.item_table.item(row, 10)
            item_type_str = type_item.text() if type_item else "No"
            is_return = (item_type_str == "Return")
            is_silver_bar = (item_type_str == "Silver Bar")

            # Validate required cells exist (optional but safer)
            # ...

            try:
                item_dict = {
                    'code': code,
                    'name': self.item_table.item(row, 1).text() if self.item_table.item(row, 1) else '',
                    'gross': self._get_cell_float(row, 2),
                    'poly': self._get_cell_float(row, 3),
                    'net_wt': self._get_cell_float(row, 4),
                    'purity': self._get_cell_float(row, 5),
                    'wage_rate': self._get_cell_float(row, 6),
                    'pieces': self._get_cell_int(row, 7),
                    'wage': self._get_cell_float(row, 8),
                    'fine': self._get_cell_float(row, 9),
                    'is_return': is_return,        # Add flag
                    'is_silver_bar': is_silver_bar # Add flag
                }
                items_to_save.append(item_dict)

                # If it's a non-return silver bar, also add it to the inventory list
                if is_silver_bar and not is_return:
                    silver_bars_for_inventory.append(item_dict)

            except Exception as e:
                QMessageBox.warning(self, "Data Error", f"Error processing row {row+1} for saving: {e}. Skipping row.")
                continue # Skip problematic row

        # Check if we have any valid items to save
        if not items_to_save:
            QMessageBox.warning(self, "Input Error", "No valid items found in the table to save.")
            return

        # --- Recalculate Totals Directly from Collected Items ---
        calc_total_gross, calc_total_net = 0.0, 0.0
        calc_net_fine, calc_net_wage = 0.0, 0.0
        # More detailed breakdown for verification:
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
            else: # Regular
                calc_reg_fine += item['fine']
                calc_reg_wage += item['wage']

        calc_net_fine = (calc_reg_fine + calc_bar_fine) - calc_ret_fine
        calc_net_wage = (calc_reg_wage + calc_bar_wage) - calc_ret_wage

        recalculated_totals = {
            'total_gross': calc_total_gross, # Overall Gross
            'total_net': calc_total_net,     # Overall Net
            'net_fine': calc_net_fine,       # NET Fine (Reg+Bar - Ret)
            'net_wage': calc_net_wage        # NET Wage (Reg+Bar - Ret)
        }

        # --- Add Silver Bars to Inventory Table ---
        bars_added_count = 0
        bars_failed_count = 0
        if silver_bars_for_inventory:
            print(f"Attempting to add {len(silver_bars_for_inventory)} silver bars to inventory...")
            for bar_item in silver_bars_for_inventory:
                # Construct a unique bar number, e.g., from voucher and item code? Or require manual input?
                # Using voucher-code might lead to duplicates if estimate is saved multiple times.
                # Let's assume the item 'code' for a silver bar IS the unique bar number for now.
                # IMPORTANT: This assumes silver bar items in ItemMaster have unique codes.
                bar_inventory_no = bar_item['code']
                weight = bar_item['net_wt'] # Use net weight for inventory
                purity = bar_item['purity']

                if not bar_inventory_no:
                     print(f"Skipping bar addition for item '{bar_item.get('name', 'N/A')}' due to missing code.")
                     bars_failed_count += 1
                     continue

                success = self.db_manager.add_silver_bar(bar_inventory_no, weight, purity)
                if success:
                    bars_added_count += 1
                else:
                    bars_failed_count += 1
                    # Error already printed by db_manager

        # --- Save Estimate Data (Header and Items with Flags) ---
        # Separate items again based on flags for the save function
        regular_items_for_db = [item for item in items_to_save if not item['is_return']]
        return_items_for_db = [item for item in items_to_save if item['is_return']]

        save_success = self.db_manager.save_estimate_with_returns(
            voucher_no, date, silver_rate,
            regular_items_for_db, # Includes non-return silver bars here
            return_items_for_db,   # Includes return silver bars here
            recalculated_totals    # Pass the recalculated totals
        )

        # --- Show Result Message ---
        if save_success:
            message_parts = [f"Estimate '{voucher_no}' saved successfully."]
            if bars_added_count > 0:
                message_parts.append(f"{bars_added_count} silver bar(s) added/updated in inventory.")
            if bars_failed_count > 0:
                 message_parts.append(f"{bars_failed_count} silver bar(s) failed to add (check console/logs).")
            QMessageBox.information(self, "Success", " ".join(message_parts))
        else:
            QMessageBox.critical(self, "Error", f"Failed to save estimate '{voucher_no}'. Check console/logs.")


    def clear_form(self, confirm=True): # Added confirm flag
        """Reset the form to create a new estimate."""
        if confirm:
            reply = QMessageBox.question(self, "Confirm New Estimate",
                                         "Start a new estimate? Unsaved changes will be lost.",
                                         QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if reply == QMessageBox.No:
                return

        # Block signals during programmatic clearing
        self.item_table.blockSignals(True)
        self.processing_cell = True
        try:
            # Clear voucher and generate a new one
            self.voucher_edit.clear()
            self.generate_voucher() # Sets new voucher number

            # Reset date to today
            self.date_edit.setDate(QDate.currentDate())

            # Reset silver rate
            self.silver_rate_spin.setValue(0)

            # Turn off return mode
            if self.return_mode:
                self.toggle_return_mode() # Call toggle to handle UI changes

            # Turn off silver bar mode
            if self.silver_bar_mode:
                 self.toggle_silver_bar_mode() # Call toggle to handle UI changes

            # Clear table
            while self.item_table.rowCount() > 0:
                self.item_table.removeRow(0)

            # Add one empty row
            self.add_empty_row() # Handles its own signals/focus

            # Reset total labels (call calculate_totals on empty table)
            self.calculate_totals() # Resets labels based on empty table

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error clearing form: {e}\n{traceback.format_exc()}")
        finally:
             self.processing_cell = False
             self.item_table.blockSignals(False)
             # Ensure focus is set correctly after clearing
             QTimer.singleShot(50, lambda: self.focus_on_code_column(0))


    def show_history(self):
        """Show the estimate history dialog."""
        # Need to import EstimateHistoryDialog locally if not already globally imported
        from estimate_history import EstimateHistoryDialog
        history_dialog = EstimateHistoryDialog(self.db_manager, self)
        if history_dialog.exec_() == QDialog.Accepted:
            voucher_no = history_dialog.selected_voucher
            if voucher_no:
                self.voucher_edit.setText(voucher_no)
                self.load_estimate() # Load the selected estimate


    def show_silver_bars(self):
        """Show the silver bar management dialog."""
        # Need to import SilverBarDialog locally
        from silver_bar_management import SilverBarDialog
        silver_dialog = SilverBarDialog(self.db_manager, self)
        silver_dialog.exec_() # Dialog is modal

    def _update_row_type_visuals(self, row):
        """Update the visual style of the Type column for a specific row."""
        if 0 <= row < self.item_table.rowCount():
             type_item = self.item_table.item(row, 10)
             if not type_item: # Ensure item exists
                  type_item = QTableWidgetItem("")
                  type_item.setTextAlignment(Qt.AlignCenter)
                  type_item.setFlags(type_item.flags() & ~Qt.ItemIsEditable)
                  self.item_table.setItem(row, 10, type_item)

             self.item_table.blockSignals(True)
             try:
                 if self.return_mode:
                     type_item.setText("Return")
                     type_item.setBackground(QColor(255, 200, 200))
                 elif self.silver_bar_mode:
                     type_item.setText("Silver Bar")
                     type_item.setBackground(QColor(200, 255, 200))
                 else:
                     type_item.setText("No")
                     type_item.setBackground(QColor(255, 255, 255)) # White
             finally:
                 self.item_table.blockSignals(False)

    def toggle_return_mode(self):
        """Toggle return item entry mode and update UI."""
        # If switching TO return mode, ensure silver bar mode is OFF
        if not self.return_mode and self.silver_bar_mode:
            self.silver_bar_mode = False
            self.silver_bar_toggle_button.setChecked(False)
            self.silver_bar_toggle_button.setText("Toggle Silver Bars (Ctrl+B)")
            self.silver_bar_toggle_button.setStyleSheet("")

        # Toggle the mode
        self.return_mode = not self.return_mode
        self.return_toggle_button.setChecked(self.return_mode)

        # Update button appearance
        if self.return_mode:
            self.return_toggle_button.setText("Return Items Mode Active (Ctrl+R)")
            self.return_toggle_button.setStyleSheet("background-color: #ffdddd;")
        else:
            self.return_toggle_button.setText("Toggle Return Items (Ctrl+R)")
            self.return_toggle_button.setStyleSheet("")

        # Update the current or next empty row's type column visually
        current_row = self.current_row
        # Check if current row has data, otherwise find first empty row
        code_item = self.item_table.item(current_row, 0) if current_row >= 0 else None
        if current_row >= 0 and code_item and code_item.text().strip():
            self._update_row_type_visuals(current_row)
            self.calculate_totals() # Recalculate if current row type changed
            self.focus_on_code_column(current_row) # Keep focus
        else:
            # Find first empty row and update it
             self.focus_on_empty_row(update_visuals=True)


    def toggle_silver_bar_mode(self):
        """Toggle silver bar entry mode and update UI."""
        # If switching TO silver bar mode, ensure return mode is OFF
        if not self.silver_bar_mode and self.return_mode:
            self.return_mode = False
            self.return_toggle_button.setChecked(False)
            self.return_toggle_button.setText("Toggle Return Items (Ctrl+R)")
            self.return_toggle_button.setStyleSheet("")

        # Toggle the mode
        self.silver_bar_mode = not self.silver_bar_mode
        self.silver_bar_toggle_button.setChecked(self.silver_bar_mode)

        # Update button appearance
        if self.silver_bar_mode:
            self.silver_bar_toggle_button.setText("Silver Bar Mode Active (Ctrl+B)")
            self.silver_bar_toggle_button.setStyleSheet("background-color: #d0f0d0;")
        else:
            self.silver_bar_toggle_button.setText("Toggle Silver Bars (Ctrl+B)")
            self.silver_bar_toggle_button.setStyleSheet("")

        # Update the current or next empty row's type column visually
        current_row = self.current_row
        code_item = self.item_table.item(current_row, 0) if current_row >= 0 else None
        if current_row >= 0 and code_item and code_item.text().strip():
            self._update_row_type_visuals(current_row)
            self.calculate_totals() # Recalculate if current row type changed
            self.focus_on_code_column(current_row) # Keep focus
        else:
             # Find first empty row and update it
             self.focus_on_empty_row(update_visuals=True)

    def focus_on_empty_row(self, update_visuals=False):
        """Find and focus the first empty row's code column. Optionally update its type visuals."""
        empty_row_index = -1
        for row in range(self.item_table.rowCount()):
            code_item = self.item_table.item(row, 0)
            if not code_item or not code_item.text().strip():
                empty_row_index = row
                break

        if empty_row_index != -1:
            if update_visuals:
                 self._update_row_type_visuals(empty_row_index)
            self.focus_on_code_column(empty_row_index)
        else:
            # No empty row found, add one
             # This will also focus the new row
             self.add_empty_row()
             # The add_empty_row sets the visuals based on current mode

    def delete_current_row(self):
        """Delete the currently selected row from the table."""
        current_row = self.item_table.currentRow()
        if current_row < 0:
            QMessageBox.information(self, "Delete Row", "Please select a row to delete.")
            return

        # Prevent deleting the last row if it's the only one (empty or not)
        if self.item_table.rowCount() <= 1:
             # Optionally clear the content of the single row instead?
             # For now, just prevent deletion.
            QMessageBox.warning(self, "Delete Row", "Cannot delete the only row.")
            return

        # Confirm deletion
        reply = QMessageBox.question(self, "Confirm Delete",
                                     f"Delete row {current_row + 1}?",
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)

        if reply == QMessageBox.Yes:
            self.item_table.removeRow(current_row)

            # Recalculate totals after deletion
            self.calculate_totals()

            # Set focus appropriately
            new_row_count = self.item_table.rowCount()
            if new_row_count == 0:
                 # Should not happen if we prevent deleting the last row, but handle anyway
                 self.add_empty_row()
            else:
                 # Focus the same row index (which now contains the next item)
                 # or the new last row if the deleted one was the last.
                 focus_row = min(current_row, new_row_count - 1)
                 self.focus_on_code_column(focus_row)


    def confirm_exit(self):
        """Confirm before exiting the estimate screen (if called by main window)."""
        # This logic is usually handled by the main window's closeEvent
        # We can check for unsaved changes here if needed.
        # For simplicity, we assume the main window handles the confirmation.
        pass # Let the main window manage closing confirmation