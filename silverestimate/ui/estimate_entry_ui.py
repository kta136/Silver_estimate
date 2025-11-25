#!/usr/bin/env python
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFormLayout, # Added QWidget, QFormLayout
                             QLineEdit, QPushButton, QTableWidget, QTableWidgetItem,
                             QHeaderView, QDoubleSpinBox, QDateEdit, QAbstractItemView,
                              QCheckBox, QStyledItemDelegate, QFrame, QSpinBox, QToolButton, QSizePolicy)
from PyQt5.QtWidgets import QStyle
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

        # Table Actions - Modernized Toolbar
        table_actions_layout = QHBoxLayout()
        table_actions_layout.setSpacing(12)
        table_actions_layout.setContentsMargins(0, 0, 0, 0)

        # Primary Action Frame with Modern Styling
        primary_frame = QFrame()
        primary_frame.setObjectName("PrimaryActionStrip")
        primary_frame.setStyleSheet("""
            QFrame#PrimaryActionStrip {
                background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #f8fafc, stop:1 #f1f5f9);
                border: 1px solid #cbd5e1;
                border-radius: 8px;
            }
            QFrame#PrimaryActionStrip QPushButton {
                background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #3b82f6, stop:1 #2563eb);
                color: white;
                border: none;
                border-radius: 6px;
                font-weight: 600;
                padding: 8px 16px;
                min-width: 120px;
                font-size: 10pt;
            }
            QFrame#PrimaryActionStrip QPushButton:hover {
                background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #2563eb, stop:1 #1d4ed8);
            }
            QFrame#PrimaryActionStrip QPushButton:pressed {
                background-color: #1e40af;
                padding: 9px 15px 7px 17px;
            }
            QFrame#PrimaryActionStrip QPushButton:disabled {
                background-color: #cbd5e1;
                color: #64748b;
            }
        """)
        primary_layout = QHBoxLayout(primary_frame)
        primary_layout.setSpacing(10)
        primary_layout.setContentsMargins(14, 8, 14, 8)

        self.save_button = QPushButton("💾 Save")
        self.save_button.setToolTip("Save the current estimate details\nKeyboard: Ctrl+S\nSaves all items and totals to database\nRequired before printing")
        self.save_button.setCursor(Qt.PointingHandCursor)
        primary_layout.addWidget(self.save_button)

        self.print_button = QPushButton("🖨 Print")
        self.print_button.setToolTip("Preview and print the current estimate\nKeyboard: Ctrl+P\nRequires saving the estimate first\nOpens print preview dialog")
        self.print_button.setCursor(Qt.PointingHandCursor)
        primary_layout.addWidget(self.print_button)

        self.clear_button = QPushButton("📄 New")
        self.clear_button.setToolTip("Clear the form to start a new estimate\nKeyboard: Ctrl+N\nResets all fields and generates new voucher\nWill ask for confirmation if unsaved changes")
        self.clear_button.setCursor(Qt.PointingHandCursor)
        primary_layout.addWidget(self.clear_button)

        # Secondary Action Frame with Modern Styling
        secondary_frame = QFrame()
        secondary_frame.setObjectName("SecondaryActionStrip")
        secondary_frame.setStyleSheet("""
            QFrame#SecondaryActionStrip {
                background-color: #ffffff;
                border: 1px solid #e2e8f0;
                border-radius: 8px;
            }
            QFrame#SecondaryActionStrip QPushButton {
                background-color: #f8fafc;
                color: #334155;
                border: 1px solid #cbd5e1;
                border-radius: 5px;
                padding: 6px 12px;
                font-size: 9pt;
                font-weight: 500;
            }
            QFrame#SecondaryActionStrip QPushButton:hover {
                background-color: #e2e8f0;
                border-color: #94a3b8;
            }
            QFrame#SecondaryActionStrip QPushButton:pressed {
                background-color: #cbd5e1;
                padding: 7px 11px 5px 13px;
            }
            QFrame#SecondaryActionStrip QPushButton:disabled {
                background-color: #f1f5f9;
                color: #94a3b8;
                border-color: #e2e8f0;
            }
        """)
        secondary_frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        secondary_layout = QHBoxLayout(secondary_frame)
        secondary_layout.setSpacing(10)
        secondary_layout.setContentsMargins(14, 8, 14, 8)

        def create_action_divider():
            divider = QFrame()
            divider.setFrameShape(QFrame.VLine)
            divider.setStyleSheet("background-color: #cbd5e1; max-width: 1px;")
            divider.setFixedHeight(24)
            return divider

        self.delete_row_button = QPushButton("🗑 Delete Row")
        self.delete_row_button.setToolTip("Delete the currently selected row\nKeyboard: Ctrl+D\nRemoves the active row from the estimate\nCannot be undone")
        self.delete_row_button.clicked.connect(widget.delete_current_row)
        secondary_layout.addWidget(self.delete_row_button)
        secondary_layout.addWidget(create_action_divider())

        self.return_toggle_button = QPushButton("↩ Return Items")
        self.return_toggle_button.setToolTip("Toggle Return Item entry mode for new rows\nKeyboard: Ctrl+R\nNew rows will be marked as Return items\nAffects calculations and item type")
        self.return_toggle_button.setCheckable(True)
        self.return_toggle_button.setMaximumWidth(150)
        self.return_toggle_button.setStyleSheet("""
            QPushButton {
                background-color: #fffbeb;
                border: 1px solid #fcd34d;
                border-radius: 5px;
                color: #92400e;
                font-weight: 600;
                padding: 6px 12px;
                font-size: 9pt;
            }
            QPushButton:hover {
                background-color: #fef3c7;
                border-color: #f59e0b;
            }
            QPushButton:checked {
                background-color: #f59e0b;
                border-color: #d97706;
                color: white;
            }
            QPushButton:checked:hover {
                background-color: #d97706;
            }
        """)
        secondary_layout.addWidget(self.return_toggle_button)

        self.silver_bar_toggle_button = QPushButton("🥈 Silver Bar")
        self.silver_bar_toggle_button.setToolTip("Toggle Silver Bar entry mode for new rows\nKeyboard: Ctrl+B\nNew rows will be marked as Silver Bar items\nCannot use both Return and Silver Bar modes")
        self.silver_bar_toggle_button.setCheckable(True)
        self.silver_bar_toggle_button.setMaximumWidth(150)
        self.silver_bar_toggle_button.setStyleSheet("""
            QPushButton {
                background-color: #eff6ff;
                border: 1px solid #93c5fd;
                border-radius: 5px;
                color: #1e40af;
                font-weight: 600;
                padding: 6px 12px;
                font-size: 9pt;
            }
            QPushButton:hover {
                background-color: #dbeafe;
                border-color: #60a5fa;
            }
            QPushButton:checked {
                background-color: #3b82f6;
                border-color: #2563eb;
                color: white;
            }
            QPushButton:checked:hover {
                background-color: #2563eb;
            }
        """)
        secondary_layout.addWidget(self.silver_bar_toggle_button)

        secondary_layout.addWidget(create_action_divider())

        self.last_balance_button = QPushButton("LB")
        self.last_balance_button.setToolTip("Add Last Balance to this estimate\nAdds previous unpaid balance\nUseful for ongoing customer accounts\nWill show dialog if multiple balances available")
        secondary_layout.addWidget(self.last_balance_button)

        secondary_layout.addWidget(create_action_divider())

        self.history_button = QPushButton("Estimate History")
        self.history_button.setToolTip("View, load, or print past estimates\nKeyboard: Ctrl+H\nBrowse all saved estimates\nDouble-click to load an estimate")
        secondary_layout.addWidget(self.history_button)

        self.silver_bars_button = QPushButton("Manage Silver Bars")
        self.silver_bars_button.setToolTip("View and manage silver bar inventory\nAdd, edit, or assign silver bars\nTrack bar usage across estimates\nManage bar transfers")
        secondary_layout.addWidget(self.silver_bars_button)

        secondary_layout.addWidget(create_action_divider())

        self.delete_estimate_button = QPushButton("Delete This Estimate")
        self.delete_estimate_button.setToolTip("Delete the currently loaded estimate\nPermanently removes estimate from database\nOnly enabled when estimate is loaded\nCannot be undone - use with caution")
        self.delete_estimate_button.setEnabled(False)
        secondary_layout.addWidget(self.delete_estimate_button)

        secondary_layout.addStretch()

        # Live rate display (non-editable) placed at the end for emphasis
        self.live_rate_label = QLabel("Live Silver Rate:")
        self.live_rate_label.setToolTip("Latest rate fetched from DDASilver.com (read-only)")
        try:
            self.live_rate_label.setStyleSheet("font-weight: 600; color: #222;")
        except Exception:
            pass
        self.live_rate_value_label = QLabel("…")
        self.live_rate_value_label.setObjectName("LiveRateValue")
        try:
            # Subtle, readable styling (less distracting)
            self.live_rate_value_label.setStyleSheet("""
                QLabel#LiveRateValue {
                  color: #0f172a;
                  background-color: #e6f0ff;
                  border: 1px solid #93c5fd;
                  border-radius: 10px;
                  padding: 2px 8px;
                  font-weight: 700;
                  font-size: 11pt;
                }
            """)
            self.live_rate_value_label.setMinimumWidth(110)
            self.live_rate_value_label.setAlignment(Qt.AlignHCenter | Qt.AlignVCenter)
        except Exception:
            pass
        self.live_rate_meta_label = QLabel("Waiting…")
        self.live_rate_meta_label.setObjectName("LiveRateMeta")
        self.live_rate_meta_label.setAccessibleName("Live Rate Status")
        self.live_rate_meta_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        try:
            self.live_rate_meta_label.setStyleSheet("color: #475569; font-size: 9pt;")
        except Exception:
            pass
        rate_container = QWidget()
        rate_layout = QVBoxLayout(rate_container)
        rate_layout.setContentsMargins(0, 0, 0, 0)
        rate_layout.setSpacing(2)
        rate_layout.addWidget(self.live_rate_value_label)
        rate_layout.addWidget(self.live_rate_meta_label)
        secondary_layout.addWidget(self.live_rate_label)
        secondary_layout.addWidget(rate_container)
        # Refresh button placed next to the live silver rate value
        self.refresh_rate_button = QToolButton()
        try:
            self.refresh_rate_button.setToolTip("Refresh live silver rate and set it here")
            self.refresh_rate_button.setIcon(self.style().standardIcon(QStyle.SP_BrowserReload))
            self.refresh_rate_button.setAutoRaise(True)
            self.refresh_rate_button.setCursor(Qt.PointingHandCursor)
            self.refresh_rate_button.setAccessibleName("Refresh Silver Rate")
        except Exception:
            pass
        secondary_layout.addWidget(self.refresh_rate_button)

        table_actions_layout.addWidget(primary_frame, 0, Qt.AlignLeft)
        table_actions_layout.addWidget(secondary_frame, 1)
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
        self.mode_indicator_label.setStyleSheet("""
            font-weight: bold; 
            color: palette(windowText);
            background-color: palette(window);
            border: 1px solid palette(mid);
            border-radius: 3px;
            padding: 2px 6px;
        """)
        self.mode_indicator_label.setToolTip("Shows which entry mode is active.\nCtrl+R: Return Items\nCtrl+B: Silver Bars")
        self.unsaved_badge = QLabel("")
        self.unsaved_badge.setObjectName("UnsavedBadge")
        self.unsaved_badge.setAccessibleName("Unsaved Changes Indicator")
        self.unsaved_badge.setVisible(False)
        self.unsaved_badge.setToolTip("Indicates there are unsaved changes in this estimate")
        self.unsaved_badge.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.unsaved_badge.setStyleSheet("""
            QLabel#UnsavedBadge {
                color: #b45309;
                background-color: #fff7ed;
                border: 1px solid #f97316;
                border-radius: 11px;
                padding: 2px 10px;
                font-weight: 600;
            }

        """)
        # Single-line layout with improved spacing and subtle visual separation
        form_layout = QHBoxLayout()
        form_layout.setSpacing(10)  # Base spacing between elements
        
        # Document group - Voucher + Load + Date
        voucher_label = QLabel("Voucher No:")
        self.voucher_edit = QLineEdit()
        self.voucher_edit.setMaximumWidth(140)
        self.voucher_edit.setToolTip("Enter an existing voucher number to load or leave blank for a new estimate.\nFormat: Any alphanumeric code (e.g., EST001, V-2024-001)\nPress Tab or Enter to load estimate")
        self.load_button = QPushButton("Load")
        self.load_button.setToolTip("Load the estimate with the entered voucher number.\nShortcut: Enter in Voucher field\nWill show error if voucher not found")
        
        date_label = QLabel("Date:")
        self.date_edit = QDateEdit()
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDate(QDate.currentDate())
        self.date_edit.setMaximumWidth(120)
        self.date_edit.setToolTip("Date of the estimate.\nClick calendar icon to choose date\nFormat: DD/MM/YYYY\nDefaults to today's date")
        
        # Business data - Silver Rate
        silver_rate_label = QLabel("Silver Rate:")
        self.silver_rate_spin = QDoubleSpinBox()
        self.silver_rate_spin.setRange(0, 1000000)
        self.silver_rate_spin.setDecimals(2)
        self.silver_rate_spin.setPrefix("₹ ")
        self.silver_rate_spin.setValue(0)
        self.silver_rate_spin.setToolTip("Silver rate for calculating fine value.\nFormat: ₹ 0.00 (up to 2 decimal places)\nRange: 0 to 1,000,000\nUsed to calculate total value of fine silver")
        
        # Additional info - Note
        note_label = QLabel("Note:")
        self.note_edit = QLineEdit()
        self.note_edit.setMinimumWidth(180)
        self.note_edit.setToolTip("Add a note for this estimate (will be saved with the estimate)\nOptional field for comments, customer details, or special instructions\nWill appear on printed estimates")
        
        # Create subtle visual separators
        def create_separator():
            sep = QLabel("|")
            sep.setStyleSheet("color: palette(mid); font-weight: normal;")
            return sep
        
        # Status area
        self.status_message_label = QLabel("")
        self.status_message_label.setObjectName("InlineStatusLabel")
        self.status_message_label.setWordWrap(False)
        self.status_message_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.status_message_label.setStyleSheet("color: #445; padding-left: 8px;")
        
        # Add all widgets to single row with logical grouping and separators
        form_layout.addWidget(voucher_label)
        form_layout.addWidget(self.voucher_edit)
        form_layout.addWidget(self.load_button)
        form_layout.addSpacing(8)
        form_layout.addWidget(date_label)
        form_layout.addWidget(self.date_edit)
        form_layout.addSpacing(15)  # Group separator
        form_layout.addWidget(create_separator())
        form_layout.addSpacing(15)
        form_layout.addWidget(silver_rate_label)
        form_layout.addWidget(self.silver_rate_spin)
        form_layout.addSpacing(15)  # Group separator
        form_layout.addWidget(create_separator())
        form_layout.addSpacing(15)
        form_layout.addWidget(note_label)
        form_layout.addWidget(self.note_edit)
        form_layout.addSpacing(15)  # Group separator
        form_layout.addWidget(create_separator())
        form_layout.addSpacing(15)
        form_layout.addWidget(self.mode_indicator_label)
        form_layout.addSpacing(6)
        form_layout.addWidget(self.unsaved_badge)
        form_layout.addSpacing(6)
        form_layout.addWidget(self.status_message_label)
        form_layout.addStretch()  # Push everything to left
        
        self.layout.addLayout(form_layout)
        
        # Buddies for labels to improve keyboard flow
        voucher_label.setBuddy(self.voucher_edit)
        date_label.setBuddy(self.date_edit)
        silver_rate_label.setBuddy(self.silver_rate_spin)
        note_label.setBuddy(self.note_edit)


    def _setup_item_table(self, widget):
        """Set up the table for item entry."""
        self.item_table = QTableWidget()
        self.item_table.setColumnCount(11)
        headers = [
            "Code", "Item Name", "Gross Wt", "Poly Wt", "Net Wt",
            "Purity %", "Wage Rate", "Pieces", "Wage Amt", "Fine Wt", "Type"
        ]
        header_tooltips = [
            "Item code (press Enter/Tab to lookup)\nEnter partial code to search\nLeave empty and press Tab to browse all items",
            "Item description (filled automatically from code)\nRead-only field\nUpdated when valid code is entered",
            "Gross Weight (grams)\nFormat: 0.000 (up to 3 decimal places)\nTotal weight including stones/poly\nLeave empty for 0.000",
            "Poly/Stone Weight (grams)\nFormat: 0.000 (up to 3 decimal places)\nWeight of non-silver parts\nLeave empty for 0.000",
            "Net Weight (Gross - Poly, calculated)\nRead-only field\nCalculated automatically\nActual silver content weight",
            "Silver Purity (%)\nFormat: 0.00 (percentage)\nRange: 0.00 to 100.00\nE.g., 92.50 for 92.5% pure silver",
            "Wage rate per gram or per piece\nFormat: 0.00 (currency)\nRate depends on item's wage type\nPer gram for GM items, per piece for PC items",
            "Number of pieces (for PC wage type only)\nFormat: Whole numbers only\nRequired for PC (per piece) items\nLeave as 0 for GM (per gram) items",
            "Total Wage Amount (calculated)\nRead-only field\nCalculated automatically\nWage Rate × (Net Weight or Pieces)",
            "Fine Silver Weight (calculated)\nRead-only field\nCalculated automatically\nNet Weight × (Purity / 100)",
            "Item Type (Regular/Return/Silver Bar)\nRead-only field\nSet automatically based on entry mode\nUse mode toggle buttons to change"
        ]
        self.item_table.setHorizontalHeaderLabels(headers)
        for i, tooltip in enumerate(header_tooltips):
            self.item_table.horizontalHeaderItem(i).setToolTip(tooltip)

        # Allow user to interactively resize columns and persist via QSettings
        header = self.item_table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Interactive)
        # Add header context menu for layout reset (no sorting enabled)
        try:
            header.setContextMenuPolicy(Qt.CustomContextMenu)
            header.customContextMenuRequested.connect(widget._show_header_context_menu)
        except Exception:
            pass

        # Initial sensible widths (user may change at runtime)
        self.item_table.setColumnWidth(COL_CODE, 80)
        self.item_table.setColumnWidth(COL_GROSS, 85)
        self.item_table.setColumnWidth(COL_POLY, 85)
        self.item_table.setColumnWidth(COL_NET_WT, 85)
        self.item_table.setColumnWidth(COL_PURITY, 80)
        self.item_table.setColumnWidth(COL_WAGE_RATE, 80)
        self.item_table.setColumnWidth(COL_PIECES, 60)
        self.item_table.setColumnWidth(COL_WAGE_AMT, 85)
        self.item_table.setColumnWidth(COL_FINE_WT, 85)
        self.item_table.setColumnWidth(COL_TYPE, 80)

        # Notify widget on resize to save widths
        try:
            header.sectionResized.connect(widget._on_item_table_section_resized)
        except Exception:
            pass

        # Start editing only on explicit user intent; avoid CurrentChanged which
        # can spam Qt warnings when the current item isn't editable.
        self.item_table.setEditTriggers(
            QTableWidget.DoubleClicked | QTableWidget.EditKeyPressed
        )
        self.item_table.setSelectionBehavior(QAbstractItemView.SelectItems)
        self.item_table.setSelectionMode(QTableWidget.SingleSelection)
        self.item_table.setAlternatingRowColors(True)

        # Modern table styling with improved visual hierarchy
        self.item_table.setStyleSheet("""
            QTableWidget {
                background-color: #ffffff;
                alternate-background-color: #f8fafc;
                gridline-color: #e2e8f0;
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                selection-background-color: #dbeafe;
                selection-color: #1e40af;
                font-size: 10pt;
            }

            QTableWidget::item {
                padding: 8px 6px;
                border-bottom: 1px solid #f1f5f9;
            }

            QTableWidget::item:hover {
                background-color: #f1f5f9;
            }

            QTableWidget::item:selected {
                background-color: #dbeafe;
                color: #1e40af;
                border: 1px solid #93c5fd;
            }

            QTableWidget::item:focus {
                background-color: #bfdbfe;
                border: 2px solid #3b82f6;
                outline: none;
            }

            QHeaderView::section {
                background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #f8fafc, stop:1 #e2e8f0);
                color: #334155;
                padding: 8px 6px;
                border: none;
                border-right: 1px solid #cbd5e1;
                border-bottom: 2px solid #94a3b8;
                font-weight: 600;
                font-size: 9pt;
                text-transform: none;
            }

            QHeaderView::section:hover {
                background-color: #e2e8f0;
            }

            QHeaderView::section:first {
                border-top-left-radius: 6px;
            }

            QHeaderView::section:last {
                border-top-right-radius: 6px;
                border-right: none;
            }

            QTableWidget QTableCornerButton::section {
                background-color: #f8fafc;
                border: none;
                border-right: 1px solid #cbd5e1;
                border-bottom: 2px solid #94a3b8;
            }

            QTableWidget::item:alternate {
                background-color: #f8fafc;
            }

            QTableWidget::item:alternate:hover {
                background-color: #f1f5f9;
            }

            QScrollBar:vertical {
                background: #f8fafc;
                width: 12px;
                border-radius: 6px;
            }

            QScrollBar::handle:vertical {
                background: #cbd5e1;
                border-radius: 6px;
                min-height: 30px;
            }

            QScrollBar::handle:vertical:hover {
                background: #94a3b8;
            }

            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }

            QScrollBar:horizontal {
                background: #f8fafc;
                height: 12px;
                border-radius: 6px;
            }

            QScrollBar::handle:horizontal {
                background: #cbd5e1;
                border-radius: 6px;
                min-width: 30px;
            }

            QScrollBar::handle:horizontal:hover {
                background: #94a3b8;
            }

            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
                width: 0px;
            }
        """)

    def _setup_totals(self):
        """Set up the totals section with modern card-based layout."""

        totals_container = QWidget()
        totals_container.setObjectName("TotalsContainer")
        totals_container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        # Add background styling to the entire totals container
        totals_container.setStyleSheet("""
            QWidget#TotalsContainer {
                background-color: #f8fafc;
                border-top: 2px solid #e2e8f0;
                border-radius: 0px;
                padding: 12px;
            }
        """)

        main_totals_layout = QHBoxLayout(totals_container)
        main_totals_layout.setSpacing(12)
        main_totals_layout.setContentsMargins(8, 12, 8, 12)

        # Helper function to create a styled card for breakdown sections
        def create_breakdown_card(title, labels_attrs, bg_color="#ffffff", title_color="#475569"):
            card = QFrame()
            card.setObjectName(f"{title}Card")
            card.setStyleSheet(f"""
                QFrame#{title}Card {{
                    background-color: {bg_color};
                    border: 1px solid #e2e8f0;
                    border-radius: 8px;
                    padding: 8px 12px;
                }}
            """)
            card.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)

            card_layout = QVBoxLayout(card)
            card_layout.setSpacing(6)
            card_layout.setContentsMargins(8, 8, 8, 8)

            # Title with styling
            title_label = QLabel(f"<b>{title}</b>")
            title_label.setStyleSheet(f"color: {title_color}; font-size: 9pt; padding-bottom: 4px;")
            title_label.setAlignment(Qt.AlignCenter)
            card_layout.addWidget(title_label)

            # Add a subtle separator line
            separator = QFrame()
            separator.setFrameShape(QFrame.HLine)
            separator.setStyleSheet("background-color: #e2e8f0; max-height: 1px;")
            card_layout.addWidget(separator)

            # Add labels in a form layout
            form = QFormLayout()
            form.setSpacing(4)
            form.setContentsMargins(4, 4, 4, 4)
            
            for label_text, attr_name, default_value in labels_attrs:
                row_label = QLabel(label_text)
                row_label.setStyleSheet("color: #64748b; font-size: 9pt;")
                
                value_label = QLabel(default_value)
                value_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
                value_label.setStyleSheet("color: #1e293b; font-weight: 600; font-size: 10pt;")
                setattr(self, attr_name, value_label)
                
                form.addRow(row_label, value_label)
            
            card_layout.addLayout(form)
            return card

        # Overall Totals Card (gray theme)
        overall_labels = [
            ("Total Gross Wt:", 'overall_gross_label', "0.0"),
            ("Total Poly Wt:", 'overall_poly_label', "0.0"),
        ]
        overall_card = create_breakdown_card("Totals", overall_labels, "#f1f5f9", "#334155")
        main_totals_layout.addWidget(overall_card)

        # Regular Items Card (green theme)
        regular_labels = [
            ("Gross Wt:", 'total_gross_label', "0.0"),
            ("Net Wt:", 'total_net_label', "0.0"),
            ("Fine Wt:", 'total_fine_label', "0.0"),
        ]
        regular_card = create_breakdown_card("Regular", regular_labels, "#f0fdf4", "#166534")
        main_totals_layout.addWidget(regular_card)

        # Return Items Card (amber theme)
        return_labels = [
            ("Gross Wt:", 'return_gross_label', "0.0"),
            ("Net Wt:", 'return_net_label', "0.0"),
            ("Fine Wt:", 'return_fine_label', "0.0"),
        ]
        return_card = create_breakdown_card("Return", return_labels, "#fffbeb", "#92400e")
        main_totals_layout.addWidget(return_card)

        # Silver Bars Card (blue theme)
        bar_labels = [
            ("Gross Wt:", 'bar_gross_label', "0.0"),
            ("Net Wt:", 'bar_net_label', "0.0"),
            ("Fine Wt:", 'bar_fine_label', "0.0"),
        ]
        bar_card = create_breakdown_card("Silver Bar", bar_labels, "#eff6ff", "#1e40af")
        main_totals_layout.addWidget(bar_card)

        # Add stretch to push Final Calculation to the right
        main_totals_layout.addStretch(1)

        # Final Calculation Card - PROMINENT DESIGN
        final_card = QFrame()
        final_card.setObjectName("FinalCalculationCard")
        final_card.setStyleSheet("""
            QFrame#FinalCalculationCard {
                background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #dbeafe, stop:1 #bfdbfe);
                border: 2px solid #3b82f6;
                border-radius: 10px;
                padding: 12px 16px;
            }
        """)
        final_card.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)

        final_layout = QVBoxLayout(final_card)
        final_layout.setSpacing(8)
        final_layout.setContentsMargins(12, 10, 12, 10)

        # Final Calculation Title
        final_title = QLabel("Final Calculation")
        final_title.setAlignment(Qt.AlignCenter)
        final_title.setStyleSheet("""
            color: #1e40af;
            font-weight: bold;
            font-size: 10pt;
            padding-bottom: 6px;
        """)
        final_layout.addWidget(final_title)

        # Separator
        sep_line = QFrame()
        sep_line.setFrameShape(QFrame.HLine)
        sep_line.setStyleSheet("background-color: #93c5fd; max-height: 2px;")
        final_layout.addWidget(sep_line)

        # Net Fine Wt
        net_fine_container = QHBoxLayout()
        net_fine_label_text = QLabel("Net Fine Wt:")
        net_fine_label_text.setStyleSheet("color: #1e40af; font-weight: 600; font-size: 10pt;")
        self.net_fine_label = QLabel("0.0")
        self.net_fine_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.net_fine_label.setStyleSheet("color: #1e293b; font-weight: bold; font-size: 11pt;")
        self.net_fine_label.setMinimumWidth(80)
        net_fine_container.addWidget(net_fine_label_text)
        net_fine_container.addStretch()
        net_fine_container.addWidget(self.net_fine_label)
        final_layout.addLayout(net_fine_container)

        # Net Wage
        net_wage_container = QHBoxLayout()
        net_wage_label_text = QLabel("Net Wage:")
        net_wage_label_text.setStyleSheet("color: #1e40af; font-weight: 600; font-size: 10pt;")
        self.net_wage_label = QLabel("0")
        self.net_wage_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.net_wage_label.setStyleSheet("color: #1e293b; font-weight: bold; font-size: 11pt;")
        self.net_wage_label.setMinimumWidth(80)
        net_wage_container.addWidget(net_wage_label_text)
        net_wage_container.addStretch()
        net_wage_container.addWidget(self.net_wage_label)
        final_layout.addLayout(net_wage_container)

        # Separator before Grand Total
        grand_sep = QFrame()
        grand_sep.setFrameShape(QFrame.HLine)
        grand_sep.setStyleSheet("background-color: #3b82f6; max-height: 2px;")
        final_layout.addWidget(grand_sep)

        # GRAND TOTAL - Extra Prominent
        grand_total_container = QWidget()
        grand_total_container.setStyleSheet("""
            background-color: #1e40af;
            border-radius: 6px;
            padding: 8px 12px;
        """)
        grand_layout = QHBoxLayout(grand_total_container)
        grand_layout.setContentsMargins(8, 6, 8, 6)
        grand_layout.setSpacing(0)

        grand_total_label_text = QLabel("GRAND TOTAL:")
        grand_total_label_text.setStyleSheet("""
            color: #ffffff;
            font-weight: bold;
            font-size: 12pt;
            letter-spacing: 0.5px;
        """)

        self.grand_total_label = QLabel("0")
        self.grand_total_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.grand_total_label.setStyleSheet("""
            color: #ffffff;
            font-weight: bold;
            font-size: 16pt;
            padding-left: 12px;
        """)
        self.grand_total_label.setMinimumWidth(120)

        grand_layout.addWidget(grand_total_label_text)
        grand_layout.addStretch()
        grand_layout.addWidget(self.grand_total_label)

        final_layout.addWidget(grand_total_container)

        main_totals_layout.addWidget(final_card)

        # Add the main container to the widget's layout
        self.layout.addWidget(totals_container)

        # Tab order: header fields -> table
        try:
            QWidget.setTabOrder(self.voucher_edit, self.load_button)
            QWidget.setTabOrder(self.load_button, self.date_edit)
            QWidget.setTabOrder(self.date_edit, self.silver_rate_spin)
            QWidget.setTabOrder(self.silver_rate_spin, self.note_edit)
            QWidget.setTabOrder(self.note_edit, self.item_table)
        except Exception:
            pass

    # Removed _setup_buttons method as buttons are now created directly in setup_ui
