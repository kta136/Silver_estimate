#!/usr/bin/env python
from __future__ import annotations

from PyQt5.QtCore import QEvent, QItemSelectionModel, Qt, QTimer
from PyQt5.QtGui import QKeySequence
from PyQt5.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QShortcut,
    QTableView,
    QVBoxLayout,
)

from silverestimate.ui.models import ItemSelectionRecord, ItemSelectionTableModel
from silverestimate.ui.shared_screen_theme import build_management_screen_stylesheet


class ItemSelectionDialog(QDialog):
    """Dialog for selecting an item when code is invalid or ambiguous."""

    MAX_VISIBLE_RESULTS = 500

    def __init__(self, db_manager, search_term, parent=None):
        super().__init__(parent)
        self.db_manager = db_manager
        self.search_term = (search_term or "").strip()
        self._filtered_items: list[ItemSelectionRecord] = []
        self._results_truncated = False
        self._search_provider = self._selection_search_provider()

        self._filter_timer = QTimer(self)
        self._filter_timer.setSingleShot(True)
        self._filter_timer.timeout.connect(self._apply_filter_now)

        self.init_ui()
        self._apply_filter_now()

    def init_ui(self):
        self.setWindowTitle("Select Item")
        self.setMinimumSize(780, 460)
        self.resize(860, 520)
        self.setWindowFlags(self.windowFlags() | Qt.WindowMaximizeButtonHint)
        self.setObjectName("ItemSelectionDialog")
        self.setStyleSheet(
            build_management_screen_stylesheet(
                root_selector="QDialog#ItemSelectionDialog",
                card_names=["ItemSelectionHeader", "ItemSelectionDetails"],
                title_label="ItemSelectionTitleLabel",
                subtitle_label="ItemSelectionSubtitleLabel",
                field_label="ItemSelectionFieldLabel",
                primary_button="ItemSelectionPrimaryButton",
                secondary_button="ItemSelectionSecondaryButton",
                input_selectors=["QLineEdit"],
                include_table=True,
                extra_rules="""
                QLabel#ItemSelectionBodyLabel {
                    color: #475569;
                    font-size: 9pt;
                }
                QLabel#ItemSelectionMutedLabel {
                    color: #64748b;
                    font-size: 9pt;
                }
                QLabel#ItemSelectionEmptyLabel {
                    color: #64748b;
                    font-style: italic;
                }
                """,
            )
        )

        root = QVBoxLayout(self)
        root.setSpacing(10)
        root.setContentsMargins(12, 12, 12, 12)

        header_band = QFrame()
        header_band.setObjectName("ItemSelectionHeader")
        header_layout = QVBoxLayout(header_band)
        header_layout.setContentsMargins(10, 8, 10, 8)
        header_layout.setSpacing(2)

        title = QLabel("Item Code Not Found")
        title.setObjectName("ItemSelectionTitleLabel")
        header_layout.addWidget(title)

        self.subtitle_label = QLabel(
            f"Code '{self.search_term}' was not found. Select the closest item."
        )
        self.subtitle_label.setObjectName("ItemSelectionSubtitleLabel")
        self.subtitle_label.setWordWrap(True)
        header_layout.addWidget(self.subtitle_label)
        root.addWidget(header_band)

        search_layout = QHBoxLayout()
        search_layout.setSpacing(6)

        search_label = QLabel("Search")
        search_label.setObjectName("ItemSelectionFieldLabel")
        search_layout.addWidget(search_label)
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Try code prefix or item name")
        self.search_edit.textChanged.connect(self._schedule_filter)
        self.search_edit.returnPressed.connect(self._accept_top_result)
        self.search_edit.installEventFilter(self)
        search_layout.addWidget(self.search_edit, 1)

        self.clear_search_button = QPushButton("Clear")
        self.clear_search_button.setObjectName("ItemSelectionSecondaryButton")
        self.clear_search_button.clicked.connect(self._clear_search)
        search_layout.addWidget(self.clear_search_button)

        self.result_count_label = QLabel("0 matches")
        self.result_count_label.setObjectName("ItemSelectionMutedLabel")
        self.result_count_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.result_count_label.setMinimumWidth(120)
        search_layout.addWidget(self.result_count_label)
        root.addLayout(search_layout)

        content_layout = QHBoxLayout()
        content_layout.setSpacing(8)

        self.items_table = QTableView(self)
        self.items_model = ItemSelectionTableModel(self.items_table)
        self.items_table.setModel(self.items_model)
        self.items_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.items_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeToContents
        )
        self.items_table.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.ResizeToContents
        )
        self.items_table.setAlternatingRowColors(True)
        self.items_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.items_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.items_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.items_table.verticalHeader().setDefaultSectionSize(26)
        self.items_table.doubleClicked.connect(lambda *_: self.accept())
        selection_model = self.items_table.selectionModel()
        if selection_model is not None:
            selection_model.selectionChanged.connect(
                lambda *_: self._update_detail_panel()
            )
            selection_model.currentChanged.connect(
                lambda *_: self._update_detail_panel()
            )
        content_layout.addWidget(self.items_table, 5)

        details_card = QFrame()
        details_card.setObjectName("ItemSelectionDetails")
        details_card.setMinimumWidth(240)
        details_layout = QVBoxLayout(details_card)
        details_layout.setContentsMargins(10, 10, 10, 10)
        details_layout.setSpacing(8)

        details_title = QLabel("Selected Item")
        details_title.setObjectName("ItemSelectionFieldLabel")
        details_layout.addWidget(details_title)

        grid = QGridLayout()
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(6)
        code_label = QLabel("Code")
        code_label.setObjectName("ItemSelectionFieldLabel")
        grid.addWidget(code_label, 0, 0)
        self.detail_code = QLabel("-")
        self.detail_code.setTextInteractionFlags(Qt.TextSelectableByMouse)
        grid.addWidget(self.detail_code, 0, 1)

        name_label = QLabel("Name")
        name_label.setObjectName("ItemSelectionFieldLabel")
        grid.addWidget(name_label, 1, 0)
        self.detail_name = QLabel("-")
        self.detail_name.setWordWrap(True)
        self.detail_name.setTextInteractionFlags(Qt.TextSelectableByMouse)
        grid.addWidget(self.detail_name, 1, 1)

        purity_label = QLabel("Purity")
        purity_label.setObjectName("ItemSelectionFieldLabel")
        grid.addWidget(purity_label, 2, 0)
        self.detail_purity = QLabel("-")
        grid.addWidget(self.detail_purity, 2, 1)

        type_label = QLabel("Wage Type")
        type_label.setObjectName("ItemSelectionFieldLabel")
        grid.addWidget(type_label, 3, 0)
        self.detail_wage_type = QLabel("-")
        grid.addWidget(self.detail_wage_type, 3, 1)

        rate_label = QLabel("Wage Rate")
        rate_label.setObjectName("ItemSelectionFieldLabel")
        grid.addWidget(rate_label, 4, 0)
        self.detail_wage_rate = QLabel("-")
        grid.addWidget(self.detail_wage_rate, 4, 1)

        details_layout.addLayout(grid)
        details_layout.addStretch(1)
        content_layout.addWidget(details_card, 2)

        root.addLayout(content_layout, 1)

        self.empty_label = QLabel(
            "No matches found. Try fewer letters or check code spelling."
        )
        self.empty_label.setAlignment(Qt.AlignCenter)
        self.empty_label.setObjectName("ItemSelectionEmptyLabel")
        self.empty_label.hide()
        root.addWidget(self.empty_label)

        footer = QHBoxLayout()
        self.hint_label = QLabel("Enter: Select  Esc: Cancel  Ctrl+F: Search")
        self.hint_label.setObjectName("ItemSelectionMutedLabel")
        footer.addWidget(self.hint_label)
        footer.addStretch(1)

        self.select_button = QPushButton("Select")
        self.select_button.setObjectName("ItemSelectionPrimaryButton")
        self.select_button.clicked.connect(self._accept_if_selected)
        footer.addWidget(self.select_button)

        cancel_button = QPushButton("Cancel")
        cancel_button.setObjectName("ItemSelectionSecondaryButton")
        cancel_button.clicked.connect(self.reject)
        footer.addWidget(cancel_button)
        root.addLayout(footer)

        QShortcut(QKeySequence.Find, self, self._focus_search)
        QShortcut(QKeySequence(Qt.Key_Return), self, self._accept_top_result)
        QShortcut(QKeySequence(Qt.Key_Enter), self, self._accept_top_result)

        self.search_edit.setText(self.search_term)
        QTimer.singleShot(0, self._focus_search)

    def _focus_search(self) -> None:
        self.search_edit.setFocus()
        self.search_edit.selectAll()

    def eventFilter(self, watched, event):
        if watched is self.search_edit and event.type() == QEvent.KeyPress:
            if event.key() == Qt.Key_Down:
                if self._filtered_items:
                    target_row = self._current_row()
                    if target_row < 0:
                        target_row = 0
                    self.items_table.setFocus()
                    self._select_row(target_row)
                    return True
        return super().eventFilter(watched, event)

    def _clear_search(self) -> None:
        self.search_edit.clear()
        self._focus_search()

    def _selection_search_provider(self):
        provider = getattr(self.db_manager, "search_items_for_selection", None)
        if callable(provider):
            return provider
        raise AttributeError(
            "db_manager must implement search_items_for_selection(search_term, limit=...)"
        )

    @staticmethod
    def _coerce_item_record(payload) -> ItemSelectionRecord | None:
        data = dict(payload) if not isinstance(payload, dict) else dict(payload)
        code = str(data.get("code", "") or "").strip()
        name = str(data.get("name", "") or "").strip()
        if not code and not name:
            return None
        try:
            purity = float(data.get("purity", 0.0) or 0.0)
        except Exception:
            purity = 0.0
        try:
            wage_rate = float(data.get("wage_rate", 0.0) or 0.0)
        except Exception:
            wage_rate = 0.0

        wage_type = str(data.get("wage_type", "WT") or "WT").strip().upper()
        if wage_type not in {"WT", "PC"}:
            wage_type = "WT"

        return ItemSelectionRecord(
            code=code,
            name=name,
            purity=purity,
            wage_type=wage_type,
            wage_rate=wage_rate,
            code_upper=code.upper(),
            name_upper=name.upper(),
        )

    def _schedule_filter(self, _text) -> None:
        self._filter_timer.start(150)

    def _apply_filter_now(self) -> None:
        self._filtered_items, self._results_truncated = self._ranked_items_from_db(
            self.search_edit.text(),
            self._search_provider,
        )
        self._render_results()

    def _ranked_items_from_db(
        self, text: str, provider
    ) -> tuple[list[ItemSelectionRecord], bool]:
        rows, truncated = provider(
            text,
            limit=self.MAX_VISIBLE_RESULTS,
        )

        records: list[ItemSelectionRecord] = []
        for row in rows or []:
            record = self._coerce_item_record(row)
            if record is None:
                continue
            records.append(record)
        return records, bool(truncated)

    def _render_results(self) -> None:
        table = self.items_table
        table.setUpdatesEnabled(False)

        try:
            self.items_model.set_rows(
                self._filtered_items,
                query=self.search_edit.text(),
            )
            if self._filtered_items:
                self._select_row(0)
            else:
                table.clearSelection()
        finally:
            table.setUpdatesEnabled(True)
            table.viewport().update()

        count = len(self._filtered_items)
        if self._results_truncated and count > 0:
            self.result_count_label.setText(f"{count}+ matches")
        else:
            self.result_count_label.setText(
                "1 match" if count == 1 else f"{count} matches"
            )
        no_results = count == 0
        self.empty_label.setVisible(no_results)
        self.select_button.setEnabled(not no_results)

        if no_results:
            self.hint_label.setText("No matches. Try fewer letters or check spelling.")
            self._clear_detail_panel()
        else:
            if self._results_truncated:
                self.hint_label.setText(
                    f"Showing top {count} matches. Refine search for more precise results."
                )
            else:
                self.hint_label.setText("Enter: Select  Esc: Cancel  Ctrl+F: Search")
            self._update_detail_panel()

    def _clear_detail_panel(self) -> None:
        self.detail_code.setText("-")
        self.detail_name.setText("-")
        self.detail_purity.setText("-")
        self.detail_wage_type.setText("-")
        self.detail_wage_rate.setText("-")

    def _selected_record(self) -> ItemSelectionRecord | None:
        row = self._current_row()
        if row < 0 or row >= len(self._filtered_items):
            return None
        return self._filtered_items[row]

    def _update_detail_panel(self) -> None:
        record = self._selected_record()
        if record is None:
            self._clear_detail_panel()
            return

        self.detail_code.setText(record.code)
        self.detail_name.setText(record.name)
        self.detail_purity.setText(f"{record.purity:.2f}")
        self.detail_wage_type.setText(record.wage_type)
        self.detail_wage_rate.setText(f"{record.wage_rate:.2f}")

    def _accept_if_selected(self) -> None:
        if self._selected_record() is None:
            self.hint_label.setText("No matches. Try fewer letters or check spelling.")
            return
        self.accept()

    def _accept_top_result(self) -> None:
        if not self._filtered_items:
            self.hint_label.setText("No matches. Try fewer letters or check spelling.")
            return

        if self._current_row() < 0:
            self._select_row(0)
        self._accept_if_selected()

    def _current_row(self) -> int:
        current = self.items_table.currentIndex()
        return current.row() if current.isValid() else -1

    def _select_row(self, row: int) -> None:
        selection_model = self.items_table.selectionModel()
        assert selection_model is not None
        index = self.items_model.index(row, 0)
        if not index.isValid():
            return
        self.items_table.setCurrentIndex(index)
        selection_model.select(
            index,
            QItemSelectionModel.ClearAndSelect | QItemSelectionModel.Rows,
        )

    def get_selected_item(self):
        record = self._selected_record()
        if record is None:
            return None

        return {
            "code": record.code,
            "name": record.name,
            "purity": float(record.purity),
            "wage_type": record.wage_type,
            "wage_rate": float(record.wage_rate),
        }
