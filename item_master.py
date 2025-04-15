#!/usr/bin/env python
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
                             QPushButton, QTableWidget, QTableWidgetItem, QHeaderView,
                             QMessageBox, QComboBox, QDoubleSpinBox, QAbstractItemView)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QKeyEvent


class ItemMasterWidget(QWidget):
    """Widget for managing silver item catalog."""

    def __init__(self, db_manager):
        super().__init__()
        self.db_manager = db_manager
        self.init_ui()
        self.load_items()

    def init_ui(self):
        """Initialize the user interface."""
        # Main layout
        layout = QVBoxLayout(self)

        # Header
        header_label = QLabel("Item Master")
        header_label.setStyleSheet("font-size: 16pt; font-weight: bold;")
        layout.addWidget(header_label)

        # Form layout for item details
        form_layout = QHBoxLayout()

        # Code field
        form_layout.addWidget(QLabel("Code:"))
        self.code_edit = QLineEdit()
        self.code_edit.setMaximumWidth(100)
        form_layout.addWidget(self.code_edit)

        # Name field
        form_layout.addWidget(QLabel("Name:"))
        self.name_edit = QLineEdit()
        self.name_edit.setMinimumWidth(200)
        form_layout.addWidget(self.name_edit)

        # Purity field
        form_layout.addWidget(QLabel("Purity (%):"))
        self.purity_spin = QDoubleSpinBox()
        self.purity_spin.setRange(0, 100)
        self.purity_spin.setDecimals(2)
        self.purity_spin.setSingleStep(0.5)
        form_layout.addWidget(self.purity_spin)

        # Wage Type field
        form_layout.addWidget(QLabel("Wage Type:"))
        self.wage_type_combo = QComboBox()
        self.wage_type_combo.addItems(["PC", "WT"])  # Changed to PC and WT
        form_layout.addWidget(self.wage_type_combo)

        # Wage Rate field
        form_layout.addWidget(QLabel("Wage Rate:"))
        self.wage_rate_spin = QDoubleSpinBox()
        self.wage_rate_spin.setRange(0, 10000)
        self.wage_rate_spin.setDecimals(2)
        form_layout.addWidget(self.wage_rate_spin)

        # Add the form layout to the main layout
        layout.addLayout(form_layout)

        # Buttons layout
        button_layout = QHBoxLayout()

        # Add button
        self.add_button = QPushButton("Add")
        self.add_button.clicked.connect(self.add_item)
        button_layout.addWidget(self.add_button)

        # Update button
        self.update_button = QPushButton("Update")
        self.update_button.clicked.connect(self.update_item)
        self.update_button.setEnabled(False)
        button_layout.addWidget(self.update_button)

        # Delete button
        self.delete_button = QPushButton("Delete")
        self.delete_button.clicked.connect(self.delete_item)
        self.delete_button.setEnabled(False)
        button_layout.addWidget(self.delete_button)

        # Clear button
        self.clear_button = QPushButton("Clear")
        self.clear_button.clicked.connect(self.clear_form)
        button_layout.addWidget(self.clear_button)

        # Add buttons layout to main layout
        layout.addLayout(button_layout)

        # Search layout
        search_layout = QHBoxLayout()
        search_layout.addWidget(QLabel("Search:"))
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Search by code or name...")
        self.search_edit.textChanged.connect(self.search_items)
        search_layout.addWidget(self.search_edit)

        layout.addLayout(search_layout)

        # Table for displaying items
        self.items_table = QTableWidget()
        self.items_table.setColumnCount(5)
        self.items_table.setHorizontalHeaderLabels(["Code", "Name", "Purity (%)", "Wage Type", "Wage Rate"])
        self.items_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.items_table.verticalHeader().setVisible(False)
        self.items_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.items_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.items_table.setSelectionMode(QTableWidget.SingleSelection)
        self.items_table.itemSelectionChanged.connect(self.on_item_selected)
        layout.addWidget(self.items_table)

    def load_items(self, search_term=None):
        """Load items from the database into the table."""
        self.items_table.setRowCount(0)

        if search_term:
            items = self.db_manager.search_items(search_term)
        else:
            items = self.db_manager.get_all_items()

        for row, item in enumerate(items):
            self.items_table.insertRow(row)
            self.items_table.setItem(row, 0, QTableWidgetItem(item['code']))
            self.items_table.setItem(row, 1, QTableWidgetItem(item['name']))
            self.items_table.setItem(row, 2, QTableWidgetItem(str(item['purity'])))
            self.items_table.setItem(row, 3, QTableWidgetItem(item['wage_type']))
            self.items_table.setItem(row, 4, QTableWidgetItem(str(item['wage_rate'])))

    def search_items(self):
        """Search for items based on the search term."""
        search_term = self.search_edit.text().strip()
        if search_term:
            self.load_items(search_term)
        else:
            self.load_items()

    def on_item_selected(self):
        """Handle item selection in the table."""
        selected_rows = self.items_table.selectedItems()
        if selected_rows:
            row = selected_rows[0].row()
            self.code_edit.setText(self.items_table.item(row, 0).text())
            self.name_edit.setText(self.items_table.item(row, 1).text())
            self.purity_spin.setValue(float(self.items_table.item(row, 2).text()))

            wage_type = self.items_table.item(row, 3).text()
            index = self.wage_type_combo.findText(wage_type)
            self.wage_type_combo.setCurrentIndex(index if index != -1 else 0)

            self.wage_rate_spin.setValue(float(self.items_table.item(row, 4).text()))

            # Enable update and delete buttons
            self.update_button.setEnabled(True)
            self.delete_button.setEnabled(True)

            # Disable code field for existing items
            self.code_edit.setReadOnly(True)
        else:
            self.clear_form()

    def clear_form(self):
        """Clear the form fields."""
        self.code_edit.clear()
        self.code_edit.setReadOnly(False)
        self.name_edit.clear()
        self.purity_spin.setValue(0)
        self.wage_type_combo.setCurrentIndex(0)
        self.wage_rate_spin.setValue(0)
        self.update_button.setEnabled(False)
        self.delete_button.setEnabled(False)
        self.items_table.clearSelection()

    def add_item(self):
        """Add a new item to the database."""
        code = self.code_edit.text().strip()
        name = self.name_edit.text().strip()
        purity = self.purity_spin.value()
        wage_type = self.wage_type_combo.currentText()
        wage_rate = self.wage_rate_spin.value()

        if not code or not name:
            QMessageBox.warning(self, "Input Error", "Code and Name are required fields.")
            return

        # Check if the code already exists
        existing_item = self.db_manager.get_item_by_code(code)
        if existing_item:
            QMessageBox.warning(self, "Duplicate Code",
                                f"Item with code '{code}' already exists. Use Update instead.")
            return

        success = self.db_manager.add_item(code, name, purity, wage_type, wage_rate)

        if success:
            QMessageBox.information(self, "Success", f"Item '{code}' added successfully.")
            self.clear_form()
            self.load_items()
        else:
            QMessageBox.critical(self, "Error", "Failed to add item. Please try again.")

    def update_item(self):
        """Update an existing item in the database."""
        code = self.code_edit.text().strip()
        name = self.name_edit.text().strip()
        purity = self.purity_spin.value()
        wage_type = self.wage_type_combo.currentText()
        wage_rate = self.wage_rate_spin.value()

        if not code or not name:
            QMessageBox.warning(self, "Input Error", "Code and Name are required fields.")
            return

        # Confirm update
        reply = QMessageBox.question(self, "Confirm Update",
                                     f"Are you sure you want to update item '{code}'?",
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)

        if reply == QMessageBox.Yes:
            success = self.db_manager.update_item(code, name, purity, wage_type, wage_rate)

            if success:
                QMessageBox.information(self, "Success", f"Item '{code}' updated successfully.")
                self.clear_form()
                self.load_items()
            else:
                QMessageBox.critical(self, "Error", "Failed to update item. Please try again.")

    def delete_item(self):
        """Delete an item from the database."""
        code = self.code_edit.text().strip()

        # Confirm deletion
        reply = QMessageBox.question(self, "Confirm Deletion",
                                     f"Are you sure you want to delete item '{code}'? This action cannot be undone.",
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)

        if reply == QMessageBox.Yes:
            success = self.db_manager.delete_item(code)

            if success:
                QMessageBox.information(self, "Success", f"Item '{code}' deleted successfully.")
                self.clear_form()
                self.load_items()
            else:
                QMessageBox.critical(self, "Error", "Failed to delete item. Please try again.")

    def keyPressEvent(self, event):
        """Handle key press events."""
        if event.key() == Qt.Key_Escape:
            # Clear form and selection on Escape key
            self.clear_form()