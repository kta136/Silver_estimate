"""UI builder for silver-bar management."""

from __future__ import annotations

from typing import cast

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QKeySequence
from PyQt5.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QShortcut,
    QSpinBox,
    QSplitter,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from silverestimate.infrastructure.settings import get_app_settings
from silverestimate.ui.models import (
    AvailableSilverBarsTableModel,
    SelectedListSilverBarsTableModel,
)

from ._host_proxy import HostProxy


class SilverBarManagementUiBuilder(HostProxy):
    """Build the management dialog widget tree and connect signals."""

    def init_ui(self):
        host_widget = cast(QWidget, self.host)
        self.host.setWindowTitle("Silver Bar Management (v2.0)")
        self.host.setMinimumSize(1180, 760)

        main_layout = QVBoxLayout(self.host)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(12)

        self._splitter = QSplitter(Qt.Horizontal, self.host)
        self._splitter.setChildrenCollapsible(False)

        left_widget = QWidget(self.host)
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(8, 8, 8, 8)
        left_layout.setSpacing(8)

        left_header = QHBoxLayout()
        left_title = QLabel("Available Silver Bars")
        self.available_header_badge = QLabel("Available: 0")
        left_header.addWidget(left_title)
        left_header.addStretch()
        left_header.addWidget(self.available_header_badge)
        left_layout.addLayout(left_header)

        filter_row = QHBoxLayout()
        self.weight_search_edit = QLineEdit()
        self.weight_search_edit.setPlaceholderText("Weight")
        filter_row.addWidget(self.weight_search_edit, 2)

        self.weight_tol_spin = QDoubleSpinBox()
        self.weight_tol_spin.setDecimals(3)
        self.weight_tol_spin.setRange(0.001, 999999.0)
        self.weight_tol_spin.setSingleStep(0.001)
        self.weight_tol_spin.setValue(0.001)
        filter_row.addWidget(self.weight_tol_spin)

        self.purity_min_spin = QDoubleSpinBox()
        self.purity_min_spin.setDecimals(2)
        self.purity_min_spin.setRange(0.0, 100.0)
        self.purity_min_spin.setValue(0.0)
        filter_row.addWidget(self.purity_min_spin)

        self.purity_max_spin = QDoubleSpinBox()
        self.purity_max_spin.setDecimals(2)
        self.purity_max_spin.setRange(0.0, 100.0)
        self.purity_max_spin.setValue(100.0)
        filter_row.addWidget(self.purity_max_spin)
        left_layout.addLayout(filter_row)

        controls_row = QHBoxLayout()
        self.date_range_combo = QComboBox()
        self.date_range_combo.addItems(
            ["Any", "Today", "Last 7 days", "Last 30 days", "This Month"]
        )
        controls_row.addWidget(self.date_range_combo)

        self.available_limit_spin = QSpinBox()
        self.available_limit_spin.setRange(100, 10000)
        saved_limit = get_app_settings().value(
            "silver_bar/available_max_rows", defaultValue=1500, type=int
        )
        self.available_limit_spin.setValue(max(100, int(saved_limit or 1500)))
        controls_row.addWidget(self.available_limit_spin)

        self.refresh_available_button = QPushButton("Refresh")
        controls_row.addWidget(self.refresh_available_button)

        self.clear_filters_button = QPushButton("Clear Filters")
        controls_row.addWidget(self.clear_filters_button)

        self.auto_refresh_checkbox = QCheckBox("Auto-refresh")
        controls_row.addWidget(self.auto_refresh_checkbox)
        left_layout.addLayout(controls_row)

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

        center_widget = QWidget(self.host)
        center_layout = QVBoxLayout(center_widget)
        center_layout.addStretch()
        self.add_to_list_button = QPushButton("Add >")
        self.add_all_button = QPushButton("Add All >>")
        self.remove_from_list_button = QPushButton("< Remove")
        self.remove_all_button = QPushButton("<< Remove All")
        for button in (
            self.add_to_list_button,
            self.add_all_button,
            self.remove_from_list_button,
            self.remove_all_button,
        ):
            center_layout.addWidget(button)
        center_layout.addStretch()

        right_widget = QWidget(self.host)
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(8, 8, 8, 8)
        right_layout.setSpacing(8)

        right_header = QHBoxLayout()
        right_title = QLabel("Lists")
        self.list_header_badge = QLabel("List: 0")
        right_header.addWidget(right_title)
        right_header.addStretch()
        right_header.addWidget(self.list_header_badge)
        right_layout.addLayout(right_header)

        list_row = QHBoxLayout()
        self.list_combo = QComboBox()
        list_row.addWidget(self.list_combo, 1)
        self.create_list_button = QPushButton("New List")
        list_row.addWidget(self.create_list_button)
        right_layout.addLayout(list_row)

        action_row = QHBoxLayout()
        self.edit_note_button = QPushButton("Edit Note")
        self.delete_list_button = QPushButton("Delete List")
        self.mark_issued_button = QPushButton("Mark Issued")
        action_row.addWidget(self.edit_note_button)
        action_row.addWidget(self.delete_list_button)
        action_row.addWidget(self.mark_issued_button)
        right_layout.addLayout(action_row)

        print_row = QHBoxLayout()
        self.print_list_button = QPushButton("Print")
        self.export_list_button = QPushButton("Export CSV")
        self.generate_optimal_button = QPushButton("Generate Optimal")
        print_row.addWidget(self.print_list_button)
        print_row.addWidget(self.export_list_button)
        print_row.addWidget(self.generate_optimal_button)
        right_layout.addLayout(print_row)

        self.list_info_label = QLabel("No list selected")
        self.list_details_label = self.list_info_label
        right_layout.addWidget(self.list_info_label)

        self.list_bars_table = QTableView(self.host)
        self.list_bars_model = SelectedListSilverBarsTableModel(self.list_bars_table)
        self.list_bars_table.setModel(self.list_bars_model)
        self.list_bars_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.list_bars_table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.list_bars_table.setSortingEnabled(True)
        self.list_bars_table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.list_bars_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.Stretch
        )
        right_layout.addWidget(self.list_bars_table, 1)

        self.list_totals_label = QLabel("List Bars: 0")
        self.list_selection_label = QLabel(
            "Selected: 0 | Weight: 0.000 g | Fine: 0.000 g"
        )
        right_layout.addWidget(self.list_totals_label)
        right_layout.addWidget(self.list_selection_label)

        self._splitter.addWidget(left_widget)
        self._splitter.addWidget(center_widget)
        self._splitter.addWidget(right_widget)
        self._splitter.setSizes([520, 120, 520])
        main_layout.addWidget(self._splitter, 1)

        bottom_row = QHBoxLayout()
        bottom_row.addStretch()
        self.print_bottom_button = QPushButton("Print")
        bottom_row.addWidget(self.print_bottom_button)
        self.close_button = QPushButton("Close")
        bottom_row.addWidget(self.close_button)
        main_layout.addLayout(bottom_row)

        self._auto_refresh_timer = QTimer(self.host)
        self._auto_refresh_timer.setInterval(5000)
        self._auto_refresh_timer.timeout.connect(self.load_available_bars)

        self._filter_reload_timer = QTimer(self.host)
        self._filter_reload_timer.setSingleShot(True)
        self._filter_reload_timer.setInterval(180)
        self._filter_reload_timer.timeout.connect(self.load_available_bars)

        self.refresh_available_button.clicked.connect(
            lambda *_: self.load_available_bars()
        )
        self.clear_filters_button.clicked.connect(lambda *_: self._clear_filters())
        self.auto_refresh_checkbox.toggled.connect(self._toggle_auto_refresh)
        self.weight_search_edit.textChanged.connect(self._schedule_available_reload)
        self.weight_tol_spin.valueChanged.connect(self._schedule_available_reload)
        self.purity_min_spin.valueChanged.connect(self._schedule_available_reload)
        self.purity_max_spin.valueChanged.connect(self._schedule_available_reload)
        self.date_range_combo.currentIndexChanged.connect(
            self._schedule_available_reload
        )
        self.available_limit_spin.valueChanged.connect(
            self._save_available_limit_setting
        )
        self.available_limit_spin.valueChanged.connect(
            lambda *_: self.load_available_bars()
        )

        self.list_combo.currentIndexChanged.connect(
            lambda *_: self.list_selection_changed()
        )
        self.create_list_button.clicked.connect(lambda *_: self.create_new_list())
        self.edit_note_button.clicked.connect(lambda *_: self.edit_list_note())
        self.delete_list_button.clicked.connect(lambda *_: self.delete_selected_list())
        self.mark_issued_button.clicked.connect(lambda *_: self.mark_list_as_issued())
        self.print_list_button.clicked.connect(lambda *_: self.print_selected_list())
        self.print_bottom_button.clicked.connect(lambda *_: self.print_selected_list())
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
        self.close_button.clicked.connect(lambda *_: self.accept())

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
            refresh_shortcut = QShortcut(QKeySequence.Refresh, host_widget)
            refresh_shortcut.activated.connect(self.load_available_bars)
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
        self._toggle_auto_refresh(self.auto_refresh_checkbox.isChecked())
        self._update_transfer_buttons_state()
