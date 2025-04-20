#!/usr/bin/env python
from PyQt5.QtWidgets import (QWidget, QHBoxLayout, QPushButton, QShortcut, QTableWidgetItem, QCheckBox,
                             QMessageBox, QStyledItemDelegate, QLineEdit, QApplication) # Added QApplication
from PyQt5.QtCore import Qt, QTimer, QLocale
from PyQt5.QtGui import QKeySequence, QColor, QDoubleValidator, QIntValidator

# Import the UI class AND the Delegate class AND the Constants
from estimate_entry_ui import EstimateUI, NumericDelegate, COL_CODE, COL_GROSS, COL_POLY, COL_PURITY, COL_WAGE_RATE, COL_PIECES, COL_TYPE # Added COL_TYPE
from estimate_entry_logic import EstimateLogic


class EstimateEntryWidget(QWidget, EstimateUI, EstimateLogic):
    """Widget for silver estimate entry and management.

    Combines UI and logic, uses validation delegate, interacts with status bar.
    """

    def __init__(self, db_manager, main_window): # Accept main_window
        super().__init__()

        # Set up database manager and main window reference
        self.db_manager = db_manager
        self.main_window = main_window # Store reference

        # Initialize tracking variables
        self.current_row = -1; self.current_column = COL_CODE
        self.processing_cell = False
        self.return_mode = False; self.silver_bar_mode = False

        # Set up UI (this creates self.item_table)
        self.setup_ui(self)

        # --- Set Delegates for Table Validation ---
        numeric_delegate = NumericDelegate(parent=self.item_table)
        # Apply the delegate to relevant numeric columns using constants
        self.item_table.setItemDelegateForColumn(COL_GROSS, numeric_delegate)
        self.item_table.setItemDelegateForColumn(COL_POLY, numeric_delegate)
        self.item_table.setItemDelegateForColumn(COL_PURITY, numeric_delegate)
        self.item_table.setItemDelegateForColumn(COL_WAGE_RATE, numeric_delegate)
        self.item_table.setItemDelegateForColumn(COL_PIECES, numeric_delegate)
        # -------------------------------------------

        # Connect signals AFTER setting delegates
        self.connect_signals()

        # Initial setup
        self.generate_voucher()
        self.clear_all_rows(); self.add_empty_row() # Add initial empty row

        # Shortcuts
        self.delete_row_shortcut = QShortcut(QKeySequence("Ctrl+D"), self)
        self.delete_row_shortcut.activated.connect(self.delete_current_row)
        self.return_toggle_shortcut = QShortcut(QKeySequence("Ctrl+R"), self)
        self.return_toggle_shortcut.activated.connect(self.toggle_return_mode)
        self.silver_bar_toggle_shortcut = QShortcut(QKeySequence("Ctrl+B"), self)
        self.silver_bar_toggle_shortcut.activated.connect(self.toggle_silver_bar_mode)

        # Initial Focus
        QTimer.singleShot(100, self.force_focus_to_first_cell)


    # --- Status Bar Helper ---
    def show_status(self, message, timeout=3000):
        if self.main_window: self.main_window.statusBar.showMessage(message, timeout)
        else: print(f"Status: {message}") # Fallback

    def force_focus_to_first_cell(self):
        """Force the cursor to the first editable cell (code column) and start editing."""
        if self.item_table.rowCount() > 0:
            self.item_table.setCurrentCell(0, COL_CODE);
            # Setting current cell should trigger selection_changed, which updates self.current_row/col
            item = self.item_table.item(0, COL_CODE)
            # Ensure item exists before trying to edit
            if not item: item = self._ensure_cell_exists(0, COL_CODE) # Use logic method to ensure it exists
            self.item_table.editItem(item)

    def clear_all_rows(self):
        """Clear all rows from the table."""
        self.item_table.blockSignals(True)
        while self.item_table.rowCount() > 0: self.item_table.removeRow(0)
        self.item_table.blockSignals(False)
        self.current_row = -1; self.current_column = -1 # Reset position


    # --- Mode Toggles ---
    def toggle_return_mode(self):
        """Toggle return item entry mode and update UI."""
        if not self.return_mode and self.silver_bar_mode:
            self.silver_bar_mode = False; self.silver_bar_toggle_button.setChecked(False)
            self.silver_bar_toggle_button.setText("Silver Bars"); self.silver_bar_toggle_button.setStyleSheet("")
        self.return_mode = not self.return_mode; self.return_toggle_button.setChecked(self.return_mode)
        if self.return_mode:
            self.return_toggle_button.setText("Return Mode ON"); self.return_toggle_button.setStyleSheet("background-color:#ffdddd;font-weight:bold;")
            self.mode_indicator_label.setText("Mode: Return Items"); self.mode_indicator_label.setStyleSheet("font-weight:bold;color:#c00000;margin:5px;")
            self.show_status("Return Items mode activated", 2000)
        else:
            self.return_toggle_button.setText("Return Items"); self.return_toggle_button.setStyleSheet("")
            if not self.silver_bar_mode: self.mode_indicator_label.setText("Mode: Regular"); self.mode_indicator_label.setStyleSheet("font-weight:bold;color:green;margin:5px;")
            self.show_status("Return Items mode deactivated", 2000)
        self.focus_on_empty_row(update_visuals=True)

    def toggle_silver_bar_mode(self):
        """Toggle silver bar entry mode and update UI."""
        if not self.silver_bar_mode and self.return_mode:
            self.return_mode = False; self.return_toggle_button.setChecked(False)
            self.return_toggle_button.setText("Return Items"); self.return_toggle_button.setStyleSheet("")
        self.silver_bar_mode = not self.silver_bar_mode; self.silver_bar_toggle_button.setChecked(self.silver_bar_mode)
        if self.silver_bar_mode:
            self.silver_bar_toggle_button.setText("Silver Bar Mode ON"); self.silver_bar_toggle_button.setStyleSheet("background-color:#d0f0d0;font-weight:bold;")
            self.mode_indicator_label.setText("Mode: Silver Bars"); self.mode_indicator_label.setStyleSheet("font-weight:bold;color:#006400;margin:5px;")
            self.show_status("Silver Bars mode activated", 2000)
        else:
            self.silver_bar_toggle_button.setText("Silver Bars"); self.silver_bar_toggle_button.setStyleSheet("")
            if not self.return_mode: self.mode_indicator_label.setText("Mode: Regular"); self.mode_indicator_label.setStyleSheet("font-weight:bold;color:green;margin:5px;")
            self.show_status("Silver Bars mode deactivated", 2000)
        self.focus_on_empty_row(update_visuals=True)

    def focus_on_empty_row(self, update_visuals=False):
        """Find and focus the first empty row's code column."""
        empty_row = -1
        for r in range(self.item_table.rowCount()):
            code_item = self.item_table.item(r, COL_CODE)
            if not code_item or not code_item.text().strip(): empty_row = r; break
        if empty_row != -1:
            if update_visuals: self._update_row_type_visuals(empty_row); self.calculate_totals()
            self.focus_on_code_column(empty_row)
        else: self.add_empty_row()


    # --- Key Press Event Handling ---
    def keyPressEvent(self, event):
        """Handle key press events for navigation and shortcuts."""
        key = event.key()
        modifiers = event.modifiers()
        row, col = self.current_row, self.current_column

        # --- Shortcuts ---
        if modifiers == Qt.ControlModifier:
            if key == Qt.Key_R: self.toggle_return_mode(); event.accept(); return
            if key == Qt.Key_B: self.toggle_silver_bar_mode(); event.accept(); return
            if key == Qt.Key_D: self.delete_current_row(); event.accept(); return

        # --- Standard Navigation (Let QTableWidget handle Arrows, PgUp/Dn etc.) ---
        if key in [Qt.Key_Up, Qt.Key_Down, Qt.Key_Left, Qt.Key_Right, Qt.Key_PageUp, Qt.Key_PageDown, Qt.Key_Home, Qt.Key_End]:
             super().keyPressEvent(event); return

        # --- Enter/Tab/Shift+Tab Navigation ---
        if key in [Qt.Key_Return, Qt.Key_Enter, Qt.Key_Tab, Qt.Key_Backtab]:
            # Handle empty Gross/Poly before moving focus
            if col in [COL_GROSS, COL_POLY]:
                item = self.item_table.item(row, col)
                # Check both item text and current editor text if editing
                text_to_check = ""
                current_editor = self.item_table.indexWidget(self.item_table.model().index(row, col)) # Better way to get editor
                if isinstance(current_editor, QLineEdit):
                    text_to_check = current_editor.text().strip()
                elif item:
                    text_to_check = item.text().strip()

                if not text_to_check: # If it's empty
                    # Block signals to prevent cellChanged firing from this programmatic change
                    self.item_table.blockSignals(True)
                    try:
                        # Ensure item exists before setting text
                        if not item:
                            item = QTableWidgetItem("0.000")
                            self.item_table.setItem(row, col, item)
                        else:
                            item.setText("0.000")
                        # Manually trigger calculation because cellChanged is blocked
                        # Use timer to ensure calculation happens after signals are unblocked
                        QTimer.singleShot(0, self.calculate_net_weight)
                    finally:
                         self.item_table.blockSignals(False) # Ensure signals are unblocked

            # Move focus (use timer to allow potential calculation to finish)
            if key == Qt.Key_Backtab:
                QTimer.singleShot(10, self.move_to_previous_cell) # Small delay
            else: # Enter, Return, Tab
                QTimer.singleShot(10, self.move_to_next_cell) # Small delay

            event.accept()
            return

        # --- Escape Key ---
        if key == Qt.Key_Escape:
            current_editor = self.item_table.indexWidget(self.item_table.model().index(row, col))
            if isinstance(current_editor, QLineEdit):
                 # If editing, maybe just close the editor without applying changes?
                 # self.item_table.closePersistentEditor(self.item_table.item(row, col)) # Needs item
                 self.item_table.clearFocus() # Try clearing focus
                 event.accept()
                 return
            else:
                 # If not editing, proceed with confirm exit logic (if any)
                 self.confirm_exit(); event.accept(); return


        # Let parent handle other keys (like character input into editor)
        super().keyPressEvent(event)

    # Inherit calculation, save, load, add_row, delete_row, etc., from EstimateLogic
    # Inherit UI setup methods from EstimateUI