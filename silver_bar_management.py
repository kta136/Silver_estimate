#!/usr/bin/env python
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel,
                            QPushButton, QTableWidget, QTableWidgetItem, QHeaderView,
                            QLineEdit, QDoubleSpinBox, QComboBox, QMessageBox,
                            QAbstractItemView, QTextEdit)
from PyQt5.QtCore import Qt, QDate

class SilverBarDialog(QDialog):
    """Dialog for adding and managing silver bars."""
    
    def __init__(self, db_manager, parent=None):
        super().__init__(parent)
        self.db_manager = db_manager
        self.init_ui()
        self.load_bars()
    
    def init_ui(self):
        """Set up the user interface."""
        self.setWindowTitle("Silver Bar Management")
        self.setMinimumWidth(800)
        self.setMinimumHeight(600)
        
        # Main layout
        layout = QVBoxLayout(self)
        
        # Header
        header_label = QLabel("Silver Bar Management")
        header_label.setStyleSheet("font-size: 16pt; font-weight: bold;")
        layout.addWidget(header_label)
        
        # Add bar section
        add_bar_layout = QGridLayout()
        
        # Bar number input
        add_bar_layout.addWidget(QLabel("Bar Number:"), 0, 0)
        self.bar_no_edit = QLineEdit()
        self.bar_no_edit.setMaximumWidth(150)
        add_bar_layout.addWidget(self.bar_no_edit, 0, 1)
        
        # Weight input
        add_bar_layout.addWidget(QLabel("Weight (g):"), 0, 2)
        self.weight_spin = QDoubleSpinBox()
        self.weight_spin.setRange(0, 100000)
        self.weight_spin.setDecimals(3)
        self.weight_spin.setSingleStep(10)
        add_bar_layout.addWidget(self.weight_spin, 0, 3)
        
        # Purity input
        add_bar_layout.addWidget(QLabel("Purity (%):"), 0, 4)
        self.purity_spin = QDoubleSpinBox()
        self.purity_spin.setRange(0, 100)
        self.purity_spin.setDecimals(2)
        self.purity_spin.setValue(100)  # Default to 100%
        self.purity_spin.setSingleStep(0.5)
        add_bar_layout.addWidget(self.purity_spin, 0, 5)
        
        # Add button
        self.add_bar_button = QPushButton("Add Bar")
        self.add_bar_button.clicked.connect(self.add_bar)
        add_bar_layout.addWidget(self.add_bar_button, 0, 6)
        
        layout.addLayout(add_bar_layout)
        
        # Filter section
        filter_layout = QHBoxLayout()
        
        filter_layout.addWidget(QLabel("Filter by Status:"))
        self.status_filter = QComboBox()
        self.status_filter.addItems(["All", "In Stock", "Transferred", "Sold", "Melted"])
        self.status_filter.currentTextChanged.connect(self.load_bars)
        filter_layout.addWidget(self.status_filter)
        
        filter_layout.addStretch()
        
        # Refresh button
        self.refresh_button = QPushButton("Refresh")
        self.refresh_button.clicked.connect(self.load_bars)
        filter_layout.addWidget(self.refresh_button)
        
        layout.addLayout(filter_layout)
        
        # Silver bars table
        self.bars_table = QTableWidget()
        self.bars_table.setColumnCount(7)
        self.bars_table.setHorizontalHeaderLabels([
            "ID", "Bar Number", "Weight (g)", "Purity (%)", 
            "Fine Weight (g)", "Date Added", "Status"
        ])
        
        # Set column widths
        self.bars_table.setColumnWidth(0, 50)   # ID
        self.bars_table.setColumnWidth(1, 120)  # Bar Number
        self.bars_table.setColumnWidth(2, 100)  # Weight
        self.bars_table.setColumnWidth(3, 100)  # Purity
        self.bars_table.setColumnWidth(4, 120)  # Fine Weight
        self.bars_table.setColumnWidth(5, 120)  # Date Added
        self.bars_table.setColumnWidth(6, 120)  # Status
        
        # Table properties
        self.bars_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.bars_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.bars_table.setSelectionMode(QTableWidget.SingleSelection)
        
        layout.addWidget(self.bars_table)
        
        # Transfer section
        transfer_layout = QGridLayout()
        
        transfer_layout.addWidget(QLabel("Transfer Selected Bar to:"), 0, 0)
        self.transfer_status = QComboBox()
        self.transfer_status.addItems(["In Stock", "Transferred", "Sold", "Melted"])
        transfer_layout.addWidget(self.transfer_status, 0, 1)
        
        transfer_layout.addWidget(QLabel("Notes:"), 0, 2)
        self.transfer_notes = QLineEdit()
        transfer_layout.addWidget(self.transfer_notes, 0, 3)
        
        self.transfer_button = QPushButton("Transfer")
        self.transfer_button.clicked.connect(self.transfer_bar)
        transfer_layout.addWidget(self.transfer_button, 0, 4)
        
        layout.addLayout(transfer_layout)
        
        # Summary section
        summary_layout = QHBoxLayout()
        
        summary_layout.addWidget(QLabel("Total Bars:"))
        self.total_bars_label = QLabel("0")
        summary_layout.addWidget(self.total_bars_label)
        
        summary_layout.addWidget(QLabel("Total Weight:"))
        self.total_weight_label = QLabel("0.000 g")
        summary_layout.addWidget(self.total_weight_label)
        
        summary_layout.addWidget(QLabel("Total Fine Weight:"))
        self.total_fine_label = QLabel("0.000 g")
        summary_layout.addWidget(self.total_fine_label)
        
        layout.addLayout(summary_layout)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        self.print_button = QPushButton("Print List")
        self.print_button.clicked.connect(self.print_bar_list)
        button_layout.addWidget(self.print_button)
        
        self.close_button = QPushButton("Close")
        self.close_button.clicked.connect(self.accept)
        button_layout.addWidget(self.close_button)
        
        layout.addLayout(button_layout)
    
    def load_bars(self):
        """Load silver bars based on filter."""
        status_filter = self.status_filter.currentText()
        if status_filter == "All":
            status = None
        else:
            status = status_filter
        
        bars = self.db_manager.get_silver_bars(status)
        
        # Clear and populate table
        self.bars_table.setRowCount(0)
        
        total_weight = 0.0
        total_fine = 0.0
        
        for row, bar in enumerate(bars):
            self.bars_table.insertRow(row)
            self.bars_table.setItem(row, 0, QTableWidgetItem(str(bar['id'])))
            self.bars_table.setItem(row, 1, QTableWidgetItem(bar['bar_no']))
            self.bars_table.setItem(row, 2, QTableWidgetItem(f"{bar['weight']:.3f}"))
            self.bars_table.setItem(row, 3, QTableWidgetItem(f"{bar['purity']:.2f}"))
            self.bars_table.setItem(row, 4, QTableWidgetItem(f"{bar['fine_weight']:.3f}"))
            self.bars_table.setItem(row, 5, QTableWidgetItem(bar['date_added']))
            self.bars_table.setItem(row, 6, QTableWidgetItem(bar['status']))
            
            # Update totals
            total_weight += bar['weight']
            total_fine += bar['fine_weight']
        
        # Update summary
        self.total_bars_label.setText(str(self.bars_table.rowCount()))
        self.total_weight_label.setText(f"{total_weight:.3f} g")
        self.total_fine_label.setText(f"{total_fine:.3f} g")
    
    def add_bar(self):
        """Add a new silver bar to inventory."""
        bar_no = self.bar_no_edit.text().strip()
        weight = self.weight_spin.value()
        purity = self.purity_spin.value()
        
        if not bar_no:
            QMessageBox.warning(self, "Input Error", "Bar number is required.")
            return
        
        if weight <= 0:
            QMessageBox.warning(self, "Input Error", "Weight must be greater than zero.")
            return
        
        success = self.db_manager.add_silver_bar(bar_no, weight, purity)
        
        if success:
            QMessageBox.information(self, "Success", f"Silver bar '{bar_no}' added to inventory.")
            
            # Clear inputs
            self.bar_no_edit.clear()
            self.weight_spin.setValue(0)
            self.purity_spin.setValue(100)
            
            # Refresh list
            self.load_bars()
        else:
            QMessageBox.critical(self, "Error", "Failed to add silver bar. Bar number may already exist.")
    
    def transfer_bar(self):
        """Transfer a selected bar to a new status."""
        selected_items = self.bars_table.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "Selection Error", "Please select a bar to transfer.")
            return
        
        row = selected_items[0].row()
        bar_id = int(self.bars_table.item(row, 0).text())
        bar_no = self.bars_table.item(row, 1).text()
        current_status = self.bars_table.item(row, 6).text()
        
        new_status = self.transfer_status.currentText()
        notes = self.transfer_notes.text()
        
        if current_status == new_status:
            QMessageBox.warning(self, "Transfer Error", "The bar is already in this status.")
            return
        
        # Confirm transfer
        reply = QMessageBox.question(self, "Confirm Transfer", 
                                    f"Transfer bar '{bar_no}' from '{current_status}' to '{new_status}'?",
                                    QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        
        if reply == QMessageBox.Yes:
            success = self.db_manager.transfer_silver_bar(bar_id, new_status, notes)
            
            if success:
                QMessageBox.information(self, "Success", f"Bar '{bar_no}' transferred successfully.")
                self.transfer_notes.clear()
                self.load_bars()
            else:
                QMessageBox.critical(self, "Error", "Failed to transfer bar.")

    def print_bar_list(self):
        """Print the current list of silver bars."""
        from print_manager import PrintManager

        # Get current status filter
        status_filter = None
        if self.status_filter.currentText() != "All":
            status_filter = self.status_filter.currentText()

        # Create print manager instance and print silver bars
        print_manager = PrintManager(self.db_manager)
        print_manager.print_silver_bars(status_filter, self)
