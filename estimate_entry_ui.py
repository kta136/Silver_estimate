#!/usr/bin/env python
from PyQt5.QtWidgets import (QVBoxLayout, QHBoxLayout, QGridLayout, QLabel,
                             QLineEdit, QPushButton, QTableWidget, QTableWidgetItem,
                             QHeaderView, QDoubleSpinBox, QDateEdit, QAbstractItemView,
                              QCheckBox, QStyledItemDelegate, QFrame) # Added QFrame
# Removed QFocusEvent, QValidator. Added QEvent
from PyQt5.QtGui import QDoubleValidator, QIntValidator
from PyQt5.QtCore import Qt, QDate, QLocale, QModelIndex, QEvent # Keep QModelIndex, Add QEvent

# --- Column Constants (defined here for UI setup & Delegate) ---
COL_CODE = 0
COL_ITEM_NAME = 1
COL_GROSS = 2
COL_POLY = 3
COL_NET_WT = 4
COL_PURITY = 5
COL_WAGE_RATE = 6
COL_PIECES = 7
COL_WAGE_AMT = 8
COL_FINE_WT = 9
COL_TYPE = 10
# --- End Constants ---

# Removed ZeroHandlingLineEdit class

# Custom Delegate for Numeric Input Validation
class NumericDelegate(QStyledItemDelegate):
    def createEditor(self, parent, option, index):
        # Use standard QLineEdit for all editable columns we handle
        editor = QLineEdit(parent)
        # Store index for use in eventFilter
        editor.setProperty("modelIndex", index)
        col = index.column()
        locale = QLocale.system()

        # Apply standard validators
        if col in [COL_GROSS, COL_POLY, COL_PURITY, COL_WAGE_RATE]:
            decimals = 3 if col in [COL_GROSS, COL_POLY] else 2
            validator = QDoubleValidator(0.0, 999999.999, decimals, editor)
            validator.setNotation(QDoubleValidator.StandardNotation)
            validator.setLocale(locale)
            editor.setValidator(validator)
        elif col == COL_PIECES:
            validator = QIntValidator(0, 999999, editor)
            editor.setValidator(validator)
        else:
             # If column is not one we explicitly handle with validation,
             # return standard editor without installing filter or validator.
             # Or potentially return super().createEditor if base class handles others.
             # For now, just return the basic QLineEdit for Code/Name/Type if needed.
             # Calculated columns won't be edited directly.
             return editor # Return basic editor for Code/Name/Type

        # Install event filter ONLY on editors with validators we manage
        editor.installEventFilter(self)
        return editor

    def setEditorData(self, editor, index):
        # Ensure editor is a QLineEdit before proceeding
        if not isinstance(editor, QLineEdit):
            super().setEditorData(editor, index)
            return

        value = index.model().data(index, Qt.EditRole)
        col = index.column()

        # For Gross/Poly, display "" if value is 0 or 0.0
        if col in [COL_GROSS, COL_POLY]:
            try:
                if value is not None and float(value) == 0.0:
                    display_text = ""
                else:
                    display_text = str(value) if value is not None else ""
            except (ValueError, TypeError):
                 display_text = str(value) if value is not None else ""
        else:
             # Default behavior for other columns
             display_text = str(value) if value is not None else ""

        editor.setText(display_text)


    def setModelData(self, editor, model, index):
         # Ensure editor is a QLineEdit before proceeding
        if not isinstance(editor, QLineEdit):
            super().setModelData(editor, model, index)
            return

        col = index.column()
        value = editor.text().strip()
        locale = QLocale.system()

        # Handle Gross and Poly: Convert empty to 0.0
        if col in [COL_GROSS, COL_POLY]:
            if not value: # Empty string directly becomes 0.0
                model.setData(index, 0.0, Qt.EditRole)
            else:
                double_val, ok = locale.toDouble(value)
                # Also treat explicit "0" as 0.0 if needed, though locale.toDouble might handle it
                if ok and double_val == 0.0:
                     model.setData(index, 0.0, Qt.EditRole)
                elif ok:
                     model.setData(index, double_val, Qt.EditRole)
                else: # Conversion failed
                    model.setData(index, 0.0, Qt.EditRole) # Default to 0.0 on error
            return # Processed

        # Handle other numeric columns
        try:
            if col in [COL_PURITY, COL_WAGE_RATE]:
                double_val, ok = locale.toDouble(value)
                model.setData(index, double_val if ok else 0.0, Qt.EditRole)
            elif col == COL_PIECES:
                model.setData(index, int(value) if value else 0, Qt.EditRole)
            else: # Handle non-numeric columns
                model.setData(index, value, Qt.EditRole)
        except ValueError: # Catch int conversion error
             if col == COL_PIECES:
                 model.setData(index, 0, Qt.EditRole)
             else: # Fallback for others
                 model.setData(index, value, Qt.EditRole) # Keep original text

    def updateEditorGeometry(self, editor, option, index):
         # Ensure editor is a QLineEdit before proceeding
        if isinstance(editor, QLineEdit):
            editor.setGeometry(option.rect)
        else:
            super().updateEditorGeometry(editor, option, index)

    # Override eventFilter to handle Enter/Tab on empty Gross/Poly
    def eventFilter(self, editor, event):
        if event.type() == QEvent.KeyPress and isinstance(editor, QLineEdit):
            index = editor.property("modelIndex")
            if index and index.isValid():
                col = index.column()
                # Check for Enter/Return/Tab press
                if event.key() in (Qt.Key_Return, Qt.Key_Enter, Qt.Key_Tab):
                    # If it's Gross/Poly and the editor is empty...
                    if col in [COL_GROSS, COL_POLY] and editor.text() == "":
                        # Directly set model data to 0.0
                        index.model().setData(index, 0.0, Qt.EditRole)
                        # Emit closeEditor signal to close the editor properly
                        self.closeEditor.emit(editor, QStyledItemDelegate.SubmitModelCache)
                        return True # Event handled, stop further processing

        # For all other events or conditions, use the default behavior
        return super().eventFilter(editor, event)


