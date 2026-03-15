#!/usr/bin/env python
import logging
import sqlite3
import time

from PyQt5.QtCore import QLocale, QModelIndex, QObject, Qt, QThread, QTimer, pyqtSignal
from PyQt5.QtGui import QDoubleValidator
from PyQt5.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from silverestimate.domain.item_validation import ItemValidationError, validate_item
from silverestimate.persistence.items_repository import fetch_item_catalog_rows
from silverestimate.ui.models import ItemMasterTableModel
from silverestimate.ui.shared_screen_theme import build_management_screen_stylesheet


class _ItemMasterLoadWorker(QObject):
    data_ready = pyqtSignal(int, list)
    error = pyqtSignal(int, str)
    finished = pyqtSignal(int)

    def __init__(self, request_id: int, db_path: str, search_term: str) -> None:
        super().__init__()
        self.request_id = request_id
        self.db_path = db_path
        self.search_term = search_term

    def run(self) -> None:
        conn = None
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            rows = fetch_item_catalog_rows(cursor, self.search_term)
            self.data_ready.emit(
                self.request_id,
                [dict(row) for row in rows],
            )
        except Exception as exc:
            self.error.emit(self.request_id, str(exc))
        finally:
            if conn is not None:
                try:
                    conn.close()
                except Exception:
                    pass
            self.finished.emit(self.request_id)


