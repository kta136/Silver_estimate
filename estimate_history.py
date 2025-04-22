#!/usr/bin/env python
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
                             QTableWidget, QTableWidgetItem, QHeaderView,
                             QAbstractItemView, QLineEdit, QDateEdit, QMessageBox)
from PyQt5.QtCore import Qt, QDate

class EstimateHistoryDialog(QDialog):
    """Dialog for browsing and selecting past estimates."""

    # Accept db_manager, an explicit main_window_ref, and the standard parent
    def __init__(self, db_manager, main_window_ref, parent=None):
        super().__init__(parent) # Use standard parent for QDialog
        self.db_manager = db_manager
        self.main_window = main_window_ref # Store the explicit reference to MainWindow
        self.selected_voucher = None
        self.init_ui()
        self.load_estimates()
    
    def init_ui(self):
        """Set up the user interface."""
        self.setWindowTitle("Estimate History")
        self.setMinimumWidth(800)
        self.setMinimumHeight(500)
        
        # Main layout
        layout = QVBoxLayout(self)
        
        # Header
        header_label = QLabel("Estimate History")
        header_label.setStyleSheet("font-size: 16pt; font-weight: bold;")
        layout.addWidget(header_label)
        
        # Search filters
        filter_layout = QHBoxLayout()
        
        # Date range filter
        filter_layout.addWidget(QLabel("From:"))
        self.date_from = QDateEdit()
        self.date_from.setCalendarPopup(True)
        self.date_from.setDate(QDate.currentDate().addMonths(-1))  # Default to 1 month ago
        filter_layout.addWidget(self.date_from)
        
        filter_layout.addWidget(QLabel("To:"))
        self.date_to = QDateEdit()
        self.date_to.setCalendarPopup(True)
        self.date_to.setDate(QDate.currentDate())
        filter_layout.addWidget(self.date_to)
        
        # Voucher search
        filter_layout.addWidget(QLabel("Voucher No:"))
        self.voucher_search = QLineEdit()
        self.voucher_search.setMaximumWidth(150)
        filter_layout.addWidget(self.voucher_search)
        
        # Search button
        self.search_button = QPushButton("Search")
        self.search_button.clicked.connect(self.load_estimates)
        filter_layout.addWidget(self.search_button)
        
        # Add filters to main layout
        layout.addLayout(filter_layout)
        
        # Estimates table
        self.estimates_table = QTableWidget()
        self.estimates_table.setColumnCount(8) # Increased column count
        self.estimates_table.setHorizontalHeaderLabels([
            "Voucher No", "Date", "Silver Rate", "Total Gross",
            "Total Net", "Net Fine", "Net Wage", "Grand Total" # Added Net Fine, Renamed Total Value, Added Net Wage for clarity
        ])

        # Set column widths (adjusting for new columns)
        self.estimates_table.setColumnWidth(0, 110)  # Voucher No
        self.estimates_table.setColumnWidth(1, 90)   # Date
        self.estimates_table.setColumnWidth(2, 90)   # Silver Rate
        self.estimates_table.setColumnWidth(3, 90)   # Total Gross
        self.estimates_table.setColumnWidth(4, 90)   # Total Net
        self.estimates_table.setColumnWidth(5, 90)   # Net Fine (New)
        self.estimates_table.setColumnWidth(6, 90)   # Net Wage (New - needed for Grand Total calc)
        self.estimates_table.setColumnWidth(7, 110)  # Grand Total (Renamed)
        
        # Table properties
        self.estimates_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.estimates_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.estimates_table.setSelectionMode(QTableWidget.SingleSelection)
        self.estimates_table.itemDoubleClicked.connect(self.accept)
        
        layout.addWidget(self.estimates_table)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        self.open_button = QPushButton("Open Selected")
        self.open_button.clicked.connect(self.accept)
        button_layout.addWidget(self.open_button)
        
        self.print_button = QPushButton("Print Selected")
        self.print_button.clicked.connect(self.print_estimate)
        button_layout.addWidget(self.print_button)

        self.delete_button = QPushButton("Delete Selected") # New button
        self.delete_button.setToolTip("Permanently delete the selected estimate")
        self.delete_button.clicked.connect(self.delete_selected_estimate) # Connect to new handler
        button_layout.addWidget(self.delete_button)

        button_layout.addStretch(1) # Add stretch before close

        self.close_button = QPushButton("Close")
        self.close_button.clicked.connect(self.reject)
        button_layout.addWidget(self.close_button)
        
        layout.addLayout(button_layout)
    
    def load_estimates(self):
        """Load estimates based on search criteria."""
        # Get search criteria
        date_from = self.date_from.date().toString("yyyy-MM-dd")
        date_to = self.date_to.date().toString("yyyy-MM-dd")
        voucher_search = self.voucher_search.text().strip()
        
        # Get estimates from database
        estimates = self.db_manager.get_estimates(date_from, date_to, voucher_search)
        
        # Clear and populate table
        self.estimates_table.setRowCount(0)
        
        for row, estimate in enumerate(estimates):
            self.estimates_table.insertRow(row)
            self.estimates_table.setItem(row, 0, QTableWidgetItem(estimate['voucher_no']))
            self.estimates_table.setItem(row, 1, QTableWidgetItem(estimate['date']))
            self.estimates_table.setItem(row, 2, QTableWidgetItem(f"{estimate['silver_rate']:.2f}"))
            self.estimates_table.setItem(row, 3, QTableWidgetItem(f"{estimate['total_gross']:.3f}"))
            self.estimates_table.setItem(row, 4, QTableWidgetItem(f"{estimate['total_net']:.3f}"))
            # Column 5: Net Fine
            net_fine = estimate['total_fine'] if estimate['total_fine'] is not None else 0.0
            self.estimates_table.setItem(row, 5, QTableWidgetItem(f"{net_fine:.3f}"))

            # Column 6: Net Wage
            net_wage = estimate['total_wage'] if estimate['total_wage'] is not None else 0.0
            self.estimates_table.setItem(row, 6, QTableWidgetItem(f"{net_wage:.2f}"))

            # Column 7: Grand Total (Net Value + Net Wage)
            silver_rate = estimate['silver_rate'] if estimate['silver_rate'] is not None else 0.0
            net_value = net_fine * silver_rate
            grand_total = net_value + net_wage
            self.estimates_table.setItem(row, 7, QTableWidgetItem(f"{grand_total:.2f}"))
    
    def get_selected_voucher(self):
        """Get the selected voucher number."""
        selected_items = self.estimates_table.selectedItems()
        if not selected_items:
            return None
        
        row = selected_items[0].row()
        return self.estimates_table.item(row, 0).text()
    
    def accept(self):
        """Handle dialog acceptance and return the selected voucher."""
        self.selected_voucher = self.get_selected_voucher()
        if not self.selected_voucher:
            QMessageBox.warning(self, "Selection Error", "Please select an estimate first.")
            return
        
        super().accept()

    def print_estimate(self):
        """Print the selected estimate."""
        from print_manager import PrintManager

        voucher_no = self.get_selected_voucher()
        if not voucher_no:
            QMessageBox.warning(self, "Selection Error", "Please select an estimate first.")
            return

        # --- Get the print font from the explicitly stored main window reference ---
        print_font_setting = None
        if self.main_window and hasattr(self.main_window, 'print_font'):
            print_font_setting = self.main_window.print_font
        # ---------------------------------------------------------

        # Create print manager instance, passing the font, and print the selected estimate
        print_manager = PrintManager(self.db_manager, print_font=print_font_setting)
        success = print_manager.print_estimate(voucher_no, self) # 'self' is the dialog, used for parent QMessageBox

        if not success:
            QMessageBox.warning(self, "Print Error", f"Failed to print estimate {voucher_no}.")

    def delete_selected_estimate(self):
        """Handle deletion of the selected estimate."""
        voucher_no = self.get_selected_voucher()
        if not voucher_no:
            QMessageBox.warning(self, "Selection Error", "Please select an estimate to delete.")
            return

        reply = QMessageBox.warning(self, "Confirm Delete Estimate",
                                     f"Are you sure you want to permanently delete estimate '{voucher_no}'?\n"
                                     "This action cannot be undone.",
                                     QMessageBox.Yes | QMessageBox.Cancel, QMessageBox.Cancel)

        if reply == QMessageBox.Yes:
            try:
                success = self.db_manager.delete_single_estimate(voucher_no)
                if success:
                    QMessageBox.information(self, "Success", f"Estimate '{voucher_no}' deleted successfully.")
                    self.load_estimates() # Refresh the list
                else:
                    QMessageBox.warning(self, "Delete Error", f"Estimate '{voucher_no}' could not be deleted (might already be deleted).")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"An unexpected error occurred during deletion: {str(e)}")
