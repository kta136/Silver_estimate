#!/usr/bin/env python
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QLineEdit, QComboBox,
    QMessageBox, QAbstractItemView, QFrame, QInputDialog, QSplitter,
    QWidget, QMenu, QShortcut, QToolButton, QStyle, QSizePolicy,
    QApplication, QCheckBox, QDoubleSpinBox, QSpinBox, QFileDialog, QStackedWidget,
    QRadioButton, QButtonGroup
)
from PyQt5.QtCore import Qt, QTimer, QSettings
from PyQt5.QtGui import QColor, QKeySequence
import traceback # Added for error handling in actions
from datetime import datetime, timedelta
from silverestimate.infrastructure.app_constants import SETTINGS_ORG, SETTINGS_APP

class SilverBarDialog(QDialog):
    """Dialog for managing silver bars and grouping them into lists (v2.0)."""

    def __init__(self, db_manager, parent=None):
        super().__init__(parent)
        self.db_manager = db_manager
        self.current_list_id = None # Track the currently selected list
        self.init_ui()
        self.load_lists()
        self.load_available_bars()

    def init_ui(self):
        """Set up the user interface."""
        self.setWindowTitle("Silver Bar Management (v2.0)")
        self.setMinimumSize(1180, 760) # Wider to accommodate side-by-side panes

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(12)

        # --- Left Pane: Search and Available Bars ---
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(8, 8, 8, 8)
        left_layout.setSpacing(10)

        # Title row with refresh controls
        title_row = QHBoxLayout()
        title_row.setSpacing(8)
        
        left_title = QLabel("Available Silver Bars")
        left_title.setStyleSheet("""
            font-weight: 700;
            font-size: 16px;
            color: #2c3e50;
            margin-bottom: 8px;
            padding: 8px 0px;
        """)
        title_row.addWidget(left_title)
        
        title_row.addStretch()
        
        # Refresh controls on title line
        self.refresh_available_button = QPushButton("Refresh")
        self.refresh_available_button.setStyleSheet("""
            QPushButton {
                padding: 4px 8px;
                font-size: 12px;
                font-weight: 600;
                border: 1px solid #007acc;
                background-color: #007acc;
                color: white;
                border-radius: 3px;
            }
            QPushButton:hover {
                background-color: #005a9e;
            }
        """)
        self.refresh_available_button.clicked.connect(self.load_available_bars)
        title_row.addWidget(self.refresh_available_button)
        
        # Auto-refresh toggle
        self.auto_refresh_checkbox = QCheckBox("Auto-refresh")
        self.auto_refresh_checkbox.setStyleSheet("font-size: 12px; margin-left: 6px;")
        self.auto_refresh_checkbox.setToolTip("Auto-refresh available bars every 5s")
        self.auto_refresh_checkbox.toggled.connect(lambda checked: self._toggle_auto_refresh(checked))
        title_row.addWidget(self.auto_refresh_checkbox)
        
        # Clear filters button
        self.clear_filters_button = QPushButton("Clear Filters")
        self.clear_filters_button.setStyleSheet("""
            QPushButton {
                padding: 4px 8px;
                font-size: 12px;
                border: 1px solid #666;
                background-color: #f5f5f5;
                color: #333;
                border-radius: 3px;
            }
            QPushButton:hover {
                background-color: #e5e5e5;
            }
        """)
        self.clear_filters_button.setToolTip("Clear all search filters")
        self.clear_filters_button.clicked.connect(lambda: self._clear_filters())
        title_row.addWidget(self.clear_filters_button)
        
        left_layout.addLayout(title_row)
        
        # Search filters with compact organization
        filters_group = QWidget()
        filters_layout = QVBoxLayout(filters_group)
        filters_layout.setSpacing(4)  # Reduced from 8 to 4
        filters_layout.setContentsMargins(0, 0, 0, 0)
        
        # Weight search row - only weight field
        weight_row = QHBoxLayout()
        weight_row.setSpacing(6)
        weight_label = QLabel("Weight Search:")
        weight_label.setStyleSheet("font-weight: 600; font-size: 13px; min-width: 90px;")
        weight_row.addWidget(weight_label)
        
        self.weight_search_edit = QLineEdit()
        self.weight_search_edit.setPlaceholderText("Enter weight (e.g., 190)")
        self.weight_search_edit.setStyleSheet("""
            QLineEdit {
                padding: 6px;
                font-size: 13px;
                border: 1px solid #ccc;
                border-radius: 3px;
            }
            QLineEdit:focus {
                border-color: #007acc;
            }
        """)
        try:
            self.weight_search_edit.setClearButtonEnabled(True)
        except Exception:
            pass
        self.weight_search_edit.textChanged.connect(self.load_available_bars)
        weight_row.addWidget(self.weight_search_edit)
        weight_row.addStretch()
        filters_layout.addLayout(weight_row)
        
        # Combined purity range and tolerance row
        purity_tol_row = QHBoxLayout()
        purity_tol_row.setSpacing(6)
        
        # Purity range
        purity_label = QLabel("Purity Range:")
        purity_label.setStyleSheet("font-weight: 600; font-size: 13px; min-width: 90px;")
        purity_tol_row.addWidget(purity_label)
        
        self.purity_min_spin = QDoubleSpinBox()
        self.purity_min_spin.setDecimals(2)
        self.purity_min_spin.setRange(0.0, 100.0)
        self.purity_min_spin.setSingleStep(0.5)
        self.purity_min_spin.setValue(0.0)
        self.purity_min_spin.setStyleSheet("""
            QDoubleSpinBox {
                padding: 4px;
                font-size: 13px;
                border: 1px solid #ccc;
                border-radius: 3px;
                max-width: 80px;
            }
        """)
        self.purity_min_spin.valueChanged.connect(self.load_available_bars)
        purity_tol_row.addWidget(self.purity_min_spin)
        
        range_lbl = QLabel("% to")
        range_lbl.setStyleSheet("font-size: 12px; margin: 0 6px;")
        purity_tol_row.addWidget(range_lbl)
        
        self.purity_max_spin = QDoubleSpinBox()
        self.purity_max_spin.setDecimals(2)
        self.purity_max_spin.setRange(0.0, 100.0)
        self.purity_max_spin.setSingleStep(0.5)
        self.purity_max_spin.setValue(100.0)
        self.purity_max_spin.setStyleSheet("""
            QDoubleSpinBox {
                padding: 4px;
                font-size: 13px;
                border: 1px solid #ccc;
                border-radius: 3px;
                max-width: 80px;
            }
        """)
        self.purity_max_spin.valueChanged.connect(self.load_available_bars)
        purity_tol_row.addWidget(self.purity_max_spin)
        
        percent_lbl = QLabel("%")
        percent_lbl.setStyleSheet("font-size: 12px; margin-left: 2px; margin-right: 12px;")
        purity_tol_row.addWidget(percent_lbl)
        
        # Weight tolerance on same line
        tol_lbl = QLabel("± Tolerance:")
        tol_lbl.setStyleSheet("font-size: 12px; margin-left: 8px; margin-right: 2px;")
        tol_lbl.setToolTip("Weight tolerance for matching")
        purity_tol_row.addWidget(tol_lbl)
        
        self.weight_tol_spin = QDoubleSpinBox()
        self.weight_tol_spin.setDecimals(3)
        self.weight_tol_spin.setRange(0.0, 999999.0)
        self.weight_tol_spin.setSingleStep(0.1)
        self.weight_tol_spin.setValue(1.0)
        self.weight_tol_spin.setToolTip("Match bars within ±tolerance (grams)")
        self.weight_tol_spin.setStyleSheet("""
            QDoubleSpinBox {
                padding: 4px;
                font-size: 13px;
                border: 1px solid #ccc;
                border-radius: 3px;
                max-width: 100px;
            }
        """)
        self.weight_tol_spin.valueChanged.connect(self.load_available_bars)
        purity_tol_row.addWidget(self.weight_tol_spin)
        
        purity_tol_row.addStretch()
        filters_layout.addLayout(purity_tol_row)
        
        # Date filter row - compact
        date_row = QHBoxLayout()
        date_row.setSpacing(6)
        date_label = QLabel("Date Filter:")
        date_label.setStyleSheet("font-weight: 600; font-size: 13px; min-width: 90px;")
        date_row.addWidget(date_label)
        
        try:
            self.date_range_combo = QComboBox()
            self.date_range_combo.addItems(["Any", "Today", "Last 7 days", "Last 30 days", "This Month"])
            self.date_range_combo.currentIndexChanged.connect(self.load_available_bars)
            self.date_range_combo.setStyleSheet("""
                QComboBox {
                    padding: 4px 8px;
                    font-size: 13px;
                    border: 1px solid #ccc;
                    border-radius: 3px;
                    min-width: 120px;
                }
            """)
            date_row.addWidget(self.date_range_combo)
        except Exception:
            pass
        date_row.addStretch()
        filters_layout.addLayout(date_row)
        
        # Add filters group to left layout
        left_layout.addWidget(filters_group)
        
        # Small header badges with better readability
        self.available_header_badge = QLabel("")
        self.available_header_badge.setStyleSheet("""
            color: #666; 
            font-size: 13px; 
            font-weight: 500;
            margin: 4px 0px;
        """)
        left_layout.addWidget(self.available_header_badge)

        self.available_bars_table = QTableWidget()
        self.available_bars_table.setColumnCount(7) # bar_id, estimate_voucher_no, weight, purity, fine_weight, date_added, status
        self.available_bars_table.setHorizontalHeaderLabels(["ID", "Voucher/Note", "Weight (g)", "Purity (%)", "Fine Wt (g)", "Date Added", "Status"])
        self.available_bars_table.setColumnHidden(0, True) # Hide bar_id
        self.available_bars_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.available_bars_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.available_bars_table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.available_bars_table.setAlternatingRowColors(True)
        self.available_bars_table.setSortingEnabled(True)
        self.available_bars_table.verticalHeader().setVisible(False)
        
        # Improved table styling for better readability
        self.available_bars_table.setStyleSheet("""
            QTableWidget {
                font-size: 13px;
                gridline-color: #ddd;
                background-color: white;
                alternate-background-color: #f9f9f9;
                selection-background-color: #e6f2ff;
            }
            QTableWidget::item {
                padding: 8px 4px;
                border-bottom: 1px solid #eee;
            }
            QTableWidget::item:selected {
                background-color: #d4e7ff;
                color: black;
            }
            QHeaderView::section {
                background-color: #f0f0f0;
                padding: 8px 4px;
                border: 1px solid #ddd;
                font-weight: 600;
                font-size: 13px;
            }
        """)
        try:
            self.available_bars_table.verticalHeader().setDefaultSectionSize(28)  # Increased row height for better readability
        except Exception:
            pass
        self.available_bars_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.available_bars_table.horizontalHeader().setStretchLastSection(True)
        # Context menu for quick actions
        self.available_bars_table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.available_bars_table.customContextMenuRequested.connect(self._show_available_context_menu)
        left_layout.addWidget(self.available_bars_table)
        
        # Improved totals section for available bars
        self.available_totals_label = QLabel("Available Bars: 0 | Total Weight: 0.000 g | Total Fine Wt: 0.000 g")
        self.available_totals_label.setStyleSheet("""
            font-weight: 600; 
            font-size: 14px; 
            color: #2c3e50;
            background-color: #f8f9fa;
            padding: 8px 12px;
            border: 1px solid #dee2e6;
            border-radius: 4px;
            margin-top: 4px;
        """)
        self.available_totals_label.setAlignment(Qt.AlignCenter)
        left_layout.addWidget(self.available_totals_label)
        
        # Improved selection summary for available table
        self.available_selection_label = QLabel("Selected: 0 | Weight: 0.000 g | Fine: 0.000 g")
        self.available_selection_label.setStyleSheet("""
            color: #6c757d;
            font-size: 13px;
            font-weight: 500;
            background-color: #ffffff;
            padding: 6px 12px;
            border: 1px solid #dee2e6;
            border-radius: 4px;
            margin-top: 2px;
        """)
        self.available_selection_label.setAlignment(Qt.AlignCenter)
        left_layout.addWidget(self.available_selection_label)

        # --- Center Pane: Transfer Buttons ---
        center_widget = QWidget()
        center_layout = QVBoxLayout(center_widget)
        center_layout.setContentsMargins(8, 16, 8, 16)
        center_layout.setSpacing(12)
        center_layout.setAlignment(Qt.AlignCenter)
        
        # Transfer section title
        transfer_title = QLabel("Transfer")
        transfer_title.setAlignment(Qt.AlignCenter)
        transfer_title.setStyleSheet("""
            font-weight: 600;
            font-size: 14px;
            color: #495057;
            margin-bottom: 8px;
        """)
        center_layout.addWidget(transfer_title)
        center_layout.addStretch()
        # Improved transfer buttons with better readability
        self.add_to_list_button = QPushButton("→")
        self.add_to_list_button.setStyleSheet("""
            QPushButton {
                font-size: 16px;
                font-weight: bold;
                padding: 8px;
                border: 2px solid #007acc;
                background-color: #007acc;
                color: white;
                border-radius: 20px;
                min-width: 40px;
                min-height: 40px;
            }
            QPushButton:hover {
                background-color: #005a9e;
                border-color: #005a9e;
            }
            QPushButton:disabled {
                background-color: #ccc;
                border-color: #ccc;
                color: #999;
            }
        """)
        self.add_to_list_button.setToolTip("Add selected 'Available' bars to the selected list.")
        self.add_to_list_button.clicked.connect(self.add_selected_to_list)
        self.add_to_list_button.setEnabled(False)
        center_layout.addWidget(self.add_to_list_button)

        # Add All button
        self.add_all_button = QPushButton("⇒")
        self.add_all_button.setStyleSheet("""
            QPushButton {
                font-size: 14px;
                font-weight: bold;
                padding: 6px;
                border: 2px solid #28a745;
                background-color: #28a745;
                color: white;
                border-radius: 16px;
                min-width: 32px;
                min-height: 32px;
            }
            QPushButton:hover {
                background-color: #218838;
                border-color: #218838;
            }
            QPushButton:disabled {
                background-color: #ccc;
                border-color: #ccc;
                color: #999;
            }
        """)
        self.add_all_button.setToolTip("Add all available (filtered) bars to the selected list.")
        self.add_all_button.clicked.connect(self.add_all_filtered_to_list)
        self.add_all_button.setEnabled(False)
        center_layout.addWidget(self.add_all_button)
        
        # Spacer
        spacer = QLabel("• • •")
        spacer.setAlignment(Qt.AlignCenter)
        spacer.setStyleSheet("color: #ccc; font-size: 12px; margin: 6px 0;")
        center_layout.addWidget(spacer)
        
        # Remove button
        self.remove_from_list_button = QPushButton("←")
        self.remove_from_list_button.setStyleSheet("""
            QPushButton {
                font-size: 16px;
                font-weight: bold;
                padding: 8px;
                border: 2px solid #dc3545;
                background-color: #dc3545;
                color: white;
                border-radius: 20px;
                min-width: 40px;
                min-height: 40px;
            }
            QPushButton:hover {
                background-color: #c82333;
                border-color: #c82333;
            }
            QPushButton:disabled {
                background-color: #ccc;
                border-color: #ccc;
                color: #999;
            }
        """)
        self.remove_from_list_button.setToolTip("Remove selected bars from the list (status becomes 'In Stock').")
        self.remove_from_list_button.clicked.connect(self.remove_selected_from_list)
        self.remove_from_list_button.setEnabled(False)
        center_layout.addWidget(self.remove_from_list_button)

        # Remove All button
        self.remove_all_button = QPushButton("⇐")
        self.remove_all_button.setStyleSheet("""
            QPushButton {
                font-size: 14px;
                font-weight: bold;
                padding: 6px;
                border: 2px solid #fd7e14;
                background-color: #fd7e14;
                color: white;
                border-radius: 16px;
                min-width: 32px;
                min-height: 32px;
            }
            QPushButton:hover {
                background-color: #e8630c;
                border-color: #e8630c;
            }
            QPushButton:disabled {
                background-color: #ccc;
                border-color: #ccc;
                color: #999;
            }
        """)
        self.remove_all_button.setToolTip("Remove all bars from the selected list (status becomes 'In Stock').")
        self.remove_all_button.clicked.connect(self.remove_all_from_list)
        self.remove_all_button.setEnabled(False)
        center_layout.addWidget(self.remove_all_button)
        center_layout.addStretch()
        try:
            center_widget.setFixedWidth(80)  # Wider for better button visibility
        except Exception:
            pass

        # --- Right Pane: List Selection, Actions, and Bars ---
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(8, 8, 8, 8)
        right_layout.setSpacing(10)

        # Improved section title
        right_title = QLabel("Silver Bar Lists")
        right_title.setStyleSheet("""
            font-weight: 700;
            font-size: 16px;
            color: #2c3e50;
            margin-bottom: 8px;
            padding: 8px 0px;
        """)
        right_layout.addWidget(right_title)

        header_row = QHBoxLayout()
        header_row.setSpacing(8)
        header_title = QLabel("Select List:")
        header_title.setStyleSheet("font-weight: 600; font-size: 13px; min-width: 80px;")
        header_row.addWidget(header_title)
        
        self.list_combo = QComboBox()
        self.list_combo.setMinimumWidth(240)
        self.list_combo.setStyleSheet("""
            QComboBox {
                padding: 6px 8px;
                font-size: 13px;
                border: 1px solid #ccc;
                border-radius: 3px;
            }
            QComboBox:focus {
                border-color: #007acc;
            }
        """)
        self.list_combo.currentIndexChanged.connect(self.list_selection_changed)
        header_row.addWidget(self.list_combo)
        
        self.create_list_button = QPushButton("Create New List...")
        self.create_list_button.setStyleSheet("""
            QPushButton {
                padding: 6px 12px;
                font-size: 13px;
                font-weight: 600;
                border: 1px solid #28a745;
                background-color: #28a745;
                color: white;
                border-radius: 3px;
            }
            QPushButton:hover {
                background-color: #218838;
            }
        """)
        self.create_list_button.clicked.connect(self.create_new_list)
        header_row.addWidget(self.create_list_button)
        
        self.generate_optimal_button = QPushButton("Generate Optimal List...")
        self.generate_optimal_button.setStyleSheet("""
            QPushButton {
                padding: 6px 12px;
                font-size: 13px;
                font-weight: 600;
                border: 1px solid #6f42c1;
                background-color: #6f42c1;
                color: white;
                border-radius: 3px;
            }
            QPushButton:hover {
                background-color: #5a32a3;
            }
        """)
        self.generate_optimal_button.setToolTip("Generate an optimal list for a target fine weight")
        self.generate_optimal_button.clicked.connect(self.generate_optimal_list)
        header_row.addWidget(self.generate_optimal_button)
        
        header_row.addStretch()
        right_layout.addLayout(header_row)
        
        # List info and actions row
        info_actions_row = QHBoxLayout()
        info_actions_row.setSpacing(8)
        
        self.list_info_label = QLabel("Select a list to view details")
        self.list_info_label.setStyleSheet("""
            color: #6c757d;
            font-size: 13px;
            font-weight: 500;
            font-style: italic;
            padding: 4px 8px;
            background-color: #f8f9fa;
            border: 1px solid #dee2e6;
            border-radius: 3px;
        """)
        info_actions_row.addWidget(self.list_info_label)
        info_actions_row.addStretch()
        
        # Action buttons with improved styling
        self.print_list_button = QPushButton("Print")
        self.print_list_button.setStyleSheet("""
            QPushButton {
                padding: 4px 8px;
                font-size: 12px;
                border: 1px solid #6f42c1;
                background-color: #6f42c1;
                color: white;
                border-radius: 3px;
            }
            QPushButton:hover { background-color: #5a32a3; }
            QPushButton:disabled { 
                background-color: #ccc; 
                border-color: #ccc;
                color: #999; 
            }
        """)
        self.print_list_button.setToolTip("Print selected list")
        self.print_list_button.clicked.connect(self.print_selected_list)
        self.print_list_button.setEnabled(False)
        info_actions_row.addWidget(self.print_list_button)
        
        self.edit_note_button = QPushButton("Edit Note")
        self.edit_note_button.setStyleSheet("""
            QPushButton {
                padding: 4px 8px;
                font-size: 12px;
                border: 1px solid #17a2b8;
                background-color: #17a2b8;
                color: white;
                border-radius: 3px;
            }
            QPushButton:hover { background-color: #138496; }
            QPushButton:disabled { 
                background-color: #ccc; 
                border-color: #ccc;
                color: #999; 
            }
        """)
        self.edit_note_button.setToolTip("Edit list note")
        self.edit_note_button.clicked.connect(self.edit_list_note)
        self.edit_note_button.setEnabled(False)
        info_actions_row.addWidget(self.edit_note_button)
        
        self.export_list_button = QPushButton("Export CSV")
        self.export_list_button.setStyleSheet("""
            QPushButton {
                padding: 4px 8px;
                font-size: 12px;
                border: 1px solid #28a745;
                background-color: #28a745;
                color: white;
                border-radius: 3px;
            }
            QPushButton:hover { background-color: #218838; }
            QPushButton:disabled { 
                background-color: #ccc; 
                border-color: #ccc;
                color: #999; 
            }
        """)
        self.export_list_button.setToolTip("Export current list to CSV")
        self.export_list_button.clicked.connect(self.export_current_list_to_csv)
        self.export_list_button.setEnabled(False)
        info_actions_row.addWidget(self.export_list_button)
        
        self.delete_list_button = QPushButton("Delete")
        self.delete_list_button.setStyleSheet("""
            QPushButton {
                padding: 4px 8px;
                font-size: 12px;
                border: 1px solid #dc3545;
                background-color: #dc3545;
                color: white;
                border-radius: 3px;
            }
            QPushButton:hover { background-color: #c82333; }
            QPushButton:disabled { 
                background-color: #ccc; 
                border-color: #ccc;
                color: #999; 
            }
        """)
        self.delete_list_button.setToolTip("Delete list")
        self.delete_list_button.clicked.connect(self.delete_selected_list)
        self.delete_list_button.setEnabled(False)
        info_actions_row.addWidget(self.delete_list_button)
        
        self.mark_issued_button = QPushButton("Mark as Issued")
        self.mark_issued_button.setStyleSheet("""
            QPushButton {
                padding: 4px 8px;
                font-size: 12px;
                border: 1px solid #fd7e14;
                background-color: #fd7e14;
                color: white;
                border-radius: 3px;
            }
            QPushButton:hover { background-color: #e8630c; }
            QPushButton:disabled { 
                background-color: #ccc; 
                border-color: #ccc;
                color: #999; 
            }
        """)
        self.mark_issued_button.setToolTip("Mark list as issued (moves to history)")
        self.mark_issued_button.clicked.connect(self.mark_list_as_issued)
        self.mark_issued_button.setEnabled(False)
        info_actions_row.addWidget(self.mark_issued_button)
        right_layout.addLayout(info_actions_row)

        # List table with improved styling
        self.list_bars_table = QTableWidget()
        self.list_bars_table.setColumnCount(7)
        self.list_bars_table.setHorizontalHeaderLabels(["ID", "Voucher/Note", "Weight (g)", "Purity (%)", "Fine Wt (g)", "Date Added", "Status"])
        self.list_bars_table.setColumnHidden(0, True)
        self.list_bars_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.list_bars_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.list_bars_table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.list_bars_table.setAlternatingRowColors(True)
        self.list_bars_table.setSortingEnabled(True)
        self.list_bars_table.verticalHeader().setVisible(False)
        
        # Apply same improved styling as available bars table
        self.list_bars_table.setStyleSheet("""
            QTableWidget {
                font-size: 13px;
                gridline-color: #ddd;
                background-color: white;
                alternate-background-color: #f9f9f9;
                selection-background-color: #e6f2ff;
            }
            QTableWidget::item {
                padding: 8px 4px;
                border-bottom: 1px solid #eee;
            }
            QTableWidget::item:selected {
                background-color: #d4e7ff;
                color: black;
            }
            QHeaderView::section {
                background-color: #f0f0f0;
                padding: 8px 4px;
                border: 1px solid #ddd;
                font-weight: 600;
                font-size: 13px;
            }
        """)
        try:
            self.list_bars_table.verticalHeader().setDefaultSectionSize(28)  # Increased row height for better readability
        except Exception:
            pass
        self.list_bars_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.list_bars_table.horizontalHeader().setStretchLastSection(True)
        self.list_bars_table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.list_bars_table.customContextMenuRequested.connect(self._show_list_context_menu)
        right_layout.addWidget(self.list_bars_table)

        # Improved totals section for list bars
        self.list_totals_label = QLabel("List Bars: 0 | Total Weight: 0.000 g | Total Fine Wt: 0.000 g")
        self.list_totals_label.setStyleSheet("""
            font-weight: 600; 
            font-size: 14px; 
            color: #2c3e50;
            background-color: #f8f9fa;
            padding: 8px 12px;
            border: 1px solid #dee2e6;
            border-radius: 4px;
            margin-top: 4px;
        """)
        self.list_totals_label.setAlignment(Qt.AlignCenter)
        right_layout.addWidget(self.list_totals_label)
        
        # Improved selection summary for list table
        self.list_selection_label = QLabel("Selected: 0 | Weight: 0.000 g | Fine: 0.000 g")
        self.list_selection_label.setStyleSheet("""
            color: #6c757d;
            font-size: 13px;
            font-weight: 500;
            background-color: #ffffff;
            padding: 6px 12px;
            border: 1px solid #dee2e6;
            border-radius: 4px;
            margin-top: 2px;
        """)
        self.list_selection_label.setAlignment(Qt.AlignCenter)
        right_layout.addWidget(self.list_selection_label)
        
        # Small header badge for list counts with better readability
        self.list_header_badge = QLabel("")
        self.list_header_badge.setAlignment(Qt.AlignRight)
        self.list_header_badge.setStyleSheet("""
            color: #666; 
            font-size: 13px; 
            font-weight: 500;
            margin: 4px 0px;
        """)
        right_layout.addWidget(self.list_header_badge)

        # --- Splitter: left | center | right ---
        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(left_widget)
        splitter.addWidget(center_widget)
        splitter.addWidget(right_widget)
        splitter.setChildrenCollapsible(False)
        splitter.setOpaqueResize(True)
        splitter.setSizes([600, 80, 600])  # Adjusted for wider center panel
        self._splitter = splitter

        # Size policies to prevent center pane from expanding
        try:
            left_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            right_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            center_widget.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Preferred)
        except Exception:
            pass

        main_layout.addWidget(splitter)

        # --- Bottom Actions (Print + Close) with improved styling ---
        close_button_layout = QHBoxLayout()
        close_button_layout.setSpacing(12)
        close_button_layout.addStretch()
        
        self.print_bottom_button = QPushButton("Print List")
        self.print_bottom_button.setStyleSheet("""
            QPushButton {
                padding: 8px 16px;
                font-size: 13px;
                font-weight: 600;
                border: 1px solid #6f42c1;
                background-color: #6f42c1;
                color: white;
                border-radius: 4px;
                min-width: 100px;
            }
            QPushButton:hover {
                background-color: #5a32a3;
            }
            QPushButton:disabled {
                background-color: #ccc;
                border-color: #ccc;
                color: #999;
            }
        """)
        self.print_bottom_button.setToolTip("Print selected list")
        self.print_bottom_button.clicked.connect(self.print_selected_list)
        self.print_bottom_button.setEnabled(False)
        close_button_layout.addWidget(self.print_bottom_button)
        
        self.close_button = QPushButton("Close")
        self.close_button.setStyleSheet("""
            QPushButton {
                padding: 8px 16px;
                font-size: 13px;
                font-weight: 600;
                border: 1px solid #6c757d;
                background-color: #f8f9fa;
                color: #495057;
                border-radius: 4px;
                min-width: 80px;
            }
            QPushButton:hover {
                background-color: #e9ecef;
                border-color: #adb5bd;
            }
        """)
        self.close_button.clicked.connect(self.accept)
        close_button_layout.addWidget(self.close_button)
        
        main_layout.addLayout(close_button_layout)

        # Shortcuts for power users
        try:
            QShortcut(QKeySequence.Refresh, self, activated=self.load_available_bars)  # F5 / Ctrl+R
            QShortcut(QKeySequence("Ctrl+N"), self, activated=self.create_new_list)
            QShortcut(QKeySequence.Print, self, activated=self.print_selected_list)
            QShortcut(QKeySequence.Cancel, self, activated=self.reject)  # Esc to close
            QShortcut(QKeySequence.Delete, self.list_bars_table, activated=self.remove_selected_from_list)
            # Enter to add from available
            QShortcut(QKeySequence(Qt.Key_Return), self.available_bars_table, activated=self.add_selected_to_list)
        except Exception:
            pass

        # Restore persisted UI state
        self._restore_ui_state()

        # Double-click transfers
        try:
            self.available_bars_table.cellDoubleClicked.connect(lambda r, c: self.add_selected_to_list())
            self.list_bars_table.cellDoubleClicked.connect(lambda r, c: self.remove_selected_from_list())
        except Exception:
            pass

        # Update transfer buttons on selection changes
        try:
            self.available_bars_table.selectionModel().selectionChanged.connect(self._on_selection_changed)
            self.list_bars_table.selectionModel().selectionChanged.connect(self._on_selection_changed)
        except Exception:
            pass

        # Persist sort changes
        try:
            self.available_bars_table.horizontalHeader().sortIndicatorChanged.connect(
                lambda col, order: self._save_table_sort_state('available', self.available_bars_table)
            )
            self.list_bars_table.horizontalHeader().sortIndicatorChanged.connect(
                lambda col, order: self._save_table_sort_state('list', self.list_bars_table)
            )
        except Exception:
            pass

        # Auto-refresh timer
        self._auto_refresh_timer = QTimer(self)
        self._auto_refresh_timer.setInterval(5000)
        self._auto_refresh_timer.timeout.connect(self.load_available_bars)

    # Ensure fresh data when the view becomes visible (embedded or modal)
    def showEvent(self, event):
        try:
            # Refresh available bars and the right pane (if a list is selected)
            self.load_available_bars()
            if self.current_list_id is not None:
                self.load_bars_in_selected_list()
        except Exception:
            pass
        try:
            super().showEvent(event)
        except Exception:
            pass

    # --- Data Loading Methods ---

    def load_available_bars(self):
        """Loads bars with status 'In Stock' and no list_id, applying weight filter."""
        # print("Loading available bars...") # Optional: Keep for debugging
        weight_query = self.weight_search_edit.text().strip()
        voucher_query = ""  # Voucher search removed
        # Read other filters
        try:
            tol = float(self.weight_tol_spin.value())
        except Exception:
            tol = 0.001
        try:
            min_purity = float(self.purity_min_spin.value())
        except Exception:
            min_purity = None
        try:
            max_purity = float(self.purity_max_spin.value())
        except Exception:
            max_purity = None
        # Busy cursor during load
        try:
            QApplication.setOverrideCursor(Qt.WaitCursor)
        except Exception:
            pass
        try:
            # Use get_silver_bars with specific filters
            available_bars = self.db_manager.get_silver_bars(
                status='In Stock',
                weight_query=weight_query if weight_query else None,
                estimate_voucher_no=voucher_query if voucher_query else None,
                weight_tolerance=tol,
                min_purity=min_purity,
                max_purity=max_purity,
                date_range=self._current_date_range()
            )
            # Filter further to ensure list_id is NULL (get_silver_bars doesn't have this filter yet)
            available_bars = [bar for bar in available_bars if bar['list_id'] is None]
            self._populate_table(self.available_bars_table, available_bars)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load available bars: {e}")
            self.available_bars_table.setRowCount(0)
        finally:
            # After loading, try to restore column widths
            self._restore_table_column_widths()
            # Update buttons state
            self._update_transfer_buttons_state()
            self._update_selection_summaries()
            try:
                QApplication.restoreOverrideCursor()
            except Exception:
                pass

    def load_lists(self):
        """Populates the list selection combo box."""
        import logging
        logging.getLogger(__name__).debug("Loading lists...")
        self.list_combo.blockSignals(True)
        self.list_combo.clear()
        self.list_combo.addItem("--- Select a List ---", None)
        try:
            # Get only active lists (not issued)
            lists = self.db_manager.get_silver_bar_lists(include_issued=False)
            for list_row in lists:
                # Store list_id as item data, show list note but remove timestamp
                list_note = list_row['list_note'] or ""
                list_date = list_row['creation_date'].split()[0] if 'creation_date' in list_row.keys() and list_row['creation_date'] else ""
                display_text = f"{list_row['list_identifier']} ({list_date})"
                if list_note:
                    display_text += f" - {list_note}"
                self.list_combo.addItem(display_text, list_row['list_id'])
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load lists: {e}")
        finally:
            # Try to restore previously selected list before firing change
            try:
                self._restore_selected_list_from_settings()
            except Exception:
                pass
            self.list_combo.blockSignals(False)
            self.list_selection_changed() # Update UI based on initial selection

    def list_selection_changed(self):
        """Handles changes in the selected list."""
        selected_index = self.list_combo.currentIndex()
        self.current_list_id = self.list_combo.itemData(selected_index)

        is_list_selected = self.current_list_id is not None
        self.edit_note_button.setEnabled(is_list_selected)
        self.print_list_button.setEnabled(is_list_selected)
        try:
            self.export_list_button.setEnabled(is_list_selected)
        except Exception:
            pass
        try:
            self.print_bottom_button.setEnabled(is_list_selected)
        except Exception:
            pass
        self.delete_list_button.setEnabled(is_list_selected)
        self.mark_issued_button.setEnabled(is_list_selected)
        # Update transfer buttons based on list selection and current table selections
        self._update_transfer_buttons_state()

        if is_list_selected:
            details = self.db_manager.get_silver_bar_list_details(self.current_list_id)
            if details:
                info = f"{details['list_identifier']}"
                try:
                    note_val = details['list_note'] if 'list_note' in details.keys() else None
                except Exception:
                    # sqlite3.Row supports keys(); if not, fallback to attribute or None
                    note_val = getattr(details, 'list_note', None)
                if note_val:
                    info += f"  –  {note_val}"
                self.list_info_label.setText(info)
            else:
                self.list_info_label.setText("Error loading list details")
            self.load_bars_in_selected_list()
        else:
            self.list_info_label.setText("No list selected")
            self.list_bars_table.setRowCount(0) # Clear list bars table

    def load_bars_in_selected_list(self):
        """Loads bars assigned to the currently selected list."""
        if self.current_list_id is None:
            self.list_bars_table.setRowCount(0)
            return

        # print(f"Loading bars for list ID: {self.current_list_id}") # Optional: Keep for debugging
        try:
            QApplication.setOverrideCursor(Qt.WaitCursor)
            bars_in_list = self.db_manager.get_bars_in_list(self.current_list_id)
            self._populate_table(self.list_bars_table, bars_in_list)
        except Exception as e:
             QMessageBox.critical(self, "Error", f"Failed to load bars for list {self.current_list_id}: {e}")
             self.list_bars_table.setRowCount(0)
        finally:
            self._update_transfer_buttons_state()
            self._update_selection_summaries()
            try:
                QApplication.restoreOverrideCursor()
            except Exception:
                pass

    # --- Action Methods ---

    def create_new_list(self):
        """Prompts for a note and creates a new list."""
        import logging
        logging.getLogger(__name__).info("Creating new list...")
        note, ok = QInputDialog.getText(self, "Create New List", "Enter a note for the new list:", QLineEdit.Normal)
        if ok:
            new_list_id = self.db_manager.create_silver_bar_list(note if note else None)
            if new_list_id:
                QMessageBox.information(self, "Success", "New list created.")
                self.load_lists()
                # Optionally select the newly created list
                index = self.list_combo.findData(new_list_id)
                if index >= 0:
                    self.list_combo.setCurrentIndex(index)
            else:
                QMessageBox.critical(self, "Error", "Failed to create new list.")

    def _create_list_from_selection(self):
        """Create a new list and assign currently selected available bars to it."""
        selected = self.available_bars_table.selectionModel().selectedRows() if self.available_bars_table.selectionModel() else []
        if not selected:
            QMessageBox.warning(self, "Selection", "Select one or more available bars first.")
            return
        note, ok = QInputDialog.getText(self, "Create List from Selection", "Enter a note for the new list:", QLineEdit.Normal)
        if not ok:
            return
        new_list_id = self.db_manager.create_silver_bar_list(note if note else None)
        if not new_list_id:
            QMessageBox.critical(self, "Error", "Failed to create new list.")
            return
        # Refresh lists and select the new one
        self.load_lists()
        idx = self.list_combo.findData(new_list_id)
        if idx >= 0:
            self.list_combo.setCurrentIndex(idx)
        # Assign selected bars
        bar_ids = []
        for index in selected:
            item = self.available_bars_table.item(index.row(), 0)
            if item:
                bar_ids.append(item.data(Qt.UserRole))
        added_count = 0
        failed = []
        try:
            QApplication.setOverrideCursor(Qt.WaitCursor)
        except Exception:
            pass
        for bar_id in bar_ids:
            if self.db_manager.assign_bar_to_list(bar_id, new_list_id):
                added_count += 1
            else:
                failed.append(str(bar_id))
        try:
            QApplication.restoreOverrideCursor()
        except Exception:
            pass
        self.load_available_bars()
        self.load_bars_in_selected_list()
        if added_count:
            QMessageBox.information(self, "Success", f"Created list and added {added_count} bar(s).")
        if failed:
            QMessageBox.warning(self, "Partial", f"Failed to add bars: {', '.join(failed)}")

    def add_selected_to_list(self):
        """Adds selected available bars to the currently selected list."""
        if self.current_list_id is None:
            QMessageBox.warning(self, "Selection Error", "Please select a list first.")
            return

        selected_rows = self.available_bars_table.selectionModel().selectedRows()
        if not selected_rows:
            QMessageBox.warning(self, "Selection Error", "Please select one or more available bars to add.")
            return

        bar_ids_to_add = []
        for index in selected_rows:
            bar_id_item = self.available_bars_table.item(index.row(), 0) # Hidden ID column
            if bar_id_item:
                bar_ids_to_add.append(bar_id_item.data(Qt.UserRole)) # Get ID from item data

        if not bar_ids_to_add:
            QMessageBox.warning(self, "Error", "Could not get IDs for selected bars.")
            return

        reply = QMessageBox.question(self, "Confirm Add",
                                     f"Add {len(bar_ids_to_add)} selected bar(s) to list '{self.list_combo.currentText()}'?",
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)

        if reply == QMessageBox.Yes:
            try:
                QApplication.setOverrideCursor(Qt.WaitCursor)
            except Exception:
                pass
            added_count = 0
            failed_ids = []
            for bar_id in bar_ids_to_add:
                if self.db_manager.assign_bar_to_list(bar_id, self.current_list_id):
                    added_count += 1
                else:
                    failed_ids.append(str(bar_id))

            if added_count > 0:
                QMessageBox.information(self, "Success", f"{added_count} bar(s) added to the list.")
            if failed_ids:
                QMessageBox.warning(self, "Error", f"Failed to add bars with IDs: {', '.join(failed_ids)}")

            self.load_available_bars()
            self.load_bars_in_selected_list()
            self._update_transfer_buttons_state()
            try:
                QApplication.restoreOverrideCursor()
            except Exception:
                pass

    def remove_selected_from_list(self):
        """Removes selected bars from the currently selected list."""
        if self.current_list_id is None:
             QMessageBox.warning(self, "Error", "No list selected.")
             return

        selected_rows = self.list_bars_table.selectionModel().selectedRows()
        if not selected_rows:
            QMessageBox.warning(self, "Selection Error", "Please select one or more bars from the list to remove.")
            return

        bar_ids_to_remove = []
        for index in selected_rows:
            bar_id_item = self.list_bars_table.item(index.row(), 0) # Hidden ID column
            if bar_id_item:
                bar_ids_to_remove.append(bar_id_item.data(Qt.UserRole))

        if not bar_ids_to_remove:
            QMessageBox.warning(self, "Error", "Could not get IDs for selected bars.")
            return

        reply = QMessageBox.question(self, "Confirm Remove",
                                     f"Remove {len(bar_ids_to_remove)} selected bar(s) from list '{self.list_combo.currentText()}'?",
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)

        if reply == QMessageBox.Yes:
            try:
                QApplication.setOverrideCursor(Qt.WaitCursor)
            except Exception:
                pass
            removed_count = 0
            failed_ids = []
            for bar_id in bar_ids_to_remove:
                if self.db_manager.remove_bar_from_list(bar_id):
                    removed_count += 1
                else:
                    failed_ids.append(str(bar_id))

            if removed_count > 0:
                QMessageBox.information(self, "Success", f"{removed_count} bar(s) removed from the list.")
            if failed_ids:
                QMessageBox.warning(self, "Error", f"Failed to remove bars with IDs: {', '.join(failed_ids)}")

            self.load_available_bars()
            self.load_bars_in_selected_list()
            self._update_transfer_buttons_state()
            try:
                QApplication.restoreOverrideCursor()
            except Exception:
                pass

    def edit_list_note(self):
        """Edits the note for the currently selected list."""
        if self.current_list_id is None:
             QMessageBox.warning(self, "Error", "No list selected.")
             return
        details = self.db_manager.get_silver_bar_list_details(self.current_list_id)
        if not details:
            QMessageBox.warning(self, "Error", "Could not retrieve current list details.")
            return

        current_note = details['list_note'] or ""
        new_note, ok = QInputDialog.getText(self, "Edit List Note",
                                            f"Enter new note for list '{details['list_identifier']}':",
                                            QLineEdit.Normal, current_note)

        if ok and new_note != current_note:
            if self.db_manager.update_silver_bar_list_note(self.current_list_id, new_note):
                QMessageBox.information(self, "Success", "List note updated.")
                # Refresh label and potentially combo box text
                self.list_details_label.setText(f"Selected List: {details['list_identifier']} (Note: {new_note or 'N/A'})")
                # Find and update combo box item text with the new note
                index = self.list_combo.findData(self.current_list_id)
                if index >= 0:
                    list_date = details['creation_date'].split()[0] if 'creation_date' in details.keys() and details['creation_date'] else ""
                    display_text = f"{details['list_identifier']} ({list_date})"
                    if new_note:
                        display_text += f" - {new_note}"
                    self.list_combo.setItemText(index, display_text)
            else:
                QMessageBox.critical(self, "Error", "Failed to update list note.")

    def delete_selected_list(self):
        """Deletes the currently selected list."""
        if self.current_list_id is None:
             QMessageBox.warning(self, "Error", "No list selected.")
             return
        details = self.db_manager.get_silver_bar_list_details(self.current_list_id)
        list_name = details['list_identifier'] if details else f"ID {self.current_list_id}"

        reply = QMessageBox.warning(self, "Confirm Delete",
                                    f"Are you sure you want to delete list '{list_name}'?\n"
                                    f"All bars currently assigned to this list will be unassigned (status set to 'In Stock').\n"
                                    f"This action cannot be undone.",
                                    QMessageBox.Yes | QMessageBox.Cancel, QMessageBox.Cancel)

        if reply == QMessageBox.Yes:
            success, msg = self.db_manager.delete_silver_bar_list(self.current_list_id)
            if success:
                QMessageBox.information(self, "Success", f"List '{list_name}' deleted successfully.")
                self.load_lists() # Reload lists, which triggers selection change and table refresh
            else:
                QMessageBox.critical(self, "Error", f"Failed to delete list: {msg}")

    def mark_list_as_issued(self):
        """Mark the currently selected list as issued."""
        if self.current_list_id is None:
            QMessageBox.warning(self, "Error", "No list selected.")
            return
        
        details = self.db_manager.get_silver_bar_list_details(self.current_list_id)
        list_name = details['list_identifier'] if details else f"ID {self.current_list_id}"
        
        reply = QMessageBox.question(self, "Mark as Issued",
                                   f"Are you sure you want to mark list '{list_name}' as issued?\n\n"
                                   f"This will:\n"
                                   f"• Remove the list from the active lists menu\n"
                                   f"• Move it to Silver Bar History\n"
                                   f"• Set all bars in the list to 'Issued' status\n\n"
                                   f"This action can be reversed from the History window.",
                                   QMessageBox.Yes | QMessageBox.Cancel, QMessageBox.Cancel)
        
        if reply == QMessageBox.Yes:
            try:
                # Mark the list as issued
                issued_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                self.db_manager.cursor.execute("""
                    UPDATE silver_bar_lists SET issued_date = ? WHERE list_id = ?
                """, (issued_date, self.current_list_id))
                
                # Update all bars in this list to 'Issued' status
                self.db_manager.cursor.execute("""
                    UPDATE silver_bars SET status = 'Issued' WHERE list_id = ?
                """, (self.current_list_id,))
                
                self.db_manager.conn.commit()
                
                QMessageBox.information(self, "Success", 
                                      f"List '{list_name}' has been marked as issued.\n"
                                      f"It has been moved to Silver Bar History.")
                
                # Refresh the interface
                self.load_lists()
                self.load_available_bars()
                
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to mark list as issued: {e}")

    def print_selected_list(self):
        """Prints the details and bars of the currently selected list."""
        if self.current_list_id is None:
             QMessageBox.warning(self, "Error", "No list selected.")
             return
        details = self.db_manager.get_silver_bar_list_details(self.current_list_id)
        if not details:
            QMessageBox.warning(self, "Error", "Could not retrieve list details for printing.")
            return

        bars_in_list = self.db_manager.get_bars_in_list(self.current_list_id)

        import logging
        logging.getLogger(__name__).info(f"Printing list {details['list_identifier']} (ID: {self.current_list_id}) with {len(bars_in_list)} bars.")

        try:
            from .print_manager import PrintManager # Import locally
            # Assuming parent() gives access to main window or similar context for font
            parent_context = self.parent()
            current_print_font = getattr(parent_context, 'print_font', None) if parent_context else None

            print_manager = PrintManager(self.db_manager, print_font=current_print_font)

            # Call the existing method, assuming it's suitable or will be adapted
            # This method is defined in print_manager.py and might need adjustment (Step 5)
            success = print_manager.print_silver_bar_list_details(details, bars_in_list, self)

            if not success:
                 QMessageBox.warning(self, "Print Error", "Failed to generate print preview for the list.")

        except ImportError:
             QMessageBox.critical(self, "Error", "Could not import PrintManager.")
        except AttributeError as ae:
             QMessageBox.critical(self, "Error", f"Print function not found or incorrect in PrintManager: {ae}")
        except Exception as e:
             QMessageBox.critical(self, "Print Error", f"An unexpected error occurred during printing: {e}\n{traceback.format_exc()}")

    def generate_optimal_list(self):
        """Generate an optimal list based on target fine weight and optimization preference."""
        dialog = OptimalListDialog(self)
        if dialog.exec_() == QDialog.Accepted:
            min_target = dialog.min_target
            max_target = dialog.max_target
            target_fine_weight = dialog.target_fine_weight
            list_name = dialog.list_name
            optimization_type = dialog.optimization_type
            
            try:
                # Get all available bars
                available_bars = self.db_manager.get_silver_bars(status='In Stock')
                # Filter to only bars not in any list
                available_bars = [bar for bar in available_bars if bar['list_id'] is None]
                
                if not available_bars:
                    QMessageBox.information(self, "No Bars Available", "No silver bars are available for list generation.")
                    return
                
                # Find optimal combination
                selected_bars = self._find_optimal_combination(available_bars, min_target, max_target, optimization_type)
                
                if not selected_bars:
                    QMessageBox.information(self, "No Solution", 
                                          f"Could not find a combination of bars within the range {min_target:.1f}g - {max_target:.1f}g.")
                    return
                
                # Create new list
                new_list_id = self.db_manager.create_silver_bar_list(list_name)
                if not new_list_id:
                    QMessageBox.critical(self, "Error", "Failed to create new list.")
                    return
                
                # Add selected bars to the list
                added_count = 0
                failed_bars = []
                for bar in selected_bars:
                    if self.db_manager.assign_bar_to_list(bar['bar_id'], new_list_id):
                        added_count += 1
                    else:
                        failed_bars.append(str(bar['bar_id']))
                
                # Calculate actual fine weight
                actual_fine_weight = sum(bar['fine_weight'] for bar in selected_bars)
                
                # Show results
                message = f"Optimal list created successfully!\n\n"
                message += f"List Name: {list_name}\n"
                message += f"Target Range: {min_target:.1f}g - {max_target:.1f}g\n"
                message += f"Actual Fine Weight: {actual_fine_weight:.1f}g\n"
                message += f"Bars Added: {added_count}\n"
                message += f"Optimization: {'Minimum bars' if optimization_type == 'min_bars' else 'Maximum bars'}"
                
                if failed_bars:
                    message += f"\n\nWarning: Failed to add {len(failed_bars)} bars: {', '.join(failed_bars)}"
                
                QMessageBox.information(self, "List Generated", message)
                
                # Refresh the interface
                self.load_lists()
                self.load_available_bars()
                
                # Select the new list
                index = self.list_combo.findData(new_list_id)
                if index >= 0:
                    self.list_combo.setCurrentIndex(index)
                
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to generate optimal list: {e}\n{traceback.format_exc()}")

    def _find_optimal_combination(self, available_bars, min_target, max_target, optimization_type):
        """Find the optimal combination of silver bars within the target range."""
        # Sort bars by fine weight for better algorithm performance
        bars = sorted(available_bars, key=lambda x: x['fine_weight'], reverse=True)
        
        if optimization_type == 'min_bars':
            # Use greedy approach for minimum number of bars
            return self._find_min_bars_combination(bars, min_target, max_target)
        else:  # max_bars
            # Use approach that maximizes number of bars while staying in range
            return self._find_max_bars_combination(bars, min_target, max_target)
    
    def _find_min_bars_combination(self, bars, min_target, max_target):
        """Find combination with minimum number of bars within the target range."""
        # Try to get as close to min_target as possible using fewest bars
        selected = []
        current_total = 0.0
        
        # Greedy approach: add largest bars that don't exceed max_target
        for bar in bars:
            if current_total + bar['fine_weight'] <= max_target:
                selected.append(bar)
                current_total += bar['fine_weight']
                if current_total >= min_target:
                    break
        
        # Check if we're in range
        if min_target <= current_total <= max_target:
            return selected
        
        # If greedy didn't work and set is small, try DP
        if len(bars) <= 50:
            return self._dp_combination_range(bars, min_target, max_target)
        
        return []
    
    def _find_max_bars_combination(self, bars, min_target, max_target):
        """Find combination that uses maximum bars while staying within the range."""
        # Sort by fine weight ascending for max bars approach
        bars_asc = sorted(bars, key=lambda x: x['fine_weight'])
        selected = []
        current_total = 0.0
        
        for bar in bars_asc:
            if current_total + bar['fine_weight'] <= max_target:
                selected.append(bar)
                current_total += bar['fine_weight']
        
        # Return only if we're within the range
        return selected if min_target <= current_total <= max_target else []
    
    def _dp_combination_range(self, bars, min_target, max_target):
        """Dynamic programming approach for finding optimal combinations within a range."""
        # Convert to integer math for DP (multiply by 10 for 1 decimal precision)
        min_target_int = int(min_target * 10)
        max_target_int = int(max_target * 10)
        
        # DP table: dp[weight] = (bars_used, bar_indices)
        n = len(bars)
        
        # Initialize DP table
        dp = {}
        dp[0] = (0, [])
        
        for i in range(n):
            bar_weight = int(bars[i]['fine_weight'] * 10)
            new_dp = dp.copy()
            
            for weight, (count, indices) in dp.items():
                new_weight = weight + bar_weight
                if new_weight <= max_target_int:
                    if new_weight not in new_dp or new_dp[new_weight][0] > count + 1:
                        new_dp[new_weight] = (count + 1, indices + [i])
            
            dp = new_dp
        
        # Find best solution within range (minimum bars first)
        best_solution = None
        best_bars_count = float('inf')
        
        for weight, (count, indices) in dp.items():
            if min_target_int <= weight <= max_target_int:
                if count < best_bars_count:
                    best_bars_count = count
                    best_solution = indices
        
        if best_solution:
            return [bars[i] for i in best_solution]
        
        return []

    # --- Helper Methods ---
    def _populate_table(self, table, bars_data):
        """Helper function to populate a table widget with bar data and update totals."""
        # Prevent signal storms and row shuffling while inserting
        table.blockSignals(True)
        sorting_was_enabled = False
        try:
            sorting_was_enabled = table.isSortingEnabled()
            if sorting_was_enabled:
                table.setSortingEnabled(False)
        except Exception:
            pass
        table.setRowCount(0) # Clear existing rows
        
        # Initialize totals
        total_weight = 0.0
        total_fine_weight = 0.0
        bar_count = 0
        try:
            if bars_data:
                table.setRowCount(len(bars_data))
                for row_idx, bar_row in enumerate(bars_data):
                    bar_id = bar_row['bar_id']
                    id_item = QTableWidgetItem(str(bar_id))
                    id_item.setData(Qt.UserRole, bar_id) # Store ID in item data

                    # Access items using dictionary-style keys for sqlite3.Row
                    voucher_no = bar_row['estimate_voucher_no'] if 'estimate_voucher_no' in bar_row.keys() else 'N/A'
                    
                    # Get the note for this estimate
                    note = ""
                    try:
                        self.db_manager.cursor.execute("SELECT note FROM estimates WHERE voucher_no = ?", (voucher_no,))
                        result = self.db_manager.cursor.fetchone()
                        if result and result['note']:
                            note = result['note']
                    except Exception:
                        pass
                    
                    # Create display text with voucher and note
                    display_text = voucher_no
                    if note:
                        display_text += f" ({note})"
                    
                    est_vch_item = QTableWidgetItem(display_text)
                    # Numeric items with proper sort role
                    weight_val = bar_row['weight'] if 'weight' in bar_row.keys() and bar_row['weight'] is not None else 0.0
                    purity_val = bar_row['purity'] if 'purity' in bar_row.keys() and bar_row['purity'] is not None else 0.0
                    fine_val = bar_row['fine_weight'] if 'fine_weight' in bar_row.keys() and bar_row['fine_weight'] is not None else 0.0
                    weight_item = QTableWidgetItem(f"{weight_val:.3f}")
                    weight_item.setData(Qt.EditRole, float(weight_val))
                    purity_item = QTableWidgetItem(f"{purity_val:.2f}")
                    purity_item.setData(Qt.EditRole, float(purity_val))
                    fine_wt_item = QTableWidgetItem(f"{fine_val:.3f}")
                    fine_wt_item.setData(Qt.EditRole, float(fine_val))
                    date_item = QTableWidgetItem(bar_row['date_added'] if 'date_added' in bar_row.keys() else '')
                    status_item = QTableWidgetItem(bar_row['status'] if 'status' in bar_row.keys() else '')

                    # Set alignment for numeric columns
                    weight_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                    purity_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                    fine_wt_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)

                    # Optional: color by status
                    try:
                        status_text = status_item.text()
                        if status_text == 'In Stock':
                            for it in (est_vch_item, weight_item, purity_item, fine_wt_item, date_item, status_item):
                                it.setForeground(QColor('#116611'))
                        elif status_text == 'Assigned':
                            for it in (est_vch_item, weight_item, purity_item, fine_wt_item, date_item, status_item):
                                it.setForeground(QColor('#134a7e'))
                    except Exception:
                        pass

                    # Set items in table
                    table.setItem(row_idx, 0, id_item) # Hidden ID
                    table.setItem(row_idx, 1, est_vch_item)
                    table.setItem(row_idx, 2, weight_item)
                    table.setItem(row_idx, 3, purity_item)
                    table.setItem(row_idx, 4, fine_wt_item)
                    table.setItem(row_idx, 5, date_item)
                    table.setItem(row_idx, 6, status_item)
                    # Update totals
                    weight = bar_row['weight'] if 'weight' in bar_row.keys() and bar_row['weight'] is not None else 0.0
                    fine_weight = bar_row['fine_weight'] if 'fine_weight' in bar_row.keys() and bar_row['fine_weight'] is not None else 0.0
                    total_weight += weight
                    total_fine_weight += fine_weight
                    bar_count += 1
                
                # Update the appropriate totals label
                totals_text = f"Bars: {bar_count} | Total Weight: {total_weight:.3f} g | Total Fine Wt: {total_fine_weight:.3f} g"
                if table == self.available_bars_table:
                    self.available_totals_label.setText(f"Available {totals_text}")
                    try:
                        self.available_header_badge.setText(f"Available: {bar_count}")
                    except Exception:
                        pass
                elif table == self.list_bars_table:
                    self.list_totals_label.setText(f"List {totals_text}")
                    try:
                        self.list_header_badge.setText(f"List: {bar_count}")
                    except Exception:
                        pass
        except Exception as e:
             QMessageBox.critical(self, "Table Error", f"Error populating table: {e}\n{traceback.format_exc()}")
        finally:
            # Restore sorting state
            try:
                if sorting_was_enabled:
                    table.setSortingEnabled(True)
            except Exception:
                pass
            table.blockSignals(False)
            # Optional: Resize columns after populating if not using fixed modes
            # table.resizeColumnsToContents()
            # Refresh selection summaries when data changes
            try:
                self._update_selection_summaries()
            except Exception:
                pass

    # --- UI Helpers: Context Menus and State Persistence ---
    def _show_available_context_menu(self, pos):
        try:
            menu = QMenu(self)
            add_action = menu.addAction("Add Selected Bars to List")
            add_all_action = menu.addAction("Add All Filtered to List")
            create_list_sel_action = menu.addAction("Create New List from Selection…")
            refresh_action = menu.addAction("Refresh Available")
            copy_action = menu.addAction("Copy Selected Rows")
            action = menu.exec_(self.available_bars_table.viewport().mapToGlobal(pos))
            if action == add_action:
                self.add_selected_to_list()
            elif action == add_all_action:
                self.add_all_filtered_to_list()
            elif action == create_list_sel_action:
                self._create_list_from_selection()
            elif action == refresh_action:
                self.load_available_bars()
            elif action == copy_action:
                self._copy_selected_rows(self.available_bars_table)
        except Exception:
            pass

    def _show_list_context_menu(self, pos):
        try:
            menu = QMenu(self)
            remove_action = menu.addAction("Remove Selected Bars from List")
            remove_all_action = menu.addAction("Remove All Bars from List")
            print_action = menu.addAction("Print List")
            export_action = menu.addAction("Export List to CSV…")
            copy_action = menu.addAction("Copy Selected Rows")
            action = menu.exec_(self.list_bars_table.viewport().mapToGlobal(pos))
            if action == remove_action:
                self.remove_selected_from_list()
            elif action == remove_all_action:
                self.remove_all_from_list()
            elif action == print_action:
                self.print_selected_list()
            elif action == export_action:
                self.export_current_list_to_csv()
            elif action == copy_action:
                self._copy_selected_rows(self.list_bars_table)
        except Exception:
            pass

    def _copy_selected_rows(self, table):
        try:
            selected = table.selectionModel().selectedRows()
            if not selected:
                return
            rows = []
            for idx in selected:
                r = idx.row()
                values = []
                for c in range(1, table.columnCount()):  # skip hidden ID col 0
                    item = table.item(r, c)
                    values.append(item.text() if item else '')
                rows.append('\t'.join(values))
            text = '\n'.join(rows)
            from PyQt5.QtWidgets import QApplication
            QApplication.clipboard().setText(text)
        except Exception:
            pass

    def _settings(self):
        return QSettings(SETTINGS_ORG, SETTINGS_APP)

    def _save_table_sort_state(self, which, table):
        try:
            s = self._settings()
            header = table.horizontalHeader()
            s.setValue(f"ui/silver_bars/{which}_sort_col", header.sortIndicatorSection())
            s.setValue(f"ui/silver_bars/{which}_sort_order", int(header.sortIndicatorOrder()))
        except Exception:
            pass

    def _save_ui_state(self):
        try:
            s = self._settings()
            # Dialog geometry
            s.setValue("ui/silver_bars/geometry", self.saveGeometry())
            # Splitter (use a new key so old vertical state doesn't apply)
            if hasattr(self, "_splitter"):
                s.setValue("ui/silver_bars/splitter_h", self._splitter.saveState())
            # Column widths
            s.setValue("ui/silver_bars/available_cols", self._get_table_column_widths(self.available_bars_table))
            s.setValue("ui/silver_bars/list_cols", self._get_table_column_widths(self.list_bars_table))
            # Sort state
            self._save_table_sort_state('available', self.available_bars_table)
            self._save_table_sort_state('list', self.list_bars_table)
            # Filters and selection
            try:
                s.setValue("ui/silver_bars/weight_query", self.weight_search_edit.text())
            except Exception:
                pass
            # Voucher search removed - no need for try/except
            try:
                s.setValue("ui/silver_bars/current_list_id", self.current_list_id)
            except Exception:
                pass
            try:
                s.setValue("ui/silver_bars/weight_tol", float(self.weight_tol_spin.value()))
            except Exception:
                pass
            try:
                s.setValue("ui/silver_bars/purity_min", float(self.purity_min_spin.value()))
                s.setValue("ui/silver_bars/purity_max", float(self.purity_max_spin.value()))
            except Exception:
                pass
            try:
                s.setValue("ui/silver_bars/date_range", self.date_range_combo.currentText())
            except Exception:
                pass
            try:
                s.setValue("ui/silver_bars/auto_refresh", bool(self.auto_refresh_checkbox.isChecked()))
            except Exception:
                pass
            s.sync()
        except Exception:
            pass

    def _restore_ui_state(self):
        try:
            s = self._settings()
            # Geometry
            geo = s.value("ui/silver_bars/geometry")
            if geo:
                self.restoreGeometry(geo)
            # Splitter (read new key; if missing, keep defaults)
            state = s.value("ui/silver_bars/splitter_h")
            if state and hasattr(self, "_splitter"):
                self._splitter.restoreState(state)
            # Ensure horizontal orientation even if old state sneaks in
            if hasattr(self, "_splitter"):
                self._splitter.setOrientation(Qt.Horizontal)
            # Restore filters (won't trigger load until after init)
            # Weight search should always start empty - don't restore previous value
            # try:
            #     wq = s.value("ui/silver_bars/weight_query", "")
            #     if isinstance(wq, str):
            #         self.weight_search_edit.setText(wq)
            # except Exception:
            #     pass
            try:
                vq = s.value("ui/silver_bars/voucher_query", "")
                # Voucher search removed
            except Exception:
                pass
            try:
                tol = s.value("ui/silver_bars/weight_tol")
                if tol is not None:
                    self.weight_tol_spin.setValue(float(tol))
            except Exception:
                pass
            try:
                pmin = s.value("ui/silver_bars/purity_min")
                pmax = s.value("ui/silver_bars/purity_max")
                if pmin is not None:
                    self.purity_min_spin.setValue(float(pmin))
                if pmax is not None:
                    self.purity_max_spin.setValue(float(pmax))
            except Exception:
                pass
            try:
                dr = s.value("ui/silver_bars/date_range")
                if isinstance(dr, str):
                    idx = self.date_range_combo.findText(dr)
                    if idx >= 0:
                        self.date_range_combo.setCurrentIndex(idx)
            except Exception:
                pass
            try:
                ar = s.value("ui/silver_bars/auto_refresh")
                if isinstance(ar, (bool, str)):
                    checked = bool(ar) if isinstance(ar, bool) else (ar.lower() == 'true')
                    self.auto_refresh_checkbox.setChecked(checked)
            except Exception:
                pass
            # Apply saved sort order
            try:
                av_col = s.value("ui/silver_bars/available_sort_col", type=int)
                av_ord = s.value("ui/silver_bars/available_sort_order", type=int)
                if av_col is not None and av_ord is not None:
                    self.available_bars_table.sortByColumn(int(av_col), Qt.SortOrder(int(av_ord)))
                ls_col = s.value("ui/silver_bars/list_sort_col", type=int)
                ls_ord = s.value("ui/silver_bars/list_sort_order", type=int)
                if ls_col is not None and ls_ord is not None:
                    self.list_bars_table.sortByColumn(int(ls_col), Qt.SortOrder(int(ls_ord)))
            except Exception:
                pass
        except Exception:
            pass

    def _restore_selected_list_from_settings(self):
        try:
            s = self._settings()
            saved_id = s.value("ui/silver_bars/current_list_id")
            if saved_id is None:
                return
            # QSettings may store as str; convert to int when possible
            try:
                saved_id_int = int(saved_id)
            except Exception:
                saved_id_int = saved_id
            idx = self.list_combo.findData(saved_id_int)
            if idx >= 0:
                self.list_combo.setCurrentIndex(idx)
        except Exception:
            pass

    def _get_table_column_widths(self, table):
        try:
            header = table.horizontalHeader()
            return [header.sectionSize(i) for i in range(table.columnCount())]
        except Exception:
            return None

    def _apply_table_column_widths(self, table, widths):
        try:
            if not widths:
                return
            header = table.horizontalHeader()
            for i, w in enumerate(widths):
                if i < table.columnCount() and isinstance(w, int) and w > 0:
                    header.resizeSection(i, w)
        except Exception:
            pass

    def _restore_table_column_widths(self):
        try:
            s = self._settings()
            avail = s.value("ui/silver_bars/available_cols", type=list)
            lcols = s.value("ui/silver_bars/list_cols", type=list)
            self._apply_table_column_widths(self.available_bars_table, avail)
            self._apply_table_column_widths(self.list_bars_table, lcols)
        except Exception:
            pass

    def _update_transfer_buttons_state(self):
        try:
            list_selected = self.current_list_id is not None
            has_avail_sel = False
            has_list_sel = False
            try:
                has_avail_sel = bool(self.available_bars_table.selectionModel().selectedRows())
            except Exception:
                pass
            try:
                has_list_sel = bool(self.list_bars_table.selectionModel().selectedRows())
            except Exception:
                pass
            if hasattr(self, 'add_to_list_button'):
                self.add_to_list_button.setEnabled(list_selected and has_avail_sel)
            if hasattr(self, 'remove_from_list_button'):
                self.remove_from_list_button.setEnabled(list_selected and has_list_sel)
            if hasattr(self, 'add_all_button'):
                self.add_all_button.setEnabled(list_selected and self.available_bars_table.rowCount() > 0)
            if hasattr(self, 'remove_all_button'):
                self.remove_all_button.setEnabled(list_selected and self.list_bars_table.rowCount() > 0)
        except Exception:
            pass

    def _on_selection_changed(self, *args, **kwargs):
        try:
            self._update_transfer_buttons_state()
            self._update_selection_summaries()
        except Exception:
            pass

    def _update_selection_summaries(self):
        try:
            def compute(table):
                sel = table.selectionModel().selectedRows() if table.selectionModel() else []
                count = len(sel)
                weight_sum = 0.0
                fine_sum = 0.0
                for idx in sel:
                    r = idx.row()
                    w_item = table.item(r, 2)
                    f_item = table.item(r, 4)
                    try:
                        w_val = w_item.data(Qt.EditRole) if w_item is not None else 0.0
                        f_val = f_item.data(Qt.EditRole) if f_item is not None else 0.0
                        weight_sum += float(w_val or 0.0)
                        fine_sum += float(f_val or 0.0)
                    except Exception:
                        pass
                return count, weight_sum, fine_sum
            ac, aw, af = compute(self.available_bars_table)
            lc, lw, lf = compute(self.list_bars_table)
            if hasattr(self, 'available_selection_label'):
                self.available_selection_label.setText(f"Selected: {ac} | Weight: {aw:.3f} g | Fine: {af:.3f} g")
            if hasattr(self, 'list_selection_label'):
                self.list_selection_label.setText(f"Selected: {lc} | Weight: {lw:.3f} g | Fine: {lf:.3f} g")
        except Exception:
            pass

    def _clear_filters(self):
        try:
            self.weight_search_edit.clear()
            # Voucher search removed
            try:
                self.weight_tol_spin.setValue(0.001)
                self.purity_min_spin.setValue(0.0)
                self.purity_max_spin.setValue(100.0)
                idx = self.date_range_combo.findText('Any')
                if idx >= 0:
                    self.date_range_combo.setCurrentIndex(idx)
            except Exception:
                pass
            self.load_available_bars()
        except Exception:
            pass

    def add_all_filtered_to_list(self):
        """Assign all bars currently shown in the Available table to the selected list."""
        if self.current_list_id is None:
            QMessageBox.warning(self, "Selection Error", "Please select a list first.")
            return
        row_count = self.available_bars_table.rowCount()
        if row_count == 0:
            QMessageBox.information(self, "No Bars", "No available bars to add.")
            return
        reply = QMessageBox.question(
            self,
            "Confirm Add All",
            f"Add all {row_count} available bar(s) to list '{self.list_combo.currentText()}'?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return
        bar_ids = []
        for r in range(row_count):
            item = self.available_bars_table.item(r, 0)
            if item:
                bar_ids.append(item.data(Qt.UserRole))
        added = 0
        failed = []
        try:
            QApplication.setOverrideCursor(Qt.WaitCursor)
        except Exception:
            pass
        for bar_id in bar_ids:
            if self.db_manager.assign_bar_to_list(bar_id, self.current_list_id):
                added += 1
            else:
                failed.append(str(bar_id))
        try:
            QApplication.restoreOverrideCursor()
        except Exception:
            pass
        self.load_available_bars()
        self.load_bars_in_selected_list()
        self._update_transfer_buttons_state()
        if added:
            QMessageBox.information(self, "Success", f"{added} bar(s) added to the list.")
        if failed:
            QMessageBox.warning(self, "Partial", f"Failed to add bars: {', '.join(failed)}")

    def remove_all_from_list(self):
        """Remove all bars currently present in the selected list."""
        if self.current_list_id is None:
            QMessageBox.warning(self, "Selection Error", "Please select a list first.")
            return
        row_count = self.list_bars_table.rowCount()
        if row_count == 0:
            QMessageBox.information(self, "No Bars", "No bars in the selected list.")
            return
        reply = QMessageBox.warning(
            self,
            "Confirm Remove All",
            f"Remove all {row_count} bar(s) from list '{self.list_combo.currentText()}'?\nThis will set their status to 'In Stock'.",
            QMessageBox.Yes | QMessageBox.Cancel,
            QMessageBox.Cancel
        )
        if reply != QMessageBox.Yes:
            return
        bar_ids = []
        for r in range(row_count):
            item = self.list_bars_table.item(r, 0)
            if item:
                bar_ids.append(item.data(Qt.UserRole))
        removed = 0
        failed = []
        try:
            QApplication.setOverrideCursor(Qt.WaitCursor)
        except Exception:
            pass
        for bar_id in bar_ids:
            if self.db_manager.remove_bar_from_list(bar_id):
                removed += 1
            else:
                failed.append(str(bar_id))
        try:
            QApplication.restoreOverrideCursor()
        except Exception:
            pass
        self.load_available_bars()
        self.load_bars_in_selected_list()
        self._update_transfer_buttons_state()
        if removed:
            QMessageBox.information(self, "Success", f"{removed} bar(s) removed from the list.")
        if failed:
            QMessageBox.warning(self, "Partial", f"Failed to remove bars: {', '.join(failed)}")

    def export_current_list_to_csv(self):
        """Export the bars in the current list to a CSV file."""
        if self.current_list_id is None:
            QMessageBox.warning(self, "Error", "No list selected.")
            return
        # Ask file path
        path, _ = QFileDialog.getSaveFileName(self, "Export List to CSV", "silver_bars.csv", "CSV Files (*.csv)")
        if not path:
            return
        # Gather data from list table (visible order)
        try:
            import csv
            with open(path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                # Header row (include hidden ID for traceability)
                writer.writerow(["bar_id", "estimate_voucher_no", "weight_g", "purity_pct", "fine_weight_g", "date_added", "status"])
                for r in range(self.list_bars_table.rowCount()):
                    row = []
                    for c in range(self.list_bars_table.columnCount()):
                        item = self.list_bars_table.item(r, c)
                        row.append(item.text() if item else '')
                    writer.writerow(row)
            QMessageBox.information(self, "Export Complete", f"List exported to\n{path}")
        except Exception as e:
            QMessageBox.critical(self, "Export Error", f"Failed to export CSV: {e}")

    def _toggle_auto_refresh(self, checked: bool):
        try:
            if checked:
                self._auto_refresh_timer.start()
            else:
                self._auto_refresh_timer.stop()
        except Exception:
            pass

    def _current_date_range(self):
        """Return (start_iso, end_iso) or None based on date range combo."""
        try:
            text = self.date_range_combo.currentText()
        except Exception:
            return None
        now = datetime.now()
        start = end = None
        if text == 'Today':
            start = datetime(now.year, now.month, now.day)
            end = now
        elif text == 'Last 7 days':
            start = now - timedelta(days=7)
            end = now
        elif text == 'Last 30 days':
            start = now - timedelta(days=30)
            end = now
        elif text == 'This Month':
            start = datetime(now.year, now.month, 1)
            end = now
        else:
            return None
        return (start.strftime('%Y-%m-%d %H:%M:%S'), end.strftime('%Y-%m-%d %H:%M:%S'))

    # Persist UI state on close/accept and navigate back when embedded
    def closeEvent(self, event):
        try:
            self._save_ui_state()
            if self._is_embedded():
                # When embedded, do not actually close; just navigate back
                self._navigate_back_to_estimate()
                try:
                    event.ignore()
                except Exception:
                    pass
                return
        except Exception:
            pass
        # Fallback: default behavior
        try:
            super().closeEvent(event)
        except Exception:
            pass

    def accept(self):
        self._save_ui_state()
        if self._is_embedded():
            # When embedded inside the main stack, navigate back without closing
            self._navigate_back_to_estimate()
            return
        # Modal usage: perform normal dialog accept
        try:
            super().accept()
        except Exception:
            pass

    def reject(self):
        self._save_ui_state()
        if self._is_embedded():
            self._navigate_back_to_estimate()
            return
        try:
            super().reject()
        except Exception:
            pass

    def _find_main_window(self):
        try:
            w = self.parent()
            # Walk up parents to find the window that owns the stack and show_estimate()
            while w is not None:
                if hasattr(w, 'show_estimate') and hasattr(w, 'stack'):
                    return w
                w = w.parent()
        except Exception:
            pass
        return None

    def _is_embedded(self):
        try:
            mw = self._find_main_window()
            if not mw:
                return False
            stk = getattr(mw, 'stack', None)
            if stk is None:
                return False
            return stk.indexOf(self) != -1
        except Exception:
            return False

    def _navigate_back_to_estimate(self):
        try:
            mw = self._find_main_window()
            if mw and hasattr(mw, 'show_estimate'):
                mw.show_estimate()
        except Exception:
            pass

class OptimalListDialog(QDialog):
    """Dialog for getting input for optimal list generation."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Generate Optimal List")
        self.setMinimumSize(450, 400)
        self.target_fine_weight = 0.0
        self.list_name = ""
        self.optimization_type = "min_bars"
        self.min_target = 0.0
        self.max_target = 0.0
        
        self.init_ui()
    
    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # Title
        title = QLabel("Generate Optimal Silver Bar List")
        title.setStyleSheet("""
            font-size: 16px;
            font-weight: bold;
            color: #2c3e50;
            margin-bottom: 10px;
        """)
        layout.addWidget(title)
        
        # Fine weight input group
        weight_group = QWidget()
        weight_layout = QVBoxLayout(weight_group)
        weight_layout.setSpacing(12)
        
        weight_title = QLabel("Target Fine Weight Range (grams):")
        weight_title.setStyleSheet("font-weight: 600; font-size: 13px; margin-bottom: 8px;")
        weight_layout.addWidget(weight_title)
        
        # Min and Max weight inputs in a row
        minmax_layout = QHBoxLayout()
        minmax_layout.setSpacing(12)
        
        # Min weight
        min_group = QVBoxLayout()
        min_label = QLabel("Minimum:")
        min_label.setStyleSheet("font-weight: 500; font-size: 12px;")
        min_group.addWidget(min_label)
        
        self.min_weight_spin = QDoubleSpinBox()
        self.min_weight_spin.setDecimals(1)
        self.min_weight_spin.setRange(0.1, 999999.9)
        self.min_weight_spin.setSingleStep(1.0)
        self.min_weight_spin.setValue(95.0)
        self.min_weight_spin.setStyleSheet("""
            QDoubleSpinBox {
                padding: 8px;
                font-size: 14px;
                border: 2px solid #ddd;
                border-radius: 4px;
            }
            QDoubleSpinBox:focus {
                border-color: #007acc;
            }
        """)
        min_group.addWidget(self.min_weight_spin)
        minmax_layout.addLayout(min_group)
        
        # Max weight  
        max_group = QVBoxLayout()
        max_label = QLabel("Maximum:")
        max_label.setStyleSheet("font-weight: 500; font-size: 12px;")
        max_group.addWidget(max_label)
        
        self.max_weight_spin = QDoubleSpinBox()
        self.max_weight_spin.setDecimals(1)
        self.max_weight_spin.setRange(0.1, 999999.9)
        self.max_weight_spin.setSingleStep(1.0)
        self.max_weight_spin.setValue(105.0)
        self.max_weight_spin.setStyleSheet("""
            QDoubleSpinBox {
                padding: 8px;
                font-size: 14px;
                border: 2px solid #ddd;
                border-radius: 4px;
            }
            QDoubleSpinBox:focus {
                border-color: #007acc;
            }
        """)
        max_group.addWidget(self.max_weight_spin)
        minmax_layout.addLayout(max_group)
        
        weight_layout.addLayout(minmax_layout)
        
        # Add explanation for range
        range_explanation = QLabel("The algorithm will find bars with total fine weight between these values.")
        range_explanation.setStyleSheet("""
            color: #666;
            font-size: 11px;
            font-style: italic;
            margin-top: 4px;
        """)
        weight_layout.addWidget(range_explanation)
        
        layout.addWidget(weight_group)
        
        # List name input
        list_name_group = QWidget()
        list_name_layout = QVBoxLayout(list_name_group)
        list_name_layout.setSpacing(8)
        
        list_name_label = QLabel("List Name:")
        list_name_label.setStyleSheet("font-weight: 600; font-size: 13px;")
        list_name_layout.addWidget(list_name_label)
        
        self.list_name_edit = QLineEdit()
        self.list_name_edit.setPlaceholderText("Enter a name for the new list")
        timestamp = datetime.now().strftime("%Y%m%d-%H%M")
        self.list_name_edit.setText(f"Optimal-{timestamp}")
        self.list_name_edit.setStyleSheet("""
            QLineEdit {
                padding: 8px;
                font-size: 14px;
                border: 2px solid #ddd;
                border-radius: 4px;
            }
            QLineEdit:focus {
                border-color: #007acc;
            }
        """)
        list_name_layout.addWidget(self.list_name_edit)
        layout.addWidget(list_name_group)
        
        # Optimization preference
        opt_group = QWidget()
        opt_layout = QVBoxLayout(opt_group)
        opt_layout.setSpacing(12)
        
        opt_label = QLabel("Optimization Preference:")
        opt_label.setStyleSheet("font-weight: 600; font-size: 13px;")
        opt_layout.addWidget(opt_label)
        
        self.opt_button_group = QButtonGroup(self)
        
        self.min_bars_radio = QRadioButton("Minimum number of silver bars")
        self.min_bars_radio.setChecked(True)
        self.min_bars_radio.setStyleSheet("""
            QRadioButton {
                font-size: 13px;
                padding: 4px;
            }
            QRadioButton::indicator {
                width: 18px;
                height: 18px;
            }
        """)
        self.opt_button_group.addButton(self.min_bars_radio, 0)
        opt_layout.addWidget(self.min_bars_radio)
        
        self.max_bars_radio = QRadioButton("Maximum number of silver bars")
        self.max_bars_radio.setStyleSheet("""
            QRadioButton {
                font-size: 13px;
                padding: 4px;
            }
            QRadioButton::indicator {
                width: 18px;
                height: 18px;
            }
        """)
        self.opt_button_group.addButton(self.max_bars_radio, 1)
        opt_layout.addWidget(self.max_bars_radio)
        
        # Add explanation
        explanation = QLabel("• Minimum bars: Find the smallest number of bars within the weight range\n• Maximum bars: Use as many bars as possible within the weight range")
        explanation.setStyleSheet("""
            color: #666;
            font-size: 12px;
            font-style: italic;
            margin-top: 8px;
            padding: 8px;
            background-color: #f8f9fa;
            border-radius: 4px;
        """)
        explanation.setWordWrap(True)
        opt_layout.addWidget(explanation)
        
        layout.addWidget(opt_group)
        
        layout.addStretch()
        
        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        cancel_button = QPushButton("Cancel")
        cancel_button.setStyleSheet("""
            QPushButton {
                padding: 10px 20px;
                font-size: 13px;
                border: 1px solid #6c757d;
                background-color: #f8f9fa;
                color: #495057;
                border-radius: 4px;
                min-width: 80px;
            }
            QPushButton:hover {
                background-color: #e9ecef;
            }
        """)
        cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(cancel_button)
        
        generate_button = QPushButton("Generate List")
        generate_button.setStyleSheet("""
            QPushButton {
                padding: 10px 20px;
                font-size: 13px;
                font-weight: 600;
                border: 1px solid #28a745;
                background-color: #28a745;
                color: white;
                border-radius: 4px;
                min-width: 100px;
            }
            QPushButton:hover {
                background-color: #218838;
            }
        """)
        generate_button.clicked.connect(self.accept)
        generate_button.setDefault(True)
        button_layout.addWidget(generate_button)
        
        layout.addLayout(button_layout)
    
    def accept(self):
        # Validate inputs
        min_val = self.min_weight_spin.value()
        max_val = self.max_weight_spin.value()
        
        if min_val <= 0 or max_val <= 0:
            QMessageBox.warning(self, "Invalid Input", "Please enter valid weight values greater than 0.")
            return
        
        if min_val >= max_val:
            QMessageBox.warning(self, "Invalid Input", "Minimum weight must be less than maximum weight.")
            return
        
        if not self.list_name_edit.text().strip():
            QMessageBox.warning(self, "Invalid Input", "Please enter a name for the list.")
            return
        
        # Store values
        self.min_target = min_val
        self.max_target = max_val
        self.target_fine_weight = (min_val + max_val) / 2  # Use midpoint for algorithms
        self.list_name = self.list_name_edit.text().strip()
        self.optimization_type = "min_bars" if self.min_bars_radio.isChecked() else "max_bars"
        
        super().accept()


# Example usage (if run directly)
if __name__ == '__main__':
    import sys
    from PyQt5.QtWidgets import QApplication
    # Mock DB Manager for testing
    class MockDBManager:
        def get_silver_bar_lists(self): return [{'list_id': 1, 'list_identifier': 'L-20250424-001', 'creation_date': '2025-04-24 10:00:00', 'list_note': 'Test List 1'}, {'list_id': 2, 'list_identifier': 'L-20250424-002', 'creation_date': '2025-04-24 11:00:00', 'list_note': None}]
        def get_silver_bars(self, status=None, weight_query=None, estimate_voucher_no=None): # Updated mock signature
             print(f"Mock DB: get_silver_bars(status={status}, weight_query={weight_query})")
             # Simulate filtering
             bars = [{'bar_id': 101, 'estimate_voucher_no': '202504231', 'weight': 1000.0, 'purity': 99.9, 'fine_weight': 999.0, 'date_added': '2025-04-23', 'status': 'In Stock', 'list_id': None},
                     {'bar_id': 103, 'estimate_voucher_no': '202504232', 'weight': 1000.123, 'purity': 99.0, 'fine_weight': 990.12177, 'date_added': '2025-04-23', 'status': 'In Stock', 'list_id': None}]
             filtered_bars = bars
             if status:
                 filtered_bars = [b for b in filtered_bars if b['status'] == status]
             if weight_query:
                 try:
                     target = float(weight_query)
                     filtered_bars = [b for b in filtered_bars if abs(b['weight'] - target) < 0.001]
                 except ValueError: pass # Ignore invalid weight query
             return filtered_bars
        def get_bars_in_list(self, list_id): return [{'bar_id': 102, 'estimate_voucher_no': '202504241', 'weight': 500.0, 'purity': 99.5, 'fine_weight': 497.5, 'date_added': '2025-04-24', 'status': 'Assigned', 'list_id': list_id}] if list_id == 1 else []
        def get_silver_bar_list_details(self, list_id): return {'list_id': list_id, 'list_identifier': f'L-20250424-{list_id:03d}', 'creation_date': '...', 'list_note': 'Mock Note'} if list_id else None
        def create_silver_bar_list(self, note): print(f"Mock: Create list with note: {note}"); return 3 # Simulate new ID
        # Add mock methods for assign, remove, update_note, delete_list as needed for testing UI flow

    app = QApplication(sys.argv)
    db_manager = MockDBManager() # Use mock for direct run
    dialog = SilverBarDialog(db_manager)
    dialog.show()
    sys.exit(app.exec_())
