#!/usr/bin/env python
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QFormLayout, # Added QWidget, QFormLayout
                             QLineEdit, QPushButton, QTableWidget, QTableWidgetItem,
                             QHeaderView, QDoubleSpinBox, QDateEdit, QAbstractItemView,
                              QCheckBox, QStyledItemDelegate, QFrame, QSpinBox) # Added QSpinBox
# Removed QFocusEvent, QValidator. Added QEvent
from PyQt5.QtGui import QDoubleValidator, QIntValidator, QFont # Added QFont
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
                key = event.key()
                # Check for Enter/Return/Tab press
                if key in (Qt.Key_Return, Qt.Key_Enter, Qt.Key_Tab):
                    # If it's Gross/Poly and the editor is empty...
                    if col in [COL_GROSS, COL_POLY] and editor.text() == "":
                        # Directly set model data to 0.0
                        index.model().setData(index, 0.0, Qt.EditRole)
                        # Emit closeEditor signal to close the editor properly
                        self.closeEditor.emit(editor, QStyledItemDelegate.SubmitModelCache)
                        return True # Event handled, stop further processing
                # --- Add Backspace handling ---
                elif key == Qt.Key_Backspace and editor.text() == "":
                    # Close the current editor without submitting data
                    self.closeEditor.emit(editor, QStyledItemDelegate.NoHint)
                    # Get the main estimate widget (parent of the table)
                    table_widget = self.parent()
                    if table_widget:
                        estimate_widget = table_widget.parent()
                        if estimate_widget and hasattr(estimate_widget, 'move_to_previous_cell'):
                            # Use QTimer to ensure focus change happens after editor closes
                            from PyQt5.QtCore import QTimer
                            QTimer.singleShot(0, estimate_widget.move_to_previous_cell)
                    return True # Event handled

        # For all other events or conditions, use the default behavior
        return super().eventFilter(editor, event)


