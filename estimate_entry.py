#!/usr/bin/env python
# Added QStyledItemDelegate, QLineEdit, QMessageBox
from PyQt5.QtWidgets import (QWidget, QHBoxLayout, QPushButton, QShortcut, QTableWidgetItem, QCheckBox,
                             QMessageBox, QStyledItemDelegate, QLineEdit)
from PyQt5.QtCore import Qt, QTimer, QLocale, QSettings # Added QSettings
# Added QKeySequence, QColor, QDoubleValidator, QIntValidator
from PyQt5.QtGui import QKeySequence, QColor, QDoubleValidator, QIntValidator
# Import the UI class AND the Delegate class AND the Constants
from estimate_entry_ui import (
    EstimateUI,
    NumericDelegate,
    COL_CODE,
    COL_ITEM_NAME,
    COL_GROSS,
    COL_POLY,
    COL_PURITY,
    COL_WAGE_RATE,
    COL_PIECES,
)
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
        
        # Flag to prevent loading estimates during initialization
        self.initializing = True

        # Initialize tracking variables
        # Use COL_CODE for initialization consistency
        self.current_row = -1
        self.current_column = COL_CODE

        self.processing_cell = False
        self.return_mode = False
        self.silver_bar_mode = False

        # Set up UI (this creates self.item_table)
        self.setup_ui(self)

        # Hybrid column sizing state
        self._use_stretch_for_item_name = False
        self._programmatic_resizing = False

        # Restore any saved column widths for the item table (enables stretch if none saved)
        self._load_column_widths_setting()

        # If stretching is active (no saved widths), do an initial auto-stretch after layout
        if self._use_stretch_for_item_name:
            QTimer.singleShot(0, self._auto_stretch_item_name)

        # --- Set Delegates for Table Validation ---
        numeric_delegate = NumericDelegate(parent=self.item_table)

        # Apply the delegate to relevant numeric columns using constants
        self.item_table.setItemDelegateForColumn(COL_GROSS, numeric_delegate)
        self.item_table.setItemDelegateForColumn(COL_POLY, numeric_delegate)
        self.item_table.setItemDelegateForColumn(COL_PURITY, numeric_delegate)
        self.item_table.setItemDelegateForColumn(COL_WAGE_RATE, numeric_delegate)
        self.item_table.setItemDelegateForColumn(COL_PIECES, numeric_delegate)
        # -------------------------------------------

        # Make sure we start with exactly one empty row
        self.clear_all_rows()
        self.add_empty_row() # This now focuses correctly
        
        # Generate a voucher number when the widget is first created
        # Do this BEFORE connecting signals to avoid triggering load_estimate
        self.generate_voucher_silent()
        
        # Connect signals AFTER setting delegates and generating voucher
        # But DO NOT connect the load_estimate signal at startup
        self.connect_signals(skip_load_estimate=True)
        
        # Connect the load button to the safe_load_estimate method
        self.load_button.clicked.connect(self.safe_load_estimate)
        
        # Generate a new voucher number automatically at startup
        # This is now done silently without the generate button
        self.generate_voucher_silent()
        
        # Set initializing flag to false after setup is complete
        self.initializing = False

        # Column width persistence is hooked in UI setup via header.sectionResized

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

        # Load initial breakdown and final calculation font sizes
        self._load_breakdown_font_size_setting()
        self._load_final_calc_font_size_setting()


    # --- Add helper to show status messages via main window ---
    def show_status(self, message, timeout=3000):
        if self.main_window:
            self.main_window.statusBar.showMessage(message, timeout)
        else:
            import logging
            logging.getLogger(__name__).info(f"Status: {message}")
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

    # --- Column Width Persistence ---
    def _settings(self):
        return QSettings("YourCompany", "SilverEstimateApp")

    def _save_column_widths_setting(self):
        try:
            if not hasattr(self, 'item_table'):
                return
            count = self.item_table.columnCount()
            widths = [str(max(30, self.item_table.columnWidth(i))) for i in range(count)]
            value = ",".join(widths)
            self._settings().setValue("ui/estimate_table_column_widths", value)
        except Exception:
            pass

    def _load_column_widths_setting(self):
        try:
            if not hasattr(self, 'item_table'):
                return
            value = self._settings().value("ui/estimate_table_column_widths", type=str)
            if not value:
                # No saved widths → enable stretch mode for Item Name
                self._use_stretch_for_item_name = True
                return
            parts = [p.strip() for p in str(value).split(',') if p.strip().isdigit()]
            if not parts:
                # Treat as no saved widths
                self._use_stretch_for_item_name = True
                return
            count = min(self.item_table.columnCount(), len(parts))
            # Applying saved widths disables stretch mode
            self._use_stretch_for_item_name = False
            self._programmatic_resizing = True
            for i in range(count):
                w = int(parts[i])
                w = max(30, min(2000, w))
                self.item_table.setColumnWidth(i, w)
            self._programmatic_resizing = False
        except Exception:
            pass

    def _on_item_table_section_resized(self, logicalIndex, oldSize, newSize):
        # Ignore programmatic resizes
        if getattr(self, '_programmatic_resizing', False):
            return
        # User resized any column → disable stretch mode going forward
        if getattr(self, '_use_stretch_for_item_name', False):
            self._use_stretch_for_item_name = False
        # Save widths
        self._save_column_widths_setting()

    def resizeEvent(self, event):
        try:
            if getattr(self, '_use_stretch_for_item_name', False):
                self._auto_stretch_item_name()
        except Exception:
            pass
        super().resizeEvent(event)

    def _auto_stretch_item_name(self):
        """Auto-size the Item Name column to fill remaining space while in stretch mode."""
        if not hasattr(self, 'item_table'):
            return
        table = self.item_table
        viewport_width = table.viewport().width()
        if viewport_width <= 0:
            return
        # Sum widths of all columns except Item Name
        count = table.columnCount()
        other_sum = 0
        for i in range(count):
            if i == COL_ITEM_NAME:
                continue
            other_sum += table.columnWidth(i)
        # Account for vertical scrollbar if visible
        try:
            if table.verticalScrollBar().isVisible():
                other_sum += table.verticalScrollBar().width()
        except Exception:
            pass
        # Minimal width for item name
        min_width = 150
        leftover = max(min_width, viewport_width - other_sum - 4)
        self._programmatic_resizing = True
        table.setColumnWidth(COL_ITEM_NAME, leftover)
        self._programmatic_resizing = False

    def closeEvent(self, event):
        # Save column widths on close
        self._save_column_widths_setting()
        super().closeEvent(event)

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
             import logging
             logging.getLogger(__name__).warning("item_table not ready during font size load.")

    # --- Totals (Regular/Return/Silver Bar) font size handling ---
    def _apply_breakdown_font_size(self, size):
        """Apply font size to totals breakdown numeric labels (bottom-left)."""
        try:
            labels = [
                getattr(self, name, None) for name in [
                    'overall_gross_label', 'overall_poly_label',
                    'total_gross_label', 'total_net_label', 'total_fine_label',
                    'return_gross_label', 'return_net_label', 'return_fine_label',
                    'bar_gross_label', 'bar_net_label', 'bar_fine_label'
                ]
            ]
            for lbl in labels:
                if lbl is not None:
                    f = lbl.font()
                    f.setPointSize(int(size))
                    lbl.setFont(f)
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"Failed to apply breakdown font size: {e}")

    def _load_breakdown_font_size_setting(self):
        settings = QSettings("YourCompany", "SilverEstimateApp")
        default_size = 9
        min_size = 7
        max_size = 16
        size = settings.value("ui/breakdown_font_size", defaultValue=default_size, type=int)
        size = max(min_size, min(size, max_size))
        self._apply_breakdown_font_size(size)

    # --- Final Calculation font size handling ---
    def _apply_final_calc_font_size(self, size):
        """Apply font size to Final Calculation numeric labels (right side)."""
        try:
            labels = [getattr(self, name, None) for name in [
                'net_fine_label', 'net_wage_label', 'grand_total_label'
            ]]
            for lbl in labels:
                if lbl is not None:
                    f = lbl.font()
                    f.setPointSize(int(size))
                    lbl.setFont(f)
            # Ensure stylesheet for grand total does not pin font-size
            if hasattr(self, 'grand_total_label') and self.grand_total_label is not None:
                # Preserve bold + color but drop any fixed font-size
                self.grand_total_label.setStyleSheet("font-weight: bold; color: blue;")
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"Failed to apply final calculation font size: {e}")

    def _load_final_calc_font_size_setting(self):
        settings = QSettings("YourCompany", "SilverEstimateApp")
        default_size = 10
        min_size = 8
        max_size = 20
        size = settings.value("ui/final_calc_font_size", defaultValue=default_size, type=int)
        size = max(min_size, min(size, max_size))
        self._apply_final_calc_font_size(size)


    def reconnect_load_estimate(self):
        """Reconnect the editingFinished signal for the voucher edit."""
        try:
            # Ensure it's not connected multiple times
            self.voucher_edit.editingFinished.disconnect(self.load_estimate)
        except TypeError:
            pass # It wasn't connected, which is fine
            
        # Use a safer approach - connect to a wrapper method that handles exceptions
        self.voucher_edit.editingFinished.connect(self.safe_load_estimate)
        import logging
        logging.getLogger(__name__).debug("Reconnected load_estimate signal with safe wrapper.")
        
    def safe_load_estimate(self):
        """Safely load an estimate, catching any exceptions to prevent crashes."""
        # Skip loading during initialization to prevent startup crashes
        if hasattr(self, 'initializing') and self.initializing:
            self.logger.debug("Skipping load_estimate during initialization")
            return
            
        try:
            # Temporarily disconnect the signal to prevent recursive calls
            try:
                self.voucher_edit.editingFinished.disconnect(self.safe_load_estimate)
            except TypeError:
                pass  # It wasn't connected, which is fine
                
            # Call the actual load_estimate method
            self.load_estimate()
            
        except Exception as e:
            # Log the error but don't crash the application
            self.logger.error(f"Error in safe_load_estimate: {str(e)}", exc_info=True)
            self._status(f"Error loading estimate: {str(e)}", 5000)
            
            # Show error message to user
            QMessageBox.critical(self, "Load Error",
                                f"An error occurred while loading the estimate: {str(e)}\n\n"
                                "Your changes have not been saved.")
        finally:
            # Reconnect the signal
            try:
                # Ensure it's not connected multiple times
                self.voucher_edit.editingFinished.disconnect(self.safe_load_estimate)
            except TypeError:
                pass  # It wasn't connected, which is fine
                
            self.voucher_edit.editingFinished.connect(self.safe_load_estimate)

    # Removed _save_table_font_size_setting as saving is handled by MainWindow
    
    def generate_voucher_silent(self):
        """Generate a new voucher number without triggering signals."""
        try:
            # Get a new voucher number from the database
            voucher_no = self.db_manager.generate_voucher_no()
            
            # Temporarily block signals from the voucher edit field
            self.voucher_edit.blockSignals(True)
            
            # Set the voucher number
            self.voucher_edit.setText(voucher_no)
            
            # Unblock signals
            self.voucher_edit.blockSignals(False)
            
            self.logger.info(f"Generated new voucher silently: {voucher_no}")
        except Exception as e:
            self.logger.error(f"Error generating voucher number silently: {str(e)}", exc_info=True)
            # Don't show error message during initialization
            
    def connect_load_estimate_signal(self):
        """
        Manually connect the load_estimate signal.
        This should be called when the user wants to load an estimate.
        """
        try:
            # First disconnect if already connected to avoid multiple connections
            try:
                self.voucher_edit.editingFinished.disconnect(self.safe_load_estimate)
            except TypeError:
                pass  # It wasn't connected, which is fine
                
            # Connect the signal
            self.voucher_edit.editingFinished.connect(self.safe_load_estimate)
            self.logger.info("Manually connected load_estimate signal")
            
            # Add a button to the UI to load the estimate
            if not hasattr(self, 'load_button') or self.load_button is None:
                from PyQt5.QtWidgets import QPushButton
                self.load_button = QPushButton("Load Estimate", self)
                self.load_button.clicked.connect(self.safe_load_estimate)
                self.header_layout.addWidget(self.load_button)
                self.logger.info("Added Load Estimate button to UI")
        except Exception as e:
            self.logger.error(f"Error connecting load_estimate signal: {str(e)}", exc_info=True)
