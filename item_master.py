#!/usr/bin/env python
# Removed QDoubleSpinBox, added QDoubleValidator, QLocale
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
                             QPushButton, QTableWidget, QTableWidgetItem, QHeaderView,
                             QMessageBox, QComboBox, QAbstractItemView)
from PyQt5.QtCore import Qt, pyqtSignal, QLocale # Added QLocale
from PyQt5.QtGui import QKeyEvent, QDoubleValidator # Added QDoubleValidator

class ItemMasterWidget(QWidget):
    """Widget for managing silver item catalog."""

    def __init__(self, db_manager, main_window=None): # Accept optional main_window
        super().__init__()
        self.db_manager = db_manager
        self.main_window = main_window # Store reference
        self.init_ui()
        self.load_items()

    # --- Helper to show status messages ---
    def show_status(self, message, timeout=3000):
        if self.main_window:
            self.main_window.show_status_message(message, timeout)
        else:
            import logging
            logging.getLogger(__name__).info(f"Status: {message}")
    # ------------------------------------

    def init_ui(self):
        """Initialize the user interface."""
        layout = QVBoxLayout(self)

        header_label = QLabel("Item Master")
        header_label.setStyleSheet("font-size: 16pt; font-weight: bold;")
        layout.addWidget(header_label)

        form_layout = QHBoxLayout()

        form_layout.addWidget(QLabel("Code:"))
        self.code_edit = QLineEdit()
        self.code_edit.setMaximumWidth(100)
        self.code_edit.setToolTip("Unique code for the item (e.g., CH001, SB999). Cannot be changed after adding.")
        form_layout.addWidget(self.code_edit)

        form_layout.addWidget(QLabel("Name:"))
        self.name_edit = QLineEdit()
        self.name_edit.setMinimumWidth(200)
        self.name_edit.setToolTip("Descriptive name of the item.")
        form_layout.addWidget(self.name_edit)

        # --- Purity: Replaced QDoubleSpinBox with QLineEdit + Validator ---
        form_layout.addWidget(QLabel("Purity (%):"))
        self.purity_edit = QLineEdit() # Changed from spin box
        self.purity_edit.setMaximumWidth(80) # Set a reasonable width
        self.purity_edit.setToolTip("Default silver purity percentage.") # Updated tooltip
        # Apply Validator
        # Removed upper limit (set to a large number)
        purity_validator = QDoubleValidator(0.00, 999999.99, 2, self.purity_edit)
        purity_validator.setNotation(QDoubleValidator.StandardNotation)
        purity_validator.setLocale(QLocale.system()) # Use system locale for decimal separator
        self.purity_edit.setValidator(purity_validator)
        form_layout.addWidget(self.purity_edit)
        # --------------------------------------------------------------------

        form_layout.addWidget(QLabel("Wage Type:"))
        self.wage_type_combo = QComboBox()
        self.wage_type_combo.addItems(["PC", "WT"])
        self.wage_type_combo.setToolTip("Select wage calculation method: PC (Per Piece) or WT (Per Weight/Gram).")
        form_layout.addWidget(self.wage_type_combo)

        # --- Wage Rate: Replaced QDoubleSpinBox with QLineEdit + Validator ---
        form_layout.addWidget(QLabel("Wage Rate:"))
        self.wage_rate_edit = QLineEdit() # Changed from spin box
        self.wage_rate_edit.setMaximumWidth(100) # Set a reasonable width
        self.wage_rate_edit.setToolTip("Wage rate corresponding to the selected Wage Type.")
         # Apply Validator
        rate_validator = QDoubleValidator(0.00, 100000.00, 2, self.wage_rate_edit) # Range 0+, 2 decimals
        rate_validator.setNotation(QDoubleValidator.StandardNotation)
        rate_validator.setLocale(QLocale.system()) # Use system locale
        self.wage_rate_edit.setValidator(rate_validator)
        form_layout.addWidget(self.wage_rate_edit)
        # --------------------------------------------------------------------

        form_layout.addStretch()
        layout.addLayout(form_layout)

        button_layout = QHBoxLayout()
        self.add_button = QPushButton("Add New Item")
        self.add_button.setToolTip("Add the details entered above as a new item.")
        self.add_button.clicked.connect(self.add_item)
        button_layout.addWidget(self.add_button)

        self.update_button = QPushButton("Update Selected")
        self.update_button.setToolTip("Update the currently selected item in the table with the details entered above.")
        self.update_button.clicked.connect(self.update_item)
        self.update_button.setEnabled(False)
        button_layout.addWidget(self.update_button)

        self.delete_button = QPushButton("Delete Selected")
        self.delete_button.setToolTip("Delete the currently selected item from the table (use with caution!).")
        self.delete_button.clicked.connect(self.delete_item)
        self.delete_button.setEnabled(False)
        button_layout.addWidget(self.delete_button)

        self.clear_button = QPushButton("Clear Form")
        self.clear_button.setToolTip("Clear the input fields above and deselect the table.")
        self.clear_button.clicked.connect(self.clear_form)
        button_layout.addWidget(self.clear_button)

        button_layout.addStretch()
        layout.addLayout(button_layout)

        search_layout = QHBoxLayout()
        search_layout.addWidget(QLabel("Search Items:"))
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Search by code or name...")
        self.search_edit.setToolTip("Type here to filter the item list below.")
        self.search_edit.textChanged.connect(self.search_items)
        search_layout.addWidget(self.search_edit)
        layout.addLayout(search_layout)

        self.items_table = QTableWidget()
        self.items_table.setColumnCount(5)
        headers = ["Code", "Name", "Purity (%)", "Wage Type", "Wage Rate"]
        header_tooltips = ["Item Code", "Item Name", "Default Purity", "Default Wage Calc Type", "Default Wage Rate"]
        self.items_table.setHorizontalHeaderLabels(headers)
        # --- Set Header Tooltips ----
        for i, tooltip in enumerate(header_tooltips):
            self.items_table.horizontalHeaderItem(i).setToolTip(tooltip)
        # ---------------------------

        self.items_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch) # Name column stretch
        self.items_table.verticalHeader().setVisible(False)
        self.items_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.items_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.items_table.setSelectionMode(QTableWidget.SingleSelection)
        self.items_table.itemSelectionChanged.connect(self.on_item_selected)
        self.items_table.setAlternatingRowColors(True)
        layout.addWidget(self.items_table)

    def load_items(self, search_term=None):
        """Load items from the database into the table."""
        table = self.items_table
        table.setUpdatesEnabled(False)
        table.blockSignals(True)
        try:
            table.setSortingEnabled(False)
            table.setRowCount(0)  # Clear table first

            if search_term:
                items = self.db_manager.search_items(search_term)  # Returns list of sqlite3.Row
            else:
                items = self.db_manager.get_all_items()  # Returns list of sqlite3.Row

            table.setRowCount(len(items))  # Set row count before populating

            # --- Corrected Loop ---
            for row, item_row in enumerate(items):  # item_row is sqlite3.Row
                # Access columns directly using ['key'], providing defaults for None
                code = item_row['code'] if item_row['code'] is not None else ''
                name = item_row['name'] if item_row['name'] is not None else ''
                purity = item_row['purity'] if item_row['purity'] is not None else 0.0
                wage_type = item_row['wage_type'] if item_row['wage_type'] is not None else 'WT'  # Default wage type
                wage_rate = item_row['wage_rate'] if item_row['wage_rate'] is not None else 0.0

                # Set table cell values using the retrieved or default values
                table.setItem(row, 0, QTableWidgetItem(code))
                table.setItem(row, 1, QTableWidgetItem(name))
                table.setItem(row, 2, QTableWidgetItem(str(purity)))
                table.setItem(row, 3, QTableWidgetItem(wage_type))
                table.setItem(row, 4, QTableWidgetItem(str(wage_rate)))
            # --- End Corrected Loop ---
        finally:
            table.setSortingEnabled(True)
            table.blockSignals(False)
            table.setUpdatesEnabled(True)
            table.viewport().update()

        self.show_status(f"Loaded {len(items)} items.", 2000)

    def search_items(self):
        """Search for items based on the search term."""
        search_term = self.search_edit.text().strip()
        self.load_items(search_term) # Pass search term (can be empty)

    def on_item_selected(self):
        """Handle item selection in the table."""
        selected_items = self.items_table.selectedItems()
        if selected_items:
            row = selected_items[0].row()
            code = self.items_table.item(row, 0).text()
            name = self.items_table.item(row, 1).text()
            purity_str = self.items_table.item(row, 2).text()
            wage_type = self.items_table.item(row, 3).text()
            wage_rate_str = self.items_table.item(row, 4).text()

            # Populate form fields - use strings for QLineEdit
            self.code_edit.setText(code)
            self.name_edit.setText(name)
            self.purity_edit.setText(purity_str) # Set text for QLineEdit
            self.wage_rate_edit.setText(wage_rate_str) # Set text for QLineEdit

            index = self.wage_type_combo.findText(wage_type, Qt.MatchFixedString)
            self.wage_type_combo.setCurrentIndex(index if index >= 0 else 0)

            # Enable/Disable buttons and fields
            self.update_button.setEnabled(True)
            self.delete_button.setEnabled(True)
            self.add_button.setEnabled(False)
            self.code_edit.setReadOnly(True)
            self.show_status(f"Selected item: {code}", 2000)
        else:
             self.clear_form()

    def clear_form(self):
        """Clear the form fields and reset button states."""
        self.code_edit.clear()
        self.code_edit.setReadOnly(False)
        self.name_edit.clear()
        self.purity_edit.clear() # Clear QLineEdit
        self.wage_type_combo.setCurrentIndex(0)
        self.wage_rate_edit.clear() # Clear QLineEdit

        self.update_button.setEnabled(False)
        self.delete_button.setEnabled(False)
        self.add_button.setEnabled(True)

        self.items_table.clearSelection()
        self.show_status("Form cleared.", 1500)

    # --- Helper to safely convert locale-aware string to float ---
    def _parse_float(self, text, default=0.0):
        locale = QLocale.system()
        f_val, ok = locale.toDouble(text.strip())
        return f_val if ok else default
    # -----------------------------------------------------------

    def add_item(self):
        """Add a new item to the database."""
        code = self.code_edit.text().strip()
        name = self.name_edit.text().strip()
        # Safely convert text from QLineEdit to float
        purity = self._parse_float(self.purity_edit.text(), 0.0)
        wage_type = self.wage_type_combo.currentText()
        wage_rate = self._parse_float(self.wage_rate_edit.text(), 0.0)

        # Removed explicit purity range check (validator handles format)
        # if not (0 <= purity <= 100):
        #     QMessageBox.warning(self, "Input Error", "Purity must be between 0 and 100.")
        #     self.show_status("Add Item Error: Invalid purity value.", 3000)
        #     return

        if not code or not name:
            QMessageBox.warning(self, "Input Error", "Item Code and Name are required.")
            self.show_status("Add Item Error: Code and Name required.", 3000)
            return

        if self.db_manager.get_item_by_code(code):
            QMessageBox.warning(self, "Duplicate Code",
                                f"Item with code '{code}' already exists. Use Update or choose a different code.")
            self.show_status(f"Add Item Error: Code '{code}' already exists.", 3000)
            return

        success = self.db_manager.add_item(code, name, purity, wage_type, wage_rate)
        if success:
            self.show_status(f"Item '{code}' added successfully.", 3000)
            self.clear_form()
            self.load_items()
        else:
            QMessageBox.critical(self, "Database Error", "Failed to add item. See console/logs.")
            self.show_status("Add Item Error: Database operation failed.", 4000)

    def update_item(self):
        """Update an existing item in the database."""
        code = self.code_edit.text().strip()
        name = self.name_edit.text().strip()
         # Safely convert text from QLineEdit to float
        purity = self._parse_float(self.purity_edit.text(), 0.0)
        wage_type = self.wage_type_combo.currentText()
        wage_rate = self._parse_float(self.wage_rate_edit.text(), 0.0)

        # Removed explicit purity range check (validator handles format)
        # if not (0 <= purity <= 100):
        #     QMessageBox.warning(self, "Input Error", "Purity must be between 0 and 100.")
        #     self.show_status("Update Item Error: Invalid purity value.", 3000)
        #     return

        if not code:
            QMessageBox.warning(self, "Update Error", "No item selected to update.")
            self.show_status("Update Item Error: No item selected", 3000)
            return
        if not name:
            QMessageBox.warning(self, "Input Error", "Item Name cannot be empty.")
            self.show_status("Update Item Error: Name required", 3000)
            return

        # Confirmation removed as per request
        success = self.db_manager.update_item(code, name, purity, wage_type, wage_rate)
        if success:
            self.show_status(f"Item '{code}' updated successfully.", 3000)
            self.clear_form()
            self.load_items()
        else:
            QMessageBox.critical(self, "Database Error", "Failed to update item. See console/logs.")
            self.show_status(f"Update Item Error: Database operation failed for '{code}'.", 4000)

    def delete_item(self):
        """Delete an item from the database."""
        code = self.code_edit.text().strip()
        if not code:
             QMessageBox.warning(self, "Delete Error", "No item selected to delete.")
             self.show_status("Delete Item Error: No item selected", 3000)
             return

        reply = QMessageBox.warning(self, "Confirm Deletion",
                                     f"Are you sure you want to delete item '{code}'?\n"
                                     f"WARNING: This may affect past estimates using this item code.\n"
                                     f"This action cannot be undone.",
                                     QMessageBox.Yes | QMessageBox.Cancel, QMessageBox.Cancel)

        if reply == QMessageBox.Yes:
            success = self.db_manager.delete_item(code)
            if success:
                self.show_status(f"Item '{code}' deleted successfully.", 3000)
                self.clear_form()
                self.load_items()
            else:
                QMessageBox.critical(self, "Database Error",
                                     f"Failed to delete item '{code}'. It might be used in existing estimates. See console/logs.")
                self.show_status(f"Delete Item Error: Database operation failed for '{code}'.", 4000)

    def keyPressEvent(self, event):
        """Handle key press events."""
        if event.key() == Qt.Key_Escape:
            if self.items_table.selectedItems():
                 self.clear_form()
            event.accept()
        else:
             super().keyPressEvent(event)
