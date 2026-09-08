"""UI builder for silver-bar management."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMenu,
    QPushButton,
    QSplitter,
    QTableView,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from silverestimate.ui.icons import get_icon
from silverestimate.ui.models import (
    AvailableSilverBarsTableModel,
    SelectedListSilverBarsTableModel,
)
from silverestimate.ui.modern_components import (
    BottomStatusStrip,
    install_table_empty_state,
    polish_dense_table,
)
from silverestimate.ui.selection_check_header import SelectionCheckHeader
from silverestimate.ui.shared_screen_theme import build_management_screen_stylesheet
from silverestimate.ui.themed_controls import ThemedComboBox
from silverestimate.ui.toolbar_overflow import ToolbarOverflow
from silverestimate.ui.window_sizing import resize_to_available_screen

if TYPE_CHECKING:
    from .silver_bar_management import SilverBarDialog


class SilverBarManagementUiBuilder:
    """Build the management dialog widget tree and connect signals."""

    def __init__(self, host: SilverBarDialog) -> None:
        self.host = host

    def init_ui(self) -> None:
        host_widget = self.host
        self.host.setWindowTitle("Silver Bar Management")
        self.host.setMinimumSize(800, 420)
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

        self.host._splitter = QSplitter(Qt.Orientation.Horizontal, self.host)
        self.host._splitter.setChildrenCollapsible(False)

        left_widget = QWidget(self.host)
        left_widget.setObjectName("SilverBarManagementPane")
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(10, 10, 10, 10)
        left_layout.setSpacing(8)

        left_header = QHBoxLayout()
        left_title = QLabel("Available Silver Bars")
        left_title.setObjectName("SilverBarSectionLabel")
        self.host.available_header_badge = QLabel("Available: 0")
        self.host.available_header_badge.setObjectName("SilverBarBadgeLabel")
        left_header.addWidget(left_title)
        left_header.addStretch()
        left_header.addWidget(self.host.available_header_badge)
        left_layout.addWidget(ToolbarOverflow(left_header))

        filter_row = QHBoxLayout()
        weight_filter_label = QLabel("Weight")
        weight_filter_label.setObjectName("SilverBarListInfoLabel")
        filter_row.addWidget(weight_filter_label)
        self.host.weight_search_edit = QLineEdit()
        self.host.weight_search_edit.setClearButtonEnabled(True)
        self.host.weight_search_edit.setMaximumWidth(120)
        self.host.weight_search_edit.setPlaceholderText("e.g. 40")
        filter_row.addWidget(self.host.weight_search_edit, 2)
        date_filter_label = QLabel("Added")
        date_filter_label.setObjectName("SilverBarListInfoLabel")
        filter_row.addWidget(date_filter_label)
        self.host.date_range_combo = ThemedComboBox()
        self.host.date_range_combo.addItems(
            ["Any", "Today", "Last 7 days", "Last 30 days", "This Month"]
        )
        self.host.date_range_combo.setMinimumWidth(140)
        filter_row.addWidget(self.host.date_range_combo)

        self.host.clear_filters_button = QPushButton("Clear Filters")
        self.host.clear_filters_button.setIcon(
            get_icon("clear_filters", widget=self.host)
        )
        filter_row.addWidget(self.host.clear_filters_button)
        left_layout.addWidget(ToolbarOverflow(filter_row))

        self.host.available_bars_table = QTableView(self.host)
        self.host.available_bars_table.setObjectName("SilverBarAvailableTable")
        self.host.available_bars_model = AvailableSilverBarsTableModel(
            self.host.available_bars_table
        )
        self.host.available_bars_table.setModel(self.host.available_bars_model)
        self.host.available_bars_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.host.available_bars_table.setSelectionMode(
            QAbstractItemView.SelectionMode.ExtendedSelection
        )
        self.host.available_bars_table.setSortingEnabled(True)
        self.host.available_bars_table.horizontalHeader().setToolTip(
            "Sort loaded rows only. Filters search all records. Up to 20,000 rows are displayed; narrow filters to see more."
        )
        self.host.available_bars_table.setContextMenuPolicy(
            Qt.ContextMenuPolicy.CustomContextMenu
        )
        available_header = self.host.available_bars_table.horizontalHeader()
        available_header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.host.available_bars_table.setColumnWidth(0, 140)
        for column, width in ((1, 78), (2, 72), (3, 82), (4, 94), (5, 82)):
            self.host.available_bars_table.setColumnWidth(column, width)
        polish_dense_table(
            self.host.available_bars_table,
            row_height=28,
            header_height=30,
            show_grid=True,
            hide_vertical_header=True,
        )
        left_layout.addWidget(self.host.available_bars_table, 1)
        self.host._available_empty_state = install_table_empty_state(
            self.host.available_bars_table,
            "No available silver bars match the current filters.",
        )

        self.host.available_totals_label = QLabel("Available Bars: 0")
        self.host.available_selection_label = QLabel(
            "Selected: 0 | Weight: 0.000 g | Fine: 0.000 g"
        )
        left_layout.addWidget(self.host.available_totals_label)
        left_layout.addWidget(self.host.available_selection_label)
        self.host.available_totals_label.setObjectName("SilverBarSummaryLabel")
        self.host.available_selection_label.setObjectName("SilverBarSummaryLabel")

        available_paging_row = QHBoxLayout()
        available_paging_row.addStretch()
        self.host.available_load_more_button = QPushButton("Load more")
        self.host.available_load_more_button.setObjectName("SilverBarSecondaryButton")
        self.host.available_load_more_button.setVisible(False)
        self.host.available_load_more_button.clicked.connect(
            lambda: self.host.load_available_bars(append=True)
        )
        available_paging_row.addWidget(self.host.available_load_more_button)
        left_layout.addLayout(available_paging_row)

        center_widget = QWidget(self.host)
        center_widget.setObjectName("SilverBarTransferPane")
        center_widget.setFixedWidth(160)
        center_layout = QVBoxLayout(center_widget)
        center_layout.setContentsMargins(6, 12, 6, 12)
        center_layout.addStretch()
        self.host.add_to_list_button = QPushButton("Add selected")
        self.host.add_to_list_button.setIcon(get_icon("move_right", widget=self.host))
        self.host.add_all_button = QPushButton("Add all")
        self.host.add_all_button.setIcon(get_icon("move_all_right", widget=self.host))
        self.host.remove_from_list_button = QPushButton("Remove selected")
        self.host.remove_from_list_button.setIcon(
            get_icon("move_left", widget=self.host)
        )
        self.host.remove_all_button = QPushButton("Remove all")
        self.host.remove_all_button.setIcon(get_icon("move_all_left", widget=self.host))
        for button in (self.host.add_to_list_button, self.host.add_all_button):
            button.setObjectName("SilverBarPrimaryButton")
            button.setEnabled(False)
            center_layout.addWidget(button)
        for button in (self.host.remove_from_list_button, self.host.remove_all_button):
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
        self.host.list_header_badge = QLabel("List: 0")
        self.host.list_header_badge.setObjectName("SilverBarBadgeLabel")
        right_header.addWidget(right_title)
        right_header.addStretch()
        right_header.addWidget(self.host.list_header_badge)
        right_layout.addWidget(ToolbarOverflow(right_header))

        list_row = QHBoxLayout()
        self.host.list_combo = ThemedComboBox()
        self.host.list_combo.setMinimumWidth(180)
        list_row.addWidget(self.host.list_combo, 1)
        self.host.create_list_button = QPushButton("New List")
        self.host.create_list_button.setObjectName("SilverBarPrimaryButton")
        self.host.create_list_button.setIcon(get_icon("new", widget=self.host))
        list_row.addWidget(self.host.create_list_button)
        right_layout.addWidget(ToolbarOverflow(list_row))

        self.host.edit_note_button = QPushButton("Edit Note")
        self.host.edit_note_button.setIcon(get_icon("edit_note", widget=self.host))
        self.host.edit_note_button.setObjectName("SilverBarSecondaryButton")
        self.host.edit_note_button.setEnabled(False)
        self.host.delete_list_button = QPushButton("Delete List")
        self.host.delete_list_button.setIcon(get_icon("delete", widget=self.host))
        self.host.delete_list_button.setObjectName("SilverBarDangerButton")
        self.host.delete_list_button.setEnabled(False)
        self.host.mark_issued_button = QPushButton("Mark Issued")
        self.host.mark_issued_button.setIcon(get_icon("mark_issued", widget=self.host))
        self.host.mark_issued_button.setObjectName("SilverBarPrimaryButton")
        self.host.mark_issued_button.setEnabled(False)

        print_row = QHBoxLayout()
        self.host.print_list_button = QPushButton("Print")
        self.host.print_list_button.setIcon(get_icon("print", widget=self.host))
        self.host.print_list_button.setObjectName("SilverBarSecondaryButton")
        self.host.print_list_button.setEnabled(False)
        self.host.export_list_button = QPushButton("Export CSV")
        self.host.export_list_button.setIcon(get_icon("export_csv", widget=self.host))
        self.host.export_list_button.setObjectName("SilverBarSecondaryButton")
        self.host.export_list_button.setEnabled(False)
        self.host.generate_optimal_button = QPushButton("Generate Optimal")
        self.host.generate_optimal_button.setIcon(
            get_icon("generate_optimal", widget=self.host)
        )
        self.host.generate_optimal_button.setObjectName("SilverBarPrimaryButton")
        print_row.addWidget(self.host.print_list_button)
        print_row.addWidget(self.host.generate_optimal_button)
        more = QToolButton(self.host)
        more.setText("More")
        more.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        menu = QMenu(more)
        secondary_buttons = (
            self.host.edit_note_button,
            self.host.export_list_button,
            self.host.delete_list_button,
        )
        secondary_actions = []
        for button in secondary_buttons:
            button.setParent(self.host)
            button.hide()
            action = menu.addAction(button.icon(), button.text())
            action.triggered.connect(button.click)
            secondary_actions.append(action)

        def refresh_secondary_actions():
            for action, button in zip(
                secondary_actions, secondary_buttons, strict=True
            ):
                action.setEnabled(button.isEnabled())

        menu.aboutToShow.connect(refresh_secondary_actions)
        more.setMenu(menu)
        print_row.addWidget(more)
        right_layout.addWidget(ToolbarOverflow(print_row))

        self.host.list_info_label = QLabel("No list selected")
        self.host.list_info_label.setObjectName("SilverBarListInfoLabel")
        self.host.list_info_label.setWordWrap(True)
        self.host.list_details_label = self.host.list_info_label
        right_layout.addWidget(self.host.list_info_label)

        self.host.list_bars_table = QTableView(self.host)
        self.host.list_bars_table.setObjectName("SilverBarListTable")
        self.host.list_bars_model = SelectedListSilverBarsTableModel(
            self.host.list_bars_table
        )
        self.host.list_bars_table.setModel(self.host.list_bars_model)
        self.host.list_bars_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.host.list_bars_table.setSelectionMode(
            QAbstractItemView.SelectionMode.ExtendedSelection
        )
        self.host.list_bars_table.setSortingEnabled(True)
        self.host.list_bars_table.horizontalHeader().setToolTip(
            "Sort loaded rows only. Filters search all records. Up to 20,000 rows are displayed; narrow filters to see more."
        )
        self.host.list_bars_table.setContextMenuPolicy(
            Qt.ContextMenuPolicy.CustomContextMenu
        )
        list_header = self.host.list_bars_table.horizontalHeader()
        list_header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.host.list_bars_table.setColumnWidth(0, 140)
        for column, width in ((1, 78), (2, 72), (3, 82), (4, 94), (5, 82)):
            self.host.list_bars_table.setColumnWidth(column, width)
        polish_dense_table(
            self.host.list_bars_table,
            row_height=28,
            header_height=30,
            show_grid=True,
            hide_vertical_header=True,
        )
        self.host.list_bars_table.horizontalHeader().setObjectName(
            "SilverBarListHeader"
        )
        self.host.list_bars_table.setProperty("listState", "inactive")
        self.host.list_bars_table.horizontalHeader().setProperty(
            "listState", "inactive"
        )
        self.host.list_bars_table.setEnabled(False)
        right_layout.addWidget(self.host.list_bars_table, 1)
        self.host._list_empty_state = install_table_empty_state(
            self.host.list_bars_table,
            "Choose a list, then add silver bars from the available inventory.",
        )

        self.host.list_totals_label = QLabel("List Bars: 0")
        self.host.list_selection_label = QLabel(
            "Selected: 0 | Weight: 0.000 g | Fine: 0.000 g"
        )
        self.host.list_totals_label.setObjectName("SilverBarSummaryLabel")
        self.host.list_selection_label.setObjectName("SilverBarSummaryLabel")
        right_layout.addWidget(self.host.list_totals_label)
        footer = QHBoxLayout()
        footer.addWidget(self.host.list_selection_label, 1)
        footer.addWidget(self.host.mark_issued_button)
        right_layout.addLayout(footer)

        list_paging_row = QHBoxLayout()
        list_paging_row.addStretch()
        self.host.list_load_more_button = QPushButton("Load more")
        self.host.list_load_more_button.setObjectName("SilverBarSecondaryButton")
        self.host.list_load_more_button.setVisible(False)
        self.host.list_load_more_button.clicked.connect(
            lambda: self.host.load_bars_in_selected_list(append=True)
        )
        list_paging_row.addWidget(self.host.list_load_more_button)
        right_layout.addLayout(list_paging_row)

        SelectionCheckHeader(self.host.available_bars_table)
        SelectionCheckHeader(self.host.list_bars_table)
        for label in (
            self.host.available_totals_label,
            self.host.available_selection_label,
            self.host.list_totals_label,
            self.host.list_selection_label,
        ):
            label.setWordWrap(True)
            label.setMinimumWidth(0)
        self.host._splitter.addWidget(left_widget)
        self.host._splitter.addWidget(center_widget)
        self.host._splitter.addWidget(right_widget)
        self.host._splitter.setSizes([530, 154, 530])
        main_layout.addWidget(self.host._splitter, 1)

        self.host.bottom_status_strip = BottomStatusStrip(self.host)
        self.host.bottom_status_strip.set_left_items(
            [
                "Double-click: Transfer selected bar",
                "Ctrl+N: New list",
                "Ctrl+P: Print list",
                "Delete: Remove from list",
            ]
        )
        main_layout.addWidget(self.host.bottom_status_strip)
        self._update_dialog_status_strip()

        self.host._filter_reload_timer = QTimer(self.host)
        self.host._filter_reload_timer.setSingleShot(True)
        self.host._filter_reload_timer.setInterval(180)
        self.host._filter_reload_timer.timeout.connect(self.host.load_available_bars)

        self.host.clear_filters_button.setObjectName("SilverBarSecondaryButton")
        self.host.clear_filters_button.clicked.connect(
            lambda *_: self.host._clear_filters()
        )
        self.host.weight_search_edit.textChanged.connect(
            self.host._schedule_available_reload
        )
        self.host.date_range_combo.currentIndexChanged.connect(
            self.host._schedule_available_reload
        )

        self.host.list_combo.currentIndexChanged.connect(
            lambda *_: self.host.list_selection_changed()
        )
        self.host.create_list_button.clicked.connect(
            lambda *_: self.host.create_new_list()
        )
        self.host.edit_note_button.clicked.connect(
            lambda *_: self.host.edit_list_note()
        )
        self.host.delete_list_button.clicked.connect(
            lambda *_: self.host.delete_selected_list()
        )
        self.host.mark_issued_button.clicked.connect(
            lambda *_: self.host.mark_list_as_issued()
        )
        self.host.print_list_button.clicked.connect(
            lambda *_: self.host.print_selected_list()
        )
        self.host.export_list_button.clicked.connect(
            lambda *_: self.host.export_current_list_to_csv()
        )
        self.host.generate_optimal_button.clicked.connect(
            lambda *_: self.host.generate_optimal_list()
        )

        self.host.add_to_list_button.clicked.connect(
            lambda *_: self.host.add_selected_to_list()
        )
        self.host.add_all_button.clicked.connect(
            lambda *_: self.host.add_all_filtered_to_list()
        )
        self.host.remove_from_list_button.clicked.connect(
            lambda *_: self.host.remove_selected_from_list()
        )
        self.host.remove_all_button.clicked.connect(
            lambda *_: self.host.remove_all_from_list()
        )

        self.host.available_bars_table.customContextMenuRequested.connect(
            self.host._show_available_context_menu
        )
        self.host.list_bars_table.customContextMenuRequested.connect(
            self.host._show_list_context_menu
        )

        available_selection = self.host.available_bars_table.selectionModel()
        if available_selection is not None:
            available_selection.selectionChanged.connect(
                self.host._on_selection_changed
            )
            available_selection.selectionChanged.connect(
                lambda *_: self._update_dialog_status_strip()
            )
        list_selection = self.host.list_bars_table.selectionModel()
        if list_selection is not None:
            list_selection.selectionChanged.connect(self.host._on_selection_changed)
            list_selection.selectionChanged.connect(
                lambda *_: self._update_dialog_status_strip()
            )

        self.host.available_bars_table.doubleClicked.connect(
            lambda _index: self.host.add_selected_to_list()
        )
        self.host.list_bars_table.doubleClicked.connect(
            lambda _index: self.host.remove_selected_from_list()
        )

        self.host.available_bars_table.horizontalHeader().sortIndicatorChanged.connect(
            lambda _col, _order: self.host._save_table_sort_state(
                "available", self.host.available_bars_table
            )
        )
        self.host.list_bars_table.horizontalHeader().sortIndicatorChanged.connect(
            lambda _col, _order: self.host._save_table_sort_state(
                "list", self.host.list_bars_table
            )
        )

        try:
            new_list_shortcut = QShortcut(QKeySequence("Ctrl+N"), host_widget)
            new_list_shortcut.activated.connect(self.host.create_new_list)
            print_shortcut = QShortcut(QKeySequence.StandardKey.Print, host_widget)
            print_shortcut.activated.connect(self.host.print_selected_list)
            cancel_shortcut = QShortcut(QKeySequence.StandardKey.Cancel, host_widget)
            cancel_shortcut.activated.connect(self.host.reject)
            remove_shortcut = QShortcut(
                QKeySequence.StandardKey.Delete, self.host.list_bars_table
            )
            remove_shortcut.activated.connect(self.host.remove_selected_from_list)
            add_shortcut = QShortcut(
                QKeySequence(Qt.Key.Key_Return), self.host.available_bars_table
            )
            add_shortcut.activated.connect(self.host.add_selected_to_list)
        except (AttributeError, RuntimeError, TypeError) as exc:
            self.host.logger.debug("Failed to configure silver bar shortcuts: %s", exc)

        self.host._restore_ui_state()
        self.host._update_transfer_buttons_state()

        for model in (self.host.available_bars_model, self.host.list_bars_model):
            try:
                model.modelReset.connect(lambda *_: self._update_dialog_status_strip())
                model.rowsInserted.connect(
                    lambda *_: self._update_dialog_status_strip()
                )
                model.rowsRemoved.connect(lambda *_: self._update_dialog_status_strip())
            except (AttributeError, RuntimeError, TypeError) as exc:
                self.host.logger.debug(
                    "Failed to bind silver bar status strip updates: %s", exc
                )

    def _update_dialog_status_strip(self) -> None:
        strip = getattr(self.host, "bottom_status_strip", None)
        if strip is None:
            return
        try:
            left_rows = self.host.available_bars_model.rowCount()
        except Exception:
            left_rows = 0
        try:
            right_rows = self.host.list_bars_model.rowCount()
        except Exception:
            right_rows = 0
        try:
            user = os.environ.get("USERNAME") or os.environ.get("USER") or "-"
        except Exception:
            user = "-"
        strip.set_right_items(
            [
                f"Rows: {left_rows} (Left)",
                f"Rows: {right_rows} (Right)",
                "Last Saved: -",
                f"User: {user}",
            ]
        )
