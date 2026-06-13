"""UI builder for silver-bar management."""

from __future__ import annotations

import os
from typing import cast

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QKeySequence, QShortcut
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QSplitter,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from silverestimate.ui.models import (
    AvailableSilverBarsTableModel,
    SelectedListSilverBarsTableModel,
)
from silverestimate.ui.modern_components import BottomStatusStrip, polish_dense_table
from silverestimate.ui.shared_screen_theme import build_management_screen_stylesheet
from silverestimate.ui.themed_controls import ThemedComboBox
from silverestimate.ui.window_sizing import resize_to_available_screen

from ._host_proxy import HostProxy


class SilverBarManagementUiBuilder(HostProxy):
    """Build the management dialog widget tree and connect signals."""

    def init_ui(self):
        host_widget = cast(QWidget, self.host)
        self.host.setWindowTitle("Silver Bar Management (v2.0)")
        self.host.setMinimumSize(900, 560)
        resize_to_available_screen(
            host_widget,
            preferred_width=1180,
            preferred_height=760,
        )
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
                    background-color: __SURFACE_BG__;
                    border: 1px solid __CARD_BORDER__;
                    border-radius: 8px;
                }
                QLabel#SilverBarSectionLabel {
                    color: __TEXT_STRONG__;
                    font-size: 10pt;
                    font-weight: 700;
                }
                QLabel#SilverBarListInfoLabel {
                    color: __FIELD_TEXT__;
                    font-weight: 600;
                    padding: 2px 0;
                }
                QLabel#SilverBarBadgeLabel,
                QLabel#SilverBarSummaryLabel {
                    background-color: __HEADER_BG__;
                    border: 1px solid __CARD_BORDER__;
                    border-radius: 6px;
                    color: __HEADER_TEXT__;
                    font-weight: 600;
                    padding: 6px 8px;
                }
                QSplitter::handle {
                    background-color: __CARD_BORDER_SOFT__;
                    width: 6px;
                }
                QPushButton#SilverBarPrimaryButton:disabled,
                QPushButton#SilverBarSecondaryButton:disabled,
                QPushButton#SilverBarDangerButton:disabled {
                    background-color: __HEADER_BG__;
                    border: 1px solid __INPUT_BORDER__;
                    color: __TEXT_MUTED__;
                }
                QTableView#SilverBarListTable[listState="inactive"] {
                    background-color: __HEADER_BG__;
                    border: 1px solid __INPUT_BORDER__;
                    color: __TEXT_MUTED__;
                    gridline-color: __CARD_BORDER_SOFT__;
                    selection-background-color: __CARD_BORDER_SOFT__;
                    selection-color: __TEXT_MUTED__;
                }
                QHeaderView#SilverBarListHeader[listState="inactive"]::section {
                    background-color: __CARD_BORDER_SOFT__;
                    color: __TEXT_MUTED__;
                    border-right: 1px solid __CARD_BORDER__;
                    border-bottom: 1px solid __CARD_BORDER__;
                }
                """,
            )
        )

        main_layout = QVBoxLayout(self.host)
        main_layout.setContentsMargins(12, 12, 12, 0)
        main_layout.setSpacing(10)

        self._splitter = QSplitter(Qt.Orientation.Horizontal, self.host)
        self._splitter.setChildrenCollapsible(False)

        left_widget = QWidget(self.host)
        left_widget.setObjectName("SilverBarManagementPane")
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(10, 10, 10, 10)
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
        self.weight_search_edit.setClearButtonEnabled(True)
        self.weight_search_edit.setMaximumWidth(120)
        self.weight_search_edit.setPlaceholderText("Weight")
        filter_row.addWidget(self.weight_search_edit, 2)
        self.date_range_combo = ThemedComboBox()
        self.date_range_combo.addItems(
            ["Any", "Today", "Last 7 days", "Last 30 days", "This Month"]
        )
        self.date_range_combo.setMinimumWidth(140)
        filter_row.addWidget(self.date_range_combo)

        self.clear_filters_button = QPushButton("Clear Filters")
        filter_row.addWidget(self.clear_filters_button)
        left_layout.addLayout(filter_row)

        self.available_bars_table = QTableView(self.host)
        self.available_bars_table.setObjectName("SilverBarAvailableTable")
        self.available_bars_model = AvailableSilverBarsTableModel(
            self.available_bars_table
        )
        self.available_bars_table.setModel(self.available_bars_model)
        self.available_bars_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.available_bars_table.setSelectionMode(
            QAbstractItemView.SelectionMode.ExtendedSelection
        )
        self.available_bars_table.setSortingEnabled(True)
        self.available_bars_table.setContextMenuPolicy(
            Qt.ContextMenuPolicy.CustomContextMenu
        )
        self.available_bars_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        polish_dense_table(
            self.available_bars_table,
            row_height=28,
            header_height=30,
            show_grid=True,
            hide_vertical_header=True,
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
        center_widget.setFixedWidth(128)
        center_layout = QVBoxLayout(center_widget)
        center_layout.setContentsMargins(6, 12, 6, 12)
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
        right_layout.setContentsMargins(10, 10, 10, 10)
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
        self.list_combo = ThemedComboBox()
        self.list_combo.setMinimumWidth(180)
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
        self.list_info_label.setObjectName("SilverBarListInfoLabel")
        self.list_info_label.setWordWrap(True)
        self.list_details_label = self.list_info_label
        right_layout.addWidget(self.list_info_label)

        self.list_bars_table = QTableView(self.host)
        self.list_bars_table.setObjectName("SilverBarListTable")
        self.list_bars_model = SelectedListSilverBarsTableModel(self.list_bars_table)
        self.list_bars_table.setModel(self.list_bars_model)
        self.list_bars_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.list_bars_table.setSelectionMode(
            QAbstractItemView.SelectionMode.ExtendedSelection
        )
        self.list_bars_table.setSortingEnabled(True)
        self.list_bars_table.setContextMenuPolicy(
            Qt.ContextMenuPolicy.CustomContextMenu
        )
        self.list_bars_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        polish_dense_table(
            self.list_bars_table,
            row_height=28,
            header_height=30,
            show_grid=True,
            hide_vertical_header=True,
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
        self._splitter.setSizes([546, 128, 546])
        main_layout.addWidget(self._splitter, 1)

        self.bottom_status_strip = BottomStatusStrip(self.host)
        self.bottom_status_strip.set_left_items(
            ["F2: Item Search", "Ins: Add Row", "Del: Delete Row", "Ctrl+S: Save", "F9: Print"]
        )
        main_layout.addWidget(self.bottom_status_strip)
        self._update_dialog_status_strip()

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
            available_selection.selectionChanged.connect(
                lambda *_: self._update_dialog_status_strip()
            )
        list_selection = self.list_bars_table.selectionModel()
        if list_selection is not None:
            list_selection.selectionChanged.connect(self._on_selection_changed)
            list_selection.selectionChanged.connect(
                lambda *_: self._update_dialog_status_strip()
            )

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
            print_shortcut = QShortcut(QKeySequence.StandardKey.Print, host_widget)
            print_shortcut.activated.connect(self.print_selected_list)
            cancel_shortcut = QShortcut(QKeySequence.StandardKey.Cancel, host_widget)
            cancel_shortcut.activated.connect(self.reject)
            remove_shortcut = QShortcut(
                QKeySequence.StandardKey.Delete, self.list_bars_table
            )
            remove_shortcut.activated.connect(self.remove_selected_from_list)
            add_shortcut = QShortcut(
                QKeySequence(Qt.Key.Key_Return), self.available_bars_table
            )
            add_shortcut.activated.connect(self.add_selected_to_list)
        except (AttributeError, RuntimeError, TypeError) as exc:
            self.logger.debug("Failed to configure silver bar shortcuts: %s", exc)

        self._restore_ui_state()
        self._update_transfer_buttons_state()

        for model in (self.available_bars_model, self.list_bars_model):
            try:
                model.modelReset.connect(lambda *_: self._update_dialog_status_strip())
                model.rowsInserted.connect(lambda *_: self._update_dialog_status_strip())
                model.rowsRemoved.connect(lambda *_: self._update_dialog_status_strip())
            except (AttributeError, RuntimeError, TypeError) as exc:
                self.logger.debug("Failed to bind silver bar status strip updates: %s", exc)

    def _update_dialog_status_strip(self) -> None:
        strip = getattr(self, "bottom_status_strip", None)
        if strip is None:
            return
        try:
            left_rows = self.available_bars_model.rowCount()
        except Exception:
            left_rows = 0
        try:
            right_rows = self.list_bars_model.rowCount()
        except Exception:
            right_rows = 0
        try:
            user = os.environ.get("USERNAME") or os.environ.get("USER") or "-"
        except Exception:
            user = "-"
        strip.set_right_items(
            [f"Rows: {left_rows} (Left)", f"Rows: {right_rows} (Right)", "Last Saved: -", f"User: {user}"]
        )
