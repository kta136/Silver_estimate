#!/usr/bin/env python
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QLineEdit, QComboBox,
    QMessageBox, QAbstractItemView, QFrame, QInputDialog, QSplitter,
    QWidget, QMenu, QShortcut, QToolButton, QStyle, QSizePolicy,
    QApplication, QCheckBox, QDoubleSpinBox, QSpinBox, QFileDialog,
    QTabWidget, QTextEdit
)
from PyQt5.QtCore import Qt, QTimer, QSettings
from PyQt5.QtGui import QColor, QKeySequence
import traceback
from datetime import datetime, timedelta
from silverestimate.infrastructure.app_constants import SETTINGS_ORG, SETTINGS_APP

class SilverBarHistoryDialog(QDialog):
    """Dialog for viewing silver bar history and searching all bars in the database."""

    def __init__(self, db_manager, parent=None):
        super().__init__(parent)
        self.db_manager = db_manager
        self.setWindowTitle("Silver Bar History")
        self.setMinimumSize(1200, 800)
        
        self.init_ui()
        self.load_all_bars()
        self.load_issued_lists()

    def init_ui(self):
        """Set up the user interface."""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(12)

        # Title
        title = QLabel("Silver Bar History & Search")
        title.setStyleSheet("""
            font-weight: bold;
            font-size: 18px;
            color: #2c3e50;
            margin-bottom: 10px;
        """)
        main_layout.addWidget(title)

        # Create tab widget
        self.tab_widget = QTabWidget()
        self.tab_widget.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #ccc;
                border-radius: 4px;
            }
            QTabBar::tab {
                padding: 8px 16px;
                margin-right: 2px;
                background-color: #f8f9fa;
                border: 1px solid #ddd;
                border-bottom: none;
                border-radius: 4px 4px 0 0;
            }
            QTabBar::tab:selected {
                background-color: white;
                font-weight: 600;
            }
            QTabBar::tab:hover {
                background-color: #e9ecef;
            }
        """)

        # Tab 1: All Silver Bars
        self.bars_tab = self.create_bars_tab()
        self.tab_widget.addTab(self.bars_tab, "All Silver Bars")

        # Tab 2: Issued Lists
        self.lists_tab = self.create_lists_tab()
        self.tab_widget.addTab(self.lists_tab, "Issued Lists")

        main_layout.addWidget(self.tab_widget)

        # Close button
        close_layout = QHBoxLayout()
        close_layout.addStretch()
        
        close_button = QPushButton("Close")
        close_button.setStyleSheet("""
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
            }
        """)
        close_button.clicked.connect(self.accept)
        close_layout.addWidget(close_button)
        
        main_layout.addLayout(close_layout)

    def create_bars_tab(self):
        """Create the all bars search tab."""
        tab_widget = QWidget()
        layout = QVBoxLayout(tab_widget)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Search filters
        filters_group = QWidget()
        filters_layout = QVBoxLayout(filters_group)
        filters_layout.setSpacing(8)

        # Search row 1
        search_row1 = QHBoxLayout()
        search_row1.setSpacing(12)

        # Voucher search
        voucher_label = QLabel("Voucher/Note:")
        voucher_label.setStyleSheet("font-weight: 600; min-width: 100px;")
        search_row1.addWidget(voucher_label)
        
        self.voucher_edit = QLineEdit()
        self.voucher_edit.setPlaceholderText("Search voucher or note")
        self.voucher_edit.setStyleSheet("""
            QLineEdit {
                padding: 6px;
                font-size: 13px;
                border: 1px solid #ccc;
                border-radius: 3px;
                min-width: 200px;
            }
            QLineEdit:focus {
                border-color: #007acc;
            }
        """)
        self.voucher_edit.textChanged.connect(self.search_bars)
        search_row1.addWidget(self.voucher_edit)

        # Weight search
        weight_label = QLabel("Weight (g):")
        weight_label.setStyleSheet("font-weight: 600; min-width: 80px; margin-left: 20px;")
        search_row1.addWidget(weight_label)
        
        self.weight_edit = QLineEdit()
        self.weight_edit.setPlaceholderText("Enter weight")
        self.weight_edit.setStyleSheet("""
            QLineEdit {
                padding: 6px;
                font-size: 13px;
                border: 1px solid #ccc;
                border-radius: 3px;
                min-width: 120px;
            }
            QLineEdit:focus {
                border-color: #007acc;
            }
        """)
        self.weight_edit.textChanged.connect(self.search_bars)
        search_row1.addWidget(self.weight_edit)

        search_row1.addStretch()
        filters_layout.addLayout(search_row1)

        # Search row 2
        search_row2 = QHBoxLayout()
        search_row2.setSpacing(12)

        # Status filter
        status_label = QLabel("Status:")
        status_label.setStyleSheet("font-weight: 600; min-width: 100px;")
        search_row2.addWidget(status_label)
        
        self.status_combo = QComboBox()
        self.status_combo.addItems(["All Statuses", "In Stock", "Assigned", "Issued", "Sold"])
        self.status_combo.setStyleSheet("""
            QComboBox {
                padding: 6px 8px;
                font-size: 13px;
                border: 1px solid #ccc;
                border-radius: 3px;
                min-width: 120px;
            }
            QComboBox:focus {
                border-color: #007acc;
            }
        """)
        self.status_combo.currentTextChanged.connect(self.search_bars)
        search_row2.addWidget(self.status_combo)

        search_row2.addStretch()

        # Clear filters button
        clear_button = QPushButton("Clear Filters")
        clear_button.setStyleSheet("""
            QPushButton {
                padding: 6px 12px;
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
        clear_button.clicked.connect(self.clear_filters)
        search_row2.addWidget(clear_button)

        filters_layout.addLayout(search_row2)
        layout.addWidget(filters_group)

        # Results table
        self.bars_table = QTableWidget()
        self.bars_table.setColumnCount(9)
        self.bars_table.setHorizontalHeaderLabels([
            "Bar ID", "Voucher/Note", "Weight (g)", "Purity (%)", 
            "Fine Wt (g)", "Status", "List", "Date Added", "List Status"
        ])
        self.bars_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.bars_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.bars_table.setAlternatingRowColors(True)
        self.bars_table.setSortingEnabled(True)
        self.bars_table.verticalHeader().setVisible(False)
        
        # Apply styling
        self.bars_table.setStyleSheet("""
            QTableWidget {
                font-size: 13px;
                gridline-color: #ddd;
                background-color: white;
                alternate-background-color: #f9f9f9;
                selection-background-color: #3daee9;
                selection-color: white;
            }
            QTableWidget::item {
                padding: 6px 4px;
                border-bottom: 1px solid #eee;
                color: #333;
            }
            QTableWidget::item:selected {
                background-color: #3daee9 !important;
                color: white !important;
            }
            QTableWidget::item:selected:active {
                background-color: #2980b9 !important;
                color: white !important;
            }
            QTableWidget::item:hover {
                background-color: #e8f4fd;
            }
            QHeaderView::section {
                background-color: #f0f0f0;
                padding: 8px 4px;
                border: 1px solid #ddd;
                font-weight: 600;
                font-size: 12px;
            }
        """)
        
        self.bars_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.bars_table.horizontalHeader().setStretchLastSection(True)
        
        # Context menu for bars table
        self.bars_table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.bars_table.customContextMenuRequested.connect(self.show_bars_context_menu)
        
        layout.addWidget(self.bars_table)

        # Summary label
        self.bars_summary = QLabel("Total Bars: 0")
        self.bars_summary.setStyleSheet("""
            font-weight: 600;
            background-color: #f8f9fa;
            padding: 8px;
            border: 1px solid #dee2e6;
            border-radius: 4px;
        """)
        layout.addWidget(self.bars_summary)

        return tab_widget

    def create_lists_tab(self):
        """Create the issued lists tab."""
        tab_widget = QWidget()
        layout = QVBoxLayout(tab_widget)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Issued lists table
        lists_header = QLabel("Issued Lists")
        lists_header.setStyleSheet("""
            font-weight: bold;
            font-size: 16px;
            color: #2c3e50;
            margin-bottom: 8px;
        """)
        layout.addWidget(lists_header)

        self.lists_table = QTableWidget()
        self.lists_table.setColumnCount(6)
        self.lists_table.setHorizontalHeaderLabels([
            "List ID", "Identifier", "Note", "Created", "Issued", "Bar Count"
        ])
        self.lists_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.lists_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.lists_table.setAlternatingRowColors(True)
        self.lists_table.setSortingEnabled(True)
        self.lists_table.verticalHeader().setVisible(False)
        
        # Apply styling
        self.lists_table.setStyleSheet("""
            QTableWidget {
                font-size: 13px;
                gridline-color: #ddd;
                background-color: white;
                alternate-background-color: #f9f9f9;
                selection-background-color: #3daee9;
                selection-color: white;
            }
            QTableWidget::item {
                padding: 8px 4px;
                border-bottom: 1px solid #eee;
                color: #333;
            }
            QTableWidget::item:selected {
                background-color: #3daee9 !important;
                color: white !important;
            }
            QTableWidget::item:selected:active {
                background-color: #2980b9 !important;
                color: white !important;
            }
            QTableWidget::item:hover {
                background-color: #e8f4fd;
            }
            QHeaderView::section {
                background-color: #f0f0f0;
                padding: 8px 4px;
                border: 1px solid #ddd;
                font-weight: 600;
                font-size: 12px;
            }
        """)
        
        self.lists_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.lists_table.horizontalHeader().setStretchLastSection(True)
        
        # Context menu for lists table
        self.lists_table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.lists_table.customContextMenuRequested.connect(self.show_lists_context_menu)
        
        # Selection changed handler
        self.lists_table.selectionModel().selectionChanged.connect(self.list_selection_changed)
        
        layout.addWidget(self.lists_table)

        # List details section
        details_header = QLabel("List Details")
        details_header.setStyleSheet("""
            font-weight: bold;
            font-size: 14px;
            color: #2c3e50;
            margin-top: 16px;
            margin-bottom: 8px;
        """)
        layout.addWidget(details_header)

        # Bars in selected list
        self.list_bars_table = QTableWidget()
        self.list_bars_table.setColumnCount(7)
        self.list_bars_table.setHorizontalHeaderLabels([
            "Bar ID", "Voucher/Note", "Weight (g)", "Purity (%)", 
            "Fine Wt (g)", "Status", "Date Added"
        ])
        self.list_bars_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.list_bars_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.list_bars_table.setAlternatingRowColors(True)
        self.list_bars_table.setSortingEnabled(True)
        self.list_bars_table.verticalHeader().setVisible(False)
        self.list_bars_table.setStyleSheet(self.bars_table.styleSheet())
        
        self.list_bars_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.list_bars_table.horizontalHeader().setStretchLastSection(True)
        
        layout.addWidget(self.list_bars_table)

        # Action buttons for lists
        actions_layout = QHBoxLayout()
        actions_layout.addStretch()
        
        self.reactivate_button = QPushButton("Reactivate List")
        self.reactivate_button.setStyleSheet("""
            QPushButton {
                padding: 8px 16px;
                font-size: 13px;
                font-weight: 600;
                border: 1px solid #28a745;
                background-color: #28a745;
                color: white;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #218838;
            }
            QPushButton:disabled {
                background-color: #ccc;
                border-color: #ccc;
                color: #999;
            }
        """)
        self.reactivate_button.setToolTip("Reactivate selected list (move back to active lists)")
        self.reactivate_button.clicked.connect(self.reactivate_list)
        self.reactivate_button.setEnabled(False)
        actions_layout.addWidget(self.reactivate_button)
        
        layout.addLayout(actions_layout)

        return tab_widget

    def load_all_bars(self):
        """Load all silver bars with their current status and list information."""
        try:
            QApplication.setOverrideCursor(Qt.WaitCursor)
            
            # Get all bars with list information
            query = """
            SELECT 
                sb.bar_id, sb.estimate_voucher_no, sb.weight, sb.purity, sb.fine_weight,
                sb.status, sb.date_added, sb.list_id,
                sbl.list_identifier, sbl.issued_date,
                e.note as estimate_note
            FROM silver_bars sb
            LEFT JOIN silver_bar_lists sbl ON sb.list_id = sbl.list_id
            LEFT JOIN estimates e ON sb.estimate_voucher_no = e.voucher_no
            ORDER BY sb.date_added DESC
            """
            
            self.db_manager.cursor.execute(query)
            results = self.db_manager.cursor.fetchall()
            
            self.populate_bars_table(results)
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load silver bars: {e}")
        finally:
            QApplication.restoreOverrideCursor()

    def populate_bars_table(self, bars_data):
        """Populate the bars table with data."""
        self.bars_table.setRowCount(0)
        
        if not bars_data:
            self.bars_summary.setText("Total Bars: 0")
            return
        
        self.bars_table.setRowCount(len(bars_data))
        
        for row_idx, bar in enumerate(bars_data):
            # Get estimate note for display
            voucher_display = bar['estimate_voucher_no'] or 'N/A'
            if bar['estimate_note']:
                voucher_display += f" ({bar['estimate_note']})"
            
            # Determine list status
            list_display = ""
            list_status = ""
            if bar['list_id']:
                list_display = bar['list_identifier'] or f"List {bar['list_id']}"
                list_status = "Issued" if bar['issued_date'] else "Active"
            else:
                list_display = "None"
                list_status = "N/A"
            
            # Create table items
            items = [
                QTableWidgetItem(str(bar['bar_id'])),
                QTableWidgetItem(voucher_display),
                QTableWidgetItem(f"{bar['weight']:.1f}" if bar['weight'] else "0.0"),
                QTableWidgetItem(f"{bar['purity']:.1f}" if bar['purity'] else "0.0"),
                QTableWidgetItem(f"{bar['fine_weight']:.1f}" if bar['fine_weight'] else "0.0"),
                QTableWidgetItem(bar['status'] or 'Unknown'),
                QTableWidgetItem(list_display),
                QTableWidgetItem(bar['date_added'] or ''),
                QTableWidgetItem(list_status)
            ]
            
            # Set alignment for numeric columns
            for i in [2, 3, 4]:  # weight, purity, fine_weight
                items[i].setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            
            # Color code by status - set background instead of foreground for better selection visibility
            status_color = None
            status_text = bar['status'] or 'Unknown'
            if status_text == 'In Stock':
                status_color = QColor('#f0f9f0')  # Very light green background
            elif status_text == 'Assigned':
                status_color = QColor('#f0f4f8')  # Very light blue background
            elif status_text == 'Issued':
                status_color = QColor('#fdf2f2')  # Very light red background
            elif status_text == 'Sold':
                status_color = QColor('#f7f0ff')  # Very light purple background
            
            if status_color:
                for item in items:
                    item.setBackground(status_color)
            
            # Set items in table
            for col_idx, item in enumerate(items):
                self.bars_table.setItem(row_idx, col_idx, item)
        
        self.bars_summary.setText(f"Total Bars: {len(bars_data)}")

    def load_issued_lists(self):
        """Load all issued lists."""
        try:
            # Get all issued lists
            lists = self.db_manager.get_silver_bar_lists(include_issued=True)
            issued_lists = [lst for lst in lists if lst['issued_date'] is not None]
            
            self.lists_table.setRowCount(len(issued_lists))
            
            for row_idx, lst in enumerate(issued_lists):
                # Get bar count for this list
                self.db_manager.cursor.execute(
                    "SELECT COUNT(*) as count FROM silver_bars WHERE list_id = ?", 
                    (lst['list_id'],)
                )
                bar_count = self.db_manager.cursor.fetchone()['count']
                
                items = [
                    QTableWidgetItem(str(lst['list_id'])),
                    QTableWidgetItem(lst['list_identifier'] or ''),
                    QTableWidgetItem(lst['list_note'] or ''),
                    QTableWidgetItem(lst['creation_date'] or ''),
                    QTableWidgetItem(lst['issued_date'] or ''),
                    QTableWidgetItem(str(bar_count))
                ]
                
                # Set alignment for numeric columns
                items[0].setTextAlignment(Qt.AlignCenter)
                items[5].setTextAlignment(Qt.AlignCenter)
                
                for col_idx, item in enumerate(items):
                    self.lists_table.setItem(row_idx, col_idx, item)
                    
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load issued lists: {e}")

    def search_bars(self):
        """Search bars based on current filter criteria."""
        try:
            QApplication.setOverrideCursor(Qt.WaitCursor)
            
            conditions = []
            params = []
            
            # Voucher/Note filter
            if self.voucher_edit.text().strip():
                conditions.append("(sb.estimate_voucher_no LIKE ? OR e.note LIKE ?)")
                search_term = f"%{self.voucher_edit.text().strip()}%"
                params.extend([search_term, search_term])
            
            # Weight filter
            if self.weight_edit.text().strip():
                try:
                    weight_value = float(self.weight_edit.text().strip())
                    conditions.append("sb.weight = ?")
                    params.append(weight_value)
                except ValueError:
                    # If invalid number, ignore the filter
                    pass
            
            # Status filter
            if self.status_combo.currentText() != "All Statuses":
                conditions.append("sb.status = ?")
                params.append(self.status_combo.currentText())
            
            # Build query
            base_query = """
            SELECT 
                sb.bar_id, sb.estimate_voucher_no, sb.weight, sb.purity, sb.fine_weight,
                sb.status, sb.date_added, sb.list_id,
                sbl.list_identifier, sbl.issued_date,
                e.note as estimate_note
            FROM silver_bars sb
            LEFT JOIN silver_bar_lists sbl ON sb.list_id = sbl.list_id
            LEFT JOIN estimates e ON sb.estimate_voucher_no = e.voucher_no
            """
            
            if conditions:
                query = base_query + " WHERE " + " AND ".join(conditions)
            else:
                query = base_query
            
            query += " ORDER BY sb.date_added DESC"
            
            self.db_manager.cursor.execute(query, params)
            results = self.db_manager.cursor.fetchall()
            
            self.populate_bars_table(results)
            
        except Exception as e:
            QMessageBox.critical(self, "Search Error", f"Failed to search bars: {e}")
        finally:
            QApplication.restoreOverrideCursor()

    def clear_filters(self):
        """Clear all search filters."""
        self.voucher_edit.clear()
        self.weight_edit.clear()
        self.status_combo.setCurrentIndex(0)
        self.load_all_bars()

    def list_selection_changed(self):
        """Handle selection change in issued lists table."""
        selected_rows = self.lists_table.selectionModel().selectedRows()
        
        if selected_rows:
            self.reactivate_button.setEnabled(True)
            row = selected_rows[0].row()
            list_id = int(self.lists_table.item(row, 0).text())
            self.load_list_bars(list_id)
        else:
            self.reactivate_button.setEnabled(False)
            self.list_bars_table.setRowCount(0)

    def load_list_bars(self, list_id):
        """Load bars for the selected list."""
        try:
            bars = self.db_manager.get_bars_in_list(list_id)
            self.list_bars_table.setRowCount(len(bars))
            
            for row_idx, bar in enumerate(bars):
                # Get estimate note
                voucher_display = bar['estimate_voucher_no'] or 'N/A'
                try:
                    self.db_manager.cursor.execute(
                        "SELECT note FROM estimates WHERE voucher_no = ?", 
                        (bar['estimate_voucher_no'],)
                    )
                    result = self.db_manager.cursor.fetchone()
                    if result and result['note']:
                        voucher_display += f" ({result['note']})"
                except Exception:
                    pass
                
                items = [
                    QTableWidgetItem(str(bar['bar_id'])),
                    QTableWidgetItem(voucher_display),
                    QTableWidgetItem(f"{bar['weight']:.1f}" if bar['weight'] else "0.0"),
                    QTableWidgetItem(f"{bar['purity']:.1f}" if bar['purity'] else "0.0"),
                    QTableWidgetItem(f"{bar['fine_weight']:.1f}" if bar['fine_weight'] else "0.0"),
                    QTableWidgetItem(bar['status'] or 'Unknown'),
                    QTableWidgetItem(bar['date_added'] or '')
                ]
                
                # Set alignment for numeric columns
                for i in [2, 3, 4]:  # weight, purity, fine_weight
                    items[i].setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                
                for col_idx, item in enumerate(items):
                    self.list_bars_table.setItem(row_idx, col_idx, item)
                    
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load list bars: {e}")

    def reactivate_list(self):
        """Reactivate the selected issued list."""
        selected_rows = self.lists_table.selectionModel().selectedRows()
        if not selected_rows:
            return
        
        row = selected_rows[0].row()
        list_id = int(self.lists_table.item(row, 0).text())
        list_identifier = self.lists_table.item(row, 1).text()
        
        reply = QMessageBox.question(
            self, "Reactivate List",
            f"Are you sure you want to reactivate list '{list_identifier}'?\n\n"
            f"This will:\n"
            f"• Move the list back to active lists\n"
            f"• Set all bars in the list back to 'Assigned' status\n"
            f"• Remove the issued date",
            QMessageBox.Yes | QMessageBox.Cancel, QMessageBox.Cancel
        )
        
        if reply == QMessageBox.Yes:
            try:
                # Remove issued date
                self.db_manager.cursor.execute(
                    "UPDATE silver_bar_lists SET issued_date = NULL WHERE list_id = ?", 
                    (list_id,)
                )
                
                # Set all bars back to 'Assigned' status
                self.db_manager.cursor.execute(
                    "UPDATE silver_bars SET status = 'Assigned' WHERE list_id = ?", 
                    (list_id,)
                )
                
                self.db_manager.conn.commit()
                
                QMessageBox.information(
                    self, "Success", 
                    f"List '{list_identifier}' has been reactivated."
                )
                
                # Refresh the interface
                self.load_issued_lists()
                self.load_all_bars()
                
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to reactivate list: {e}")

    def show_bars_context_menu(self, pos):
        """Show context menu for bars table."""
        try:
            menu = QMenu(self)
            refresh_action = menu.addAction("Refresh")
            copy_action = menu.addAction("Copy Selected Rows")
            
            action = menu.exec_(self.bars_table.viewport().mapToGlobal(pos))
            
            if action == refresh_action:
                self.load_all_bars()
            elif action == copy_action:
                self.copy_selected_rows(self.bars_table)
                
        except Exception:
            pass

    def show_lists_context_menu(self, pos):
        """Show context menu for lists table."""
        try:
            menu = QMenu(self)
            reactivate_action = menu.addAction("Reactivate List")
            refresh_action = menu.addAction("Refresh")
            copy_action = menu.addAction("Copy Selected Rows")
            
            # Enable reactivate only if a row is selected
            reactivate_action.setEnabled(bool(self.lists_table.selectionModel().selectedRows()))
            
            action = menu.exec_(self.lists_table.viewport().mapToGlobal(pos))
            
            if action == reactivate_action:
                self.reactivate_list()
            elif action == refresh_action:
                self.load_issued_lists()
            elif action == copy_action:
                self.copy_selected_rows(self.lists_table)
                
        except Exception:
            pass

    def copy_selected_rows(self, table):
        """Copy selected rows to clipboard."""
        try:
            selected = table.selectionModel().selectedRows()
            if not selected:
                return
            
            rows = []
            for idx in selected:
                r = idx.row()
                values = []
                for c in range(table.columnCount()):
                    item = table.item(r, c)
                    values.append(item.text() if item else '')
                rows.append('\t'.join(values))
            
            text = '\n'.join(rows)
            QApplication.clipboard().setText(text)
            
        except Exception:
            pass


# Example usage (if run directly)
if __name__ == '__main__':
    import sys
    from PyQt5.QtWidgets import QApplication
    
    # Mock DB Manager for testing
    class MockDBManager:
        def get_silver_bar_lists(self, include_issued=True):
            return []
        
        def get_bars_in_list(self, list_id):
            return []
    
    app = QApplication(sys.argv)
    db_manager = MockDBManager()
    dialog = SilverBarHistoryDialog(db_manager)
    dialog.show()
    sys.exit(app.exec_())