#!/usr/bin/env python
# Added QStyledItemDelegate, QLineEdit, QMessageBox
from PyQt5.QtWidgets import (QWidget, QHBoxLayout, QPushButton, QShortcut, QTableWidgetItem, QCheckBox,
                             QMessageBox, QStyledItemDelegate, QLineEdit)
from PyQt5.QtCore import Qt, QTimer, QLocale, QSettings # Added QSettings
# Added QKeySequence, QColor, QDoubleValidator, QIntValidator
from PyQt5.QtGui import QKeySequence, QColor, QDoubleValidator, QIntValidator
# Import the UI class AND the Delegate class AND the Constants
from estimate_entry_ui import EstimateUI, NumericDelegate, COL_CODE, COL_GROSS, COL_POLY, COL_PURITY, COL_WAGE_RATE, COL_PIECES
from estimate_entry_logic import EstimateLogic


class EstimateEntryWidget(QWidget, EstimateUI, EstimateLogic):
    """Widget for silver estimate entry and management.

    Combines UI and logic, uses validation delegate, interacts with status bar.
    """

    def __init__(self, db_manager, main_window): # Accept main_window
        super().__init__()
        # Explicitly call EstimateLogic.__init__() to initialize the logger
        EstimateLogic.__init__(self)

        # Set up database manager and main window reference
        self.db_manager = db_manager
        self.main_window = main_window # Store reference

        # Initialize tracking variables
        # Use COL_CODE for initialization consistency
        self.current_row = -1
        self.current_column = COL_CODE

        self.processing_cell = False
        self.return_mode = False
        self.silver_bar_mode = False

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

        # Disconnect load_estimate initially to prevent premature trigger
        try:
            self.voucher_edit.editingFinished.disconnect(self.load_estimate)
        except TypeError: # Signal not connected yet or already disconnected
            pass

        # Generate a voucher number when the widget is first created
        self.generate_voucher()

        # Reconnect load_estimate after a short delay
        QTimer.singleShot(200, self.reconnect_load_estimate)

        # Make sure we start with exactly one empty row
        self.clear_all_rows()
        self.add_empty_row() # This now focuses correctly

        # Set up keyboard shortcuts
        self.delete_row_shortcut = QShortcut(QKeySequence("Ctrl+D"), self)
        self.delete_row_shortcut.activated.connect(self.delete_current_row)

        self.return_toggle_shortcut = QShortcut(QKeySequence(" Ctrl+R"), self)
        self.return_toggle_shortcut.activated.connect(self.toggle_return_mode)

        self.silver_bar_toggle_shortcut = QShortcut(QKeySequence("Ctrl+B"), self)
        self.silver_bar_toggle_shortcut.activated.connect(self.toggle_silver_bar_mode)

        # Add shortcuts for main actions
        self.save_shortcut = QShortcut(QKeySequence("Ctrl+S"), self)
        self.save_shortcut.activated.connect(self.save_estimate)

        self.print_shortcut = QShortcut(QKeySequence("Ctrl+P"), self)
        self.print_shortcut.activated.connect(self.print_estimate)

        self.history_shortcut = QShortcut(QKeySequence("Ctrl+H"), self)
        self.history_shortcut.activated.connect(self.show_history)

        self.new_shortcut = QShortcut(QKeySequence("Ctrl+N"), self)
        self.new_shortcut.activated.connect(self.clear_form)

        # Force focus to the first cell (Code column) after initialization
        QTimer.singleShot(100, self.force_focus_to_first_cell)

        # Load initial table font size
        self._load_table_font_size_setting()


    # --- Add helper to show status messages via main window ---
    def show_status(self, message, timeout=3000):
        if self.main_window:
            self.main_window.statusBar.showMessage(message, timeout)
        else:
            print(f"Status: {message}") # Fallback if no main window
    # --------------------------------------------------------


    def force_focus_to_first_cell(self):
        """Force the cursor to the first cell (code column) and start editing."""
        if self.item_table.rowCount() > 0:
            # Use constant
            self.item_table.setCurrentCell(0, COL_CODE)
            self.current_row = 0
            self.current_column = COL_CODE # Use constant
            if self.item_table.item(0, COL_CODE): # Use constant
                self.item_table.editItem(self.item_table.item(0, COL_CODE)) # Use constant

    # ... (rest of EstimateEntryWidget methods remain the same,
    #      as they inherit the constant-updated logic from EstimateLogic) ...
    def clear_all_rows(self):
        """Clear all rows from the table."""
        # Block signals while clearing
        self.item_table.blockSignals(True)
        while self.item_table.rowCount() > 0:
            self.item_table.removeRow(0)
        self.item_table.blockSignals(False)
        self.current_row = -1 # Reset position
        self.current_column = -1


    def toggle_return_mode(self):
        """Toggle return item entry mode and update UI."""
        # If switching TO return mode, ensure silver bar mode is OFF
        if not self.return_mode and self.silver_bar_mode:
            self.silver_bar_mode = False
            self.silver_bar_toggle_button.setChecked(False)
            # Use the tooltip text directly if needed, or just reset
            self.silver_bar_toggle_button.setText("Toggle Silver Bars (Ctrl+B)")
            self.silver_bar_toggle_button.setStyleSheet("")
            # Mode label updated below

        # Toggle the mode
        self.return_mode = not self.return_mode
        self.return_toggle_button.setChecked(self.return_mode)

        # Update button appearance and Mode Label
        if self.return_mode:
            self.return_toggle_button.setText("Return Items Mode Active (Ctrl+R)")
            self.return_toggle_button.setStyleSheet("background-color: #ffdddd; font-weight: bold;") # Added bold
            self.mode_indicator_label.setText("Mode: Return Items")
            self.mode_indicator_label.setStyleSheet("font-weight: bold; color: #c00000; margin-top: 5px; margin-bottom: 5px;") # Red color
            self.show_status("Return Items mode activated", 2000)
        else:
            self.return_toggle_button.setText("Toggle Return Items (Ctrl+R)")
            self.return_toggle_button.setStyleSheet("")
            # Only reset mode label if silver bar mode is also off
            if not self.silver_bar_mode:
                 self.mode_indicator_label.setText("Mode: Regular")
                 self.mode_indicator_label.setStyleSheet("font-weight: bold; color: #333; margin-top: 5px; margin-bottom: 5px;") # Default color
            self.show_status("Return Items mode deactivated", 2000)

        # Update the current or next empty row's type column visually
        self.focus_on_empty_row(update_visuals=True)


    def toggle_silver_bar_mode(self):
        """Toggle silver bar entry mode and update UI."""
        # If switching TO silver bar mode, ensure return mode is OFF
        if not self.silver_bar_mode and self.return_mode:
            self.return_mode = False
            self.return_toggle_button.setChecked(False)
            self.return_toggle_button.setText("Toggle Return Items (Ctrl+R)")
            self.return_toggle_button.setStyleSheet("")
             # Mode label updated below

        # Toggle the mode
        self.silver_bar_mode = not self.silver_bar_mode
        self.silver_bar_toggle_button.setChecked(self.silver_bar_mode)

        # Update button appearance and Mode Label
        if self.silver_bar_mode:
            self.silver_bar_toggle_button.setText("Silver Bar Mode Active (Ctrl+B)")
            self.silver_bar_toggle_button.setStyleSheet("background-color: #d0f0d0; font-weight: bold;") # Added bold
            self.mode_indicator_label.setText("Mode: Silver Bars")
            self.mode_indicator_label.setStyleSheet("font-weight: bold; color: #006400; margin-top: 5px; margin-bottom: 5px;") # Dark green color
            self.show_status("Silver Bars mode activated", 2000)
        else:
            self.silver_bar_toggle_button.setText("Toggle Silver Bars (Ctrl+B)")
            self.silver_bar_toggle_button.setStyleSheet("")
            # Only reset mode label if return mode is also off
            if not self.return_mode:
                 self.mode_indicator_label.setText("Mode: Regular")
                 self.mode_indicator_label.setStyleSheet("font-weight: bold; color: #333; margin-top: 5px; margin-bottom: 5px;") # Default color
            self.show_status("Silver Bars mode deactivated", 2000)

        # Update the current or next empty row's type column visually
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
                # Delegate logic to the logic class method
                 self._update_row_type_visuals(empty_row_index)
                 self.calculate_totals() # Recalculate if visuals/type might change interpretation
            self.focus_on_code_column(empty_row_index)
        else:
            # No empty row found, add one
            self.add_empty_row() # This sets visuals and focuses


    def keyPressEvent(self, event):
        """Handle key press events for navigation and shortcuts."""
        key = event.key()
        modifiers = event.modifiers()

        # --- Shortcut Handlers (already connected via QShortcut, but can intercept here too) ---
        if modifiers == Qt.ControlModifier:
            if key == Qt.Key_R:
                self.toggle_return_mode()
                event.accept()
                return
            elif key == Qt.Key_B:
                self.toggle_silver_bar_mode()
                event.accept()
                return
            elif key == Qt.Key_D:
                self.delete_current_row()
                event.accept()
                return

        # --- Standard Navigation ---
        if key in [Qt.Key_Up, Qt.Key_Down, Qt.Key_Left, Qt.Key_Right, Qt.Key_PageUp, Qt.Key_PageDown, Qt.Key_Home, Qt.Key_End]:
             super().keyPressEvent(event) # Let QTableWidget handle standard navigation
             return

        # --- Enter/Tab Key Navigation ---
        if key in [Qt.Key_Return, Qt.Key_Enter, Qt.Key_Tab]:
            # Delegate navigation logic to the logic class method
            self.move_to_next_cell()
            event.accept()
            return
        if key == Qt.Key_Backtab: # Shift+Tab
            # Delegate navigation logic to the logic class method
            self.move_to_previous_cell()
            event.accept()
            return

        # --- Escape Key ---
        if key == Qt.Key_Escape:
            # Delegate exit confirmation to the logic class method (or main window)
            self.confirm_exit()
            event.accept()
            return

        # Let the parent handle other key events (like character input)
        super().keyPressEvent(event)

    # --- Font Size Handling ---
    def _apply_table_font_size(self, size):
        """Applies the selected font size to the item table. Called by MainWindow."""
        if hasattr(self, 'item_table'):
            # Import QFont if not already imported at the top
            from PyQt5.QtGui import QFont
            font = self.item_table.font() # Get current font
            font.setPointSize(size)      # Set new point size
            self.item_table.setFont(font)
            # Adjust row heights and column widths if necessary (optional)
            self.item_table.resizeRowsToContents()
            # self.item_table.resizeColumnsToContents() # Might make columns too wide
            # Saving is now handled by MainWindow

    def _load_table_font_size_setting(self):
        """Loads the table font size from settings and applies it on init."""
        settings = QSettings("YourCompany", "SilverEstimateApp")
        # Use a reasonable default font size (e.g., 9)
        # Define default min/max here in case spinbox doesn't exist yet or range changes
        default_size = 9
        min_size = 7
        max_size = 16
        size = settings.value("ui/table_font_size", defaultValue=default_size, type=int)
        # Clamp value to a reasonable range
        size = max(min_size, min(size, max_size))

        # Apply the loaded/default size initially
        # Need to ensure item_table exists before applying
        if hasattr(self, 'item_table'):
             self._apply_table_font_size(size)
        else:
             # Should not happen if called at end of __init__, but as fallback:
             print("Warning: item_table not ready during font size load.")


    def reconnect_load_estimate(self):
        """Reconnect the editingFinished signal for the voucher edit."""
        try:
            # Ensure it's not connected multiple times
            self.voucher_edit.editingFinished.disconnect(self.load_estimate)
        except TypeError:
            pass # It wasn't connected, which is fine
        self.voucher_edit.editingFinished.connect(self.load_estimate)
        print("Reconnected load_estimate signal.") # Debug print

    # Removed _save_table_font_size_setting as saving is handled by MainWindow