class EstimateUI:
    """UI components and setup for the estimate entry widget."""

    def setup_ui(self, widget):
        """Set up the user interface for the estimate entry widget."""
        # Main layout
        self.layout = QVBoxLayout(widget)

        # Header Form
        self._setup_header_form(widget)
        self.layout.addSpacing(5)
        line_header = QFrame()
        line_header.setFrameShape(QFrame.HLine)
        line_header.setFrameShadow(QFrame.Sunken)
        self.layout.addWidget(line_header)
        self.layout.addSpacing(8)

        # Table Actions
        table_actions_layout = QHBoxLayout()
        self.delete_row_button = QPushButton("Delete Row")
        self.delete_row_button.setToolTip("Delete the currently selected row (Ctrl+D)")
        self.delete_row_button.clicked.connect(widget.delete_current_row)
        table_actions_layout.addWidget(self.delete_row_button)
        self.return_toggle_button = QPushButton("Return Items")
        self.return_toggle_button.setToolTip("Toggle Return Item entry mode for new rows (Ctrl+R)")
        self.return_toggle_button.setCheckable(True)
        table_actions_layout.addWidget(self.return_toggle_button)
        self.silver_bar_toggle_button = QPushButton("Silver Bars")
        self.silver_bar_toggle_button.setToolTip("Toggle Silver Bar entry mode for new rows (Ctrl+B)")
        self.silver_bar_toggle_button.setCheckable(True)
        table_actions_layout.addWidget(self.silver_bar_toggle_button)
        table_actions_layout.addSpacing(20)
        self.last_balance_button = QPushButton("LB")
        self.last_balance_button.setToolTip("Add Last Balance to this estimate")
        table_actions_layout.addWidget(self.last_balance_button)
        self.save_button = QPushButton("Save Estimate")
        self.save_button.setToolTip("Save the current estimate details (Ctrl+S - standard shortcut often works)")
        table_actions_layout.addWidget(self.save_button)
        self.print_button = QPushButton("Print Preview")
        self.print_button.setToolTip("Preview and print the current estimate (requires saving first)")
        table_actions_layout.addWidget(self.print_button)
        self.history_button = QPushButton("Estimate History")
        self.history_button.setToolTip("View, load, or print past estimates")
        table_actions_layout.addWidget(self.history_button)
        self.silver_bars_button = QPushButton("Manage Silver Bars")
        self.silver_bars_button.setToolTip("View and manage silver bar inventory")
        table_actions_layout.addWidget(self.silver_bars_button)
        self.clear_button = QPushButton("New Estimate")
        self.clear_button.setToolTip("Clear the form to start a new estimate")
        table_actions_layout.addWidget(self.clear_button)
        table_actions_layout.addSpacing(10)
        self.delete_estimate_button = QPushButton("Delete This Estimate")
        self.delete_estimate_button.setToolTip("Delete the currently loaded/displayed estimate")
        table_actions_layout.addWidget(self.delete_estimate_button)
        table_actions_layout.addStretch()
        self.layout.addLayout(table_actions_layout)
        self.layout.addSpacing(8)

        # Item Table
        self._setup_item_table(widget)
        self.layout.addWidget(self.item_table)

        # Totals Section
        self._setup_totals() # Call the redesigned totals setup


    def _setup_header_form(self, widget):
        """Set up the header form for voucher details."""
        self.mode_indicator_label = QLabel("Mode: Regular Items")
        self.mode_indicator_label.setStyleSheet("font-weight: bold; color: green;")
        self.mode_indicator_label.setToolTip("Indicates whether Return Items or Silver Bar entry mode is active.")

        form_layout = QGridLayout()
        form_layout.addWidget(QLabel("Voucher No:"), 0, 0)
        self.voucher_edit = QLineEdit()
        self.voucher_edit.setMaximumWidth(150)
        self.voucher_edit.setToolTip("Enter an existing voucher number to load or leave blank for a new estimate.")
        form_layout.addWidget(self.voucher_edit, 0, 1)
        self.load_button = QPushButton("Load")
        self.load_button.setToolTip("Load the estimate with the entered voucher number.")
        form_layout.addWidget(self.load_button, 0, 2)
        form_layout.addWidget(QLabel("Date:"), 0, 3)
        self.date_edit = QDateEdit()
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDate(QDate.currentDate())
        self.date_edit.setMaximumWidth(120)
        self.date_edit.setToolTip("Date of the estimate.")
        form_layout.addWidget(self.date_edit, 0, 4)
        form_layout.addWidget(QLabel("Silver Rate:"), 0, 5)
        self.silver_rate_spin = QDoubleSpinBox()
        self.silver_rate_spin.setRange(0, 1000000)
        self.silver_rate_spin.setDecimals(2)
        self.silver_rate_spin.setPrefix("₹ ")
        self.silver_rate_spin.setValue(0)
        self.silver_rate_spin.setToolTip("Silver rate for calculating fine value.")
        form_layout.addWidget(self.silver_rate_spin, 0, 6)
        form_layout.addWidget(QLabel("Note:"), 0, 7)
        self.note_edit = QLineEdit()
        self.note_edit.setMinimumWidth(200)
        self.note_edit.setToolTip("Add a note for this estimate (will be saved with the estimate)")
        form_layout.addWidget(self.note_edit, 0, 8)
        form_layout.addWidget(self.mode_indicator_label, 0, 9, alignment=Qt.AlignLeft | Qt.AlignVCenter)
        form_layout.setColumnStretch(10, 1)
        self.layout.addLayout(form_layout)


    def _setup_item_table(self, widget):
        """Set up the table for item entry."""
        self.item_table = QTableWidget()
        self.item_table.setColumnCount(11)
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
        self.item_table.setStyleSheet("""
            QTableWidget {
                background-color: #f8f8f8; /* Base color: Off-white */
                alternate-background-color: #eeeeee; /* Alternate color: Light Gray */
                gridline-color: #d0d0d0; /* Optional: Adjust gridline color */
            }
        """)

    def _setup_totals(self):
        """Set up the totals section with Breakdown | [Stretch] | Final layout."""

        main_totals_layout = QHBoxLayout()
        main_totals_layout.setSpacing(15) # Spacing between sections

        # Helper function to create a form layout for a breakdown section
        def create_breakdown_form(title, labels_attrs):
            form = QFormLayout()
            form.setSpacing(5)
            form.addRow(QLabel(f"<b><u>{title}</u></b>"))
            for label_text, attr_name, default_value in labels_attrs:
                label = QLabel(default_value)
                label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
                setattr(self, attr_name, label)
                form.addRow(label_text, label)
            # REMOVED Spacer row and QVBoxLayout wrapper
            return form # Return the QFormLayout directly

        # Regular Items
        regular_labels = [
            ("Gross Wt:", 'total_gross_label', "0.000"),
            ("Net Wt:", 'total_net_label', "0.000"),
            ("Fine Wt:", 'total_fine_label', "0.000"),
        ]
        main_totals_layout.addLayout(create_breakdown_form("Regular", regular_labels))

        # Vertical Separator 1
        sep1 = QFrame()
        sep1.setFrameShape(QFrame.VLine)
        sep1.setFrameShadow(QFrame.Sunken)
        main_totals_layout.addWidget(sep1)

        # Return Items
        return_labels = [
            ("Gross Wt:", 'return_gross_label', "0.000"),
            ("Net Wt:", 'return_net_label', "0.000"),
            ("Fine Wt:", 'return_fine_label', "0.000"),
        ]
        main_totals_layout.addLayout(create_breakdown_form("Return", return_labels))

        # Vertical Separator 2
        sep2 = QFrame()
        sep2.setFrameShape(QFrame.VLine)
        sep2.setFrameShadow(QFrame.Sunken)
        main_totals_layout.addWidget(sep2)

        # Silver Bars
        bar_labels = [
            ("Gross Wt:", 'bar_gross_label', "0.000"),
            ("Net Wt:", 'bar_net_label', "0.000"),
            ("Fine Wt:", 'bar_fine_label', "0.000"),
        ]
        main_totals_layout.addLayout(create_breakdown_form("Silver Bar", bar_labels))

        # Add stretch to push Final Calculation to the right
        main_totals_layout.addStretch(1)

        # Vertical Separator 3 (Before Final Calc)
        sep3 = QFrame()
        sep3.setFrameShape(QFrame.VLine)
        sep3.setFrameShadow(QFrame.Sunken)
        main_totals_layout.addWidget(sep3)

        # Final Calculation Section (using QFormLayout directly)
        final_calc_form = QFormLayout()
        final_calc_form.setSpacing(8)
        final_title_label = QLabel("<b><u>Final Calculation</u></b>")
        # Increase title font size
        final_title_font = final_title_label.font()
        final_title_font.setPointSize(final_title_font.pointSize() + 1) # Increase by 1pt
        final_title_label.setFont(final_title_font)
        final_calc_form.addRow(final_title_label) # Title for the section

        # Net Fine
        self.net_fine_label = QLabel("0.000")
        self.net_fine_label.setStyleSheet("font-weight: bold;")
        self.net_fine_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        net_fine_header = QLabel("<b>Net Fine Wt:</b>")
        # Increase font size
        net_fine_font = self.net_fine_label.font(); net_fine_font.setPointSize(net_fine_font.pointSize() + 1); self.net_fine_label.setFont(net_fine_font)
        net_fine_header_font = net_fine_header.font(); net_fine_header_font.setPointSize(net_fine_header_font.pointSize() + 1); net_fine_header.setFont(net_fine_header_font)
        final_calc_form.addRow(net_fine_header, self.net_fine_label)

        # Net Wage
        self.net_wage_label = QLabel("0.00")
        self.net_wage_label.setStyleSheet("font-weight: bold;")
        self.net_wage_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        net_wage_header = QLabel("<b>Net Wage:</b>")
        # Increase font size
        net_wage_font = self.net_wage_label.font(); net_wage_font.setPointSize(net_wage_font.pointSize() + 1); self.net_wage_label.setFont(net_wage_font)
        net_wage_header_font = net_wage_header.font(); net_wage_header_font.setPointSize(net_wage_header_font.pointSize() + 1); net_wage_header.setFont(net_wage_header_font)
        final_calc_form.addRow(net_wage_header, self.net_wage_label)

        # Separator before Grand Total
        line_before_grand = QFrame()
        line_before_grand.setFrameShape(QFrame.HLine)
        line_before_grand.setFrameShadow(QFrame.Sunken)
        final_calc_form.addRow(line_before_grand)

        # Grand Total
        self.grand_total_label = QLabel("0.00")
        self.grand_total_label.setStyleSheet("font-weight: bold; color: blue; font-size: 10pt;")
        self.grand_total_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        final_calc_form.addRow("<b>Grand Total:</b>", self.grand_total_label)

        # REMOVED QVBoxLayout wrapper for Final Calc
        # Add Final Calc form layout directly to the main horizontal layout
        main_totals_layout.addLayout(final_calc_form)

        # Add the main horizontal layout to the widget's main vertical layout
        self.layout.addLayout(main_totals_layout)

    # Removed _setup_buttons method as buttons are now created directly in setup_ui
