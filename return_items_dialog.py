#!/usr/bin/env python
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
                            QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox,
                            QAbstractItemView)
from PyQt5.QtCore import Qt

class ReturnItemsDialog(QDialog):
    """Dialog for handling return items in an estimate."""
    
    def __init__(self, db_manager, parent=None):
        super().__init__(parent)
        self.db_manager = db_manager
        self.return_items = []
        self.init_ui()
    
    def init_ui(self):
        """Set up the user interface."""
        self.setWindowTitle("Return Items")
        self.setMinimumWidth(800)
        self.setMinimumHeight(500)
        
        # Main layout
        layout = QVBoxLayout(self)
        
        # Header
        header_label = QLabel("Return Items")
        header_label.setStyleSheet("font-size: 16pt; font-weight: bold;")
        layout.addWidget(header_label)
        
        instruction_label = QLabel("Enter any items being returned for this estimate.")
        layout.addWidget(instruction_label)
        
        # Return items table (similar to the regular items table)
        self.return_table = QTableWidget()
        self.return_table.setColumnCount(10)
        self.return_table.setHorizontalHeaderLabels([
            "Code", "Item Name", "Gross", "Poly", "Net Wt", 
            "P%", "W.Rate", "P/Q", "Wage", "Fine"
        ])
        
        # Set column widths
        self.return_table.setColumnWidth(0, 80)  # Code
        self.return_table.setColumnWidth(1, 200) # Item Name
        self.return_table.setColumnWidth(2, 80)  # Gross
        self.return_table.setColumnWidth(3, 80)  # Poly
        self.return_table.setColumnWidth(4, 80)  # Net Wt
        self.return_table.setColumnWidth(5, 80)  # P%
        self.return_table.setColumnWidth(6, 80)  # W.Rate
        self.return_table.setColumnWidth(7, 80)  # P/Q
        self.return_table.setColumnWidth(8, 80)  # Wage
        self.return_table.setColumnWidth(9, 80)  # Fine
        
        # Set table properties
        self.return_table.setEditTriggers(
            QTableWidget.DoubleClicked | 
            QTableWidget.EditKeyPressed
        )
        self.return_table.setSelectionBehavior(QAbstractItemView.SelectItems)
        self.return_table.setSelectionMode(QTableWidget.SingleSelection)
        
        layout.addWidget(self.return_table)
        
        # Add an empty row for data entry
        self.add_empty_row()
        
        # Summary section
        summary_layout = QHBoxLayout()
        
        summary_layout.addWidget(QLabel("Total Return Gross:"))
        self.total_gross_label = QLabel("0.000")
        summary_layout.addWidget(self.total_gross_label)
        
        summary_layout.addWidget(QLabel("Total Return Net:"))
        self.total_net_label = QLabel("0.000")
        summary_layout.addWidget(self.total_net_label)
        
        summary_layout.addWidget(QLabel("Total Return Fine:"))
        self.total_fine_label = QLabel("0.000")
        summary_layout.addWidget(self.total_fine_label)
        
        layout.addLayout(summary_layout)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        self.done_button = QPushButton("Done")
        self.done_button.clicked.connect(self.accept)
        button_layout.addWidget(self.done_button)
        
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_button)
        
        layout.addLayout(button_layout)
        
        # Connect signals for calculations
        self.return_table.cellChanged.connect(self.handle_cell_changed)
    
    def add_empty_row(self):
        """Add an empty row to the return items table."""
        row = self.return_table.rowCount()
        self.return_table.insertRow(row)
        
        # Create cells for each column
        for col in range(self.return_table.columnCount()):
            item = QTableWidgetItem("")
            
            # Make calculated fields non-editable
            if col in [4, 8, 9]:  # Net Wt, Wage, Fine
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)
            
            self.return_table.setItem(row, col, item)
    
    def handle_cell_changed(self, row, column):
        """Process cell changes and update calculations."""
        # Only process data entry columns
        if column in [0, 2, 3, 5, 6, 7]:  # Code, Gross, Poly, P%, W.Rate, P/Q
            # Process the value based on which column was changed
            if column == 0:  # Code column
                self.process_item_code(row)
            elif column in [2, 3]:  # Gross or Poly
                self.calculate_net_weight(row)
            elif column == 5:  # P%
                self.calculate_fine(row)
            elif column == 6 or column == 7:  # W.Rate or P/Q
                self.calculate_wage(row)
            
            # If this is the last row and we've entered data, add a new row
            if row == self.return_table.rowCount() - 1:
                if self.return_table.item(row, 0).text().strip():
                    self.add_empty_row()
            
            # Update totals
            self.calculate_totals()
    
    def process_item_code(self, row):
        """Look up and process the item code entered by the user."""
        code = self.return_table.item(row, 0).text().strip()
        if not code:
            return
        
        # Look up the item code in the database
        item = self.db_manager.get_item_by_code(code)
        if item:
            # Set item details
            self.return_table.item(row, 1).setText(item['name'])
            self.return_table.item(row, 5).setText(str(item['purity']))
            self.return_table.item(row, 6).setText(str(item['wage_rate']))
            
            # Set default piece count if empty
            if self.return_table.item(row, 7).text() == "":
                self.return_table.item(row, 7).setText("1")
    
    def calculate_net_weight(self, row):
        """Calculate net weight (Gross - Poly) for the given row."""
        try:
            gross_item = self.return_table.item(row, 2)
            poly_item = self.return_table.item(row, 3)

            gross = float(gross_item.text() if gross_item and gross_item.text() else "0")
            poly = float(poly_item.text() if poly_item and poly_item.text() else "0")
            
            net = gross - poly
            self.return_table.item(row, 4).setText(f"{net:.3f}")
            
            # Update dependent values
            self.calculate_fine(row)
            self.calculate_wage(row)
        except ValueError:
            pass
    
    def calculate_fine(self, row):
        """Calculate fine weight based on net weight and purity."""
        try:
            net = float(self.return_table.item(row, 4).text() or "0")
            purity = float(self.return_table.item(row, 5).text() or "0")
            
            fine = net * (purity / 100)
            self.return_table.item(row, 9).setText(f"{fine:.3f}")
        except ValueError:
            pass
    
    def calculate_wage(self, row):
        """Calculate wage based on net weight, wage rate, and pieces."""
        try:
            net = float(self.return_table.item(row, 4).text() or "0")
            wage_rate = float(self.return_table.item(row, 6).text() or "0")
            pieces = int(self.return_table.item(row, 7).text() or "1")
            
            wage = net * wage_rate * pieces
            self.return_table.item(row, 8).setText(f"{wage:.2f}")
        except ValueError:
            pass
    
    def calculate_totals(self):
        """Calculate and update total values for returns."""
        total_gross = 0.0
        total_net = 0.0
        total_fine = 0.0
        
        for row in range(self.return_table.rowCount()):
            try:
                # Skip empty rows
                code = self.return_table.item(row, 0).text().strip()
                if not code:
                    continue
                
                # Add up values
                gross_text = self.return_table.item(row, 2).text()
                if gross_text:
                    total_gross += float(gross_text)
                
                net_text = self.return_table.item(row, 4).text()
                if net_text:
                    total_net += float(net_text)
                
                fine_text = self.return_table.item(row, 9).text()
                if fine_text:
                    total_fine += float(fine_text)
            except (ValueError, AttributeError):
                continue
        
        # Update summary labels
        self.total_gross_label.setText(f"{total_gross:.3f}")
        self.total_net_label.setText(f"{total_net:.3f}")
        self.total_fine_label.setText(f"{total_fine:.3f}")
    
    def get_return_items(self):
        """Get the list of return items for processing."""
        return_items = []
        
        for row in range(self.return_table.rowCount()):
            code = self.return_table.item(row, 0).text().strip()
            if not code:  # Skip empty rows
                continue
            
            # Create item dictionary
            item = {
                'code': code,
                'name': self.return_table.item(row, 1).text(),
                'gross': float(self.return_table.item(row, 2).text() or "0"),
                'poly': float(self.return_table.item(row, 3).text() or "0"),
                'net_wt': float(self.return_table.item(row, 4).text() or "0"),
                'purity': float(self.return_table.item(row, 5).text() or "0"),
                'wage_rate': float(self.return_table.item(row, 6).text() or "0"),
                'pieces': int(self.return_table.item(row, 7).text() or "1"),
                'wage': float(self.return_table.item(row, 8).text() or "0"),
                'fine': float(self.return_table.item(row, 9).text() or "0")
            }
            return_items.append(item)
        
        return return_items
