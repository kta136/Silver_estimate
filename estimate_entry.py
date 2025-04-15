#!/usr/bin/env python
from PyQt5.QtWidgets import QWidget, QHBoxLayout, QPushButton, QShortcut, QTableWidgetItem, QCheckBox
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QKeySequence, QColor

from estimate_entry_ui import EstimateUI
from estimate_entry_logic import EstimateLogic


class EstimateEntryWidget(QWidget, EstimateUI, EstimateLogic):
    """Widget for silver estimate entry and management.

    This class combines the UI components and business logic for
    the silver estimation screen.
    """

    def __init__(self, db_manager):
        super().__init__()

        # Set up database manager
        self.db_manager = db_manager

        # Initialize tracking variables
        self.current_row = 0
        self.current_column = 0
        self.processing_cell = False  # Flag to prevent recursive processing
        self.return_mode = False  # Flag to track if we're adding return items
        self.silver_bar_mode = False  # Flag to track if we're adding silver bars

        # Set up UI
        self.setup_ui(self)

        # Connect signals
        self.connect_signals()

        # Generate a voucher number when the widget is first created
        self.generate_voucher()

        # Make sure we start with exactly one empty row
        self.clear_all_rows()
        self.add_empty_row()

        # Set up delete row shortcut
        self.delete_row_shortcut = QShortcut(QKeySequence("Ctrl+D"), self)
        self.delete_row_shortcut.activated.connect(self.delete_current_row)

        # Set up return items toggle shortcut
        self.return_toggle_shortcut = QShortcut(QKeySequence("Ctrl+R"), self)
        self.return_toggle_shortcut.activated.connect(self.toggle_return_mode)

        # Set up silver bar toggle shortcut
        self.silver_bar_toggle_shortcut = QShortcut(QKeySequence("Ctrl+B"), self)
        self.silver_bar_toggle_shortcut.activated.connect(self.toggle_silver_bar_mode)

        # Force focus to the first cell after initialization
        QTimer.singleShot(100, self.force_focus_to_first_cell)

    def force_focus_to_first_cell(self):
        """Force the cursor to the first cell (code column) and start editing."""
        if self.item_table.rowCount() > 0:
            self.item_table.setCurrentCell(0, 0)
            self.current_row = 0
            self.current_column = 0
            if self.item_table.item(0, 0):
                self.item_table.editItem(self.item_table.item(0, 0))

    def clear_all_rows(self):
        """Clear all rows from the table."""
        while self.item_table.rowCount() > 0:
            self.item_table.removeRow(0)

    def toggle_return_mode(self):
        """Toggle between regular and return item entry modes."""
        # Turn off silver bar mode if it's on
        if self.silver_bar_mode:
            self.silver_bar_mode = False
            self.silver_bar_toggle_button.setChecked(False)
            self.silver_bar_toggle_button.setText("Toggle Silver Bars (Ctrl+B)")
            self.silver_bar_toggle_button.setStyleSheet("")

        self.return_mode = not self.return_mode
        self.return_toggle_button.setChecked(self.return_mode)

        # Update button text and style
        if self.return_mode:
            self.return_toggle_button.setText("Return Items Mode Active (Ctrl+R)")
            self.return_toggle_button.setStyleSheet("background-color: #ffdddd;")
        else:
            self.return_toggle_button.setText("Toggle Return Items (Ctrl+R)")
            self.return_toggle_button.setStyleSheet("")

        # Focus on the first cell of the next empty row
        self.focus_on_empty_row()

    def toggle_silver_bar_mode(self):
        """Toggle between regular and silver bar entry modes."""
        # Turn off return mode if it's on
        if self.return_mode:
            self.return_mode = False
            self.return_toggle_button.setChecked(False)
            self.return_toggle_button.setText("Toggle Return Items (Ctrl+R)")
            self.return_toggle_button.setStyleSheet("")

        self.silver_bar_mode = not self.silver_bar_mode
        self.silver_bar_toggle_button.setChecked(self.silver_bar_mode)

        # Update button text and style
        if self.silver_bar_mode:
            self.silver_bar_toggle_button.setText("Silver Bar Mode Active (Ctrl+B)")
            self.silver_bar_toggle_button.setStyleSheet("background-color: #d0f0d0;")
        else:
            self.silver_bar_toggle_button.setText("Toggle Silver Bars (Ctrl+B)")
            self.silver_bar_toggle_button.setStyleSheet("")

        # Focus on the first cell of the next empty row
        self.focus_on_empty_row()

    def focus_on_empty_row(self):
        """Focus on the first empty row in the table."""
        # Look for the first empty row
        found = False
        for row in range(self.item_table.rowCount()):
            if (not self.item_table.item(row, 0) or
                    not self.item_table.item(row, 0).text().strip()):
                self.focus_on_code_column(row)
                found = True
                break

        # If no empty row found, add one
        if not found:
            self.add_empty_row()

    def keyPressEvent(self, event):
        """Handle key press events for navigation and shortcuts."""
        if event.key() == Qt.Key_Escape:
            # Confirm exit on Escape key
            self.confirm_exit()
            return

        # Toggle return mode with Ctrl+R
        if event.key() == Qt.Key_R and event.modifiers() & Qt.ControlModifier:
            self.toggle_return_mode()
            return

        # Toggle silver bar mode with Ctrl+B
        if event.key() == Qt.Key_B and event.modifiers() & Qt.ControlModifier:
            self.toggle_silver_bar_mode()
            return

        # Handle arrow key navigation
        if event.key() in [Qt.Key_Left, Qt.Key_Right, Qt.Key_Up, Qt.Key_Down]:
            current_row = self.item_table.currentRow()
            current_col = self.item_table.currentColumn()

            if event.key() == Qt.Key_Left:
                next_col = max(0, current_col - 1)
                next_row = current_row if next_col != current_col else max(0, current_row - 1)
                next_col = self.item_table.columnCount() - 1 if next_row != current_row else next_col
            elif event.key() == Qt.Key_Right:
                next_col = min(self.item_table.columnCount() - 1, current_col + 1)
                next_row = current_row if next_col != current_col else min(self.item_table.rowCount() - 1,
                                                                           current_row + 1)
                next_col = 0 if next_row != current_row else next_col
            elif event.key() == Qt.Key_Up:
                next_row = max(0, current_row - 1)
                next_col = current_col
            elif event.key() == Qt.Key_Down:
                next_row = min(self.item_table.rowCount() - 1, current_row + 1)
                next_col = current_col

            self.item_table.setCurrentCell(next_row, next_col)

            # If the cell is editable, start editing
            if self.item_table.item(next_row, next_col) and \
                    self.item_table.item(next_row, next_col).flags() & Qt.ItemIsEditable:
                self.item_table.editItem(self.item_table.item(next_row, next_col))

            return

        # Existing Enter key handling
        if event.key() == Qt.Key_Return or event.key() == Qt.Key_Enter:
            # Process Enter key manually to support keyboard navigation
            if not self.processing_cell:
                column = self.current_column
                row = self.current_row

                if column == 0:  # Code column
                    self.process_item_code()
                elif column in [2, 3]:  # Gross or Poly
                    self.calculate_net_weight()
                    self.move_to_next_cell()
                elif column == 5:  # P%
                    self.calculate_fine()
                    self.move_to_next_cell()
                elif column == 6:  # W.Rate
                    self.calculate_wage()
                    self.move_to_next_cell()
                elif column == 7:  # P/Q
                    self.calculate_wage()

                    # If this is the last column of the last row, add a new row
                    if row == self.item_table.rowCount() - 1:
                        self.add_empty_row()
                    else:
                        # Move to the first column of the next row
                        self.focus_on_code_column(row + 1)

                return

        # Let the parent handle other key events
        super().keyPressEvent(event)

    def delete_current_row(self):
        """Delete the currently selected row from the table."""
        current_row = self.item_table.currentRow()

        # Don't delete if it's the only row
        if self.item_table.rowCount() <= 1:
            return

        # Remove the row
        self.item_table.removeRow(current_row)

        # Update current position
        if current_row >= self.item_table.rowCount():
            current_row = self.item_table.rowCount() - 1

        # Focus on code column of current row
        self.focus_on_code_column(current_row)

        # Update calculations
        self.calculate_totals()

    def add_empty_row(self):
        """Add an empty row to the item table."""
        # Prevent adding more than one empty row at the end
        if self.item_table.rowCount() > 0:
            last_row = self.item_table.rowCount() - 1
            last_row_empty = True

            for col in range(self.item_table.columnCount()):
                if self.item_table.item(last_row, col) and self.item_table.item(last_row, col).text().strip():
                    last_row_empty = False
                    break

            if last_row_empty:
                return

        # Stop processing to prevent unexpected focus changes
        self.processing_cell = True

        row = self.item_table.rowCount()
        self.item_table.insertRow(row)

        # Create a new item for each cell with appropriate flags
        for col in range(self.item_table.columnCount()):
            item = QTableWidgetItem("")

            # Only make specific columns non-editable (Net Wt, Wage, Fine)
            if col in [4, 8, 9]:  # Net Wt, Wage, Fine
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)
            # For the Return/Silver Bar column, create a more visual indicator
            elif col == 10:  # Return/Silver Bar column
                if self.return_mode:
                    item.setText("Return")
                    item.setBackground(QColor(255, 200, 200))
                elif self.silver_bar_mode:
                    item.setText("Silver Bar")
                    item.setBackground(QColor(200, 255, 200))
                else:
                    item.setText("No")
                item.setTextAlignment(Qt.AlignCenter)
            else:
                # Ensure all other columns are editable
                item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsEditable)

            self.item_table.setItem(row, col, item)

        # Reset processing flag
        self.processing_cell = False

        # Use a timer to ensure UI has updated before setting focus
        QTimer.singleShot(50, lambda: self.focus_on_code_column(row))