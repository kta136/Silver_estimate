"""UI builder for silver-bar management."""

from __future__ import annotations

from typing import cast

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QKeySequence
from PyQt5.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QShortcut,
    QSplitter,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from silverestimate.ui.models import (
    AvailableSilverBarsTableModel,
    SelectedListSilverBarsTableModel,
)
from silverestimate.ui.shared_screen_theme import build_management_screen_stylesheet

from ._host_proxy import HostProxy


class SilverBarManagementUiBuilder(HostProxy):
    """Build the management dialog widget tree and connect signals."""

    def init_ui(self):
        host_widget = cast(QWidget, self.host)
        self.host.setWindowTitle("Silver Bar Management (v2.0)")
        self.host.setMinimumSize(1180, 760)
        host_widget.setObjectName("SilverBarManagementDialog")
        host_widget.setStyleSheet(
            build_management_screen_stylesheet(
                root_selector="QDialog#SilverBarManagementDialog",
                card_names=[],
                title_label="SilverBarManagementTitleLabel",
                subtitle_label="SilverBarManagementSubtitleLabel",
                primary_button="SilverBarPrimaryButton",
                secondary_button="SilverBarSecondaryButton",
                danger_button="SilverBarDangerButton",
                input_selectors=[
                    "QLineEdit",
                    "QComboBox",
                    "QSpinBox",
                    "QDoubleSpinBox",
                ],
                include_table=True,
                extra_rules="""
                QWidget#SilverBarManagementPane,
                QWidget#SilverBarTransferPane {
                    background-color: #ffffff;
                    border: 1px solid #d8e1ec;
                    border-radius: 12px;
                }
                QLabel#SilverBarSectionLabel {
                    color: #0f172a;
                    font-size: 10pt;
                    font-weight: 700;
                }
                QLabel#SilverBarBadgeLabel,
                QLabel#SilverBarSummaryLabel {
                    background-color: #f8fafc;
                    border: 1px solid #d8e1ec;
                    border-radius: 8px;
                    color: #334155;
                    font-weight: 600;
                    padding: 6px 8px;
                }
                QSplitter::handle {
                    background-color: #e2e8f0;
                    width: 6px;
                }
                QPushButton#SilverBarPrimaryButton:disabled,
                QPushButton#SilverBarSecondaryButton:disabled,
                QPushButton#SilverBarDangerButton:disabled {
                    background-color: #e5e7eb;
                    border: 1px solid #cbd5e1;
                    color: #94a3b8;
                }
                QTableView#SilverBarListTable[listState="inactive"] {
                    background-color: #f1f5f9;
                    border: 1px solid #cbd5e1;
                    color: #94a3b8;
                    gridline-color: #e2e8f0;
                    selection-background-color: #e2e8f0;
                    selection-color: #94a3b8;
                }
                QHeaderView#SilverBarListHeader[listState="inactive"]::section {
                    background-color: #e2e8f0;
                    color: #94a3b8;
                    border-right: 1px solid #d8e1ec;
                    border-bottom: 1px solid #d8e1ec;
                }
                """,
            )
        )

        main_layout = QVBoxLayout(self.host)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(12)

        self._splitter = QSplitter(Qt.Horizontal, self.host)
        self._splitter.setChildrenCollapsible(False)

        left_widget = QWidget(self.host)
        left_widget.setObjectName("SilverBarManagementPane")
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(8, 8, 8, 8)
        left_layout.setSpacing(8)

        left_header = QHBoxLayout()
        left_title = QLabel("Available Silver Bars")
        left_title.setObjectName("SilverBarSectionLabel")
        self.available_header_badge = QLabel("Available: 0")
        self.available_header_badge.setObjectName("SilverBarBadgeLabel")
        left_header.addWidget(left_title)
        left_header.addStretch()
        left_header.addWidget(self.available_header_badge)
        left_layout.addLayout(left_header)

        filter_row = QHBoxLayout()
        self.weight_search_edit = QLineEdit()
        self.weight_search_edit.setPlaceholderText("Weight")
        filter_row.addWidget(self.weight_search_edit, 2)
        self.date_range_combo = QComboBox()
        self.date_range_combo.addItems(
            ["Any", "Today", "Last 7 days", "Last 30 days", "This Month"]
        )
        filter_row.addWidget(self.date_range_combo)

        self.clear_filters_button = QPushButton("Clear Filters")
        filter_row.addWidget(self.clear_filters_button)
        left_layout.addLayout(filter_row)

        self.available_bars_table = QTableView(self.host)
        self.available_bars_model = AvailableSilverBarsTableModel(
            self.available_bars_table
        )
        self.available_bars_table.setModel(self.available_bars_model)
        self.available_bars_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.available_bars_table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.available_bars_table.setSortingEnabled(True)
        self.available_bars_table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.available_bars_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.Stretch
        )
        left_layout.addWidget(self.available_bars_table, 1)

        self.available_totals_label = QLabel("Available Bars: 0")
        self.available_selection_label = QLabel(
            "Selected: 0 | Weight: 0.000 g | Fine: 0.000 g"
        )
        left_layout.addWidget(self.available_totals_label)
        left_layout.addWidget(self.available_selection_label)
        self.available_totals_label.setObjectName("SilverBarSummaryLabel")
        self.available_selection_label.setObjectName("SilverBarSummaryLabel")

        center_widget = QWidget(self.host)
        center_widget.setObjectName("SilverBarTransferPane")
        center_layout = QVBoxLayout(center_widget)
        center_layout.setContentsMargins(12, 12, 12, 12)
        center_layout.addStretch()
        self.add_to_list_button = QPushButton("Add >")
        self.add_all_button = QPushButton("Add All >>")
        self.remove_from_list_button = QPushButton("< Remove")
        self.remove_all_button = QPushButton("<< Remove All")
        for button in (self.add_to_list_button, self.add_all_button):
            button.setObjectName("SilverBarPrimaryButton")
            button.setEnabled(False)
            center_layout.addWidget(button)
        for button in (self.remove_from_list_button, self.remove_all_button):
            button.setObjectName("SilverBarDangerButton")
            button.setEnabled(False)
            center_layout.addWidget(button)
        center_layout.addStretch()

        right_widget = QWidget(self.host)
        right_widget.setObjectName("SilverBarManagementPane")
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(8, 8, 8, 8)
        right_layout.setSpacing(8)

        right_header = QHBoxLayout()
        right_title = QLabel("Lists")
        right_title.setObjectName("SilverBarSectionLabel")
        self.list_header_badge = QLabel("List: 0")
        self.list_header_badge.setObjectName("SilverBarBadgeLabel")
        right_header.addWidget(right_title)
        right_header.addStretch()
        right_header.addWidget(self.list_header_badge)
        right_layout.addLayout(right_header)

        list_row = QHBoxLayout()
        self.list_combo = QComboBox()
        list_row.addWidget(self.list_combo, 1)
        self.create_list_button = QPushButton("New List")
        self.create_list_button.setObjectName("SilverBarPrimaryButton")
        list_row.addWidget(self.create_list_button)
        right_layout.addLayout(list_row)

        action_row = QHBoxLayout()
        self.edit_note_button = QPushButton("Edit Note")
        self.edit_note_button.setObjectName("SilverBarSecondaryButton")
        self.edit_note_button.setEnabled(False)
        self.delete_list_button = QPushButton("Delete List")
        self.delete_list_button.setObjectName("SilverBarDangerButton")
        self.delete_list_button.setEnabled(False)
        self.mark_issued_button = QPushButton("Mark Issued")
        self.mark_issued_button.setObjectName("SilverBarPrimaryButton")
        self.mark_issued_button.setEnabled(False)
        action_row.addWidget(self.edit_note_button)
        action_row.addWidget(self.delete_list_button)
        action_row.addWidget(self.mark_issued_button)
        right_layout.addLayout(action_row)

        print_row = QHBoxLayout()
        self.print_list_button = QPushButton("Print")
        self.print_list_button.setObjectName("SilverBarSecondaryButton")
        self.print_list_button.setEnabled(False)
        self.export_list_button = QPushButton("Export CSV")
        self.export_list_button.setObjectName("SilverBarSecondaryButton")
        self.export_list_button.setEnabled(False)
        self.generate_optimal_button = QPushButton("Generate Optimal")
        self.generate_optimal_button.setObjectName("SilverBarPrimaryButton")
        print_row.addWidget(self.print_list_button)
        print_row.addWidget(self.export_list_button)
        print_row.addWidget(self.generate_optimal_button)
        right_layout.addLayout(print_row)

        self.list_info_label = QLabel("No list selected")
        self.list_details_label = self.list_info_label
        right_layout.addWidget(self.list_info_label)

        self.list_bars_table = QTableView(self.host)
        self.list_bars_table.setObjectName("SilverBarListTable")
        self.list_bars_model = SelectedListSilverBarsTableModel(self.list_bars_table)
        self.list_bars_table.setModel(self.list_bars_model)
        self.list_bars_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.list_bars_table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.list_bars_table.setSortingEnabled(True)
        self.list_bars_table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.list_bars_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.Stretch
        )
        self.list_bars_table.horizontalHeader().setObjectName("SilverBarListHeader")
        self.list_bars_table.setProperty("listState", "inactive")
        self.list_bars_table.horizontalHeader().setProperty("listState", "inactive")
        self.list_bars_table.setEnabled(False)
        right_layout.addWidget(self.list_bars_table, 1)

        self.list_totals_label = QLabel("List Bars: 0")
        self.list_selection_label = QLabel(
            "Selected: 0 | Weight: 0.000 g | Fine: 0.000 g"
        )
        self.list_totals_label.setObjectName("SilverBarSummaryLabel")
        self.list_selection_label.setObjectName("SilverBarSummaryLabel")
        right_layout.addWidget(self.list_totals_label)
        right_layout.addWidget(self.list_selection_label)

        self._splitter.addWidget(left_widget)
        self._splitter.addWidget(center_widget)
        self._splitter.addWidget(right_widget)
        self._splitter.setSizes([520, 120, 520])
        main_layout.addWidget(self._splitter, 1)

        self._filter_reload_timer = QTimer(self.host)
        self._filter_reload_timer.setSingleShot(True)
        self._filter_reload_timer.setInterval(180)
        self._filter_reload_timer.timeout.connect(self.load_available_bars)

        self.clear_filters_button.setObjectName("SilverBarSecondaryButton")
        self.clear_filters_button.clicked.connect(lambda *_: self._clear_filters())
        self.weight_search_edit.textChanged.connect(self._schedule_available_reload)
        self.date_range_combo.currentIndexChanged.connect(
            self._schedule_available_reload
        )

        self.list_combo.currentIndexChanged.connect(
            lambda *_: self.list_selection_changed()
        )
        self.create_list_button.clicked.connect(lambda *_: self.create_new_list())
        self.edit_note_button.clicked.connect(lambda *_: self.edit_list_note())
        self.delete_list_button.clicked.connect(lambda *_: self.delete_selected_list())
        self.mark_issued_button.clicked.connect(lambda *_: self.mark_list_as_issued())
        self.print_list_button.clicked.connect(lambda *_: self.print_selected_list())
        self.export_list_button.clicked.connect(
            lambda *_: self.export_current_list_to_csv()
        )
        self.generate_optimal_button.clicked.connect(
            lambda *_: self.generate_optimal_list()
        )

        self.add_to_list_button.clicked.connect(lambda *_: self.add_selected_to_list())
        self.add_all_button.clicked.connect(lambda *_: self.add_all_filtered_to_list())
        self.remove_from_list_button.clicked.connect(
            lambda *_: self.remove_selected_from_list()
        )
        self.remove_all_button.clicked.connect(lambda *_: self.remove_all_from_list())

        self.available_bars_table.customContextMenuRequested.connect(
            self._show_available_context_menu
        )
        self.list_bars_table.customContextMenuRequested.connect(
            self._show_list_context_menu
        )

        available_selection = self.available_bars_table.selectionModel()
        if available_selection is not None:
            available_selection.selectionChanged.connect(self._on_selection_changed)
        list_selection = self.list_bars_table.selectionModel()
        if list_selection is not None:
            list_selection.selectionChanged.connect(self._on_selection_changed)

        self.available_bars_table.doubleClicked.connect(
            lambda _index: self.add_selected_to_list()
        )
        self.list_bars_table.doubleClicked.connect(
            lambda _index: self.remove_selected_from_list()
        )

        self.available_bars_table.horizontalHeader().sortIndicatorChanged.connect(
            lambda _col, _order: self._save_table_sort_state(
                "available", self.available_bars_table
            )
        )
        self.list_bars_table.horizontalHeader().sortIndicatorChanged.connect(
            lambda _col, _order: self._save_table_sort_state(
                "list", self.list_bars_table
            )
        )

        try:
            new_list_shortcut = QShortcut(QKeySequence("Ctrl+N"), host_widget)
            new_list_shortcut.activated.connect(self.create_new_list)
            print_shortcut = QShortcut(QKeySequence.Print, host_widget)
            print_shortcut.activated.connect(self.print_selected_list)
            cancel_shortcut = QShortcut(QKeySequence.Cancel, host_widget)
            cancel_shortcut.activated.connect(self.reject)
            remove_shortcut = QShortcut(QKeySequence.Delete, self.list_bars_table)
            remove_shortcut.activated.connect(self.remove_selected_from_list)
            add_shortcut = QShortcut(
                QKeySequence(Qt.Key_Return), self.available_bars_table
            )
            add_shortcut.activated.connect(self.add_selected_to_list)
        except (AttributeError, RuntimeError, TypeError) as exc:
            self.logger.debug("Failed to configure silver bar shortcuts: %s", exc)

        self._restore_ui_state()
        self._update_transfer_buttons_state()