class EstimateUI:
    """UI components and setup for the estimate entry widget."""

    def setup_ui(self, widget):
        """Set up the user interface for the estimate entry widget."""
        # ... (Main layout, Header, Header Form - unchanged) ...
        # Main layout
        self.layout = QVBoxLayout(widget)

        # Header
        header_layout = QHBoxLayout()
        header_label = QLabel("Silver Estimation")
        header_label.setStyleSheet("font-size: 16pt; font-weight: bold;")
        header_layout.addWidget(header_label)
        header_layout.addStretch()
        # ---- Add Mode Status Label ----
        self.mode_indicator_label = QLabel("Mode: Regular Items") # Changed name
        self.mode_indicator_label.setStyleSheet("font-weight: bold; color: green;")
        self.mode_indicator_label.setToolTip("Indicates whether Return Items or Silver Bar entry mode is active.")
        header_layout.addWidget(self.mode_indicator_label)
        # ------------------------------
        self.layout.addLayout(header_layout)


        # Form layout for voucher details
        self._setup_header_form(widget) # Pass widget for tooltips

        # Item table actions layout
        table_actions_layout = QHBoxLayout()

        # Add delete row button
        self.delete_row_button = QPushButton("Delete Row") # Removed shortcut hint from text
        self.delete_row_button.setToolTip("Delete the currently selected row (Ctrl+D)")
        self.delete_row_button.clicked.connect(widget.delete_current_row)
        table_actions_layout.addWidget(self.delete_row_button)

        # Add Return Items toggle button
        self.return_toggle_button = QPushButton("Return Items") # Removed shortcut hint
        self.return_toggle_button.setToolTip("Toggle Return Item entry mode for new rows (Ctrl+R)")
        self.return_toggle_button.setCheckable(True)
        #self.return_toggle_button.clicked.connect(widget.toggle_return_mode)
        table_actions_layout.addWidget(self.return_toggle_button)

        # Add Silver Bar toggle button
        self.silver_bar_toggle_button = QPushButton("Silver Bars") # Removed shortcut hint
        self.silver_bar_toggle_button.setToolTip("Toggle Silver Bar entry mode for new rows (Ctrl+B)")
        self.silver_bar_toggle_button.setCheckable(True)
        #self.silver_bar_toggle_button.clicked.connect(widget.toggle_silver_bar_mode)
        table_actions_layout.addWidget(self.silver_bar_toggle_button)

        # Add stretch to push buttons to the left
        table_actions_layout.addStretch()

        self.layout.addLayout(table_actions_layout)

        # Create Table for Item Entry
        self._setup_item_table(widget) # Pass widget for tooltips
        self.layout.addWidget(self.item_table)

        # Set up totals section
        self._setup_totals()

        # Add a visual separator
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        self.layout.addWidget(line)

        # Buttons layout
        self._setup_buttons(widget) # Pass widget for tooltips


    def _setup_header_form(self, widget):
        """Set up the header form for voucher details."""
        form_layout = QGridLayout()

        # Voucher No
        form_layout.addWidget(QLabel("Voucher No:"), 0, 0)
        self.voucher_edit = QLineEdit()
        self.voucher_edit.setMaximumWidth(150)
        self.voucher_edit.setToolTip("Enter an existing voucher number to load or leave blank/generate new.")
        form_layout.addWidget(self.voucher_edit, 0, 1)

        # Generate button
        self.generate_button = QPushButton("Generate")
        self.generate_button.setToolTip("Generate a new voucher number based on today's date.")
        form_layout.addWidget(self.generate_button, 0, 2)

        # Date
        form_layout.addWidget(QLabel("Date:"), 0, 3)
        self.date_edit = QDateEdit()
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDate(QDate.currentDate())
        self.date_edit.setMaximumWidth(120)
        self.date_edit.setToolTip("Date of the estimate.")
        form_layout.addWidget(self.date_edit, 0, 4)

        # Silver Rate
        form_layout.addWidget(QLabel("Silver Rate:"), 0, 5)
        self.silver_rate_spin = QDoubleSpinBox()
        self.silver_rate_spin.setRange(0, 1000000)
        self.silver_rate_spin.setDecimals(2)
        self.silver_rate_spin.setPrefix("₹ ") # Optional: Add currency prefix
        self.silver_rate_spin.setValue(0)
        self.silver_rate_spin.setToolTip("Silver rate for calculating fine value.")
        form_layout.addWidget(self.silver_rate_spin, 0, 6)

        # Add some spacing
        form_layout.setColumnStretch(7, 1) # Add stretch to push elements left

        # Add the form layout to the main layout
        self.layout.addLayout(form_layout)


    def _setup_item_table(self, widget):
        """Set up the table for item entry."""
        self.item_table = QTableWidget()
        self.item_table.setColumnCount(11) # Consistent column count
        headers = [
            "Code", "Item Name", "Gross Wt", "Poly Wt", "Net Wt",
            "Purity %", "Wage Rate", "Pieces", "Wage Amt", "Fine Wt", "Type"
        ]
        header_tooltips = [
            "Item code (press Enter/Tab to lookup)", "Item description (filled from code)",
            "Gross Weight (grams)", "Poly/Stone Weight (grams)", "Net Weight (Gross - Poly, calculated)",
            "Silver Purity (%)", "Wage rate per gram or per piece", "Number of pieces (for PC wage type)",
            "Total Wage Amount (calculated)", "Fine Silver Weight (calculated)", "Item Type (Regular/Return/Silver Bar)"
        ]
        self.item_table.setHorizontalHeaderLabels(headers)

        for i, tooltip in enumerate(header_tooltips):
            self.item_table.horizontalHeaderItem(i).setToolTip(tooltip)

        # Use constants for setting column widths and properties
        self.item_table.setColumnWidth(COL_CODE, 80)
        self.item_table.horizontalHeader().setSectionResizeMode(COL_ITEM_NAME, QHeaderView.Stretch)
        self.item_table.setColumnWidth(COL_GROSS, 85)
        self.item_table.setColumnWidth(COL_POLY, 85)
        self.item_table.setColumnWidth(COL_NET_WT, 85)
        self.item_table.setColumnWidth(COL_PURITY, 80)
        self.item_table.setColumnWidth(COL_WAGE_RATE, 80)
        self.item_table.setColumnWidth(COL_PIECES, 60)
        self.item_table.setColumnWidth(COL_WAGE_AMT, 85)
        self.item_table.setColumnWidth(COL_FINE_WT, 85)
        self.item_table.setColumnWidth(COL_TYPE, 80)

        self.item_table.setEditTriggers(
            QTableWidget.DoubleClicked | QTableWidget.EditKeyPressed | QTableWidget.CurrentChanged
        )
        self.item_table.setSelectionBehavior(QAbstractItemView.SelectItems)
        self.item_table.setSelectionMode(QTableWidget.SingleSelection)
        self.item_table.setAlternatingRowColors(True)

        # Delegate application moved to EstimateEntryWidget __init__

    # ... (_setup_totals and _setup_buttons remain the same) ...
    def _setup_totals(self):
        """Set up the totals section."""
        totals_layout = QGridLayout()

        col1, col2, col3, col4, col5, col6, col7, col8 = 0, 1, 2, 3, 4, 5, 6, 7

        # --- Row 0: Headers ---
        totals_layout.addWidget(QLabel("<u>Regular Items</u>"), 0, col1, 1, col2+1, alignment=Qt.AlignCenter)
        totals_layout.addWidget(QLabel("<u>Return Items</u>"), 0, col3, 1, col2+1, alignment=Qt.AlignCenter)
        totals_layout.addWidget(QLabel("<u>Silver Bars</u>"), 0, col5, 1, col2+1, alignment=Qt.AlignCenter)
        totals_layout.addWidget(QLabel("<u><b>Net Totals</b></u>"), 0, col7, 1, col2+1, alignment=Qt.AlignCenter)


        # --- Row 1: Gross/Net ---
        totals_layout.addWidget(QLabel("Gross:"), 1, col1)
        self.total_gross_label = QLabel("0.000")
        totals_layout.addWidget(self.total_gross_label, 1, col2)

        totals_layout.addWidget(QLabel("Gross:"), 1, col3)
        self.return_gross_label = QLabel("0.000")
        totals_layout.addWidget(self.return_gross_label, 1, col4)

        totals_layout.addWidget(QLabel("Gross:"), 1, col5)
        self.bar_gross_label = QLabel("0.000")
        totals_layout.addWidget(self.bar_gross_label, 1, col6)

        # (Net totals don't usually show Gross/Net)
        totals_layout.addWidget(QLabel(""), 1, col7) # Spacer
        totals_layout.addWidget(QLabel(""), 1, col8) # Spacer


        # --- Row 2: Net/Fine ---
        totals_layout.addWidget(QLabel("Net:"), 2, col1)
        self.total_net_label = QLabel("0.000")
        totals_layout.addWidget(self.total_net_label, 2, col2)

        totals_layout.addWidget(QLabel("Net:"), 2, col3)
        self.return_net_label = QLabel("0.000")
        totals_layout.addWidget(self.return_net_label, 2, col4)

        totals_layout.addWidget(QLabel("Net:"), 2, col5)
        self.bar_net_label = QLabel("0.000")
        totals_layout.addWidget(self.bar_net_label, 2, col6)

        totals_layout.addWidget(QLabel("<b>Net Fine:</b>"), 2, col7)
        self.net_fine_label = QLabel("0.000")
        self.net_fine_label.setStyleSheet("font-weight: bold;")
        totals_layout.addWidget(self.net_fine_label, 2, col8)


        # --- Row 3: Fine/Value ---
        totals_layout.addWidget(QLabel("Fine:"), 3, col1)
        self.total_fine_label = QLabel("0.000")
        totals_layout.addWidget(self.total_fine_label, 3, col2)

        totals_layout.addWidget(QLabel("Fine:"), 3, col3)
        self.return_fine_label = QLabel("0.000")
        totals_layout.addWidget(self.return_fine_label, 3, col4)

        totals_layout.addWidget(QLabel("Fine:"), 3, col5)
        self.bar_fine_label = QLabel("0.000")
        totals_layout.addWidget(self.bar_fine_label, 3, col6)

        totals_layout.addWidget(QLabel("<b>Net Value:</b>"), 3, col7)
        self.net_value_label = QLabel("0.00")
        self.net_value_label.setStyleSheet("font-weight: bold;")
        totals_layout.addWidget(self.net_value_label, 3, col8)


        # --- Row 4: Value/Wage ---
        totals_layout.addWidget(QLabel("Value:"), 4, col1)
        self.fine_value_label = QLabel("0.00")
        totals_layout.addWidget(self.fine_value_label, 4, col2)

        totals_layout.addWidget(QLabel("Value:"), 4, col3)
        self.return_value_label = QLabel("0.00")
        totals_layout.addWidget(self.return_value_label, 4, col4)

        totals_layout.addWidget(QLabel("Value:"), 4, col5)
        self.bar_value_label = QLabel("0.00")
        totals_layout.addWidget(self.bar_value_label, 4, col6)

        totals_layout.addWidget(QLabel("<b>Net Wage:</b>"), 4, col7)
        self.net_wage_label = QLabel("0.00")
        self.net_wage_label.setStyleSheet("font-weight: bold;")
        totals_layout.addWidget(self.net_wage_label, 4, col8)

        # --- Row 5: Wage ---
        totals_layout.addWidget(QLabel("Wage:"), 5, col1)
        self.total_wage_label = QLabel("0.00")
        totals_layout.addWidget(self.total_wage_label, 5, col2)

        totals_layout.addWidget(QLabel("Wage:"), 5, col3)
        self.return_wage_label = QLabel("0.00")
        totals_layout.addWidget(self.return_wage_label, 5, col4)

        # (Silver bars typically have 0 wage, no label needed)

        # --- Row 6: Grand Total ---
        totals_layout.addWidget(QLabel(""), 5, col1) # Spacer
        totals_layout.addWidget(QLabel(""), 5, col2) # Spacer
        totals_layout.addWidget(QLabel(""), 5, col3) # Spacer
        totals_layout.addWidget(QLabel(""), 5, col4) # Spacer
        totals_layout.addWidget(QLabel(""), 5, col5) # Spacer
        totals_layout.addWidget(QLabel(""), 5, col6) # Spacer

        totals_layout.addWidget(QLabel("<b>Grand Total:</b>"), 5, col7)
        self.grand_total_label = QLabel("0.00")
        self.grand_total_label.setStyleSheet("font-weight: bold; color: blue;") # Make it stand out
        totals_layout.addWidget(self.grand_total_label, 5, col8)


        # Set column stretch factors for spacing
        totals_layout.setColumnStretch(col2, 1)
        totals_layout.setColumnStretch(col4, 1)
        totals_layout.setColumnStretch(col6, 1)
        totals_layout.setColumnStretch(col8, 1)

        self.layout.addLayout(totals_layout)

    def _setup_buttons(self, widget):
        """Set up the action buttons."""
        button_layout = QHBoxLayout()
        button_layout.addStretch() # Push buttons to the right

        # Save button
        self.save_button = QPushButton("Save Estimate")
        self.save_button.setToolTip("Save the current estimate details (Ctrl+S - standard shortcut often works)")
        button_layout.addWidget(self.save_button)

        # Print button
        self.print_button = QPushButton("Print Preview")
        self.print_button.setToolTip("Preview and print the current estimate (requires saving first)")
        button_layout.addWidget(self.print_button)

        # History button
        self.history_button = QPushButton("Estimate History")
        self.history_button.setToolTip("View, load, or print past estimates")
        button_layout.addWidget(self.history_button)

        # Silver Bars button (perhaps rename for clarity?)
        self.silver_bars_button = QPushButton("Manage Silver Bars")
        self.silver_bars_button.setToolTip("View and manage silver bar inventory")
        button_layout.addWidget(self.silver_bars_button)

        # Clear button
        self.clear_button = QPushButton("New Estimate")
        self.clear_button.setToolTip("Clear the form to start a new estimate")
        button_layout.addWidget(self.clear_button)

        button_layout.addStretch() # Push buttons to the left

        self.layout.addLayout(button_layout)
