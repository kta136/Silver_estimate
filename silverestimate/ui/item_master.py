#!/usr/bin/env python
import logging
import os
import threading
import time
from dataclasses import dataclass
from typing import Any, cast

from PyQt6.QtCore import QLocale, QModelIndex, Qt, QTimer
from PyQt6.QtGui import QDoubleValidator
from PyQt6.QtWidgets import (
    QAbstractItemView,
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
from silverestimate.domain.pagination import ItemCursor, Page
from silverestimate.infrastructure.latest_request_runner import LatestRequestRunner
from silverestimate.infrastructure.sqlite_worker import cancellable_sqlite_connection
from silverestimate.persistence.items_repository import fetch_item_catalog_page
from silverestimate.ui.models import ItemMasterTableModel
from silverestimate.ui.modern_components import BottomStatusStrip, polish_dense_table
from silverestimate.ui.shared_screen_theme import build_management_screen_stylesheet
from silverestimate.ui.themed_controls import ThemedComboBox


@dataclass(frozen=True)
class _ItemLoadRequest:
    db_path: str
    search_term: str
    cursor: ItemCursor | None
    append: bool
    started_at: float


def _load_item_page(
    request: _ItemLoadRequest,
    cancel_event: threading.Event,
) -> tuple[_ItemLoadRequest, Page[dict[str, Any], ItemCursor]]:
    with cancellable_sqlite_connection(request.db_path, cancel_event) as connection:
        page = fetch_item_catalog_page(
            connection.cursor(),
            request.search_term,
            page_cursor=request.cursor,
            limit=1000,
        )
    return request, page


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
        self._loaded_items: list[dict[str, Any]] = []
        self._item_cursor: ItemCursor | None = None
        self._item_total = 0
        self._load_runner = LatestRequestRunner(
            _load_item_page,
            self,
            name="item-master-loader",
        )
        self._load_runner.result.connect(self._handle_async_load_result)
        self._load_runner.failed.connect(self._handle_async_load_error)
        self._load_runner.settled.connect(self._finish_async_load)
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
                    color: __TEXT_STRONG__;
                    padding-bottom: 2px;
                }
                QLabel#ItemMasterFormHeading[formMode="edit"] {
                    color: __PRIMARY_BG__;
                }
                QLabel#ItemMasterCountLabel {
                    color: __TEXT_MUTED__;
                    font-size: 8.5pt;
                }
                QFrame#ItemMasterSeparator {
                    background-color: __CARD_BORDER_SOFT__;
                    border: none;
                    max-height: 1px;
                }
                QTableView {
                    border-radius: 8px;
                }
                QTableView::item {
                    padding: 1px 6px;
                }
                QTableView::item:selected {
                    border-radius: 0px;
                }
                """,
            )
        )

        outer = QVBoxLayout(self)
        outer.setContentsMargins(10, 10, 10, 0)
        outer.setSpacing(8)

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
        subtitle_label.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        header_row.addWidget(subtitle_label)
        header_row.addStretch()
        outer.addLayout(header_row)

        # ── Horizontal split ────────────────────────────────────
        split = QHBoxLayout()
        split.setSpacing(12)

        # ── LEFT: Form panel ────────────────────────────────────
        self._form_panel = QFrame(self)
        self._form_panel.setObjectName("ItemMasterFormPanel")
        self._form_panel.setMinimumWidth(280)
        self._form_panel.setMaximumWidth(340)
        form_vbox = QVBoxLayout(self._form_panel)
        form_vbox.setContentsMargins(14, 14, 14, 14)
        form_vbox.setSpacing(8)

        self._form_heading = QLabel("New Item")
        self._form_heading.setObjectName("ItemMasterFormHeading")
        self._form_heading.setProperty("formMode", "new")
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
        purity_validator.setNotation(QDoubleValidator.Notation.StandardNotation)
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
        self.wage_type_combo = ThemedComboBox()
        self.wage_type_combo.addItems(["PC", "WT"])
        self.wage_type_combo.setMinimumWidth(92)
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
        rate_validator.setNotation(QDoubleValidator.Notation.StandardNotation)
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

        # Separator
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setObjectName("ItemMasterSeparator")
        form_vbox.addWidget(sep)

        self.delete_button = QPushButton("Delete Item")
        self.delete_button.setObjectName("ItemMasterDangerButton")
        self.delete_button.setToolTip("Permanently delete this item. Cannot be undone.")
        self.delete_button.clicked.connect(self.delete_item)
        self.delete_button.setEnabled(False)
        form_vbox.addWidget(self.delete_button)

        form_vbox.addStretch()

        split.addWidget(self._form_panel)

        # ── RIGHT: Search + table ───────────────────────────────
        right_col = QVBoxLayout()
        right_col.setSpacing(6)

        search_row = QHBoxLayout()
        search_row.setSpacing(8)
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Search by code or name...")
        self.search_edit.setToolTip("Filter items by code or name.")
        self.search_edit.setClearButtonEnabled(True)
        self.search_edit.textChanged.connect(self._schedule_search)
        search_row.addWidget(self.search_edit)
        self._item_count_label = QLabel("")
        self._item_count_label.setObjectName("ItemMasterCountLabel")
        self._item_count_label.setMinimumWidth(96)
        self._item_count_label.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        search_row.addWidget(self._item_count_label)
        right_col.addLayout(search_row)

        self.items_table = QTableView(self)
        self.items_model = ItemMasterTableModel(self.items_table)
        self.items_table.setModel(self.items_model)
        hdr = self.items_table.horizontalHeader()
        hdr.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        hdr.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.items_table.verticalHeader().setVisible(False)
        polish_dense_table(
            self.items_table,
            row_height=28,
            header_height=30,
            show_grid=False,
            hide_vertical_header=True,
        )
        self.items_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.items_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.items_table.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
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

        paging_row = QHBoxLayout()
        paging_row.addStretch()
        self.load_more_button = QPushButton("Load more")
        self.load_more_button.setObjectName("ItemMasterSecondaryButton")
        self.load_more_button.setVisible(False)
        self.load_more_button.clicked.connect(self._load_more_items)
        paging_row.addWidget(self.load_more_button)
        right_col.addLayout(paging_row)

        split.addLayout(right_col, 1)
        outer.addLayout(split, 1)

        self.bottom_status_strip = BottomStatusStrip(self)
        self.bottom_status_strip.set_left_items(
            [
                "F2: Item Search",
                "Ins: Add Row",
                "Del: Delete Row",
                "Ctrl+S: Save",
                "F9: Print",
            ]
        )
        outer.addWidget(self.bottom_status_strip)
        self._update_bottom_status(0)

    def load_items(self, search_term=None, *, append: bool = False):
        """Load items from the database into the table."""
        normalized_term = (search_term or "").strip()
        if not append:
            self._loaded_items = []
            self._item_cursor = None
            self._item_total = 0
            self.items_model.set_rows([])
            self._item_count_label.setText("0 of 0 items")
            self.load_more_button.setVisible(False)
        elif self._item_cursor is None:
            return

        started_at = time.perf_counter()
        temp_db_path = getattr(self.db_manager, "temp_db_path", None)
        if isinstance(temp_db_path, str) and temp_db_path:
            request = _ItemLoadRequest(
                temp_db_path,
                normalized_term,
                self._item_cursor,
                append,
                started_at,
            )
            self.load_more_button.setEnabled(False)
            self._load_runner.submit(request)
            return

        try:
            page = self._load_items_sync(normalized_term)
        except Exception as exc:
            QMessageBox.warning(self, "Load Error", str(exc))
            self.logger.warning(
                "Failed to load item master rows: %s", exc, exc_info=True
            )
            return
        self._apply_loaded_items(
            page,
            search_term=normalized_term,
            started_at=started_at,
            append=append,
        )

    def _schedule_search(self, *_args) -> None:
        try:
            self._search_timer.start()
        except Exception:
            self.search_items()

    def search_items(self):
        """Search for items based on the search term."""
        search_term = self.search_edit.text().strip()
        self.load_items(search_term)

    def _load_more_items(self) -> None:
        self.load_items(self.search_edit.text().strip(), append=True)

    def _load_items_sync(self, search_term: str) -> Page[dict[str, Any], ItemCursor]:
        getter = getattr(self.db_manager, "search_items_page", None)
        if callable(getter):
            return cast(
                Page[dict[str, Any], ItemCursor],
                getter(search_term, cursor=self._item_cursor, limit=1000),
            )
        rows = (
            self.db_manager.search_items(search_term)
            if search_term
            else self.db_manager.get_all_items()
        )
        converted = tuple(dict(row) for row in rows[:1000])
        return Page(converted, len(rows), None)

    def _handle_async_load_result(self, _generation: int, value: object) -> None:
        request, page = cast(
            tuple[_ItemLoadRequest, Page[dict[str, Any], ItemCursor]],
            value,
        )
        self._apply_loaded_items(
            page,
            search_term=request.search_term,
            started_at=request.started_at,
            append=request.append,
        )

    def _handle_async_load_error(self, _generation: int, error: object) -> None:
        QMessageBox.warning(self, "Load Error", str(error))
        self.logger.warning("Failed to load item master rows: %s", error)

    def _finish_async_load(self, _generation: int) -> None:
        self.load_more_button.setEnabled(True)

    def _apply_loaded_items(
        self,
        page: Page[dict[str, Any], ItemCursor],
        *,
        search_term: str,
        started_at: float,
        append: bool,
    ) -> None:
        page_items = list(page.items)
        self._loaded_items = (
            [*self._loaded_items, *page_items] if append else page_items
        )
        self._item_cursor = page.next_cursor
        self._item_total = page.total
        table = self.items_table
        model = self.items_model
        sorting_enabled = table.isSortingEnabled()
        table.setUpdatesEnabled(False)
        table.blockSignals(True)
        try:
            if sorting_enabled:
                table.setSortingEnabled(False)
            model.set_rows(cast(list[object], self._loaded_items))
        finally:
            if sorting_enabled:
                table.setSortingEnabled(True)
            table.blockSignals(False)
            table.setUpdatesEnabled(True)
            table.viewport().update()

        count = len(self._loaded_items)
        self._item_count_label.setText(f"{count} of {self._item_total} items")
        self.load_more_button.setVisible(self._item_cursor is not None)
        self.load_more_button.setEnabled(True)
        self._update_bottom_status(count)
        self.show_status(f"Loaded {count} of {self._item_total} items.", 2000)
        elapsed_ms = (time.perf_counter() - started_at) * 1000.0
        self.logger.debug(
            "[perf] item_master.load_items=%.2fms search_term=%r rows=%s",
            elapsed_ms,
            search_term,
            len(self._loaded_items),
        )

    def _update_bottom_status(self, count: int | None = None) -> None:
        strip = getattr(self, "bottom_status_strip", None)
        if strip is None:
            return
        try:
            user = os.environ.get("USERNAME") or os.environ.get("USER") or "-"
        except Exception:
            user = "-"
        rows = self.items_model.rowCount() if count is None else int(count)
        strip.set_right_items([f"Rows: {rows}", "Last Saved: -", f"User: {user}"])

    def _cancel_active_loads(self) -> None:
        self._load_runner.cancel()
        self._load_runner.shutdown()

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

        index = self.wage_type_combo.findText(wage_type, Qt.MatchFlag.MatchFixedString)
        self.wage_type_combo.setCurrentIndex(index if index >= 0 else 0)

        # Switch form panel to edit mode
        self._form_heading.setText(f"Editing: {code}")
        self._set_form_heading_mode("edit")
        self.code_edit.setReadOnly(True)
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
        self._set_form_heading_mode("new")
        self.add_button.setVisible(True)
        self.update_button.setVisible(False)
        self.delete_button.setEnabled(False)

        if clear_selection:
            self.items_table.clearSelection()
            self.items_table.setCurrentIndex(QModelIndex())
        self.show_status("Form cleared.", 1500)

    def _set_form_heading_mode(self, mode: str) -> None:
        self._form_heading.setProperty("formMode", mode)
        self._refresh_widget_style(self._form_heading)

    @staticmethod
    def _refresh_widget_style(widget: QWidget) -> None:
        style = widget.style()
        style.unpolish(widget)
        style.polish(widget)
        widget.update()

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
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )

        if reply == QMessageBox.StandardButton.Yes:
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
        if event.key() == Qt.Key.Key_Escape:
            selection_model = self.items_table.selectionModel()
            if selection_model and selection_model.hasSelection():
                self.clear_form()
            event.accept()
        else:
            super().keyPressEvent(event)

    def closeEvent(self, event):
        self._cancel_active_loads()
        super().closeEvent(event)
