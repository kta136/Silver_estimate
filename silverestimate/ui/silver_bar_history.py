#!/usr/bin/env python
import logging

from PyQt5.QtCore import QObject, Qt, QThread, QTimer, pyqtSignal
from PyQt5.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QComboBox,
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTableView,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from silverestimate.infrastructure.settings import get_app_settings
from silverestimate.persistence.silver_bars_snapshot_repository import (
    SilverBarsSnapshotRepository,
)
from silverestimate.ui.models import (
    HistoryListBarsTableModel,
    HistorySilverBarsTableModel,
    IssuedSilverBarListsTableModel,
)


class SilverBarHistoryDialog(QDialog):
    """Dialog for viewing silver bar history and searching all bars in the database."""

    def __init__(self, db_manager, parent=None):
        super().__init__(parent)
        self.db_manager = db_manager
        self.logger = logging.getLogger(__name__)
        self.setWindowTitle("Silver Bar History")
        self.setMinimumSize(1200, 800)
        self._suppress_search = False
        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(180)
        self._search_timer.timeout.connect(self.search_bars)
        self._bars_load_request_id = 0
        self._active_load_workers: dict[QThread, QObject] = {}

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
        self.voucher_edit.textChanged.connect(self._schedule_search)
        search_row1.addWidget(self.voucher_edit)

        # Weight search
        weight_label = QLabel("Weight (g):")
        weight_label.setStyleSheet(
            "font-weight: 600; min-width: 80px; margin-left: 20px;"
        )
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
        self.weight_edit.textChanged.connect(self._schedule_search)
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
        self.status_combo.addItems(
            ["All Statuses", "In Stock", "Assigned", "Issued", "Sold"]
        )
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
        self.status_combo.currentTextChanged.connect(self._schedule_search)
        search_row2.addWidget(self.status_combo)

        # Max rows limit
        limit_label = QLabel("Max Rows:")
        limit_label.setStyleSheet(
            "font-weight: 600; min-width: 80px; margin-left: 20px;"
        )
        search_row2.addWidget(limit_label)

        self.max_rows_spin = QSpinBox()
        self.max_rows_spin.setRange(100, 50000)
        self.max_rows_spin.setSingleStep(100)
        default_limit = 2000
        try:
            default_limit = get_app_settings().value(
                "silver_bar/history_max_rows", defaultValue=2000, type=int
            )
        except Exception as exc:
            self.logger.debug(
                "Could not read persisted history max rows setting: %s", exc
            )
        self.max_rows_spin.setValue(max(100, int(default_limit or 2000)))
        self.max_rows_spin.setSuffix(" rows")
        self.max_rows_spin.setToolTip(
            "Limit maximum rows loaded in history tables to keep UI responsive."
        )
        self.max_rows_spin.valueChanged.connect(self._on_row_limit_changed)
        search_row2.addWidget(self.max_rows_spin)

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
        self.bars_model = HistorySilverBarsTableModel(self)
        self.bars_table = QTableView()
        self.bars_table.setModel(self.bars_model)
        self.bars_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.bars_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.bars_table.setAlternatingRowColors(True)
        self.bars_table.setSortingEnabled(True)
        self.bars_table.verticalHeader().setVisible(False)

        # Apply styling
        self.bars_table.setStyleSheet("""
            QTableView {
                font-size: 13px;
                gridline-color: #ddd;
                background-color: white;
                alternate-background-color: #f9f9f9;
                selection-background-color: #3daee9;
                selection-color: white;
            }
            QTableView::item {
                padding: 6px 4px;
                border-bottom: 1px solid #eee;
                color: #333;
            }
            QTableView::item:selected {
                background-color: #3daee9 !important;
                color: white !important;
            }
            QTableView::item:selected:active {
                background-color: #2980b9 !important;
                color: white !important;
            }
            QTableView::item:hover {
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

        self.bars_table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.bars_table.setColumnWidth(0, 80)
        self.bars_table.setColumnWidth(1, 260)
        self.bars_table.setColumnWidth(2, 100)
        self.bars_table.setColumnWidth(3, 100)
        self.bars_table.setColumnWidth(4, 110)
        self.bars_table.setColumnWidth(5, 110)
        self.bars_table.setColumnWidth(6, 160)
        self.bars_table.setColumnWidth(7, 160)
        self.bars_table.setColumnWidth(8, 110)
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

        self.lists_model = IssuedSilverBarListsTableModel(self)
        self.lists_table = QTableView()
        self.lists_table.setModel(self.lists_model)
        self.lists_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.lists_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.lists_table.setAlternatingRowColors(True)
        self.lists_table.setSortingEnabled(True)
        self.lists_table.verticalHeader().setVisible(False)

        # Apply styling
        self.lists_table.setStyleSheet("""
            QTableView {
                font-size: 13px;
                gridline-color: #ddd;
                background-color: white;
                alternate-background-color: #f9f9f9;
                selection-background-color: #3daee9;
                selection-color: white;
            }
            QTableView::item {
                padding: 8px 4px;
                border-bottom: 1px solid #eee;
                color: #333;
            }
            QTableView::item:selected {
                background-color: #3daee9 !important;
                color: white !important;
            }
            QTableView::item:selected:active {
                background-color: #2980b9 !important;
                color: white !important;
            }
            QTableView::item:hover {
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

        self.lists_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.Interactive
        )
        self.lists_table.setColumnWidth(0, 80)
        self.lists_table.setColumnWidth(1, 160)
        self.lists_table.setColumnWidth(2, 260)
        self.lists_table.setColumnWidth(3, 150)
        self.lists_table.setColumnWidth(4, 150)
        self.lists_table.setColumnWidth(5, 90)
        self.lists_table.horizontalHeader().setStretchLastSection(True)

        # Context menu for lists table
        self.lists_table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.lists_table.customContextMenuRequested.connect(
            self.show_lists_context_menu
        )

        # Selection changed handler
        self.lists_table.selectionModel().selectionChanged.connect(
            self.list_selection_changed
        )

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
        self.list_bars_model = HistoryListBarsTableModel(self)
        self.list_bars_table = QTableView()
        self.list_bars_table.setModel(self.list_bars_model)
        self.list_bars_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.list_bars_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.list_bars_table.setAlternatingRowColors(True)
        self.list_bars_table.setSortingEnabled(True)
        self.list_bars_table.verticalHeader().setVisible(False)
        self.list_bars_table.setStyleSheet(self.bars_table.styleSheet())

        self.list_bars_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.Interactive
        )
        self.list_bars_table.setColumnWidth(0, 80)
        self.list_bars_table.setColumnWidth(1, 260)
        self.list_bars_table.setColumnWidth(2, 100)
        self.list_bars_table.setColumnWidth(3, 100)
        self.list_bars_table.setColumnWidth(4, 110)
        self.list_bars_table.setColumnWidth(5, 110)
        self.list_bars_table.setColumnWidth(6, 150)
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
        self.reactivate_button.setToolTip(
            "Reactivate selected list (move back to active lists)"
        )
        self.reactivate_button.clicked.connect(self.reactivate_list)
        self.reactivate_button.setEnabled(False)
        actions_layout.addWidget(self.reactivate_button)

        layout.addLayout(actions_layout)

        return tab_widget

    def load_all_bars(self):
        """Load all silver bars with their current status and list information."""
        self._start_bars_load(
            {
                "voucher_term": "",
                "weight_text": "",
                "status_text": "All Statuses",
                "limit": self._table_result_limit(),
            }
        )

    def _start_bars_load(self, payload: dict) -> None:
        self._bars_load_request_id += 1
        request_id = self._bars_load_request_id
        db_path = getattr(self.db_manager, "temp_db_path", None)
        if not db_path:
            self._load_bars_fallback(payload, request_id)
            return

        worker = _BarsHistoryLoadWorker(db_path, payload)
        thread = QThread(self)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.data_ready.connect(
            lambda rows, req=request_id: self._on_bars_load_ready(req, rows)
        )
        worker.error.connect(
            lambda message, req=request_id: self._on_bars_load_error(req, message)
        )
        worker.finished.connect(
            lambda req=request_id, th=thread, w=worker: self._on_bars_load_finished(
                req, th, w
            )
        )
        self._active_load_workers[thread] = worker
        thread.start()

    @staticmethod
    def _table_cell_value(table, row: int, column: int, role: int = Qt.DisplayRole):
        try:
            model = table.model()
            if model is None:
                return None
            index = model.index(row, column)
            if not index.isValid():
                return None
            return model.data(index, role)
        except Exception:
            return None

    @classmethod
    def _table_cell_text(cls, table, row: int, column: int) -> str:
        value = cls._table_cell_value(table, row, column, Qt.DisplayRole)
        return "" if value is None else str(value)

    @staticmethod
    def _clear_history_table(table) -> None:
        try:
            model = table.model()
            setter = getattr(model, "set_rows", None)
            if callable(setter):
                setter([])
        except Exception as exc:
            logging.getLogger(__name__).debug(
                "Failed to clear silver bar history table rows: %s", exc
            )

    def _load_bars_fallback(self, payload: dict, request_id: int) -> None:
        try:
            rows = self.db_manager.search_silver_bar_history(
                voucher_term=str(payload.get("voucher_term") or "").strip(),
                weight_text=str(payload.get("weight_text") or "").strip(),
                status_text=str(payload.get("status_text") or "").strip(),
                limit=int(payload.get("limit", 2000) or 2000),
            )
            rows = [
                dict(row) if not isinstance(row, dict) else dict(row) for row in rows
            ]
            self._on_bars_load_ready(request_id, rows)
        except Exception as exc:
            self._on_bars_load_error(request_id, str(exc))

    def _on_bars_load_ready(self, request_id: int, rows: list[dict]) -> None:
        if request_id != self._bars_load_request_id:
            return
        self.populate_bars_table(rows)

    def _on_bars_load_error(self, request_id: int, message: str) -> None:
        if request_id != self._bars_load_request_id:
            return
        QMessageBox.critical(
            self, "Search Error", f"Failed to load silver bars: {message}"
        )

    def _on_bars_load_finished(self, request_id: int, thread: QThread, worker: QObject):
        del request_id
        self._active_load_workers.pop(thread, None)
        try:
            thread.quit()
            thread.wait(1000)
        except Exception as exc:
            self.logger.debug("Failed to stop silver bar history worker thread: %s", exc)
        try:
            worker.deleteLater()
        except Exception as exc:
            self.logger.debug(
                "Failed to schedule silver bar history worker deletion: %s", exc
            )

    def _schedule_search(self, *args, **kwargs):
        if self._suppress_search:
            return
        try:
            self._search_timer.start()
        except Exception as exc:
            self.logger.debug("Failed to start history search timer: %s", exc)
            self.search_bars()

    def _table_result_limit(self) -> int:
        try:
            return max(100, int(self.max_rows_spin.value()))
        except Exception as exc:
            self.logger.debug("Invalid history row limit value: %s", exc)
            return 2000

    def _save_row_limit_setting(self, value: int) -> None:
        try:
            get_app_settings().setValue("silver_bar/history_max_rows", int(value))
        except Exception as exc:
            self.logger.debug("Could not persist history max rows setting: %s", exc)

    def _on_row_limit_changed(self, value: int) -> None:
        self._save_row_limit_setting(value)
        self._schedule_search()

    def populate_bars_table(self, bars_data):
        """Populate the bars table with data."""
        normalized_rows = [
            dict(bar) if not isinstance(bar, dict) else dict(bar)
            for bar in list(bars_data or [])
        ]
        self.bars_model.set_rows(normalized_rows)
        self.bars_summary.setText(
            f"Loaded Bars: {len(normalized_rows)} (max {self._table_result_limit()})"
        )
        try:
            self.bars_table.viewport().update()
        except Exception as exc:
            self.logger.debug("Failed to refresh bars table viewport: %s", exc)

    def load_issued_lists(self):
        """Load all issued lists."""
        try:
            # Get all issued lists
            lists = self.db_manager.get_silver_bar_lists(include_issued=True)
            issued_lists = [lst for lst in lists if lst["issued_date"] is not None]
            list_ids = [int(lst["list_id"]) for lst in issued_lists if lst["list_id"]]
            counts_by_list = self.db_manager.count_silver_bars_by_list_ids(list_ids)
            rows = []
            for lst in issued_lists:
                row = dict(lst) if not isinstance(lst, dict) else dict(lst)
                try:
                    row["bar_count"] = counts_by_list.get(int(row["list_id"]), 0)
                except (TypeError, ValueError, KeyError):
                    row["bar_count"] = 0
                rows.append(row)
            self.lists_model.set_rows(rows)
            try:
                self.lists_table.viewport().update()
            except Exception as exc:
                self.logger.debug("Failed to refresh issued-lists viewport: %s", exc)

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load issued lists: {e}")

    def search_bars(self):
        """Search bars based on current filter criteria."""
        self._start_bars_load(
            {
                "voucher_term": self.voucher_edit.text().strip(),
                "weight_text": self.weight_edit.text().strip(),
                "status_text": self.status_combo.currentText(),
                "limit": self._table_result_limit(),
            }
        )

    def clear_filters(self):
        """Clear all search filters."""
        self._suppress_search = True
        try:
            self._search_timer.stop()
        except Exception as exc:
            self.logger.debug("Failed to stop history search timer: %s", exc)
        for widget in (self.voucher_edit, self.weight_edit, self.status_combo):
            widget.blockSignals(True)
        self.voucher_edit.clear()
        self.weight_edit.clear()
        self.status_combo.setCurrentIndex(0)
        for widget in (self.voucher_edit, self.weight_edit, self.status_combo):
            widget.blockSignals(False)
        self._suppress_search = False
        self.load_all_bars()

    def list_selection_changed(self):
        """Handle selection change in issued lists table."""
        selected_rows = self.lists_table.selectionModel().selectedRows()

        if selected_rows:
            self.reactivate_button.setEnabled(True)
            row = selected_rows[0].row()
            list_id = int(self._table_cell_text(self.lists_table, row, 0))
            self.load_list_bars(list_id)
        else:
            self.reactivate_button.setEnabled(False)
            self._clear_history_table(self.list_bars_table)

    def load_list_bars(self, list_id):
        """Load bars for the selected list."""
        try:
            bars = self.db_manager.get_bars_in_list(
                list_id, limit=self._table_result_limit()
            )
            normalized_rows = [
                dict(bar) if not isinstance(bar, dict) else dict(bar)
                for bar in list(bars or [])
            ]
            self.list_bars_model.set_rows(normalized_rows)
            try:
                self.list_bars_table.viewport().update()
            except Exception as exc:
                self.logger.debug("Failed to refresh list-bars viewport: %s", exc)

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load list bars: {e}")

    def reactivate_list(self):
        """Reactivate the selected issued list."""
        selected_rows = self.lists_table.selectionModel().selectedRows()
        if not selected_rows:
            return

        row = selected_rows[0].row()
        list_id = int(self._table_cell_text(self.lists_table, row, 0))
        list_identifier = self._table_cell_text(self.lists_table, row, 1)

        reply = QMessageBox.question(
            self,
            "Reactivate List",
            f"Are you sure you want to reactivate list '{list_identifier}'?\n\n"
            f"This will:\n"
            f"• Move the list back to active lists\n"
            f"• Set all bars in the list back to 'Assigned' status\n"
            f"• Remove the issued date",
            QMessageBox.Yes | QMessageBox.Cancel,
            QMessageBox.Cancel,
        )

        if reply == QMessageBox.Yes:
            try:
                success = self.db_manager.reactivate_silver_bar_list(list_id)
                if not success:
                    raise RuntimeError("Failed to reactivate the selected list.")

                QMessageBox.information(
                    self, "Success", f"List '{list_identifier}' has been reactivated."
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

        except Exception as exc:
            self.logger.warning(
                "Failed to show bars context menu: %s", exc, exc_info=True
            )

    def show_lists_context_menu(self, pos):
        """Show context menu for lists table."""
        try:
            menu = QMenu(self)
            reactivate_action = menu.addAction("Reactivate List")
            refresh_action = menu.addAction("Refresh")
            copy_action = menu.addAction("Copy Selected Rows")

            # Enable reactivate only if a row is selected
            reactivate_action.setEnabled(
                bool(self.lists_table.selectionModel().selectedRows())
            )

            action = menu.exec_(self.lists_table.viewport().mapToGlobal(pos))

            if action == reactivate_action:
                self.reactivate_list()
            elif action == refresh_action:
                self.load_issued_lists()
            elif action == copy_action:
                self.copy_selected_rows(self.lists_table)

        except Exception as exc:
            self.logger.warning(
                "Failed to show lists context menu: %s", exc, exc_info=True
            )

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
                for c in range(table.model().columnCount()):
                    values.append(self._table_cell_text(table, r, c))
                rows.append("\t".join(values))

            text = "\n".join(rows)
            QApplication.clipboard().setText(text)

        except Exception as exc:
            self.logger.warning("Failed to copy selected rows: %s", exc, exc_info=True)

    def _cancel_active_loads(self, timeout_ms: int = 3000) -> None:
        self._bars_load_request_id += 1
        active = list(self._active_load_workers.items())
        self._active_load_workers.clear()
        for thread, worker in active:
            try:
                worker.deleteLater()
            except Exception as exc:
                self.logger.debug(
                    "Failed to schedule silver bar history worker deletion during cancel: %s",
                    exc,
                )
            try:
                if thread.isRunning():
                    thread.quit()
                    if not thread.wait(timeout_ms):
                        thread.terminate()
                        thread.wait(1000)
            except Exception as exc:
                self.logger.debug(
                    "Failed to stop silver bar history worker thread during cancel: %s",
                    exc,
                )

    def reject(self):
        self._cancel_active_loads()
        super().reject()

    def closeEvent(self, event):
        self._cancel_active_loads()
        super().closeEvent(event)


class _BarsHistoryLoadWorker(QObject):
    data_ready = pyqtSignal(list)
    error = pyqtSignal(str)
    finished = pyqtSignal()

    def __init__(self, db_path: str, payload: dict):
        super().__init__()
        self.db_path = db_path
        self.payload = payload or {}

    def run(self):
        try:
            snapshot = SilverBarsSnapshotRepository(self.db_path)
            rows = snapshot.search_history_bars(
                voucher_term=str(self.payload.get("voucher_term") or "").strip(),
                weight_text=str(self.payload.get("weight_text") or "").strip(),
                status_text=str(self.payload.get("status_text") or "").strip(),
                limit=int(self.payload.get("limit", 2000) or 2000),
            )
            self.data_ready.emit(rows)
        except Exception as exc:
            self.error.emit(str(exc))
        finally:
            self.finished.emit()


# Example usage (if run directly)
if __name__ == "__main__":
    import sys

    # Mock DB Manager for testing
    class MockDBManager:
        def get_silver_bar_lists(self, include_issued=True):
            return []

        def get_bars_in_list(self, list_id, limit=None, offset=0):
            return []

    app = QApplication(sys.argv)
    db_manager = MockDBManager()
    dialog = SilverBarHistoryDialog(db_manager)
    dialog.show()
    sys.exit(app.exec_())
