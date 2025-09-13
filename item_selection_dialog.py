#!/usr/bin/env python
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                             QPushButton, QTableWidget, QTableWidgetItem,
                             QHeaderView, QAbstractItemView, QLineEdit)
from PyQt5.QtCore import Qt


class ItemSelectionDialog(QDialog):
    """Dialog for selecting an item when code is invalid or ambiguous."""

    def __init__(self, db_manager, search_term, parent=None):
        super().__init__(parent)
        self.db_manager = db_manager
        self.search_term = search_term
        self.selected_item = None
        self.init_ui()

    def init_ui(self):
        """Initialize the user interface."""
        self.setWindowTitle("Select Item")
        self.setMinimumWidth(500)
        self.setMinimumHeight(300)

        layout = QVBoxLayout(self)

        # Header
        layout.addWidget(QLabel(f"Select an item matching '{self.search_term}':"))

        # Search box
        search_layout = QHBoxLayout()
        search_layout.addWidget(QLabel("Search (Code or Name):")) # Clarify search scope
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Type to filter...") # Add placeholder
        self.search_edit.setToolTip("Search by item code or name\nFilters the list as you type\nPartial matches supported\nClear to show all items")
        self.search_edit.textChanged.connect(self.filter_items) # Connect to filter method
        search_layout.addWidget(self.search_edit)
        layout.addLayout(search_layout)

        # Items table
        self.items_table = QTableWidget()
        self.items_table.setColumnCount(5)
        self.items_table.setHorizontalHeaderLabels(["Code", "Name", "Purity", "Type", "Rate"])
        self.items_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.items_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.items_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.items_table.setSelectionMode(QTableWidget.SingleSelection)
        self.items_table.itemDoubleClicked.connect(self.accept)
        self.items_table.setToolTip("Double-click to select an item\nOr single-click and press Select button\nShows code, name, purity, type, and rate")
        layout.addWidget(self.items_table)

        # Load all items instead of filtering
        self.load_all_items()

        # Buttons
        button_layout = QHBoxLayout()

        select_button = QPushButton("Select")
        select_button.clicked.connect(self.accept)
        select_button.setToolTip("Select the highlighted item\nKeyboard: Enter\nDouble-click table row also selects")
        button_layout.addWidget(select_button)

        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(self.reject)
        cancel_button.setToolTip("Cancel item selection\nKeyboard: Escape\nReturns to estimate without selecting")
        button_layout.addWidget(cancel_button)

        layout.addLayout(button_layout)

    def load_all_items(self):
        """Load all items from the database."""
        table = self.items_table
        table.setUpdatesEnabled(False)
        table.blockSignals(True)
        try:
            table.setSortingEnabled(False)
            items = self.db_manager.get_all_items()
            table.setRowCount(len(items))
            for row, item in enumerate(items):
                table.setItem(row, 0, QTableWidgetItem(item['code']))
                table.setItem(row, 1, QTableWidgetItem(item['name']))
                table.setItem(row, 2, QTableWidgetItem(str(item['purity'])))
                table.setItem(row, 3, QTableWidgetItem(item['wage_type']))
                table.setItem(row, 4, QTableWidgetItem(str(item['wage_rate'])))
            # Select the first row if available
            if table.rowCount() > 0:
                table.selectRow(0)
            # Set initial search text if provided
            if self.search_term:
                self.search_edit.setText(self.search_term)
                self.filter_items(self.search_term)  # Apply initial filter
        finally:
            table.setSortingEnabled(True)
            table.blockSignals(False)
            table.setUpdatesEnabled(True)
            table.viewport().update()

    def filter_items(self, text):
        """Filter table rows based on search text in Code or Name columns."""
        search_text = text.lower().strip()
        first_visible_row = -1

        for row in range(self.items_table.rowCount()):
            code_item = self.items_table.item(row, 0)
            name_item = self.items_table.item(row, 1)

            # Ensure items exist before accessing text
            code_matches = code_item and search_text in code_item.text().lower()
            name_matches = name_item and search_text in name_item.text().lower()

            if code_matches or name_matches:
                self.items_table.setRowHidden(row, False)
                if first_visible_row == -1:
                    first_visible_row = row
            else:
                self.items_table.setRowHidden(row, True)

        # Select the first visible row after filtering
        if first_visible_row != -1:
            self.items_table.selectRow(first_visible_row)
        else:
            # If no rows are visible, clear selection
            self.items_table.clearSelection()

    # Removed jump_to_item method

    def get_selected_item(self):
        """Get the selected item after dialog is accepted."""
        selected_rows = self.items_table.selectedItems()
        if not selected_rows:
            return None

        row = selected_rows[0].row()
        return {
            'code': self.items_table.item(row, 0).text(),
            'name': self.items_table.item(row, 1).text(),
            'purity': float(self.items_table.item(row, 2).text()),
            'wage_type': self.items_table.item(row, 3).text(),
            'wage_rate': float(self.items_table.item(row, 4).text())
        }
