#!/usr/bin/env python
import logging
import threading
import time
from dataclasses import dataclass
from typing import Any, Callable, cast

from PySide6.QtCore import QLocale, QModelIndex, Qt, QTimer
from PySide6.QtGui import QDoubleValidator
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QTableView,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from silverestimate.domain.item_validation import ItemValidationError, validate_item
from silverestimate.domain.numeric_policy import fixed_decimal
from silverestimate.domain.pagination import ItemCursor, Page
from silverestimate.infrastructure.latest_request_runner import LatestRequestRunner
from silverestimate.infrastructure.paged_load_state import PagedLoadState
from silverestimate.infrastructure.sqlite_worker import cancellable_sqlite_connection
from silverestimate.persistence.items_repository import fetch_item_catalog_page
from silverestimate.ui.display_formatting import count_label
from silverestimate.ui.message_dialogs import (
    ask_save_discard,
    confirm_destructive,
    with_details,
)
from silverestimate.ui.models import ItemMasterTableModel
from silverestimate.ui.modern_components import (
    BottomStatusStrip,
    install_table_empty_state,
    polish_dense_table,
)
from silverestimate.ui.shared_screen_theme import build_management_screen_stylesheet
from silverestimate.ui.themed_controls import ThemedComboBox
from silverestimate.ui.toolbar_overflow import ToolbarOverflow


@dataclass(frozen=True)
class _ItemLoadRequest:
    connection_factory: Callable[[threading.Event | None], Any]
    search_term: str
    cursor: ItemCursor | None
    append: bool
    started_at: float


