#!/usr/bin/env python
from __future__ import annotations

from dataclasses import dataclass

from PyQt5.QtCore import QEvent, Qt, QTimer
from PyQt5.QtGui import QColor, QKeySequence
from PyQt5.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QShortcut,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QDialog,
)


@dataclass(frozen=True)
class _ItemRecord:
    code: str
    name: str
    purity: float
    wage_type: str
    wage_rate: float
    code_upper: str
    name_upper: str


class ItemSelectionDialog(QDialog):
    """Dialog for selecting an item when code is invalid or ambiguous."""

    def __init__(self, db_manager, search_term, parent=None):
        super().__init__(parent)
        self.db_manager = db_manager
        self.search_term = (search_term or "").strip()
        self._all_items: list[_ItemRecord] = []
        self._filtered_items: list[_ItemRecord] = []

        self._filter_timer = QTimer(self)
        self._filter_timer.setSingleShot(True)
        self._filter_timer.timeout.connect(self._apply_filter_now)

        self.init_ui()
        self._load_all_items()

    def init_ui(self):
        self.setWindowTitle("Select Item")
        self.setMinimumSize(780, 460)
        self.resize(860, 520)
        self.setWindowFlags(self.windowFlags() | Qt.WindowMaximizeButtonHint)

        root = QVBoxLayout(self)
        root.setSpacing(10)

        header_band = QFrame()
        header_band.setObjectName("ItemSelectionHeader")
        header_band.setStyleSheet(
            "QFrame#ItemSelectionHeader {"
            "background: palette(base);"
            "border: 1px solid palette(midlight);"
            "border-radius: 6px;"
            "padding: 4px;"
            "}"
        )
        header_layout = QVBoxLayout(header_band)
        header_layout.setContentsMargins(10, 8, 10, 8)
        header_layout.setSpacing(2)

        title = QLabel("Item Code Not Found")
        title.setStyleSheet("font-weight: 600; font-size: 13px;")
        header_layout.addWidget(title)

        self.subtitle_label = QLabel(
            f"Code '{self.search_term}' was not found. Select the closest item."
        )
        self.subtitle_label.setWordWrap(True)
        header_layout.addWidget(self.subtitle_label)
        root.addWidget(header_band)

        search_layout = QHBoxLayout()
        search_layout.setSpacing(6)

        search_layout.addWidget(QLabel("Search:"))
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Try code prefix or item name")
        self.search_edit.textChanged.connect(self._schedule_filter)
        self.search_edit.returnPressed.connect(self._accept_top_result)
        self.search_edit.installEventFilter(self)
        search_layout.addWidget(self.search_edit, 1)

        self.clear_search_button = QPushButton("Clear")
        self.clear_search_button.clicked.connect(self._clear_search)
        search_layout.addWidget(self.clear_search_button)

        self.result_count_label = QLabel("0 matches")
        self.result_count_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.result_count_label.setMinimumWidth(120)
        search_layout.addWidget(self.result_count_label)
        root.addLayout(search_layout)

        content_layout = QHBoxLayout()
        content_layout.setSpacing(8)

        self.items_table = QTableWidget()
        self.items_table.setColumnCount(3)
        self.items_table.setHorizontalHeaderLabels(["Code", "Name", "Purity"])
        self.items_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.items_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.items_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.items_table.setAlternatingRowColors(True)
        self.items_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.items_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.items_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.items_table.verticalHeader().setDefaultSectionSize(26)
        self.items_table.itemDoubleClicked.connect(self.accept)
        self.items_table.itemSelectionChanged.connect(self._update_detail_panel)
        self.items_table.currentCellChanged.connect(
            lambda *_: self._update_detail_panel()
        )
        content_layout.addWidget(self.items_table, 5)

        details_card = QFrame()
        details_card.setObjectName("ItemSelectionDetails")
        details_card.setStyleSheet(
            "QFrame#ItemSelectionDetails {"
            "border: 1px solid palette(midlight);"
            "border-radius: 6px;"
            "background: palette(base);"
            "}"
        )
        details_card.setMinimumWidth(240)
        details_layout = QVBoxLayout(details_card)
        details_layout.setContentsMargins(10, 10, 10, 10)
        details_layout.setSpacing(8)

        details_title = QLabel("Selected Item")
        details_title.setStyleSheet("font-weight: 600;")
        details_layout.addWidget(details_title)

        grid = QGridLayout()
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(6)
        grid.addWidget(QLabel("Code"), 0, 0)
        self.detail_code = QLabel("-")
        self.detail_code.setTextInteractionFlags(Qt.TextSelectableByMouse)
        grid.addWidget(self.detail_code, 0, 1)

        grid.addWidget(QLabel("Name"), 1, 0)
        self.detail_name = QLabel("-")
        self.detail_name.setWordWrap(True)
        self.detail_name.setTextInteractionFlags(Qt.TextSelectableByMouse)
        grid.addWidget(self.detail_name, 1, 1)

        grid.addWidget(QLabel("Purity"), 2, 0)
        self.detail_purity = QLabel("-")
        grid.addWidget(self.detail_purity, 2, 1)

        grid.addWidget(QLabel("Wage Type"), 3, 0)
        self.detail_wage_type = QLabel("-")
        grid.addWidget(self.detail_wage_type, 3, 1)

        grid.addWidget(QLabel("Wage Rate"), 4, 0)
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
        self.empty_label.setStyleSheet("color: #666; font-style: italic;")
        self.empty_label.hide()
        root.addWidget(self.empty_label)

        footer = QHBoxLayout()
        self.hint_label = QLabel("Enter: Select  Esc: Cancel  Ctrl+F: Search")
        self.hint_label.setStyleSheet("color: #666;")
        footer.addWidget(self.hint_label)
        footer.addStretch(1)

        self.select_button = QPushButton("Select")
        self.select_button.clicked.connect(self._accept_if_selected)
        footer.addWidget(self.select_button)

        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(self.reject)
        footer.addWidget(cancel_button)
        root.addLayout(footer)

        QShortcut(QKeySequence.Find, self, activated=self._focus_search)
        QShortcut(QKeySequence(Qt.Key_Return), self, activated=self._accept_top_result)
        QShortcut(QKeySequence(Qt.Key_Enter), self, activated=self._accept_top_result)

        self.search_edit.setText(self.search_term)
        QTimer.singleShot(0, self._focus_search)

    def _focus_search(self) -> None:
        self.search_edit.setFocus()
        self.search_edit.selectAll()

    def eventFilter(self, watched, event):
        if watched is self.search_edit and event.type() == QEvent.KeyPress:
            if event.key() == Qt.Key_Down:
                if self._filtered_items:
                    target_row = self.items_table.currentRow()
                    if target_row < 0:
                        target_row = 0
                    self.items_table.setFocus()
                    self.items_table.selectRow(target_row)
                    return True
        return super().eventFilter(watched, event)

    def _clear_search(self) -> None:
        self.search_edit.clear()
        self._focus_search()

    def _load_all_items(self) -> None:
        rows = self.db_manager.get_all_items() or []
        loaded: list[_ItemRecord] = []

        for row in rows:
            payload = dict(row) if not isinstance(row, dict) else row
            code = str(payload.get("code", "") or "").strip()
            name = str(payload.get("name", "") or "").strip()
            if not code and not name:
                continue

            try:
                purity = float(payload.get("purity", 0.0) or 0.0)
            except Exception:
                purity = 0.0
            try:
                wage_rate = float(payload.get("wage_rate", 0.0) or 0.0)
            except Exception:
                wage_rate = 0.0

            wage_type = str(payload.get("wage_type", "WT") or "WT").strip().upper()
            if wage_type not in {"WT", "PC"}:
                wage_type = "WT"

            loaded.append(
                _ItemRecord(
                    code=code,
                    name=name,
                    purity=purity,
                    wage_type=wage_type,
                    wage_rate=wage_rate,
                    code_upper=code.upper(),
                    name_upper=name.upper(),
                )
            )

        self._all_items = sorted(loaded, key=lambda item: item.code_upper)
        self._apply_filter_now()

    def _schedule_filter(self, _text) -> None:
        self._filter_timer.start(150)

    def _apply_filter_now(self) -> None:
        self._filtered_items = self._ranked_items(self.search_edit.text())
        self._render_results()

    def _ranked_items(self, text: str) -> list[_ItemRecord]:
        query = (text or "").strip().upper()
        if not query:
            return list(self._all_items)

        scored: list[tuple[int, str, _ItemRecord]] = []
        for item in self._all_items:
            rank = self._rank_for_item(item, query)
            if rank is None:
                continue
            scored.append((rank, item.code_upper, item))

        scored.sort(key=lambda row: (row[0], row[1]))
        return [entry[2] for entry in scored]

    @staticmethod
    def _rank_for_item(item: _ItemRecord, query: str) -> int | None:
        if item.code_upper.startswith(query):
            return 0
        if item.name_upper.startswith(query):
            return 1
        if query in item.code_upper:
            return 2
        if query in item.name_upper:
            return 3
        return None

    def _render_results(self) -> None:
        table = self.items_table
        table.setUpdatesEnabled(False)
        table.blockSignals(True)

        try:
            table.setRowCount(len(self._filtered_items))
            highlight = QColor(255, 246, 196)
            query = (self.search_edit.text() or "").strip().upper()

            for row, item in enumerate(self._filtered_items):
                code_item = QTableWidgetItem(item.code)
                name_item = QTableWidgetItem(item.name)
                purity_item = QTableWidgetItem(f"{item.purity:.2f}")
                purity_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)

                if query:
                    if query in item.code_upper:
                        code_item.setBackground(highlight)
                    if query in item.name_upper:
                        name_item.setBackground(highlight)

                table.setItem(row, 0, code_item)
                table.setItem(row, 1, name_item)
                table.setItem(row, 2, purity_item)

            if self._filtered_items:
                table.selectRow(0)
            else:
                table.clearSelection()
        finally:
            table.blockSignals(False)
            table.setUpdatesEnabled(True)
            table.viewport().update()

        count = len(self._filtered_items)
        self.result_count_label.setText("1 match" if count == 1 else f"{count} matches")
        no_results = count == 0
        self.empty_label.setVisible(no_results)
        self.select_button.setEnabled(not no_results)

        if no_results:
            self.hint_label.setText("No matches. Try fewer letters or check spelling.")
            self._clear_detail_panel()
        else:
            self.hint_label.setText("Enter: Select  Esc: Cancel  Ctrl+F: Search")
            self._update_detail_panel()

    def _clear_detail_panel(self) -> None:
        self.detail_code.setText("-")
        self.detail_name.setText("-")
        self.detail_purity.setText("-")
        self.detail_wage_type.setText("-")
        self.detail_wage_rate.setText("-")

    def _selected_record(self) -> _ItemRecord | None:
        row = self.items_table.currentRow()
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

        if self.items_table.currentRow() < 0:
            self.items_table.selectRow(0)
        self._accept_if_selected()

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
