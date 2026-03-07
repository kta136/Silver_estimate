#!/usr/bin/env python
import logging
import time

from PyQt5.QtCore import QLocale, QModelIndex, Qt, QTimer
from PyQt5.QtGui import QDoubleValidator
from PyQt5.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QFrame,
    QGridLayout,
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
from silverestimate.ui.models import ItemMasterTableModel
from silverestimate.ui.shared_screen_theme import build_management_screen_stylesheet


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
        self.init_ui()
        self.load_items()

    # --- Helper to show status messages ---
    def show_status(self, message, timeout=3000):
        if self.main_window:
            self.main_window.show_status_message(message, timeout)
        else:
            import logging

            logging.getLogger(__name__).info(f"Status: {message}")

    # ------------------------------------

    def init_ui(self):
        """Initialize the user interface."""
        self.setObjectName("ItemMasterWidget")
        self.setStyleSheet(
            build_management_screen_stylesheet(
                root_selector="QWidget#ItemMasterWidget",
                card_names=[
                    "ItemMasterHeaderCard",
                    "ItemMasterFormCard",
                    "ItemMasterSearchCard",
                ],
                title_label="ItemMasterTitleLabel",
                subtitle_label="ItemMasterSubtitleLabel",
                field_label="ItemMasterFieldLabel",
                primary_button="ItemMasterPrimaryButton",
                secondary_button="ItemMasterSecondaryButton",
                danger_button="ItemMasterDangerButton",
                input_selectors=["QLineEdit", "QComboBox"],
                include_table=True,
            )
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        header_card = QFrame(self)
        header_card.setObjectName("ItemMasterHeaderCard")
        header_layout = QVBoxLayout(header_card)
        header_layout.setContentsMargins(12, 12, 12, 12)
        header_layout.setSpacing(2)

        header_label = QLabel("Item Master")
        header_label.setObjectName("ItemMasterTitleLabel")
        header_layout.addWidget(header_label)

        subtitle_label = QLabel(
            "Maintain catalog codes, purity defaults, and wage settings."
        )
        subtitle_label.setObjectName("ItemMasterSubtitleLabel")
        header_layout.addWidget(subtitle_label)
        layout.addWidget(header_card)

        form_card = QFrame(self)
        form_card.setObjectName("ItemMasterFormCard")
        form_layout = QGridLayout(form_card)
        form_layout.setContentsMargins(12, 12, 12, 12)
        form_layout.setHorizontalSpacing(10)
        form_layout.setVerticalSpacing(6)

        code_label = QLabel("Code")
        code_label.setObjectName("ItemMasterFieldLabel")
        form_layout.addWidget(code_label, 0, 0)
        self.code_edit = QLineEdit()
        self.code_edit.setMaximumWidth(100)
        self.code_edit.setToolTip(
            "Unique code for the item (e.g., CH001, SB999). Cannot be changed after adding."
        )
        form_layout.addWidget(self.code_edit, 1, 0)

        name_label = QLabel("Name")
        name_label.setObjectName("ItemMasterFieldLabel")
        form_layout.addWidget(name_label, 0, 1)
        self.name_edit = QLineEdit()
        self.name_edit.setMinimumWidth(200)
        self.name_edit.setToolTip("Descriptive name of the item.")
        form_layout.addWidget(self.name_edit, 1, 1)

        purity_label = QLabel("Purity (%)")
        purity_label.setObjectName("ItemMasterFieldLabel")
        form_layout.addWidget(purity_label, 0, 2)
        self.purity_edit = QLineEdit()
        self.purity_edit.setMaximumWidth(90)
        self.purity_edit.setToolTip("Default silver purity percentage.")
        purity_validator = QDoubleValidator(0.00, 100.00, 2, self.purity_edit)
        purity_validator.setNotation(QDoubleValidator.StandardNotation)
        purity_validator.setLocale(QLocale.system())
        self.purity_edit.setValidator(purity_validator)
        form_layout.addWidget(self.purity_edit, 1, 2)

        wage_type_label = QLabel("Wage Type")
        wage_type_label.setObjectName("ItemMasterFieldLabel")
        form_layout.addWidget(wage_type_label, 0, 3)
        self.wage_type_combo = QComboBox()
        self.wage_type_combo.addItems(["PC", "WT"])
        self.wage_type_combo.setToolTip(
            "Select wage calculation method: PC (Per Piece) or WT (Per Weight/Gram)."
        )
        form_layout.addWidget(self.wage_type_combo, 1, 3)

        wage_rate_label = QLabel("Wage Rate")
        wage_rate_label.setObjectName("ItemMasterFieldLabel")
        form_layout.addWidget(wage_rate_label, 0, 4)
        self.wage_rate_edit = QLineEdit()
        self.wage_rate_edit.setMaximumWidth(110)
        self.wage_rate_edit.setToolTip(
            "Wage rate corresponding to the selected Wage Type."
        )
        rate_validator = QDoubleValidator(0.00, 100000.00, 2, self.wage_rate_edit)
        rate_validator.setNotation(QDoubleValidator.StandardNotation)
        rate_validator.setLocale(QLocale.system())
        self.wage_rate_edit.setValidator(rate_validator)
        form_layout.addWidget(self.wage_rate_edit, 1, 4)

        button_layout = QHBoxLayout()
        button_layout.setSpacing(8)
        self.add_button = QPushButton("Add New Item")
        self.add_button.setObjectName("ItemMasterPrimaryButton")
        self.add_button.setToolTip("Add the details entered above as a new item.")
        self.add_button.clicked.connect(self.add_item)
        button_layout.addWidget(self.add_button)

        self.update_button = QPushButton("Update Selected")
        self.update_button.setObjectName("ItemMasterSecondaryButton")
        self.update_button.setToolTip(
            "Update the currently selected item in the table with the details entered above."
        )
        self.update_button.clicked.connect(self.update_item)
        self.update_button.setEnabled(False)
        button_layout.addWidget(self.update_button)

        self.delete_button = QPushButton("Delete Selected")
        self.delete_button.setObjectName("ItemMasterDangerButton")
        self.delete_button.setToolTip(
            "Delete the currently selected item from the table (use with caution!)."
        )
        self.delete_button.clicked.connect(self.delete_item)
        self.delete_button.setEnabled(False)
        button_layout.addWidget(self.delete_button)

        self.clear_button = QPushButton("Clear Form")
        self.clear_button.setObjectName("ItemMasterSecondaryButton")
        self.clear_button.setToolTip(
            "Clear the input fields above and deselect the table."
        )
        self.clear_button.clicked.connect(self.clear_form)
        button_layout.addWidget(self.clear_button)

        button_layout.addStretch()
        form_layout.addLayout(button_layout, 2, 0, 1, 5)
        layout.addWidget(form_card)

        search_card = QFrame(self)
        search_card.setObjectName("ItemMasterSearchCard")
        search_layout = QHBoxLayout(search_card)
        search_layout.setContentsMargins(12, 10, 12, 10)
        search_layout.setSpacing(8)

        search_label = QLabel("Search")
        search_label.setObjectName("ItemMasterFieldLabel")
        search_layout.addWidget(search_label)
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Search by code or name...")
        self.search_edit.setToolTip("Type here to filter the item list below.")
        self.search_edit.textChanged.connect(self._schedule_search)
        search_layout.addWidget(self.search_edit)
        layout.addWidget(search_card)

        self.items_table = QTableView(self)
        self.items_model = ItemMasterTableModel(self.items_table)
        self.items_table.setModel(self.items_model)
        self.items_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeToContents
        )
        self.items_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.items_table.verticalHeader().setVisible(False)
        self.items_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.items_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.items_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.items_table.setSortingEnabled(True)
        self.items_table.setAlternatingRowColors(True)
        selection_model = self.items_table.selectionModel()
        if selection_model:
            selection_model.selectionChanged.connect(lambda *_: self.on_item_selected())
        layout.addWidget(self.items_table)

    def load_items(self, search_term=None):
        """Load items from the database into the table."""
        start = time.perf_counter()
        table = self.items_table
        model = self.items_model
        table.setUpdatesEnabled(False)
        table.blockSignals(True)
        try:
            if search_term:
                items = self.db_manager.search_items(search_term)
            else:
                items = self.db_manager.get_all_items()
            items = list(items or [])
            model.set_rows(items)
        finally:
            table.blockSignals(False)
            table.setUpdatesEnabled(True)
            table.viewport().update()

        self.show_status(f"Loaded {len(items)} items.", 2000)
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        if elapsed_ms >= 20.0:
            self.logger.debug(
                "[perf] item_master.load_items=%.2fms search_term=%r rows=%s",
                elapsed_ms,
                search_term,
                len(items),
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

        self.update_button.setEnabled(True)
        self.delete_button.setEnabled(True)
        self.add_button.setEnabled(False)
        self.code_edit.setReadOnly(True)
        self.show_status(f"Selected item: {code}", 2000)

    def clear_form(self):
        """Clear the form fields and reset button states."""
        self._set_form_cleared(clear_selection=True)

    def _set_form_cleared(self, *, clear_selection: bool) -> None:
        self.code_edit.clear()
        self.code_edit.setReadOnly(False)
        self.name_edit.clear()
        self.purity_edit.clear()
        self.wage_type_combo.setCurrentIndex(0)
        self.wage_rate_edit.clear()

        self.update_button.setEnabled(False)
        self.delete_button.setEnabled(False)
        self.add_button.setEnabled(True)

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