def _load_item_page(
    request: _ItemLoadRequest,
    cancel_event: threading.Event,
) -> tuple[_ItemLoadRequest, Page[dict[str, Any], ItemCursor]]:
    with cancellable_sqlite_connection(
        request.connection_factory, cancel_event
    ) as connection:
        connection.execute("BEGIN")
        page = fetch_item_catalog_page(
            connection.cursor(),
            request.search_term,
            page_cursor=request.cursor,
            include_total=not request.append,
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
        self._item_page_state = PagedLoadState[dict[str, Any], ItemCursor]()
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

    def notify(self, message, timeout=3000, level="info"):
        """Report an outcome the user should see, as a brief toast."""
        self.show_status(message, timeout)
        show_toast = getattr(self.main_window, "show_toast", None)
        if callable(show_toast):
            show_toast(message, timeout=timeout, level=level)

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
                QLabel#ItemMasterFormError {
                    color: #b91c1c;
                    font-weight: 600;
                }
                QLineEdit[invalid="true"] {
                    border: 1px solid #dc2626;
                    background-color: #fff7f7;
                }
                QLabel#ItemMasterCountLabel {
                    color: __TEXT_MUTED__;

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
            "Maintain catalog codes, Tunch, purity defaults, and labour settings."
        )
        subtitle_label.setObjectName("ItemMasterSubtitleLabel")
        subtitle_label.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        subtitle_label.hide()
        header_row.addStretch()
        outer.addWidget(ToolbarOverflow(header_row))

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

        # Tunch
        tunch_lbl = QLabel("Tunch")
        tunch_lbl.setObjectName("ItemMasterFieldLabel")
        self.tunch_edit = QLineEdit()
        self.tunch_edit.setPlaceholderText("Optional text")
        self.tunch_edit.setToolTip(
            "Optional Tunch text. Leave blank when no value exists."
        )
        form_vbox.addWidget(tunch_lbl)
        form_vbox.addWidget(self.tunch_edit)

        # Purity
        purity_lbl = QLabel("Purity (%)")
        purity_lbl.setObjectName("ItemMasterFieldLabel")
        self.purity_edit = QLineEdit()
        self.purity_edit.setPlaceholderText("e.g. 92.50 or 125.50")
        self.purity_edit.setToolTip(
            "Numeric Purity/Tunch %. Values above 100% are allowed."
        )
        purity_validator = QDoubleValidator(0.00, float("inf"), 2, self.purity_edit)
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
        wt_lbl = QLabel("Labour Type")
        wt_lbl.setObjectName("ItemMasterFieldLabel")
        self.wage_type_combo = ThemedComboBox()
        self.wage_type_combo.addItem("Per gram", "WT")
        self.wage_type_combo.addItem("Per piece", "PC")
        self.wage_type_combo.setMinimumWidth(92)
        self.wage_type_combo.setToolTip(
            "Charge labour on the net weight (per gram) or on the piece count."
        )
        wt_col.addWidget(wt_lbl)
        wt_col.addWidget(self.wage_type_combo)
        wage_row.addLayout(wt_col)

        wr_col = QVBoxLayout()
        wr_col.setSpacing(4)
        wr_lbl = QLabel("Labour Rate")
        wr_lbl.setObjectName("ItemMasterFieldLabel")
        self.wage_rate_edit = QLineEdit()
        self.wage_rate_edit.setPlaceholderText("0.00")
        self.wage_rate_edit.setToolTip("Labour rate for the selected labour type.")
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
        sep.setVisible(False)
        self._delete_separator = sep
        form_vbox.addWidget(sep)

        self.delete_button = QPushButton("Delete Item")
        self.delete_button.setObjectName("ItemMasterDangerButton")
        self.delete_button.setToolTip("Permanently delete this item. Cannot be undone.")
        self.delete_button.clicked.connect(self.delete_item)
        self.delete_button.setEnabled(False)
        self.delete_button.setVisible(False)
        form_vbox.addWidget(self.delete_button)

        form_vbox.addStretch()

        # ── RIGHT: Search + table ───────────────────────────────
        right_col = QVBoxLayout()
        right_col.setSpacing(6)

        search_row = QHBoxLayout()
        search_row.setSpacing(8)
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Search code, name or Tunch...")
        self.search_edit.setToolTip("Filter items by code, name or Tunch.")
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
        self.items_table.horizontalHeader().setSortIndicator(
            0, Qt.SortOrder.AscendingOrder
        )
        self.items_table.setSortingEnabled(True)
        self.items_table.horizontalHeader().setToolTip(
            "Sort loaded rows only. Filters search all records. Up to 20,000 rows are displayed; narrow filters to see more."
        )
        self.items_table.setAlternatingRowColors(True)
        self.items_table.setShowGrid(False)
        self.items_table.setColumnWidth(0, 110)
        self.items_table.setColumnWidth(2, 95)
        self.items_table.setColumnWidth(3, 95)
        self.items_table.setColumnWidth(4, 116)
        self.items_table.setColumnWidth(5, 116)
        install_table_empty_state(
            self.items_table,
            "No catalog items match the current search.",
        )
        selection_model = self.items_table.selectionModel()
        if selection_model:
            selection_model.selectionChanged.connect(lambda *_: self.on_item_selected())
        right_col.addWidget(self.items_table)

        paging_row = QHBoxLayout()
        paging_row.addStretch()
        self.load_more_button = QPushButton("Load More")
        self.load_more_button.setObjectName("ItemMasterSecondaryButton")
        self.load_more_button.setVisible(False)
        self.load_more_button.clicked.connect(self._load_more_items)
        paging_row.addWidget(self.load_more_button)
        right_col.addLayout(paging_row)

        split.addLayout(right_col, 1)
        form_scroll = QScrollArea()
        form_scroll.setWidgetResizable(True)
        form_scroll.setFrameShape(QFrame.Shape.NoFrame)
        form_scroll.setMinimumWidth(300)
        form_scroll.setMaximumWidth(360)
        form_scroll.setWidget(self._form_panel)
        split.addWidget(form_scroll)
        header_row.insertWidget(1, self.search_edit, 1)
        header_row.addWidget(self._item_count_label)
        self.new_item_button = QPushButton("+ New Item")
        self.new_item_button.setObjectName("ItemMasterPrimaryButton")
        self.new_item_button.clicked.connect(self.clear_form)
        header_row.addWidget(self.new_item_button)
        backup = QToolButton()
        backup.setText("Backup")
        backup.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        menu = QMenu(backup)
        for label, method in (
            ("Back Up Item Catalog...", "create_item_catalog_backup"),
            ("Restore Item Catalog...", "restore_item_catalog"),
        ):
            action = menu.addAction(label)
            action.triggered.connect(
                lambda checked=False, name=method: self._catalog_command(name)
            )
        backup.setMenu(menu)
        header_row.addWidget(backup)
        close = QPushButton("Close")
        close.clicked.connect(self._close_catalog)
        header_row.addWidget(close)
        self.dirty_label = QLabel("")
        self.dirty_label.setVisible(False)
        form_vbox.insertWidget(form_vbox.indexOf(self.add_button), self.dirty_label)
        self.form_error_label = QLabel("")
        self.form_error_label.setObjectName("ItemMasterFormError")
        self.form_error_label.setWordWrap(True)
        self.form_error_label.setVisible(False)
        form_vbox.insertWidget(
            form_vbox.indexOf(self.dirty_label), self.form_error_label
        )
        self.clear_button.setText("Cancel")
        self._clean_form = self._form_values()
        self._selection_guard = False
        for edit in (
            self.code_edit,
            self.name_edit,
            self.tunch_edit,
            self.purity_edit,
            self.wage_rate_edit,
        ):
            edit.textEdited.connect(self._update_dirty_label)
            edit.textEdited.connect(self._clear_form_error)
        self.wage_type_combo.activated.connect(self._update_dirty_label)
        outer.addLayout(split, 1)

        self.bottom_status_strip = BottomStatusStrip(self)
        self.bottom_status_strip.set_left_items(
            [
                "Select a row to edit",
                "Esc clears the form",
            ]
        )
        outer.addWidget(self.bottom_status_strip)

    def _show_form_error(self, message: str, field: QWidget | None = None) -> None:
        """Explain what to fix beside the form and put the cursor there."""
        self._mark_invalid(field)
        self.form_error_label.setText(message)
        self.form_error_label.setVisible(True)
        if field is not None:
            field.setFocus()
            select_all = getattr(field, "selectAll", None)
            if callable(select_all):
                select_all()

    def _clear_form_error(self, *_args) -> None:
        self._mark_invalid(None)
        self.form_error_label.clear()
        self.form_error_label.setVisible(False)

    def _mark_invalid(self, field: QWidget | None) -> None:
        """Outline the one field the message is about, and no other."""
        for edit in (
            self.code_edit,
            self.name_edit,
            self.tunch_edit,
            self.purity_edit,
            self.wage_rate_edit,
        ):
            wanted = "true" if edit is field else "false"
            if edit.property("invalid") != wanted:
                edit.setProperty("invalid", wanted)
                self._refresh_widget_style(edit)

    def _field_for_error(self, message: str) -> QWidget | None:
        text = message.lower()
        for keyword, field in (
            ("code", self.code_edit),
            ("name", self.name_edit),
            ("purity", self.purity_edit),
            ("labour", self.wage_rate_edit),
        ):
            if keyword in text:
                return field
        return None

    def _form_values(self) -> tuple:
        return tuple(
            edit.text()
            for edit in (
                self.code_edit,
                self.name_edit,
                self.tunch_edit,
                self.purity_edit,
                self.wage_rate_edit,
            )
        ) + (self.wage_type_combo.currentData(),)

    def _update_dirty_label(self, *_args) -> None:
        dirty = self._form_values() != self._clean_form
        self.dirty_label.setText("● Unsaved changes" if dirty else "")
        # Hidden when empty, so it leaves no gap between the buttons.
        self.dirty_label.setVisible(dirty)

    def confirm_discard_edits(self) -> bool:
        if not hasattr(self, "_clean_form") or self._form_values() == self._clean_form:
            return True
        reply = ask_save_discard(
            self,
            title="Unsaved Item Changes",
            heading="Save the changes to this item first?",
            detail="The item form has changes that are not saved yet.",
        )
        if reply == "discard":
            for field, value in zip(
                (
                    self.code_edit,
                    self.name_edit,
                    self.tunch_edit,
                    self.purity_edit,
                    self.wage_rate_edit,
                ),
                self._clean_form[:5],
                strict=True,
            ):
                field.setText(value)
            self.wage_type_combo.setCurrentIndex(
                self.wage_type_combo.findData(self._clean_form[5])
            )
            self._update_dirty_label()
            return True
        if reply == "save":
            self._selection_guard = True
            try:
                self.update_item() if self.code_edit.isReadOnly() else self.add_item()
            finally:
                self._selection_guard = False
            return self._form_values() == self._clean_form
        return False

    def _catalog_command(self, name: str) -> None:
        if self.confirm_discard_edits():
            callback = getattr(getattr(self.main_window, "commands", None), name, None)
            if callable(callback):
                callback()

    def _close_catalog(self) -> None:
        if self.confirm_discard_edits():
            callback = getattr(self.main_window, "show_estimate", None)
            if callable(callback):
                callback()
            else:
                self.close()

    def load_items(self, search_term=None, *, append: bool = False):
        """Load items from the database into the table."""
        normalized_term = (search_term or "").strip()
        if not append:
            self._item_page_state.reset()
            self.items_model.set_rows([])
            self._item_count_label.setText("Loading…")
            self.load_more_button.setVisible(False)
        elif not self._item_page_state.has_more:
            return

        started_at = time.perf_counter()
        connection_factory = getattr(self.db_manager, "open_read_connection", None)
        if callable(connection_factory):
            request = _ItemLoadRequest(
                connection_factory,
                normalized_term,
                self._item_page_state.cursor,
                append,
                started_at,
            )
            self.load_more_button.setEnabled(False)
            self._load_runner.submit(request)
            return

        try:
            page = self._load_items_sync(normalized_term)
        except Exception as exc:
            QMessageBox.warning(
                self,
                "Items Not Loaded",
                with_details("The item list could not be loaded.", exc),
            )
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
                getter(
                    search_term,
                    cursor=self._item_page_state.cursor,
                    limit=1000,
                ),
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
        QMessageBox.warning(
            self,
            "Items Not Loaded",
            with_details("The item list could not be loaded.", error),
        )
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
        self._item_page_state.apply(page, append=append)
        loaded_items = self._item_page_state.last_page_rows
        table = self.items_table
        model = self.items_model
        table.setUpdatesEnabled(False)
        table.blockSignals(True)
        try:
            if append:
                model.append_rows(cast(list[object], loaded_items))
            else:
                model.set_rows(cast(list[object], loaded_items))
        finally:
            table.blockSignals(False)
            table.setUpdatesEnabled(True)
            table.viewport().update()

        count = self._item_page_state.loaded
        total = self._item_page_state.total
        noun = "match" if search_term else "item"
        plural = "matches" if search_term else "items"
        if total is None:
            summary = f"{count_label(count, noun, plural)} loaded"
        elif count >= total:
            summary = (
                "No matches"
                if search_term and total == 0
                else count_label(total, noun, plural)
            )
        else:
            # Sorting reorders only what is on screen, which matters
            # only while part of the list is still unloaded.
            summary = f"Showing {count} of {total} {plural} · sorted as shown"
        if self._item_page_state.limit_reached:
            summary += " · Display limit reached; narrow the search"
        self._item_count_label.setText(summary)
        self.load_more_button.setVisible(self._item_page_state.has_more)
        self.load_more_button.setEnabled(True)
        self.show_status(
            summary,
            2000,
        )
        elapsed_ms = (time.perf_counter() - started_at) * 1000.0
        self.logger.debug(
            "[perf] item_master.load_items=%.2fms search_term=%r rows=%s",
            elapsed_ms,
            search_term,
            self._item_page_state.loaded,
        )

    def _cancel_active_loads(self) -> None:
        self._load_runner.shutdown()

    def on_item_selected(self):
        """Handle item selection in the table."""
        if self._selection_guard:
            return
        payload = self._selected_item_payload()
        target_code = str(payload.get("code") or "") if payload else ""
        if self.code_edit.text() != target_code and not self.confirm_discard_edits():
            self._selection_guard = True
            try:
                for row in range(self.items_model.rowCount()):
                    if (
                        self.items_model.row_payload(row).get("code")
                        == self.code_edit.text()
                    ):
                        self.items_table.selectRow(row)
                        break
            finally:
                self._selection_guard = False
            return
        if payload is None:
            self._set_form_cleared(clear_selection=False)
            return

        code = str(payload.get("code") or "")
        name = str(payload.get("name") or "")
        raw_tunch = payload.get("tunch")
        tunch_str = "" if raw_tunch is None else str(raw_tunch)
        purity_str = self._form_number(payload.get("purity"))
        wage_type = str(payload.get("wage_type") or "WT")
        wage_rate_str = self._form_number(payload.get("wage_rate"))

        self.code_edit.setText(code)
        self.name_edit.setText(name)
        self.tunch_edit.setText(tunch_str)
        self.purity_edit.setText(purity_str)
        self.wage_rate_edit.setText(wage_rate_str)

        index = self.wage_type_combo.findData(wage_type)
        self.wage_type_combo.setCurrentIndex(index if index >= 0 else 0)

        # Switch form panel to edit mode
        self._form_heading.setText(f"Editing: {code}")
        self._set_form_heading_mode("edit")
        self.code_edit.setReadOnly(True)
        self.add_button.setVisible(False)
        self.update_button.setVisible(True)
        self.delete_button.setEnabled(True)
        self.delete_button.setVisible(True)
        self._delete_separator.setVisible(True)
        self._clear_form_error()
        self._clean_form = self._form_values()
        self._update_dirty_label()
        self.show_status(f"Selected item: {code}", 2000)

    @staticmethod
    def _form_number(value: object) -> str:
        """Show a stored figure with two decimals, as the table does.

        A value saved with more precision is shown in full, so opening and
        saving an item never rounds it.
        """
        try:
            number = float(value if value is not None else 0.0)  # type: ignore[arg-type]
        except TypeError, ValueError:
            return str(value)
        text = fixed_decimal(number, 2)
        return text if float(text) == number else str(number)

    def clear_form(self):
        """Clear the form fields and reset button states."""
        if self.confirm_discard_edits():
            self._set_form_cleared(clear_selection=True)

    def _set_form_cleared(self, *, clear_selection: bool) -> None:
        self.code_edit.clear()
        self.code_edit.setReadOnly(False)
        self.code_edit.setStyleSheet("")
        self.name_edit.clear()
        self.tunch_edit.clear()
        self.purity_edit.clear()
        self.wage_type_combo.setCurrentIndex(0)
        self.wage_rate_edit.clear()

        # Switch form panel back to add mode
        self._form_heading.setText("New Item")
        self._set_form_heading_mode("new")
        self.add_button.setVisible(True)
        self.update_button.setVisible(False)
        # Nothing to delete while a new item is being typed.
        self.delete_button.setEnabled(False)
        self.delete_button.setVisible(False)
        self._delete_separator.setVisible(False)

        self._clear_form_error()
        self._clean_form = self._form_values()
        if clear_selection:
            self.items_table.clearSelection()
            self.items_table.setCurrentIndex(QModelIndex())
        self._clean_form = self._form_values()
        self._update_dirty_label()
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
        tunch = self.tunch_edit.text().strip() or None
        purity = self._parse_float(self.purity_edit.text(), 0.0)
        wage_type = self.wage_type_combo.currentData()
        wage_rate = self._parse_float(self.wage_rate_edit.text(), 0.0)

        try:
            validated = validate_item(
                code=code,
                name=name,
                purity=purity,
                wage_type=wage_type,
                wage_rate=wage_rate,
                tunch=tunch,
            )
        except ItemValidationError as exc:
            self._show_form_error(str(exc), self._field_for_error(str(exc)))
            return

        if self.db_manager.get_item_by_code(validated.code):
            self._show_form_error(
                f"Code '{validated.code}' is already in use. Pick it in the list "
                "to edit that item, or enter a different code.",
                self.code_edit,
            )
            return
        self._clear_form_error()

        success = self.db_manager.add_item(
            validated.code,
            validated.name,
            validated.purity,
            validated.wage_type,
            validated.wage_rate,
            tunch=validated.tunch,
        )
        if success:
            self.notify(f"Item '{validated.code}' added.", 3000)
            self._clean_form = self._form_values()
            self._set_form_cleared(clear_selection=True)
            self.load_items()
        else:
            QMessageBox.critical(
                self,
                "Item Not Added",
                with_details(
                    f"Item '{validated.code}' could not be added.",
                    getattr(self.db_manager, "last_error", None),
                ),
            )

    def update_item(self):
        """Update an existing item in the database."""
        code = self.code_edit.text().strip()
        name = self.name_edit.text().strip()
        tunch = self.tunch_edit.text().strip() or None
        purity = self._parse_float(self.purity_edit.text(), 0.0)
        wage_type = self.wage_type_combo.currentData()
        wage_rate = self._parse_float(self.wage_rate_edit.text(), 0.0)

        try:
            validated = validate_item(
                code=code,
                name=name,
                purity=purity,
                wage_type=wage_type,
                wage_rate=wage_rate,
                tunch=tunch,
            )
        except ItemValidationError as exc:
            self._show_form_error(str(exc), self._field_for_error(str(exc)))
            return
        self._clear_form_error()

        success = self.db_manager.update_item(
            validated.code,
            validated.name,
            validated.purity,
            validated.wage_type,
            validated.wage_rate,
            tunch=validated.tunch,
        )
        if success:
            self.notify(f"Item '{validated.code}' saved.", 3000)
            self._clean_form = self._form_values()
            self._set_form_cleared(clear_selection=True)
            self.load_items()
        else:
            QMessageBox.critical(
                self,
                "Item Not Saved",
                with_details(
                    f"Changes to item '{validated.code}' could not be saved.",
                    getattr(self.db_manager, "last_error", None),
                ),
            )

    def delete_item(self):
        """Delete an item from the database."""
        code = self.code_edit.text().strip()
        if not code or not self.code_edit.isReadOnly():
            self.notify("Select an item in the list to delete it.", 3000)
            return

        name = self.name_edit.text().strip()
        if confirm_destructive(
            self,
            title="Delete Item",
            heading=f"Delete item {code}?",
            detail=(
                (f"{name}\n\n" if name else "")
                + "Saved estimates keep their own copy of the item details. "
                "This action cannot be undone."
            ),
            action_label="Delete Item",
        ):
            success = self.db_manager.delete_item(code)
            if success:
                self.notify(f"Item '{code}' deleted.", 3000)
                self._clean_form = self._form_values()
                self._set_form_cleared(clear_selection=True)
                self.load_items()
            else:
                QMessageBox.critical(
                    self,
                    "Item Not Deleted",
                    with_details(
                        f"Item '{code}' could not be deleted.",
                        getattr(self.db_manager, "last_error", None),
                    ),
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
        if not self.confirm_discard_edits():
            event.ignore()
            return
        self._cancel_active_loads()
        super().closeEvent(event)
