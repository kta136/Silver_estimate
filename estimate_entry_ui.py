#!/usr/bin/env python
from PyQt5.QtWidgets import (QVBoxLayout, QHBoxLayout, QGridLayout, QLabel,
                             QLineEdit, QPushButton, QTableWidget, QTableWidgetItem,
                             QHeaderView, QDoubleSpinBox, QDateEdit, QAbstractItemView,
                             QCheckBox)
from PyQt5.QtCore import Qt, QDate


class EstimateUI:
    """UI components and setup for the estimate entry widget."""

    def setup_ui(self, widget):
        """Set up the user interface for the estimate entry widget.

        Args:
            widget: The parent widget that will contain the UI elements
        """
        # Main layout
        self.layout = QVBoxLayout(widget)

        # Header
        header_label = QLabel("Silver Estimation")
        header_label.setStyleSheet("font-size: 16pt; font-weight: bold;")
        self.layout.addWidget(header_label)

        # Form layout for voucher details
        self._setup_header_form()

        # Item table actions layout
        table_actions_layout = QHBoxLayout()

        # Add delete row button
        self.delete_row_button = QPushButton("Delete Row (Ctrl+D)")
        self.delete_row_button.clicked.connect(widget.delete_current_row)
        table_actions_layout.addWidget(self.delete_row_button)

        # Add Return Items toggle button
        self.return_toggle_button = QPushButton("Toggle Return Items (Ctrl+R)")
        self.return_toggle_button.setCheckable(True)
        self.return_toggle_button.clicked.connect(widget.toggle_return_mode)
        table_actions_layout.addWidget(self.return_toggle_button)

        # Add Silver Bar toggle button
        self.silver_bar_toggle_button = QPushButton("Toggle Silver Bars (Ctrl+B)")
        self.silver_bar_toggle_button.setCheckable(True)
        self.silver_bar_toggle_button.clicked.connect(widget.toggle_silver_bar_mode)
        table_actions_layout.addWidget(self.silver_bar_toggle_button)

        # Add stretch to push button to the left
        table_actions_layout.addStretch()

        self.layout.addLayout(table_actions_layout)

        # Create Table for Item Entry
        self._setup_item_table()
        self.layout.addWidget(self.item_table)

        # Set up totals section
        self._setup_totals()

        # Buttons layout
        self._setup_buttons()

    def _setup_header_form(self):
        """Set up the header form for voucher details."""
        form_layout = QGridLayout()

        # Voucher No
        form_layout.addWidget(QLabel("Voucher No:"), 0, 0)
        self.voucher_edit = QLineEdit()
        self.voucher_edit.setMaximumWidth(150)
        form_layout.addWidget(self.voucher_edit, 0, 1)

        # Generate button
        self.generate_button = QPushButton("Generate")
        form_layout.addWidget(self.generate_button, 0, 2)

        # Date
        form_layout.addWidget(QLabel("Date:"), 0, 3)
        self.date_edit = QDateEdit()
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDate(QDate.currentDate())
        self.date_edit.setMaximumWidth(120)
        form_layout.addWidget(self.date_edit, 0, 4)

        # Silver Rate
        form_layout.addWidget(QLabel("Silver Rate:"), 0, 5)
        self.silver_rate_spin = QDoubleSpinBox()
        self.silver_rate_spin.setRange(0, 1000000)
        self.silver_rate_spin.setDecimals(2)
        self.silver_rate_spin.setValue(0)
        form_layout.addWidget(self.silver_rate_spin, 0, 6)

        # Add the form layout to the main layout
        self.layout.addLayout(form_layout)

    def _setup_item_table(self):
        """Set up the table for item entry."""
        self.item_table = QTableWidget()
        self.item_table.setColumnCount(11)  # Column for Return/Silver Bar indicator
        self.item_table.setHorizontalHeaderLabels([
            "Code", "Item Name", "Gross", "Poly", "Net Wt",
            "P%", "W.Rate", "P/Q", "Wage", "Fine", "Type"
        ])

        # Set column widths
        self.item_table.setColumnWidth(0, 80)  # Code
        self.item_table.setColumnWidth(1, 200)  # Item Name
        self.item_table.setColumnWidth(2, 80)  # Gross
        self.item_table.setColumnWidth(3, 80)  # Poly
        self.item_table.setColumnWidth(4, 80)  # Net Wt
        self.item_table.setColumnWidth(5, 80)  # P%
        self.item_table.setColumnWidth(6, 80)  # W.Rate
        self.item_table.setColumnWidth(7, 80)  # P/Q
        self.item_table.setColumnWidth(8, 80)  # Wage
        self.item_table.setColumnWidth(9, 80)  # Fine
        self.item_table.setColumnWidth(10, 80)  # Type (Return/Silver Bar/No)

        # Set table properties - enable as many edit triggers as possible
        self.item_table.setEditTriggers(
            QTableWidget.DoubleClicked |
            QTableWidget.EditKeyPressed |
            QTableWidget.AnyKeyPressed |
            QTableWidget.CurrentChanged
        )

        self.item_table.setSelectionBehavior(QAbstractItemView.SelectItems)
        self.item_table.setSelectionMode(QTableWidget.SingleSelection)

        # Do not create any rows here - we'll do that in the add_empty_row method

    def _setup_totals(self):
        """Set up the totals section."""
        totals_layout = QGridLayout()

        # Regular items totals
        totals_layout.addWidget(QLabel("Regular Items:"), 0, 0, 1, 2)

        # Total Gross (Regular)
        totals_layout.addWidget(QLabel("Total Gross:"), 1, 0)
        self.total_gross_label = QLabel("0.000")
        totals_layout.addWidget(self.total_gross_label, 1, 1)

        # Total Net (Regular)
        totals_layout.addWidget(QLabel("Total Net:"), 1, 2)
        self.total_net_label = QLabel("0.000")
        totals_layout.addWidget(self.total_net_label, 1, 3)

        # Total Fine (Regular)
        totals_layout.addWidget(QLabel("Total Fine:"), 2, 0)
        self.total_fine_label = QLabel("0.000")
        totals_layout.addWidget(self.total_fine_label, 2, 1)

        # Fine Value (Total Fine × Silver Rate)
        totals_layout.addWidget(QLabel("Fine Value:"), 2, 2)
        self.fine_value_label = QLabel("0.00")
        totals_layout.addWidget(self.fine_value_label, 2, 3)

        # Total Wage (Regular)
        totals_layout.addWidget(QLabel("Total Wage:"), 3, 0)
        self.total_wage_label = QLabel("0.00")
        totals_layout.addWidget(self.total_wage_label, 3, 1)

        # Return items totals
        totals_layout.addWidget(QLabel("Return Items:"), 4, 0, 1, 2)

        # Total Gross (Return)
        totals_layout.addWidget(QLabel("Return Gross:"), 5, 0)
        self.return_gross_label = QLabel("0.000")
        totals_layout.addWidget(self.return_gross_label, 5, 1)

        # Total Net (Return)
        totals_layout.addWidget(QLabel("Return Net:"), 5, 2)
        self.return_net_label = QLabel("0.000")
        totals_layout.addWidget(self.return_net_label, 5, 3)

        # Total Fine (Return)
        totals_layout.addWidget(QLabel("Return Fine:"), 6, 0)
        self.return_fine_label = QLabel("0.000")
        totals_layout.addWidget(self.return_fine_label, 6, 1)

        # Fine Value (Return Fine × Silver Rate)
        totals_layout.addWidget(QLabel("Return Value:"), 6, 2)
        self.return_value_label = QLabel("0.00")
        totals_layout.addWidget(self.return_value_label, 6, 3)

        # Total Wage (Return)
        totals_layout.addWidget(QLabel("Return Wage:"), 7, 0)
        self.return_wage_label = QLabel("0.00")
        totals_layout.addWidget(self.return_wage_label, 7, 1)

        # Silver Bar totals (new)
        totals_layout.addWidget(QLabel("Silver Bars:"), 8, 0, 1, 2)

        # Total Gross (Silver Bars)
        totals_layout.addWidget(QLabel("Bar Gross:"), 9, 0)
        self.bar_gross_label = QLabel("0.000")
        totals_layout.addWidget(self.bar_gross_label, 9, 1)

        # Total Net (Silver Bars)
        totals_layout.addWidget(QLabel("Bar Net:"), 9, 2)
        self.bar_net_label = QLabel("0.000")
        totals_layout.addWidget(self.bar_net_label, 9, 3)

        # Total Fine (Silver Bars)
        totals_layout.addWidget(QLabel("Bar Fine:"), 10, 0)
        self.bar_fine_label = QLabel("0.000")
        totals_layout.addWidget(self.bar_fine_label, 10, 1)

        # Fine Value (Silver Bar Fine × Silver Rate)
        totals_layout.addWidget(QLabel("Bar Value:"), 10, 2)
        self.bar_value_label = QLabel("0.00")
        totals_layout.addWidget(self.bar_value_label, 10, 3)

        # Net totals (includes silver bars now)
        totals_layout.addWidget(QLabel("Net Totals:"), 11, 0, 1, 2)

        # Net Fine (Regular - Return - Silver Bars)
        totals_layout.addWidget(QLabel("Net Fine:"), 12, 0)
        self.net_fine_label = QLabel("0.000")
        totals_layout.addWidget(self.net_fine_label, 12, 1)

        # Net Value
        totals_layout.addWidget(QLabel("Net Value:"), 12, 2)
        self.net_value_label = QLabel("0.00")
        totals_layout.addWidget(self.net_value_label, 12, 3)

        # Net Wage
        totals_layout.addWidget(QLabel("Net Wage:"), 13, 0)
        self.net_wage_label = QLabel("0.00")
        totals_layout.addWidget(self.net_wage_label, 13, 1)

        self.layout.addLayout(totals_layout)

    def _setup_buttons(self):
        """Set up the action buttons."""
        button_layout = QHBoxLayout()

        # Save button
        self.save_button = QPushButton("Save")
        button_layout.addWidget(self.save_button)

        # Print button
        self.print_button = QPushButton("Print")
        button_layout.addWidget(self.print_button)

        # History button
        self.history_button = QPushButton("History")
        button_layout.addWidget(self.history_button)

        # Silver Bars button
        self.silver_bars_button = QPushButton("Silver Bars")
        button_layout.addWidget(self.silver_bars_button)

        # Clear button
        self.clear_button = QPushButton("New")
        button_layout.addWidget(self.clear_button)

        self.layout.addLayout(button_layout)