class ItemMasterWidget(QWidget):
    """Widget for managing silver item catalog."""

    def __init__(self, db_manager, main_window=None):  # Accept optional main_window
        super().__init__()
        self.db_manager = db_manager
        self.main_window = main_window  # Store reference
        self.logger = logging.getLogger(__name__)
        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(180)
        self._search_timer.timeout.connect(self.search_items)
        self._load_request_id = 0
        self._active_load_workers = {}
        self._load_request_meta = {}
        self.init_ui()
        self.load_items()

    # --- Helper to show status messages ---
    def show_status(self, message, timeout=3000):
        if self.main_window:
            self.main_window.show_status_message(message, timeout)
        else:
            logging.getLogger(__name__).info(f"Status: {message}")

    # ------------------------------------

    def init_ui(self):
        """Initialize the user interface."""
        self.setObjectName("ItemMasterWidget")
        self.setStyleSheet(
            build_management_screen_stylesheet(
                root_selector="QWidget#ItemMasterWidget",
                card_names=["ItemMasterFormPanel"],
                title_label="ItemMasterTitleLabel",
                subtitle_label="ItemMasterSubtitleLabel",
                field_label="ItemMasterFieldLabel",
                primary_button="ItemMasterPrimaryButton",
                secondary_button="ItemMasterSecondaryButton",
                danger_button="ItemMasterDangerButton",
                input_selectors=["QLineEdit", "QComboBox"],
                include_table=True,
                extra_rules="""
                QLabel#ItemMasterFormHeading {
                    font-size: 11pt;
                    font-weight: 700;
                    color: #0f172a;
                    padding-bottom: 2px;
                }
                QTableView {
                    border-radius: 10px;
                }
                QTableView::item {
                    padding: 4px 8px;
                }
                QTableView::item:selected {
                    border-radius: 0px;
                }
                """,
            )
        )

        outer = QVBoxLayout(self)
        outer.setContentsMargins(12, 12, 12, 12)
        outer.setSpacing(10)

        # ── Page header ─────────────────────────────────────────
        header_row = QHBoxLayout()
        header_row.setSpacing(10)
        header_label = QLabel("Item Master")
        header_label.setObjectName("ItemMasterTitleLabel")
        header_row.addWidget(header_label)
        subtitle_label = QLabel(
            "Maintain catalog codes, purity defaults, and wage settings."
        )
        subtitle_label.setObjectName("ItemMasterSubtitleLabel")
        subtitle_label.setAlignment(Qt.AlignVCenter)
        header_row.addWidget(subtitle_label)
        header_row.addStretch()
        outer.addLayout(header_row)

        # ── Horizontal split ────────────────────────────────────
        split = QHBoxLayout()
        split.setSpacing(12)

        # ── LEFT: Form panel ────────────────────────────────────
        self._form_panel = QFrame(self)
        self._form_panel.setObjectName("ItemMasterFormPanel")
        self._form_panel.setFixedWidth(280)
        form_vbox = QVBoxLayout(self._form_panel)
        form_vbox.setContentsMargins(16, 16, 16, 16)
        form_vbox.setSpacing(10)

        self._form_heading = QLabel("New Item")
        self._form_heading.setObjectName("ItemMasterFormHeading")
        form_vbox.addWidget(self._form_heading)

        # Code
        code_lbl = QLabel("Code")
        code_lbl.setObjectName("ItemMasterFieldLabel")
        self.code_edit = QLineEdit()
        self.code_edit.setPlaceholderText("e.g. CH001")
        self.code_edit.setToolTip(
            "Unique code for the item (e.g., CH001). Cannot be changed after adding."
        )
        form_vbox.addWidget(code_lbl)
        form_vbox.addWidget(self.code_edit)

        # Name
        name_lbl = QLabel("Name")
        name_lbl.setObjectName("ItemMasterFieldLabel")
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("Item description")
        self.name_edit.setToolTip("Descriptive name of the item.")
        form_vbox.addWidget(name_lbl)
        form_vbox.addWidget(self.name_edit)

        # Purity
        purity_lbl = QLabel("Purity (%)")
        purity_lbl.setObjectName("ItemMasterFieldLabel")
        self.purity_edit = QLineEdit()
        self.purity_edit.setPlaceholderText("0.00 – 100.00")
        self.purity_edit.setToolTip("Default silver purity percentage.")
        purity_validator = QDoubleValidator(0.00, 100.00, 2, self.purity_edit)
        purity_validator.setNotation(QDoubleValidator.StandardNotation)
        purity_validator.setLocale(QLocale.system())
        self.purity_edit.setValidator(purity_validator)
        form_vbox.addWidget(purity_lbl)
        form_vbox.addWidget(self.purity_edit)

        # Wage type + rate side by side
        wage_row = QHBoxLayout()
        wage_row.setSpacing(8)

        wt_col = QVBoxLayout()
        wt_col.setSpacing(4)
        wt_lbl = QLabel("Wage Type")
        wt_lbl.setObjectName("ItemMasterFieldLabel")
        self.wage_type_combo = QComboBox()
        self.wage_type_combo.addItems(["PC", "WT"])
        self.wage_type_combo.setToolTip("PC = Per Piece  |  WT = Per Weight (gram)")
        wt_col.addWidget(wt_lbl)
        wt_col.addWidget(self.wage_type_combo)
        wage_row.addLayout(wt_col)

        wr_col = QVBoxLayout()
        wr_col.setSpacing(4)
        wr_lbl = QLabel("Wage Rate")
        wr_lbl.setObjectName("ItemMasterFieldLabel")
        self.wage_rate_edit = QLineEdit()
        self.wage_rate_edit.setPlaceholderText("0.00")
        self.wage_rate_edit.setToolTip("Wage rate for the selected wage type.")
        rate_validator = QDoubleValidator(0.00, 100000.00, 2, self.wage_rate_edit)
        rate_validator.setNotation(QDoubleValidator.StandardNotation)
        rate_validator.setLocale(QLocale.system())
        self.wage_rate_edit.setValidator(rate_validator)
        wr_col.addWidget(wr_lbl)
        wr_col.addWidget(self.wage_rate_edit)
        wage_row.addLayout(wr_col, 1)

        form_vbox.addLayout(wage_row)
        form_vbox.addSpacing(4)

        # Primary action — swaps between Add and Save depending on mode
        self.add_button = QPushButton("Add Item")
        self.add_button.setObjectName("ItemMasterPrimaryButton")
        self.add_button.setToolTip("Add these details as a new item.")
        self.add_button.clicked.connect(self.add_item)
        form_vbox.addWidget(self.add_button)

        self.update_button = QPushButton("Save Changes")
        self.update_button.setObjectName("ItemMasterPrimaryButton")
        self.update_button.setToolTip("Save changes to the selected item.")
        self.update_button.clicked.connect(self.update_item)
        self.update_button.setVisible(False)
        form_vbox.addWidget(self.update_button)

        self.clear_button = QPushButton("Clear")
        self.clear_button.setObjectName("ItemMasterSecondaryButton")
        self.clear_button.setToolTip("Clear fields and deselect the current item.")
        self.clear_button.clicked.connect(self.clear_form)
        form_vbox.addWidget(self.clear_button)

        form_vbox.addStretch()

        # Separator
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("background-color: #e2e8f0; border: none; max-height: 1px;")
        form_vbox.addWidget(sep)

        self.delete_button = QPushButton("Delete Item")
        self.delete_button.setObjectName("ItemMasterDangerButton")
        self.delete_button.setToolTip("Permanently delete this item. Cannot be undone.")
        self.delete_button.clicked.connect(self.delete_item)
        self.delete_button.setEnabled(False)
        form_vbox.addWidget(self.delete_button)

        split.addWidget(self._form_panel)

        # ── RIGHT: Search + table ───────────────────────────────
        right_col = QVBoxLayout()
        right_col.setSpacing(8)

        search_row = QHBoxLayout()
        search_row.setSpacing(8)
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Search by code or name...")
        self.search_edit.setToolTip("Filter items by code or name.")
        self.search_edit.setClearButtonEnabled(True)
        self.search_edit.textChanged.connect(self._schedule_search)
        search_row.addWidget(self.search_edit)
        self._item_count_label = QLabel("")
        self._item_count_label.setObjectName("ItemMasterFieldLabel")
        self._item_count_label.setStyleSheet("color: #94a3b8; font-size: 8.5pt;")
        search_row.addWidget(self._item_count_label)
        right_col.addLayout(search_row)

        self.items_table = QTableView(self)
        self.items_model = ItemMasterTableModel(self.items_table)
        self.items_table.setModel(self.items_model)
        hdr = self.items_table.horizontalHeader()
        hdr.setSectionResizeMode(QHeaderView.Interactive)
        hdr.setSectionResizeMode(1, QHeaderView.Stretch)
        self.items_table.verticalHeader().setVisible(False)
        self.items_table.verticalHeader().setDefaultSectionSize(30)
        self.items_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.items_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.items_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.items_table.setSortingEnabled(True)
        self.items_table.setAlternatingRowColors(True)
        self.items_table.setShowGrid(False)
        self.items_table.setColumnWidth(0, 110)
        self.items_table.setColumnWidth(2, 95)
        self.items_table.setColumnWidth(3, 90)
        self.items_table.setColumnWidth(4, 110)
        selection_model = self.items_table.selectionModel()
        if selection_model:
            selection_model.selectionChanged.connect(lambda *_: self.on_item_selected())
        right_col.addWidget(self.items_table)

        split.addLayout(right_col, 1)
        outer.addLayout(split, 1)

    def load_items(self, search_term=None):
        """Load items from the database into the table."""
        normalized_term = (search_term or "").strip()
        temp_db_path = getattr(self.db_manager, "temp_db_path", None)
        if isinstance(temp_db_path, str) and temp_db_path:
            self._start_async_load(normalized_term, temp_db_path)
            return

        started_at = time.perf_counter()
        try:
            items = self._load_items_sync(normalized_term)
        except Exception as exc:
            QMessageBox.warning(self, "Load Error", str(exc))
            self.logger.warning(
                "Failed to load item master rows: %s", exc, exc_info=True
            )
            return
        self._apply_loaded_items(
            list(items or []),
            search_term=normalized_term,
            started_at=started_at,
        )

    def _schedule_search(self, *_args) -> None:
        try:
            self._search_timer.start()
        except Exception:
            self.search_items()

    def search_items(self):
        """Search for items based on the search term."""
        search_term = self.search_edit.text().strip()
        self.load_items(search_term)  # Pass search term (can be empty)

    def _load_items_sync(self, search_term: str):
        if search_term:
            return self.db_manager.search_items(search_term)
        return self.db_manager.get_all_items()

    def _next_load_request_id(self) -> int:
        self._load_request_id += 1
        return self._load_request_id

    def _start_async_load(self, search_term: str, db_path: str) -> None:
        request_id = self._next_load_request_id()
        self._load_request_meta[request_id] = (time.perf_counter(), search_term)

        worker = _ItemMasterLoadWorker(request_id, db_path, search_term)
        thread = QThread(self)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.data_ready.connect(self._handle_async_load_result)
        worker.error.connect(self._handle_async_load_error)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(
            lambda finished_request_id=request_id, th=thread: self._finish_async_load(
                finished_request_id, th
            )
        )
        self._active_load_workers[thread] = worker
        thread.start()

    def _handle_async_load_result(self, request_id: int, rows: list) -> None:
        meta = self._load_request_meta.get(request_id)
        if meta is None or request_id != self._load_request_id:
            return
        started_at, search_term = meta
        self._apply_loaded_items(
            list(rows or []),
            search_term=search_term,
            started_at=started_at,
        )

    def _handle_async_load_error(self, request_id: int, message: str) -> None:
        if request_id != self._load_request_id:
            return
        QMessageBox.warning(self, "Load Error", message)
        self.logger.warning("Failed to load item master rows: %s", message)

    def _finish_async_load(
        self,
        request_id: int,
        thread: QThread,
    ) -> None:
        self._load_request_meta.pop(request_id, None)
        self._active_load_workers.pop(thread, None)

    def _apply_loaded_items(
        self,
        items: list,
        *,
        search_term: str,
        started_at: float,
    ) -> None:
        table = self.items_table
        model = self.items_model
        sorting_enabled = table.isSortingEnabled()
        table.setUpdatesEnabled(False)
        table.blockSignals(True)
        try:
            if sorting_enabled:
                table.setSortingEnabled(False)
            model.set_rows(items)
        finally:
            if sorting_enabled:
                table.setSortingEnabled(True)
            table.blockSignals(False)
            table.setUpdatesEnabled(True)
            table.viewport().update()

        count = len(items)
        noun = "item" if count == 1 else "items"
        self._item_count_label.setText(f"{count} {noun}")
        self.show_status(f"Loaded {count} items.", 2000)
        elapsed_ms = (time.perf_counter() - started_at) * 1000.0
        self.logger.debug(
            "[perf] item_master.load_items=%.2fms search_term=%r rows=%s",
            elapsed_ms,
            search_term,
            len(items),
        )

    def _cancel_active_loads(self, timeout_ms: int = 3000) -> None:
        self._load_request_id += 1
        active = list(self._active_load_workers.items())
        self._active_load_workers.clear()
        self._load_request_meta.clear()

        for thread, worker in active:
            try:
                worker.deleteLater()
            except Exception as exc:
                self.logger.debug("Failed to queue item-master worker cleanup: %s", exc)
            try:
                if thread.isRunning():
                    thread.quit()
                    if not thread.wait(timeout_ms):
                        thread.terminate()
                        thread.wait(1000)
            except Exception as exc:
                self.logger.debug(
                    "Failed to stop item-master worker thread during cancel: %s",
                    exc,
                )

    def on_item_selected(self):
        """Handle item selection in the table."""
        payload = self._selected_item_payload()
        if payload is None:
            self._set_form_cleared(clear_selection=False)
            return

        code = str(payload.get("code") or "")
        name = str(payload.get("name") or "")
        purity_str = str(
            payload.get("purity") if payload.get("purity") is not None else 0.0
        )
        wage_type = str(payload.get("wage_type") or "WT")
        wage_rate_str = str(
            payload.get("wage_rate") if payload.get("wage_rate") is not None else 0.0
        )

        self.code_edit.setText(code)
        self.name_edit.setText(name)
        self.purity_edit.setText(purity_str)
        self.wage_rate_edit.setText(wage_rate_str)

        index = self.wage_type_combo.findText(wage_type, Qt.MatchFixedString)
        self.wage_type_combo.setCurrentIndex(index if index >= 0 else 0)

        # Switch form panel to edit mode
        self._form_heading.setText(f"Editing: {code}")
        self._form_heading.setStyleSheet(
            "font-size: 11pt; font-weight: 700; color: #0f766e; padding-bottom: 2px;"
        )
        self.code_edit.setReadOnly(True)
        self.code_edit.setStyleSheet(
            "background-color: #f1f5f9; color: #475569; border: 1px solid #d8e1ec;"
        )
        self.add_button.setVisible(False)
        self.update_button.setVisible(True)
        self.delete_button.setEnabled(True)
        self.show_status(f"Selected item: {code}", 2000)

    def clear_form(self):
        """Clear the form fields and reset button states."""
        self._set_form_cleared(clear_selection=True)

    def _set_form_cleared(self, *, clear_selection: bool) -> None:
        self.code_edit.clear()
        self.code_edit.setReadOnly(False)
        self.code_edit.setStyleSheet("")
        self.name_edit.clear()
        self.purity_edit.clear()
        self.wage_type_combo.setCurrentIndex(0)
        self.wage_rate_edit.clear()

        # Switch form panel back to add mode
        self._form_heading.setText("New Item")
        self._form_heading.setStyleSheet(
            "font-size: 11pt; font-weight: 700; color: #0f172a; padding-bottom: 2px;"
        )
        self.add_button.setVisible(True)
        self.update_button.setVisible(False)
        self.delete_button.setEnabled(False)

        if clear_selection:
            self.items_table.clearSelection()
            self.items_table.setCurrentIndex(QModelIndex())
        self.show_status("Form cleared.", 1500)

    def _selected_item_payload(self):
        selection_model = self.items_table.selectionModel()
        assert selection_model is not None
        selected_rows = selection_model.selectedRows()
        if not selected_rows:
            return None
        return self.items_model.row_payload(selected_rows[0].row())

    # --- Helper to safely convert locale-aware string to float ---
    def _parse_float(self, text, default=0.0):
        locale = QLocale.system()
        f_val, ok = locale.toDouble(text.strip())
        return f_val if ok else default

    # -----------------------------------------------------------

    def add_item(self):
        """Add a new item to the database."""
        code = self.code_edit.text().strip()
        name = self.name_edit.text().strip()
        purity = self._parse_float(self.purity_edit.text(), 0.0)
        wage_type = self.wage_type_combo.currentText()
        wage_rate = self._parse_float(self.wage_rate_edit.text(), 0.0)

        try:
            validated = validate_item(
                code=code,
                name=name,
                purity=purity,
                wage_type=wage_type,
                wage_rate=wage_rate,
            )
        except ItemValidationError as exc:
            QMessageBox.warning(self, "Input Error", str(exc))
            self.show_status(f"Add Item Error: {exc}", 3000)
            return

        if self.db_manager.get_item_by_code(validated.code):
            QMessageBox.warning(
                self,
                "Duplicate Code",
                f"Item with code '{validated.code}' already exists. Use Update or choose a different code.",
            )
            self.show_status(
                f"Add Item Error: Code '{validated.code}' already exists.", 3000
            )
            return

        success = self.db_manager.add_item(
            validated.code,
            validated.name,
            validated.purity,
            validated.wage_type,
            validated.wage_rate,
        )
        if success:
            self.show_status(f"Item '{validated.code}' added successfully.", 3000)
            self.clear_form()
            self.load_items()
        else:
            QMessageBox.critical(
                self,
                "Save Failed",
                "Failed to add item. Please verify values and try again.",
            )
            self.show_status("Add Item Error: Database operation failed.", 4000)

    def update_item(self):
        """Update an existing item in the database."""
        code = self.code_edit.text().strip()
        name = self.name_edit.text().strip()
        purity = self._parse_float(self.purity_edit.text(), 0.0)
        wage_type = self.wage_type_combo.currentText()
        wage_rate = self._parse_float(self.wage_rate_edit.text(), 0.0)

        try:
            validated = validate_item(
                code=code,
                name=name,
                purity=purity,
                wage_type=wage_type,
                wage_rate=wage_rate,
            )
        except ItemValidationError as exc:
            QMessageBox.warning(self, "Input Error", str(exc))
            self.show_status(f"Update Item Error: {exc}", 3000)
            return

        success = self.db_manager.update_item(
            validated.code,
            validated.name,
            validated.purity,
            validated.wage_type,
            validated.wage_rate,
        )
        if success:
            self.show_status(f"Item '{validated.code}' updated successfully.", 3000)
            self.clear_form()
            self.load_items()
        else:
            QMessageBox.critical(
                self,
                "Save Failed",
                "Failed to update item. Please verify values and try again.",
            )
            self.show_status(
                f"Update Item Error: Database operation failed for '{validated.code}'.",
                4000,
            )

    def delete_item(self):
        """Delete an item from the database."""
        code = self.code_edit.text().strip()
        if not code:
            QMessageBox.warning(self, "Delete Error", "No item selected to delete.")
            self.show_status("Delete Item Error: No item selected", 3000)
            return

        reply = QMessageBox.warning(
            self,
            "Confirm Deletion",
            f"Are you sure you want to delete item '{code}'?\n"
            f"WARNING: This may affect past estimates using this item code.\n"
            f"This action cannot be undone.",
            QMessageBox.Yes | QMessageBox.Cancel,
            QMessageBox.Cancel,
        )

        if reply == QMessageBox.Yes:
            success = self.db_manager.delete_item(code)
            if success:
                self.show_status(f"Item '{code}' deleted successfully.", 3000)
                self.clear_form()
                self.load_items()
            else:
                QMessageBox.critical(
                    self,
                    "Database Error",
                    f"Failed to delete item '{code}'. It might be used in existing estimates. See console/logs.",
                )
                self.show_status(
                    f"Delete Item Error: Database operation failed for '{code}'.", 4000
                )

    def keyPressEvent(self, event):
        """Handle key press events."""
        if event.key() == Qt.Key_Escape:
            selection_model = self.items_table.selectionModel()
            if selection_model and selection_model.hasSelection():
                self.clear_form()
            event.accept()
        else:
            super().keyPressEvent(event)

    def closeEvent(self, event):
        self._cancel_active_loads()
        super().closeEvent(event)
