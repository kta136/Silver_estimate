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
        search_layout.addWidget(QLabel("Search:"))
        self.search_edit = QLineEdit()
        self.search_edit.textChanged.connect(self.jump_to_item)
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
        layout.addWidget(self.items_table)

        # Load all items instead of filtering
        self.load_all_items()

        # Buttons
        button_layout = QHBoxLayout()

        select_button = QPushButton("Select")
        select_button.clicked.connect(self.accept)
        button_layout.addWidget(select_button)

        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(cancel_button)

        layout.addLayout(button_layout)

    def load_all_items(self):
        """Load all items from the database."""
        items = self.db_manager.get_all_items()

        self.items_table.setRowCount(len(items))
        for row, item in enumerate(items):
            self.items_table.setItem(row, 0, QTableWidgetItem(item['code']))
            self.items_table.setItem(row, 1, QTableWidgetItem(item['name']))
            self.items_table.setItem(row, 2, QTableWidgetItem(str(item['purity'])))
            self.items_table.setItem(row, 3, QTableWidgetItem(item['wage_type']))
            self.items_table.setItem(row, 4, QTableWidgetItem(str(item['wage_rate'])))

        # Select the first row if available
        if self.items_table.rowCount() > 0:
            self.items_table.selectRow(0)

    def jump_to_item(self, text):
        """Jump to the first item that starts with the entered text."""
        if not text:
            return

        # Search the Name column (column 1) for items starting with the text
        for row in range(self.items_table.rowCount()):
            item_name = self.items_table.item(row, 1).text()
            if item_name.lower().startswith(text.lower()):
                # Found a match, select this row and scroll to it
                self.items_table.selectRow(row)
                self.items_table.scrollToItem(self.items_table.item(row, 0))
                break

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