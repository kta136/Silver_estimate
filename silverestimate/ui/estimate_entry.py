#!/usr/bin/env python
"""Estimate entry widget - refactored to use component architecture."""

from __future__ import annotations

import logging
import threading
import time
import traceback
from typing import TYPE_CHECKING, Dict, Optional

from PyQt5 import sip
from PyQt5.QtCore import QDate, QLocale, QSignalBlocker, Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QColor, QFont, QKeySequence
from PyQt5.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QShortcut,
    QSizePolicy,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from silverestimate.domain.estimate_models import (
    EstimateLine,
    EstimateLineCategory,
    TotalsResult,
)
from silverestimate.infrastructure.settings import get_app_settings
from silverestimate.presenter import (
    EstimateEntryPresenter,
    EstimateEntryViewState,
    LoadedEstimate,
)
from silverestimate.services.estimate_calculator import (
    compute_fine_weight,
    compute_net_weight,
    compute_totals,
    compute_wage_amount,
)
from silverestimate.services.estimate_entry_persistence import (
    EstimateEntryPersistenceService,
)

from .adapters import EstimateTableAdapter
from .estimate_entry_components import (
    EstimateTableView,
    PrimaryActionsBar,
    SecondaryActionsBar,
    TotalsPanel,
    VoucherToolbar,
)
from .estimate_entry_ui import (
    COL_CODE,
    COL_FINE_WT,
    COL_GROSS,
    COL_ITEM_NAME,
    COL_NET_WT,
    COL_PIECES,
    COL_POLY,
    COL_PURITY,
    COL_TYPE,
    COL_WAGE_AMT,
    COL_WAGE_RATE,
    NumericDelegate,
)
from .inline_status import InlineStatusController
from .item_selection_dialog import ItemSelectionDialog
from .view_models import EstimateEntryRowState, EstimateEntryViewModel

if TYPE_CHECKING:
    from silverestimate.ui.print_manager import PrintManager


class EstimateEntryWidget(QWidget):
    """Widget for silver estimate entry and management.

    Refactored to eliminate EstimateLogic mixins. Now implements the full
    EstimateEntryView protocol directly or via components.
    """

    live_rate_fetched = pyqtSignal(object)
    EDITABLE_ENTRY_COLS = (
        COL_CODE,
        COL_GROSS,
        COL_POLY,
        COL_PURITY,
        COL_WAGE_RATE,
        COL_PIECES,
    )

    @staticmethod
    def _normalize_wage_type(value: object) -> str:
        return "PC" if str(value or "").strip().upper() == "PC" else "WT"

    def __init__(self, db_manager, main_window, repository):
        super().__init__()

        self.logger = logging.getLogger(__name__)

        # Core dependencies
        self.db_manager = db_manager
        self.main_window = main_window
        self.presenter = EstimateEntryPresenter(self, repository)
        self.live_rate_fetched.connect(self._apply_refreshed_live_rate)

        # State flags (formerly in _EstimateBaseMixin)
        self.initializing = True
        self._loading_estimate = False
        self._estimate_loaded = False
        self._unsaved_changes = False
        self._unsaved_block = 0
        self._enforcing_code_nav = False
        self.processing_cell = False
        self.current_row = -1
        self.current_column = COL_CODE
        self.last_balance_silver = 0.0
        self.last_balance_amount = 0.0

        self._table_adapter = None
        self._last_manual_row_nav_ts = 0.0
        self._edit_request_token = 0
        self._manual_row_nav_edit_delay_ms = 35

        # Mode state
        self.return_mode = False
        self.silver_bar_mode = False
        self.view_model = EstimateEntryViewModel()
        self.view_model.set_modes(
            return_mode=self.return_mode,
            silver_bar_mode=self.silver_bar_mode,
        )

        # Column sizing state
        self._use_stretch_for_item_name = False
        self._programmatic_resizing = False
        self._auto_fit_columns_by_content = True
        self._pending_autofit_columns: set[int] = set()
        self._column_autofit_timer = QTimer(self)
        self._column_autofit_timer.setSingleShot(True)
        self._column_autofit_timer.setInterval(70)
        self._column_autofit_timer.timeout.connect(self._apply_pending_column_autofit)

        # Set up UI with components
        self._setup_ui()

        # Restore preferred summary section order
        self._load_totals_section_order_setting()

        # Restore preferred totals panel position (right/left/bottom)
        self._load_totals_position_setting()

        # Initialize table delegates
        self._setup_table_delegates()

        # Column width persistence
        self._column_save_timer = QTimer(self)
        self._column_save_timer.setSingleShot(True)
        self._column_save_timer.setInterval(350)
        self._column_save_timer.timeout.connect(self._save_column_widths_setting)
        self._load_column_widths_setting()

        if self._use_stretch_for_item_name:
            QTimer.singleShot(0, self._auto_stretch_item_name)

        # Status helper
        self._status_helper = InlineStatusController(
            parent=self,
            label_getter=lambda: getattr(self.toolbar, "status_message_label", None),
            logger=self.logger,
        )

        # Initialize with one empty row
        self.clear_all_rows()
        self.add_empty_row()

        # Generate initial voucher number
        if self.presenter:
            try:
                self.presenter.generate_voucher(silent=True)
                self.logger.info("Generated new voucher silently.")
                self.secondary_actions.enable_delete_estimate(False)
                self._estimate_loaded = False
            except Exception as exc:
                self.logger.error(
                    "Error generating voucher number silently: %s", exc, exc_info=True
                )

        # Connect signals
        self.connect_signals(skip_load_estimate=True)
        self._wire_component_signals()

        # Totals calculation timer
        self._totals_timer = QTimer(self)
        self._totals_timer.setSingleShot(True)
        self._totals_timer.setInterval(100)
        self._totals_timer.timeout.connect(self.calculate_totals)

        # Set up keyboard shortcuts
        self._setup_keyboard_shortcuts()

        # Update UI state
        self._on_unsaved_state_changed(False)
        self._update_mode_tooltip()

        # Load font size settings
        self._load_table_font_size_setting()
        self._load_breakdown_font_size_setting()
        self._load_final_calc_font_size_setting()

        # Finish initialization
        self.initializing = False
        QTimer.singleShot(100, self.force_focus_to_first_cell)
        QTimer.singleShot(100, self.reconnect_load_estimate)

    # --- UI Setup -----------------------------------------------------------

    def _setup_ui(self):
        """Set up the user interface using components."""
        layout = QVBoxLayout(self)
        layout.setSpacing(4)
        layout.setContentsMargins(0, 0, 0, 0)

        # Header ribbon
        header_container = QWidget()
        header_container.setObjectName("EstimateHeaderContainer")
        header_container.setStyleSheet("""
            QWidget#EstimateHeaderContainer {
                background-color: palette(base);
                border: 1px solid palette(midlight);
                border-radius: 6px;
            }
            """)
        header_layout = QHBoxLayout(header_container)
        header_layout.setContentsMargins(4, 2, 4, 2)
        header_layout.setSpacing(6)

        self.toolbar = VoucherToolbar()
        self.toolbar.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        header_layout.addWidget(self.toolbar, 5)

        actions_panel = QWidget()
        actions_panel_layout = QHBoxLayout(actions_panel)
        actions_panel_layout.setContentsMargins(0, 0, 0, 0)
        actions_panel_layout.setSpacing(6)

        self.primary_actions = PrimaryActionsBar(shortcut_parent=self)
        self.primary_actions.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        actions_panel_layout.addWidget(self.primary_actions, 1)

        self.secondary_actions = SecondaryActionsBar(shortcut_parent=self)
        self.secondary_actions.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        actions_panel_layout.addWidget(self.secondary_actions, 2)

        header_layout.addWidget(actions_panel, 7)
        layout.addWidget(header_container, 0)

        # Table + summary sidebar row (keeps vertical space dedicated to rows)
        self._content_splitter = QSplitter(Qt.Horizontal)
        self._content_splitter.setChildrenCollapsible(False)
        self._content_splitter.setOpaqueResize(True)

        self.item_table = EstimateTableView()
        self.item_table.host_widget = self
        self.item_table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._content_splitter.addWidget(self.item_table)

        # Totals panel components (sidebar + bottom variants)
        self._totals_panel_sidebar = TotalsPanel(layout_mode="sidebar")
        self._totals_panel_sidebar.setSizePolicy(
            QSizePolicy.Preferred, QSizePolicy.Expanding
        )
        self._totals_panel_sidebar.setMinimumWidth(275)
        self._totals_panel_sidebar.setMaximumWidth(420)

        self._totals_panel_bottom = TotalsPanel(layout_mode="horizontal")
        self._totals_panel_bottom.setSizePolicy(
            QSizePolicy.Expanding, QSizePolicy.Maximum
        )
        self._totals_panel_bottom.setMinimumWidth(0)
        self._totals_panel_bottom.setMaximumWidth(16777215)
        self._totals_panel_bottom.setMaximumHeight(280)

        self.totals_panel = self._totals_panel_sidebar
        self._content_splitter.addWidget(self.totals_panel)

        self._content_splitter.setStretchFactor(0, 1)
        self._content_splitter.setStretchFactor(1, 0)
        self._content_splitter.setSizes([1080, 300])

        layout.addWidget(self._content_splitter, 1)

        # Prioritize vertical space for the table/splitter row.
        layout.setStretch(0, 0)
        layout.setStretch(1, 1)

        # Expose widgets (for legacy method compatibility)
        self.voucher_edit = self.toolbar.voucher_edit
        self.date_edit = self.toolbar.date_edit
        self.note_edit = self.toolbar.note_edit
        self.silver_rate_spin = self.toolbar.silver_rate_spin
        self.load_button = self.toolbar.load_button

        self.save_button = self.primary_actions.save_button
        self.print_button = self.primary_actions.print_button
        self.clear_button = self.primary_actions.new_button
        self.delete_estimate_button = self.secondary_actions.delete_estimate_button
        self.history_button = self.secondary_actions.history_button

        self.delete_row_button = self.secondary_actions.delete_row_button
        self.return_toggle_button = self.secondary_actions.return_button
        self.silver_bar_toggle_button = self.secondary_actions.silver_bar_button
        self.last_balance_button = self.secondary_actions.last_balance_button
        self.silver_bars_button = self.secondary_actions.silver_bars_button
        self.live_rate_label = self.secondary_actions.live_rate_label
        self.live_rate_value_label = self.secondary_actions.live_rate_value_label
        self.live_rate_meta_label = self.secondary_actions.live_rate_meta_label
        self.refresh_rate_button = self.secondary_actions.refresh_rate_button

        self._sync_live_rate_card_placement("right")

        self._bind_totals_panel_labels()

        self.unsaved_badge = self.toolbar.unsaved_badge
        self.status_message_label = self.toolbar.status_message_label

    def _move_live_rate_card_to_summary_top(self) -> None:
        """Place the live-rate card above summary cards in sidebar totals."""
        sidebar_panel = getattr(self, "_totals_panel_sidebar", None)
        live_rate_card = getattr(self.secondary_actions, "live_rate_container", None)
        if sidebar_panel is None or live_rate_card is None:
            return
        try:
            sidebar_panel.set_sidebar_top_widget(live_rate_card)
        except Exception:
            return

        live_rate_divider = getattr(self.secondary_actions, "live_rate_divider", None)
        if live_rate_divider is not None:
            live_rate_divider.setVisible(False)

    def _sync_live_rate_card_placement(self, totals_position: str) -> None:
        """Place live-rate card in sidebar (left/right) or header (bottom)."""
        normalized = self._normalize_totals_position(totals_position)
        sidebar_panel = getattr(self, "_totals_panel_sidebar", None)
        if sidebar_panel is None:
            return

        if normalized == "bottom":
            try:
                sidebar_panel.set_sidebar_top_widget(None)
            except Exception:
                pass
            if hasattr(self.secondary_actions, "show_live_rate_in_header"):
                self.secondary_actions.show_live_rate_in_header(show_divider=True)
            return

        self._move_live_rate_card_to_summary_top()

    def _setup_table_delegates(self):
        """Set up input delegates for table validation."""
        numeric_delegate = NumericDelegate(parent=self.item_table)
        self.item_table.setItemDelegateForColumn(COL_GROSS, numeric_delegate)
        self.item_table.setItemDelegateForColumn(COL_POLY, numeric_delegate)
        self.item_table.setItemDelegateForColumn(COL_PURITY, numeric_delegate)
        self.item_table.setItemDelegateForColumn(COL_WAGE_RATE, numeric_delegate)
        self.item_table.setItemDelegateForColumn(COL_PIECES, numeric_delegate)

        # Set up column widths
        self.item_table.setColumnWidth(COL_CODE, 82)
        self.item_table.setColumnWidth(COL_GROSS, 80)
        self.item_table.setColumnWidth(COL_POLY, 80)
        self.item_table.setColumnWidth(4, 82)  # Net Wt
        self.item_table.setColumnWidth(COL_PURITY, 80)
        self.item_table.setColumnWidth(COL_WAGE_RATE, 82)
        self.item_table.setColumnWidth(COL_PIECES, 60)
        self.item_table.setColumnWidth(8, 82)  # Wage Amt
        self.item_table.setColumnWidth(9, 82)  # Fine Wt
        self.item_table.setColumnWidth(10, 78)  # Type

        # Wire header signals
        header = self.item_table.horizontalHeader()
        header.sectionResized.connect(self._on_item_table_section_resized)

    def _wire_component_signals(self):
        """Wire component signals to handlers."""
        self.toolbar.load_clicked.connect(self.safe_load_estimate)

        self.primary_actions.save_clicked.connect(self.save_estimate)
        self.primary_actions.print_clicked.connect(self.print_estimate)
        self.primary_actions.new_clicked.connect(self.clear_form)

        self.secondary_actions.delete_row_clicked.connect(self.delete_current_row)
        self.secondary_actions.last_balance_clicked.connect(
            self.show_last_balance_dialog
        )
        self.secondary_actions.history_clicked.connect(self.show_history)
        self.secondary_actions.silver_bars_clicked.connect(self.show_silver_bars)
        self.secondary_actions.refresh_rate_clicked.connect(self.refresh_silver_rate)
        self.secondary_actions.delete_estimate_clicked.connect(
            self.delete_current_estimate
        )

        self.item_table.cell_edited.connect(self._on_table_cell_edited)
        self.item_table.column_layout_reset_requested.connect(
            self._reset_columns_layout
        )
        self.item_table.row_deleted.connect(self._on_table_row_delete_requested)
        self.item_table.history_requested.connect(self.show_history)
        self._totals_panel_sidebar.section_order_changed.connect(
            self._on_totals_section_order_changed
        )
        self._totals_panel_bottom.section_order_changed.connect(
            self._on_totals_section_order_changed
        )

    def _bind_totals_panel_labels(self) -> None:
        """Refresh convenience references to totals labels after panel rebuilds."""
        self.mode_indicator_label = self.totals_panel.mode_indicator_label

        self.overall_gross_label = self.totals_panel.overall_gross_label
        self.overall_poly_label = self.totals_panel.overall_poly_label
        self.total_gross_label = self.totals_panel.total_gross_label
        self.total_net_label = self.totals_panel.total_net_label
        self.total_fine_label = self.totals_panel.total_fine_label
        self.return_gross_label = self.totals_panel.return_gross_label
        self.return_net_label = self.totals_panel.return_net_label
        self.return_fine_label = self.totals_panel.return_fine_label
        self.bar_gross_label = self.totals_panel.bar_gross_label
        self.bar_net_label = self.totals_panel.bar_net_label
        self.bar_fine_label = self.totals_panel.bar_fine_label
        self.net_fine_label = self.totals_panel.net_fine_label
        self.net_wage_label = self.totals_panel.net_wage_label
        self.grand_total_label = self.totals_panel.grand_total_label

    def _normalize_totals_position(self, position: str) -> str:
        value = (position or "").strip().lower()
        if value in {"left", "right", "bottom"}:
            return value
        return "right"

    def _normalize_totals_section_order(self, order) -> list[str]:
        return TotalsPanel.normalize_section_order(order)

    def _apply_totals_section_order(
        self, order, *, persist: bool = True, source_panel: TotalsPanel | None = None
    ) -> None:
        normalized = self._normalize_totals_section_order(order)
        for panel in (self._totals_panel_sidebar, self._totals_panel_bottom):
            if panel is None or sip.isdeleted(panel):
                continue
            if panel is source_panel and panel.section_order() == normalized:
                continue
            panel.set_section_order(normalized)
        self._totals_section_order = list(normalized)
        self._bind_totals_panel_labels()

        if persist:
            try:
                self._settings().setValue(
                    "ui/estimate_totals_section_order", ",".join(normalized)
                )
            except Exception as exc:
                self.logger.debug(
                    "Failed to save totals section order setting: %s", exc
                )

    def _load_totals_section_order_setting(self) -> None:
        default_order = ",".join(TotalsPanel.default_section_order())
        try:
            saved = self._settings().value(
                "ui/estimate_totals_section_order",
                defaultValue=default_order,
                type=str,
            )
        except Exception:
            saved = default_order
        self._apply_totals_section_order(saved, persist=False)

    def _on_totals_section_order_changed(self, order) -> None:
        sender = self.sender()
        source_panel = sender if isinstance(sender, TotalsPanel) else None
        self._apply_totals_section_order(order, persist=True, source_panel=source_panel)

    def _apply_totals_position(self, position: str, *, persist: bool = True) -> None:
        normalized = self._normalize_totals_position(position)
        splitter = getattr(self, "_content_splitter", None)
        if splitter is None or sip.isdeleted(splitter):
            return

        sidebar_panel = self._totals_panel_sidebar
        bottom_panel = self._totals_panel_bottom

        if normalized == "bottom":
            if sidebar_panel.parent() is splitter:
                sidebar_panel.setParent(None)
            if bottom_panel.parent() is not splitter:
                splitter.addWidget(bottom_panel)

            splitter.setOrientation(Qt.Vertical)
            splitter.insertWidget(0, self.item_table)
            splitter.insertWidget(1, bottom_panel)
            splitter.setStretchFactor(0, 1)
            splitter.setStretchFactor(1, 0)
            splitter.setSizes([860, 200])
            self.totals_panel = bottom_panel
        else:
            if bottom_panel.parent() is splitter:
                bottom_panel.setParent(None)
            if sidebar_panel.parent() is not splitter:
                splitter.addWidget(sidebar_panel)

            splitter.setOrientation(Qt.Horizontal)
            if normalized == "left":
                splitter.insertWidget(0, sidebar_panel)
                splitter.insertWidget(1, self.item_table)
                splitter.setSizes([320, 1060])
            else:
                splitter.insertWidget(0, self.item_table)
                splitter.insertWidget(1, sidebar_panel)
                splitter.setSizes([1060, 320])
            splitter.setStretchFactor(0, 1)
            splitter.setStretchFactor(1, 0)
            self.totals_panel = sidebar_panel

        self._sync_live_rate_card_placement(normalized)
        self._bind_totals_panel_labels()
        self.calculate_totals()
        self._totals_position = normalized

        if persist:
            try:
                self._settings().setValue("ui/estimate_totals_position", normalized)
            except Exception as exc:
                self.logger.debug("Failed to save totals position setting: %s", exc)

    def _load_totals_position_setting(self) -> None:
        default_position = "right"
        try:
            saved = self._settings().value(
                "ui/estimate_totals_position",
                defaultValue=default_position,
                type=str,
            )
        except Exception:
            saved = default_position
        self._apply_totals_position(saved, persist=False)

    def _on_totals_position_requested(self, position: str) -> None:
        self._apply_totals_position(position, persist=True)

    def apply_totals_position(self, position: str) -> bool:
        """Apply totals panel position preference at runtime."""
        try:
            self._apply_totals_position(position, persist=True)
            return True
        except Exception as exc:
            self.logger.warning("Failed to apply totals position: %s", exc)
            return False

    def connect_signals(self, skip_load_estimate: bool = False):
        """Connect other signals."""
        if not skip_load_estimate:
            self.voucher_edit.returnPressed.connect(self.safe_load_estimate)

        self.silver_rate_spin.valueChanged.connect(self._handle_silver_rate_changed)

        if hasattr(self, "note_edit"):
            self.note_edit.textEdited.connect(self._mark_unsaved)
        if hasattr(self, "date_edit"):
            self.date_edit.dateChanged.connect(self._mark_unsaved)

        # Table signals
        self.item_table.cellClicked.connect(self.cell_clicked)
        self.item_table.itemSelectionChanged.connect(self.selection_changed)
        self.item_table.currentCellChanged.connect(self.current_cell_changed)
        self.item_table.cellChanged.connect(self.handle_cell_changed)

        # Mode toggles
        self.return_toggle_button.clicked.connect(self.toggle_return_mode)
        self.silver_bar_toggle_button.clicked.connect(self.toggle_silver_bar_mode)

    def _setup_keyboard_shortcuts(self):
        pass

    # --- Status & Helper Methods --------------------------------------------

    def show_status(self, message, timeout=3000, level="info"):
        self._status_helper.show(message, timeout=timeout, level=level)

    def show_inline_status(self, message, timeout=3000, level="info"):
        self._status_helper.show(message, timeout=timeout, level=level)

    def _status(self, message, timeout=3000):
        self.show_status(message, timeout)

    def has_unsaved_changes(self) -> bool:
        return bool(getattr(self, "_unsaved_changes", False))

    def _push_unsaved_block(self) -> None:
        self._unsaved_block = getattr(self, "_unsaved_block", 0) + 1

    def _pop_unsaved_block(self) -> None:
        if getattr(self, "_unsaved_block", 0) > 0:
            self._unsaved_block -= 1

    def _set_unsaved(self, dirty: bool, *, force: bool = False) -> None:
        if not force and dirty and getattr(self, "_unsaved_block", 0) > 0:
            return
        previous = getattr(self, "_unsaved_changes", False)
        self._unsaved_changes = dirty
        if previous != dirty or force:
            self._on_unsaved_state_changed(dirty)

    def _mark_unsaved(self, *_, **__) -> None:
        self._set_unsaved(True)

    def _on_unsaved_state_changed(self, dirty: bool) -> None:
        self.toolbar.show_unsaved_badge(dirty)
        if self.main_window and hasattr(self.main_window, "setWindowModified"):
            try:
                self.main_window.setWindowModified(bool(dirty))
            except Exception:
                pass

    def _update_mode_tooltip(self) -> None:
        if self.return_mode:
            mode = "Return Items"
        elif self.silver_bar_mode:
            mode = "Silver Bars"
        else:
            mode = "Regular Items"
        tip = f"Current mode: {mode}\n" "Ctrl+R: Return Items\n" "Ctrl+B: Silver Bars"
        try:
            self.mode_indicator_label.setToolTip(tip)
        except Exception:
            pass

    def _format_currency(self, value):
        try:
            locale = QLocale.system()
            return locale.toCurrencyString(float(round(value)))
        except Exception:
            try:
                return f"₹ {int(round(value)):,}"  # Assuming INR for fallback
            except Exception:
                return str(value)

    # --- Table Methods (formerly _EstimateTableMixin) -----------------------

    def _get_table_adapter(self) -> EstimateTableAdapter:
        if (
            self._table_adapter is None
            or getattr(self._table_adapter, "_table", None) is not self.item_table
        ):
            self._table_adapter = EstimateTableAdapter(self, self.item_table)
        return self._table_adapter

    @property
    def table_adapter(self) -> EstimateTableAdapter:
        """Public adapter accessor for tests and legacy integration points."""
        return self._get_table_adapter()

    def populate_item_row(self, item_data):
        if self.current_row < 0:
            return
        self.populate_row(self.current_row, item_data)

    def add_empty_row(self):
        self._get_table_adapter().add_empty_row()
        self._schedule_columns_autofit()

    def clear_all_rows(self):
        self.item_table.blockSignals(True)
        while self.item_table.rowCount() > 0:
            self.item_table.removeRow(0)
        self.item_table.blockSignals(False)
        self.current_row = -1
        self.current_column = -1
        self._schedule_columns_autofit()

    def _on_table_cell_edited(self, row: int, column: int):
        self._schedule_columns_autofit(columns=[column])
        self.handle_cell_changed(row, column)

    def _on_table_row_delete_requested(self, row: int):
        if row < 0 or row >= self.item_table.rowCount():
            return
        target_col = self.current_column
        if (
            target_col is None
            or target_col < 0
            or target_col >= self.item_table.columnCount()
        ):
            target_col = COL_CODE
        try:
            self.item_table.setCurrentCell(row, target_col)
        except Exception:
            pass
        self.current_row = row
        self.current_column = target_col
        self.delete_current_row()

    def cell_clicked(self, row, column):
        self.current_row = row
        self.current_column = column
        if column in self.EDITABLE_ENTRY_COLS:
            self._request_edit_cell(row, column, delay_ms=0)

    def selection_changed(self):
        index = self.item_table.currentIndex()
        if not index.isValid():
            selected_indexes = self.item_table.selectedIndexes()
            if not selected_indexes:
                return
            index = selected_indexes[0]
        if not index.isValid():
            return
        self.current_row = index.row()
        self.current_column = index.column()

    def current_cell_changed(self, currentRow, currentCol, previousRow, previousCol):
        try:
            mouse_pressed = QApplication.mouseButtons() != Qt.NoButton
        except Exception:
            mouse_pressed = False
        row_changed = (
            previousRow is not None
            and previousRow >= 0
            and currentRow is not None
            and currentRow >= 0
            and currentRow != previousRow
        )
        if row_changed and not mouse_pressed:
            # Arrow-key row navigation often lands here without bubbling keyPressEvent.
            self._mark_manual_row_navigation()
        if not mouse_pressed:
            if not self._enforce_code_required(currentRow, currentCol):
                return
        self.current_row = currentRow
        self.current_column = currentCol
        if (
            currentCol in self.EDITABLE_ENTRY_COLS
            and 0 <= currentRow < self.item_table.rowCount()
        ):
            if row_changed and self._manual_row_nav_recent():
                self._request_edit_cell(
                    currentRow,
                    currentCol,
                    delay_ms=self._manual_row_nav_edit_delay_ms,
                )
                return
            self._request_edit_cell(currentRow, currentCol, delay_ms=0)

    def handle_cell_changed(self, row, column):
        if self.processing_cell:
            return

        self.current_row = row
        self.current_column = column

        self.item_table.blockSignals(True)
        try:
            if column == COL_CODE:
                self.process_item_code()
            elif column in [COL_GROSS, COL_POLY]:
                self.calculate_net_weight()
                self._schedule_auto_advance_from(row, column)
            elif column == COL_PURITY:
                self.calculate_fine()
                self._schedule_auto_advance_from(row, column)
            elif column == COL_WAGE_RATE:
                self.calculate_wage()
                self._schedule_auto_advance_from(row, column)
            elif column == COL_PIECES:
                self.calculate_wage()
                if row == self.item_table.rowCount() - 1:
                    code_item = self.item_table.item(row, COL_CODE)
                    if code_item and code_item.text().strip():
                        QTimer.singleShot(10, self.add_empty_row)
                else:
                    self._schedule_focus_code_from(row, column, row + 1, delay_ms=10)
            else:
                self.calculate_totals()

        except Exception as exc:
            self.logger.error("Error in calculation: %s", exc, exc_info=True)
            self._status(f"Error: {exc}", 5000)
        finally:
            self.item_table.blockSignals(False)
        self._mark_unsaved()

    def _schedule_auto_advance_from(self, row: int, col: int) -> None:
        """Advance only if the user did not navigate away before timer fires."""
        QTimer.singleShot(0, lambda: self._auto_advance_if_origin_unchanged(row, col))

    def _auto_advance_if_origin_unchanged(self, row: int, col: int) -> None:
        if self._manual_row_nav_recent():
            return
        if self.current_row != row or self.current_column != col:
            return
        self.move_to_next_cell()

    def _schedule_focus_code_from(
        self, origin_row: int, origin_col: int, target_row: int, *, delay_ms: int
    ) -> None:
        """Focus next row code only if cursor is still on the originating cell."""
        QTimer.singleShot(
            delay_ms,
            lambda: self._focus_code_if_origin_unchanged(
                origin_row, origin_col, target_row
            ),
        )

    def _focus_code_if_origin_unchanged(
        self, origin_row: int, origin_col: int, target_row: int
    ) -> None:
        if self._manual_row_nav_recent():
            return
        if self.current_row != origin_row or self.current_column != origin_col:
            return
        self.focus_on_code_column(target_row)

    def _mark_manual_row_navigation(self) -> None:
        """Record recent manual row navigation intent (e.g. arrow up/down)."""
        self._last_manual_row_nav_ts = time.monotonic()

    def _manual_row_nav_recent(self, *, threshold_seconds: float = 0.25) -> bool:
        return (time.monotonic() - self._last_manual_row_nav_ts) <= threshold_seconds

    def process_item_code(self):
        if self.processing_cell:
            return
        if self.current_row < 0 or not self.item_table.item(self.current_row, COL_CODE):
            return

        code_item = self.item_table.item(self.current_row, COL_CODE)
        code = code_item.text().strip().upper()
        code_item.setText(code)
        code_item.setData(Qt.UserRole, None)

        if not code:
            self._status("Enter item code first", 1500)
            if self._should_force_code_focus():
                QTimer.singleShot(
                    0, lambda: self.focus_on_code_column(self.current_row)
                )
            return

        if self.presenter is None:
            self._status("Item lookup unavailable; presenter not initialised.", 4000)
            return

        try:
            if self.presenter.handle_item_code(self.current_row, code):
                self._mark_unsaved()
        except Exception as exc:
            self.logger.error(
                "Presenter handle_item_code failed: %s", exc, exc_info=True
            )

    def _is_code_empty(self, row):
        try:
            item = self.item_table.item(row, COL_CODE)
            return (not item) or (not item.text().strip())
        except Exception:
            return True

    def _enforce_code_required(self, target_row, target_col, show_hint=True):
        if self._enforcing_code_nav:
            return True
        try:
            if not self._is_table_valid():
                return True
            if (
                target_row is None
                or target_col is None
                or target_row < 0
                or target_col < 0
            ):
                return True

            if 0 <= self.current_row < self.item_table.rowCount():
                if self._is_code_empty(self.current_row):
                    if target_row != self.current_row or target_col != COL_CODE:
                        if show_hint:
                            self._status("Enter item code first", 1500)
                        self._enforcing_code_nav = True
                        try:
                            self.focus_on_code_column(self.current_row)
                        finally:
                            self._enforcing_code_nav = False
                        return False
        except Exception:
            return True
        return True

    def move_to_next_cell(self):
        if self.processing_cell:
            return

        current_col = self.current_column
        current_row = self.current_row

        if current_row is None or current_row < 0:
            self.focus_on_code_column(0)
            return

        if current_col == COL_CODE and self._is_code_empty(current_row):
            self._status("Enter item code first", 1500)
            self.focus_on_code_column(current_row)
            return

        next_row, next_col = self._next_edit_target(current_row, current_col)

        if next_row >= self.item_table.rowCount():
            last_code_item = self.item_table.item(current_row, COL_CODE)
            if last_code_item and last_code_item.text().strip():
                self.add_empty_row()
                return
            next_row = current_row
            next_col = current_col

        if self._is_table_valid() and 0 <= next_row < self.item_table.rowCount():
            self.item_table.blockSignals(True)
            try:
                self.item_table.setCurrentCell(next_row, next_col)
            finally:
                self.item_table.blockSignals(False)
            if next_col in self.EDITABLE_ENTRY_COLS:
                QTimer.singleShot(10, lambda: self._safe_edit_item(next_row, next_col))

    def move_to_previous_cell(self):
        if self.processing_cell:
            return
        current_col = self.current_column
        current_row = self.current_row

        if current_row is None or current_row < 0:
            self.focus_on_code_column(0)
            return

        prev_row, prev_col = self._previous_edit_target(current_row, current_col)

        if 0 <= prev_row < self.item_table.rowCount():
            self.item_table.setCurrentCell(prev_row, prev_col)
            QTimer.singleShot(10, lambda: self._safe_edit_item(prev_row, prev_col))

    def _next_edit_target(self, row: int, col: int) -> tuple[int, int]:
        """Return next editable cell target for enter/tab-like navigation."""
        if col == COL_CODE:
            return row, COL_GROSS
        if col == COL_GROSS:
            return row, COL_POLY
        if col == COL_POLY:
            return row, COL_PURITY
        if col == COL_PURITY:
            return row, COL_WAGE_RATE
        if col == COL_WAGE_RATE:
            if self._is_pieces_editable_for_row(row):
                return row, COL_PIECES
            return row + 1, COL_CODE
        if col == COL_PIECES:
            return row + 1, COL_CODE
        return row, COL_CODE

    def _previous_edit_target(self, row: int, col: int) -> tuple[int, int]:
        """Return previous editable cell target for shift-tab/backspace navigation."""
        if col == COL_PIECES:
            return row, COL_WAGE_RATE
        if col == COL_WAGE_RATE:
            return row, COL_PURITY
        if col == COL_PURITY:
            return row, COL_POLY
        if col == COL_POLY:
            return row, COL_GROSS
        if col == COL_GROSS:
            return row, COL_CODE
        if col == COL_CODE:
            if row > 0:
                prev_row = row - 1
                if self._is_pieces_editable_for_row(prev_row):
                    return prev_row, COL_PIECES
                return prev_row, COL_WAGE_RATE
            return 0, COL_CODE
        return row, COL_CODE

    def focus_on_code_column(self, row):
        try:
            if sip.isdeleted(self):
                return
        except RuntimeError:
            return

        def _apply_focus(target_row):
            try:
                if not self._is_table_valid():
                    return
                if 0 <= target_row < self.item_table.rowCount():
                    self._ensure_cell_exists(target_row, COL_CODE)
                    self.item_table.blockSignals(True)
                    try:
                        self.item_table.setCurrentCell(target_row, COL_CODE)
                    finally:
                        self.item_table.blockSignals(False)
                    QTimer.singleShot(
                        10, lambda: self._safe_edit_item(target_row, COL_CODE)
                    )
            except Exception:
                pass

        timer = getattr(self, "_code_focus_timer", None)
        if timer is None or sip.isdeleted(timer):
            timer = QTimer(self)
            timer.setSingleShot(True)
            timer.timeout.connect(
                lambda: _apply_focus(getattr(self, "_pending_focus_row", 0))
            )
            self._code_focus_timer = timer
        try:
            timer.stop()
        except RuntimeError:
            return
        self._pending_focus_row = row
        timer.start(0)

    def _safe_edit_item(self, row, col):
        try:
            table = self.item_table
            if not table or sip.isdeleted(table) or not table.isVisible():
                return
            if self._loading_estimate:
                return
            if table.state() == QAbstractItemView.EditingState:
                current = table.currentIndex()
                if (
                    current.isValid()
                    and current.row() == row
                    and current.column() == col
                ):
                    return

            # Use Model/View edit
            model = table.model()
            if model and not sip.isdeleted(model):
                index = model.index(row, col)
                if index.isValid() and (model.flags(index) & Qt.ItemIsEditable):
                    table.setCurrentIndex(index)
                    table.edit(index)
        except Exception:
            pass

    def _is_table_valid(self) -> bool:
        try:
            return self.item_table is not None and not sip.isdeleted(self.item_table)
        except Exception:
            return False

    def _is_pieces_editable_for_row(self, row: int) -> bool:
        if not self._is_table_valid():
            return False
        table = self.item_table
        model = table.model() if table is not None else None
        if model is None:
            return True
        try:
            index = model.index(row, COL_PIECES)
            if not index.isValid():
                return True
            return bool(model.flags(index) & Qt.ItemIsEditable)
        except Exception:
            return True

    def _should_force_code_focus(self) -> bool:
        try:
            table = self.item_table
            if not self._is_table_valid():
                return False
            app = QApplication.instance()
            if not app:
                return True
            focus_widget = app.focusWidget()
            if not focus_widget:
                return True
            if focus_widget is table:
                return True
            if hasattr(table, "isAncestorOf") and table.isAncestorOf(focus_widget):
                return True
            return False
        except Exception:
            return False

    def _ensure_cell_exists(self, row, col, editable=True):
        try:
            item = self.item_table.item(row, col)
            if not item:
                item = QTableWidgetItem("")
                self.item_table.setItem(row, col, item)

            flags = Qt.ItemIsSelectable | Qt.ItemIsEnabled
            if editable:
                flags |= Qt.ItemIsEditable
            item.setFlags(flags)
            return item
        except Exception:
            return None

    def _get_cell_float(self, row, col, default=0.0):
        item = self.item_table.item(row, col)
        text = item.text().strip() if item else ""
        try:
            return float(text.replace(",", ".")) if text else default
        except ValueError:
            return default

    def _get_cell_int(self, row, col, default=1):
        item = self.item_table.item(row, col)
        text = item.text().strip() if item else ""
        try:
            return int(text) if text else default
        except ValueError:
            return default

    def _schedule_cell_edit(self, row, col):
        self._request_edit_cell(row, col, delay_ms=0)

    def _request_edit_cell(self, row: int, col: int, *, delay_ms: int = 0) -> None:
        """Queue a single latest edit request to prevent signal-induced edit storms."""
        self._edit_request_token += 1
        token = self._edit_request_token
        QTimer.singleShot(delay_ms, lambda: self._run_edit_request(token, row, col))

    def _run_edit_request(self, token: int, row: int, col: int) -> None:
        if token != self._edit_request_token:
            return
        if self.processing_cell or self._loading_estimate:
            return
        if not self._is_table_valid():
            return
        if row < 0 or col < 0 or row >= self.item_table.rowCount():
            return
        if col not in self.EDITABLE_ENTRY_COLS:
            return
        cell = self._ensure_cell_exists(row, col)
        if cell and (cell.flags() & Qt.ItemIsEditable):
            self._safe_edit_item(row, col)

    # --- Calculations -------------------------------------------------------

    def calculate_net_weight(self):
        if self.current_row < 0:
            return
        try:
            gross = self._get_cell_float(self.current_row, COL_GROSS)
            poly = self._get_cell_float(self.current_row, COL_POLY)
            net = compute_net_weight(gross, poly)
            net_item = self._ensure_cell_exists(
                self.current_row, COL_NET_WT, editable=False
            )
            net_item.setText(f"{net:.2f}")
            self.calculate_fine()
            self.calculate_wage()
        except Exception:
            pass

    def calculate_fine(self):
        if self.current_row < 0:
            return
        try:
            net = self._get_cell_float(self.current_row, COL_NET_WT)
            purity = self._get_cell_float(self.current_row, COL_PURITY)
            fine = compute_fine_weight(net, purity)
            fine_item = self._ensure_cell_exists(
                self.current_row, COL_FINE_WT, editable=False
            )
            fine_item.setText(f"{fine:.2f}")
            self.calculate_totals()
        except Exception:
            pass

    def calculate_wage(self):
        if self.current_row < 0:
            return
        try:
            net = self._get_cell_float(self.current_row, COL_NET_WT)
            wage_rate = self._get_cell_float(self.current_row, COL_WAGE_RATE)
            pieces = self._get_cell_int(self.current_row, COL_PIECES)

            wage_basis = "WT"
            repo = getattr(self.presenter, "repository", None)
            if repo:
                code_item = self.item_table.item(self.current_row, COL_CODE)
                code = code_item.text().strip() if code_item else ""
                if code:
                    item_data = repo.fetch_item(code)
                    if item_data:
                        wage_basis = item_data.get("wage_type", "WT")

            wage = compute_wage_amount(
                wage_basis,
                net_weight=net,
                wage_rate=wage_rate,
                pieces=pieces,
            )
            wage_item = self._ensure_cell_exists(
                self.current_row, COL_WAGE_AMT, editable=False
            )
            wage_item.setText(f"{wage:.0f}")
            self.calculate_totals()
        except Exception:
            pass

    def calculate_totals(self):
        if self.presenter:
            try:
                self.presenter.refresh_totals()
            except Exception:
                pass

        state = self.capture_state()
        totals = compute_totals(
            state.lines,
            silver_rate=state.silver_rate,
            last_balance_silver=state.last_balance_silver,
            last_balance_amount=state.last_balance_amount,
        )
        self.apply_totals(totals)

    # --- Persistence & Presenter Interactions -------------------------------

    def generate_voucher(self):
        try:
            self.voucher_edit.returnPressed.disconnect(self.safe_load_estimate)
        except TypeError:
            pass

        if self.presenter:
            self.presenter.generate_voucher()
        if hasattr(self, "delete_estimate_button"):
            self.delete_estimate_button.setEnabled(False)
        self._estimate_loaded = False

        try:
            self.voucher_edit.returnPressed.connect(self.safe_load_estimate)
        except Exception:
            pass

    def load_estimate(self):
        if self.initializing:
            return
        if not self.presenter:
            return

        voucher_no = self.voucher_edit.text().strip()
        if not voucher_no:
            return

        self._status(f"Loading estimate {voucher_no}...", 2000)
        try:
            loaded = self.presenter.load_estimate(voucher_no)
            if loaded:
                if self.apply_loaded_estimate(loaded):
                    self._status(f"Estimate {voucher_no} loaded successfully.", 3000)
            else:
                self._status(
                    f"Estimate {voucher_no} not found. Starting new entry.", 4000
                )
                self._estimate_loaded = False
                if hasattr(self, "delete_estimate_button"):
                    self.delete_estimate_button.setEnabled(False)
                self.focus_on_code_column(0)
        except Exception as exc:
            self._status(f"Error loading estimate: {exc}", 4000)

    def safe_load_estimate(self):
        if self._loading_estimate:
            return
        if self.initializing:
            return

        voucher_text = self.voucher_edit.text().strip()
        if not voucher_text:
            return

        if self.has_unsaved_changes():
            reply = QMessageBox.question(
                self,
                "Discard Unsaved Changes?",
                "You have unsaved changes. Loading another estimate will discard them.\n\nContinue?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if reply != QMessageBox.Yes:
                return

        self._loading_estimate = True
        blocker = QSignalBlocker(self.voucher_edit)
        try:
            self.load_estimate()
        except Exception:
            pass
        finally:
            del blocker
            self._loading_estimate = False

    def save_estimate(self):
        voucher_no = self.voucher_edit.text().strip()
        if not voucher_no:
            QMessageBox.warning(self, "Input Error", "Voucher number is required.")
            return

        if not self.presenter:
            return

        self._status(f"Saving estimate {voucher_no}...", 2000)
        self._update_view_model_snapshot()

        service = EstimateEntryPersistenceService(self.view_model)
        try:
            outcome, preparation = service.execute_save(
                voucher_no=voucher_no,
                date=self.date_edit.date().toString("yyyy-MM-dd"),
                note=(
                    self.note_edit.text().strip() if hasattr(self, "note_edit") else ""
                ),
                presenter=self.presenter,
            )

            if outcome.success:
                self._status(outcome.message, 5000)
                QMessageBox.information(self, "Success", outcome.message)
                self.print_estimate()
                self.clear_form(confirm=False)
            else:
                QMessageBox.critical(self, "Save Error", outcome.message)
                self._status(outcome.message, 5000)
        except Exception as exc:
            QMessageBox.critical(self, "Save Error", str(exc))

    def delete_current_estimate(self):
        voucher_no = self.voucher_edit.text().strip()
        if not voucher_no:
            return

        reply = QMessageBox.warning(
            self,
            "Confirm Delete",
            f"Are you sure you want to delete estimate '{voucher_no}'?",
            QMessageBox.Yes | QMessageBox.Cancel,
            QMessageBox.Cancel,
        )
        if reply == QMessageBox.Yes and self.presenter:
            if self.presenter.delete_estimate(voucher_no):
                self._status(f"Estimate {voucher_no} deleted.", 3000)
                self.clear_form(confirm=False)
            else:
                QMessageBox.warning(self, "Error", "Could not delete estimate.")

    def print_estimate(self):
        from silverestimate.ui.print_manager import PrintManager

        voucher_no = self.voucher_edit.text().strip()
        if not voucher_no:
            return

        current_font = getattr(self.main_window, "print_font", None)
        pm = PrintManager(self.db_manager, print_font=current_font)
        pm.print_estimate(voucher_no, self)

    def clear_form(self, confirm: bool = True):
        if confirm:
            reply = QMessageBox.question(
                self,
                "Confirm New Estimate",
                "Start a new estimate? Unsaved changes will be lost.",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if reply != QMessageBox.Yes:
                return

        self._push_unsaved_block()
        self.item_table.blockSignals(True)
        self.processing_cell = True
        try:
            self.voucher_edit.clear()
            if self.presenter:
                self.presenter.generate_voucher()
            self.date_edit.setDate(QDate.currentDate())
            self.silver_rate_spin.setValue(0)
            if hasattr(self, "note_edit"):
                self.note_edit.clear()

            self.last_balance_silver = 0.0
            self.last_balance_amount = 0.0

            if self.return_mode:
                self.toggle_return_mode()
            if self.silver_bar_mode:
                self.toggle_silver_bar_mode()

            self.clear_all_rows()
            self.add_empty_row()
            self.calculate_totals()

            self._estimate_loaded = False
            if hasattr(self, "delete_estimate_button"):
                self.delete_estimate_button.setEnabled(False)
        finally:
            self.processing_cell = False
            self.item_table.blockSignals(False)
            self._pop_unsaved_block()
            QTimer.singleShot(50, lambda: self.focus_on_code_column(0))
        self._set_unsaved(False, force=True)

    def confirm_exit(self) -> bool:
        if not self.has_unsaved_changes():
            return True
        reply = QMessageBox.question(
            self,
            "Discard Changes?",
            "You have unsaved changes. Exit anyway?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        return reply == QMessageBox.Yes

    # --- Mode Switching & Visuals -------------------------------------------

    def show_history(self):
        if self.presenter:
            self.presenter.open_history()

    def _update_row_type_visuals_direct(self, type_item):
        try:
            if not type_item:
                return

            if self.return_mode:
                type_item.setText("return")
                type_item.setBackground(QColor(255, 200, 200))
            elif self.silver_bar_mode:
                type_item.setText("silver_bar")
                type_item.setBackground(QColor(200, 255, 200))
            else:
                type_item.setText("regular")
                type_item.setBackground(QColor(255, 255, 255))
        except Exception:
            pass

    def _set_row_type_visuals_from_category(self, row, category):
        try:
            type_item = self.item_table.item(row, COL_TYPE)
            if not type_item:
                type_item = QTableWidgetItem("")
                self.item_table.setItem(row, COL_TYPE, type_item)

            if category.is_return():
                type_item.setText("return")
                type_item.setBackground(QColor(255, 200, 200))
            elif category.is_silver_bar():
                type_item.setText("silver_bar")
                type_item.setBackground(QColor(200, 255, 200))
            else:
                type_item.setText("regular")
                type_item.setBackground(QColor(255, 255, 255))
            type_item.setTextAlignment(Qt.AlignCenter)
        except Exception:
            pass

    def toggle_return_mode(self):
        if not self.return_mode and self.silver_bar_mode:
            self.toggle_silver_bar_mode()  # Mutual exclusion

        self.return_mode = not self.return_mode
        self.return_toggle_button.setChecked(self.return_mode)

        if self.return_mode:
            self.return_toggle_button.setText("↩ RETURN ON")
            self.return_toggle_button.setStyleSheet(
                "background-color: #e8f4fd; border: 2px solid #0066cc; font-weight: bold; color: #003d7a;"
            )
            self.mode_indicator_label.setText("Mode: Return Items")
            self.mode_indicator_label.setStyleSheet(
                "font-weight: bold; color: #0066cc;"
            )
        else:
            self.return_toggle_button.setText("↩ Return Items")
            self.return_toggle_button.setStyleSheet("")
            self.mode_indicator_label.setText("Mode: Regular")
            self.mode_indicator_label.setStyleSheet("")

        self._get_table_adapter().refresh_empty_row_type()
        self.focus_on_empty_row(update_visuals=True)
        self.view_model.set_modes(
            return_mode=self.return_mode, silver_bar_mode=self.silver_bar_mode
        )
        self._update_mode_tooltip()

    def toggle_silver_bar_mode(self):
        if not self.silver_bar_mode and self.return_mode:
            self.toggle_return_mode()

        self.silver_bar_mode = not self.silver_bar_mode
        self.silver_bar_toggle_button.setChecked(self.silver_bar_mode)

        if self.silver_bar_mode:
            self.silver_bar_toggle_button.setText("🥈 BAR ON")
            self.silver_bar_toggle_button.setStyleSheet(
                "background-color: #fff4e6; border: 2px solid #cc6600; font-weight: bold; color: #994d00;"
            )
            self.mode_indicator_label.setText("Mode: Silver Bars")
            self.mode_indicator_label.setStyleSheet(
                "font-weight: bold; color: #cc6600;"
            )
        else:
            self.silver_bar_toggle_button.setText("🥈 Silver Bars")
            self.silver_bar_toggle_button.setStyleSheet("")
            self.mode_indicator_label.setText("Mode: Regular")
            self.mode_indicator_label.setStyleSheet("")

        self._get_table_adapter().refresh_empty_row_type()
        self.focus_on_empty_row(update_visuals=True)
        self.view_model.set_modes(
            return_mode=self.return_mode, silver_bar_mode=self.silver_bar_mode
        )
        self._update_mode_tooltip()

    def delete_current_row(self):
        row = self.item_table.currentRow()
        if row < 0:
            return
        if self.item_table.rowCount() <= 1:
            QMessageBox.warning(self, "Error", "Cannot delete the only row.")
            return

        reply = QMessageBox.question(
            self,
            "Delete Row",
            f"Delete row {row+1}?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            self.item_table.removeRow(row)
            self.calculate_totals()
            self._mark_unsaved()
            if self.item_table.rowCount() == 0:
                self.add_empty_row()

            new_row = min(row, self.item_table.rowCount() - 1)
            QTimer.singleShot(
                0, lambda: self.item_table.setCurrentCell(new_row, COL_CODE)
            )

    def focus_on_empty_row(self, update_visuals=False):
        self._get_table_adapter().focus_on_empty_row(update_visuals=update_visuals)

    # --- EstimateEntryView Protocol Implementation --------------------------

    def capture_state(self) -> EstimateEntryViewState:
        self._update_view_model_snapshot()
        return self.view_model.as_view_state()

    def apply_totals(self, totals: TotalsResult) -> None:
        self.totals_panel.set_totals(totals)

    def set_voucher_number(self, voucher_no: str) -> None:
        self.voucher_edit.blockSignals(True)
        self.voucher_edit.setText(voucher_no)
        self.voucher_edit.blockSignals(False)

    def populate_row(self, row_index: int, item_data: Dict) -> None:
        self._get_table_adapter().populate_row(row_index, item_data)
        self._schedule_columns_autofit()

    def prompt_item_selection(self, code: str) -> Optional[Dict]:
        dialog = ItemSelectionDialog(self.db_manager, code, self)
        if dialog.exec_() == QDialog.Accepted:
            return dialog.get_selected_item()
        return None

    def focus_after_item_lookup(self, row_index: int) -> None:
        self._schedule_cell_edit(row_index, COL_GROSS)

    def open_history_dialog(self) -> Optional[str]:
        from silverestimate.ui.estimate_history import EstimateHistoryDialog

        dialog = EstimateHistoryDialog(
            self.db_manager, main_window_ref=self.main_window, parent=self
        )
        if dialog.exec_() == QDialog.Accepted:
            return dialog.selected_voucher
        return None

    def show_silver_bar_management(self) -> None:
        if hasattr(self.main_window, "show_silver_bars"):
            self.main_window.show_silver_bars()

    def show_silver_bars(self):
        self.show_silver_bar_management()

    def apply_loaded_estimate(self, loaded: LoadedEstimate) -> bool:
        self._push_unsaved_block()
        self.item_table.blockSignals(True)
        self.processing_cell = True
        try:
            self.clear_all_rows()

            try:
                date = QDate.fromString(loaded.date, "yyyy-MM-dd")
                self.date_edit.setDate(date if date.isValid() else QDate.currentDate())
            except Exception as exc:
                self.logger.debug(
                    "Failed to parse loaded estimate date '%s': %s",
                    loaded.date,
                    exc,
                )
                self.date_edit.setDate(QDate.currentDate())

            self.silver_rate_spin.setValue(loaded.silver_rate)
            if hasattr(self, "note_edit"):
                self.note_edit.setText(loaded.note or "")

            self.last_balance_silver = loaded.last_balance_silver
            self.last_balance_amount = loaded.last_balance_amount

            row_states = EstimateEntryPersistenceService.build_row_states_from_items(
                loaded.items
            )

            for row_state in row_states:
                row = self.item_table.rowCount()
                self.item_table.insertRow(row)

                code_item = QTableWidgetItem(row_state.code.upper())
                code_item.setData(Qt.UserRole, row_state.code)
                self.item_table.setItem(row, COL_CODE, code_item)

                self.item_table.setItem(
                    row, COL_ITEM_NAME, QTableWidgetItem(row_state.name)
                )
                self.item_table.setItem(
                    row, COL_GROSS, QTableWidgetItem(f"{row_state.gross:.2f}")
                )
                self.item_table.setItem(
                    row, COL_POLY, QTableWidgetItem(f"{row_state.poly:.2f}")
                )
                self.item_table.setItem(
                    row, COL_NET_WT, QTableWidgetItem(f"{row_state.net_weight:.2f}")
                )
                self.item_table.setItem(
                    row, COL_PURITY, QTableWidgetItem(f"{row_state.purity:.2f}")
                )
                self.item_table.setItem(
                    row, COL_WAGE_RATE, QTableWidgetItem(f"{row_state.wage_rate:.2f}")
                )
                self.item_table.setItem(
                    row, COL_PIECES, QTableWidgetItem(str(row_state.pieces))
                )
                self.item_table.setItem(
                    row, COL_WAGE_AMT, QTableWidgetItem(f"{row_state.wage_amount:.0f}")
                )
                self.item_table.setItem(
                    row, COL_FINE_WT, QTableWidgetItem(f"{row_state.fine_weight:.2f}")
                )

                self._set_row_type_visuals_from_category(row, row_state.category)

                wage_type = "WT"
                repo = getattr(self.presenter, "repository", None)
                if repo:
                    try:
                        item_data = repo.fetch_item(row_state.code)
                    except Exception:
                        item_data = None
                    if item_data and item_data.get("wage_type") is not None:
                        wage_type = self._normalize_wage_type(
                            item_data.get("wage_type")
                        )
                model = self.item_table.get_model()
                model.set_row_wage_type(row, wage_type)
                pieces_item = self.item_table.item(row, COL_PIECES)
                if pieces_item is not None:
                    current_text = pieces_item.text().strip()
                    if wage_type == "WT":
                        pieces_item.setText("0")
                    elif not current_text or current_text == "0":
                        pieces_item.setText("1")

                # Lock calculated cells
                for col in [COL_NET_WT, COL_WAGE_AMT, COL_FINE_WT, COL_TYPE]:
                    item = self.item_table.item(row, col)
                    if item:
                        item.setFlags(item.flags() & ~Qt.ItemIsEditable)

            self.add_empty_row()
            self.calculate_totals()
            self._schedule_columns_autofit()
            self._estimate_loaded = True

            if hasattr(self, "delete_estimate_button"):
                self.delete_estimate_button.setEnabled(True)

            self.set_voucher_number(loaded.voucher_no)
            return True
        except Exception as exc:
            self.logger.error("Failed to apply estimate: %s", exc, exc_info=True)
            return False
        finally:
            self.processing_cell = False
            self.item_table.blockSignals(False)
            self._pop_unsaved_block()
            self._set_unsaved(False, force=True)

    # --- Live Rate ----------------------------------------------------------

    def refresh_silver_rate(self):
        button = getattr(self, "refresh_rate_button", None)
        if button is not None:
            button.setEnabled(False)
        self._status("Refreshing live silver rate...", 2000)

        def worker():
            try:
                from silverestimate.services.dda_rate_fetcher import (
                    fetch_broadcast_rate_exact,
                    fetch_silver_agra_local_mohar_rate,
                )

                rate, _, _ = fetch_broadcast_rate_exact(timeout=7)
                if rate is None:
                    rate, _ = fetch_silver_agra_local_mohar_rate(timeout=7)
                self.live_rate_fetched.emit(rate)
            except Exception as exc:
                self.logger.warning(
                    "Live silver rate refresh failed: %s", exc, exc_info=True
                )
                self.live_rate_fetched.emit(None)

        threading.Thread(target=worker, daemon=True).start()

    def _apply_refreshed_live_rate(self, rate) -> None:
        button = getattr(self, "refresh_rate_button", None)
        if button is not None:
            button.setEnabled(True)
        if rate:
            try:
                gram_rate = float(rate) / 1000.0
            except (TypeError, ValueError):
                gram_rate = None
            if gram_rate is None:
                if hasattr(self, "live_rate_value_label"):
                    self.live_rate_value_label.setText("N/A")
                self._status("Live rate unavailable.", 3000)
                return
            if hasattr(self, "live_rate_value_label"):
                self.live_rate_value_label.setText(f"₹ {gram_rate:.2f} /g")
            self._status("Live rate refreshed.", 2000)
            return
        if hasattr(self, "live_rate_value_label"):
            self.live_rate_value_label.setText("N/A")
        self._status("Live rate unavailable.", 3000)

    def _handle_silver_rate_changed(self, *_):
        self.calculate_totals()
        self._mark_unsaved()

    # --- View Model Sync ----------------------------------------------------

    def _update_view_model_snapshot(self):
        rows = []
        table = self.item_table
        for row in range(table.rowCount()):
            try:
                type_item = table.item(row, COL_TYPE)
                category = EstimateLineCategory.from_label(
                    type_item.text() if type_item else None
                )

                rows.append(
                    EstimateEntryRowState(
                        code=self._get_row_code(row),
                        name=self._get_cell_str(row, COL_ITEM_NAME),
                        gross=self._get_cell_float(row, COL_GROSS),
                        poly=self._get_cell_float(row, COL_POLY),
                        net_weight=self._get_cell_float(row, COL_NET_WT),
                        purity=self._get_cell_float(row, COL_PURITY),
                        wage_rate=self._get_cell_float(row, COL_WAGE_RATE),
                        pieces=self._get_cell_int(row, COL_PIECES),
                        wage_amount=self._get_cell_float(row, COL_WAGE_AMT),
                        fine_weight=self._get_cell_float(row, COL_FINE_WT),
                        category=category,
                        row_index=row + 1,
                    )
                )
            except Exception as exc:
                self.logger.debug(
                    "Skipping invalid row while syncing view model (row=%s): %s",
                    row,
                    exc,
                )
                continue

        self.view_model.set_rows(rows)
        self.view_model.set_totals_inputs(
            silver_rate=self.silver_rate_spin.value(),
            last_balance_silver=self.last_balance_silver,
            last_balance_amount=self.last_balance_amount,
        )
        self.view_model.set_modes(
            return_mode=self.return_mode, silver_bar_mode=self.silver_bar_mode
        )

    def _get_row_code(self, row):
        item = self.item_table.item(row, COL_CODE)
        if not item:
            return ""
        data = item.data(Qt.UserRole)
        return str(data).strip() if data else item.text().strip()

    def _get_cell_str(self, row, col):
        item = self.item_table.item(row, col)
        return item.text() if item else ""

    # --- Dialogs ------------------------------------------------------------

    def show_last_balance_dialog(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Enter Last Balance")
        layout = QVBoxLayout(dialog)
        form = QFormLayout()

        lb_silver = QDoubleSpinBox()
        lb_silver.setRange(0, 1000000)
        lb_silver.setValue(self.last_balance_silver)
        form.addRow("Silver Weight (g):", lb_silver)

        lb_amount = QDoubleSpinBox()
        lb_amount.setRange(0, 10000000)
        lb_amount.setValue(self.last_balance_amount)
        form.addRow("Amount:", lb_amount)

        layout.addLayout(form)
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(dialog.accept)
        btns.rejected.connect(dialog.reject)
        layout.addWidget(btns)

        if dialog.exec_():
            self.last_balance_silver = lb_silver.value()
            self.last_balance_amount = lb_amount.value()
            self.calculate_totals()
            self._mark_unsaved()

    # --- Column Persistence -------------------------------------------------

    def _settings(self):
        return get_app_settings()

    def _column_width_limits(self) -> Dict[int, tuple[int, int]]:
        """Minimum/maximum widths used by content-driven column sizing."""
        return {
            COL_CODE: (72, 260),
            COL_ITEM_NAME: (120, 900),
            COL_GROSS: (72, 220),
            COL_POLY: (72, 220),
            COL_NET_WT: (78, 220),
            COL_PURITY: (72, 220),
            COL_WAGE_RATE: (78, 220),
            COL_PIECES: (56, 150),
            COL_WAGE_AMT: (78, 220),
            COL_FINE_WT: (78, 220),
            COL_TYPE: (74, 220),
        }

    def _schedule_columns_autofit(
        self, columns: Optional[list[int]] = None, *, delay_ms: int = 70
    ) -> None:
        """Debounce content-based column auto-fit requests."""
        if not getattr(self, "_auto_fit_columns_by_content", False):
            return
        table = getattr(self, "item_table", None)
        if table is None or sip.isdeleted(table):
            return

        if columns is None:
            self._pending_autofit_columns.update(range(table.columnCount()))
        else:
            for col in columns:
                if isinstance(col, int) and 0 <= col < table.columnCount():
                    self._pending_autofit_columns.add(col)

        if not self._pending_autofit_columns:
            return

        try:
            self._column_autofit_timer.setInterval(max(0, int(delay_ms)))
            self._column_autofit_timer.start()
        except Exception as exc:
            self.logger.debug("Failed to schedule column auto-fit: %s", exc)

    def _apply_pending_column_autofit(self) -> None:
        """Resize pending columns to fit current text and header content."""
        if not getattr(self, "_auto_fit_columns_by_content", False):
            return
        if not self._is_table_valid():
            return

        table = self.item_table
        columns = sorted(self._pending_autofit_columns)
        self._pending_autofit_columns.clear()
        if not columns:
            columns = list(range(table.columnCount()))

        model = table.model()
        if model is None or sip.isdeleted(model):
            return

        metrics = table.fontMetrics()
        limits = self._column_width_limits()

        self._programmatic_resizing = True
        try:
            for col in columns:
                if col < 0 or col >= table.columnCount():
                    continue

                header_text = model.headerData(col, Qt.Horizontal, Qt.DisplayRole) or ""
                header_width = metrics.horizontalAdvance(str(header_text)) + 28
                hint_width = table.sizeHintForColumn(col) + 16
                target_width = max(header_width, hint_width)

                min_width, max_width = limits.get(col, (60, 700))
                target_width = max(min_width, min(max_width, int(target_width)))

                current_width = table.columnWidth(col)
                if abs(current_width - target_width) >= 2:
                    table.setColumnWidth(col, target_width)
        except Exception as exc:
            self.logger.debug("Failed to auto-fit columns by content: %s", exc)
        finally:
            self._programmatic_resizing = False

    def _save_column_widths_setting(self):
        if self._auto_fit_columns_by_content:
            return
        try:
            widths = [
                str(self.item_table.columnWidth(i))
                for i in range(self.item_table.columnCount())
            ]
            self._settings().setValue(
                "ui/estimate_table_column_widths", ",".join(widths)
            )
        except Exception as exc:
            self.logger.debug("Failed to save column widths setting: %s", exc)

    def _load_column_widths_setting(self):
        if self._auto_fit_columns_by_content:
            self._use_stretch_for_item_name = False
            self._schedule_columns_autofit(delay_ms=0)
            return

        val = self._settings().value("ui/estimate_table_column_widths", type=str)
        if val:
            try:
                widths = [int(w) for w in val.split(",")]
                for i, w in enumerate(widths):
                    if i < self.item_table.columnCount():
                        self.item_table.setColumnWidth(i, w)
                self._use_stretch_for_item_name = False
            except (TypeError, ValueError) as exc:
                self.logger.debug("Failed to restore column widths setting: %s", exc)
                self._use_stretch_for_item_name = True
        else:
            self._use_stretch_for_item_name = True

    def _on_item_table_section_resized(self, idx, old, new):
        if not self._programmatic_resizing:
            self._use_stretch_for_item_name = False
            self._column_save_timer.start()

    def _auto_stretch_item_name(self):
        if self._auto_fit_columns_by_content:
            return
        if not self._use_stretch_for_item_name:
            return
        total = self.item_table.viewport().width()
        used = sum(
            self.item_table.columnWidth(i)
            for i in range(self.item_table.columnCount())
            if i != COL_ITEM_NAME
        )
        self._programmatic_resizing = True
        self.item_table.setColumnWidth(COL_ITEM_NAME, max(120, total - used - 20))
        self._programmatic_resizing = False

    def resizeEvent(self, event):
        self._auto_stretch_item_name()
        super().resizeEvent(event)

    def closeEvent(self, event):
        if not self.confirm_exit():
            event.ignore()
            return
        self._save_column_widths_setting()
        super().closeEvent(event)

    def _reset_columns_layout(self):
        if self._auto_fit_columns_by_content:
            self._schedule_columns_autofit(delay_ms=0)
            return
        self._settings().remove("ui/estimate_table_column_widths")
        self._use_stretch_for_item_name = True
        self._auto_stretch_item_name()

    # --- Font Sizes ---------------------------------------------------------

    def _load_table_font_size_setting(self):
        size = self._settings().value("ui/table_font_size", defaultValue=9, type=int)
        self.apply_table_font_size(size)

    def _load_breakdown_font_size_setting(self):
        size = self._settings().value(
            "ui/breakdown_font_size", defaultValue=9, type=int
        )
        self.apply_breakdown_font_size(size)

    def _load_final_calc_font_size_setting(self):
        size = self._settings().value(
            "ui/final_calc_font_size", defaultValue=10, type=int
        )
        self.apply_final_calc_font_size(size)

    def apply_table_font_size(self, size: int) -> bool:
        """Apply estimate-table font size at runtime."""
        try:
            size_i = int(size)
        except (TypeError, ValueError):
            self.logger.warning("Invalid table font size value: %r", size)
            return False
        size_i = max(7, min(16, size_i))
        try:
            font = self.item_table.font()
            font.setPointSize(size_i)
            self.item_table.setFont(font)
            row_height = max(20, min(34, size_i + 14))
            self.item_table.verticalHeader().setDefaultSectionSize(row_height)
            self._schedule_columns_autofit(delay_ms=0)
            self.item_table.viewport().update()
            return True
        except Exception as exc:
            self.logger.warning("Failed to apply table font size: %s", exc)
            return False

    def apply_breakdown_font_size(self, size: int) -> bool:
        """Apply totals-breakdown font size at runtime."""
        try:
            size_i = int(size)
        except (TypeError, ValueError):
            self.logger.warning("Invalid breakdown font size value: %r", size)
            return False
        size_i = max(7, min(16, size_i))
        try:
            for panel in (
                getattr(self, "_totals_panel_sidebar", None),
                getattr(self, "_totals_panel_bottom", None),
            ):
                if panel is not None:
                    panel.set_breakdown_font_size(size_i)
            return True
        except Exception as exc:
            self.logger.warning("Failed to apply breakdown font size: %s", exc)
            return False

    def apply_final_calc_font_size(self, size: int) -> bool:
        """Apply final-calculation panel font size at runtime."""
        try:
            size_i = int(size)
        except (TypeError, ValueError):
            self.logger.warning("Invalid final calculation font size value: %r", size)
            return False
        size_i = max(8, min(20, size_i))
        try:
            for panel in (
                getattr(self, "_totals_panel_sidebar", None),
                getattr(self, "_totals_panel_bottom", None),
            ):
                if panel is not None:
                    panel.set_final_calc_font_size(size_i)
            return True
        except Exception as exc:
            self.logger.warning("Failed to apply final calculation font size: %s", exc)
            return False

    # Backward-compatible private aliases still referenced by older callers.
    def _apply_table_font_size(self, size: int) -> bool:
        return self.apply_table_font_size(size)

    def _apply_breakdown_font_size(self, size: int) -> bool:
        return self.apply_breakdown_font_size(size)

    def _apply_final_calc_font_size(self, size: int) -> bool:
        return self.apply_final_calc_font_size(size)

    # --- Keyboard -----------------------------------------------------------

    def keyPressEvent(self, event):
        key = event.key()
        modifiers = event.modifiers()

        if modifiers & Qt.ControlModifier:
            if key == Qt.Key_R:
                self.toggle_return_mode()
                event.accept()
                return
            if key == Qt.Key_B:
                self.toggle_silver_bar_mode()
                event.accept()
                return

        focus_widget = QApplication.focusWidget()
        table_has_focus = focus_widget is self.item_table or (
            focus_widget is not None and self.item_table.isAncestorOf(focus_widget)
        )

        if table_has_focus and key in [Qt.Key_Return, Qt.Key_Enter, Qt.Key_Tab]:
            self.move_to_next_cell()
            event.accept()
        elif table_has_focus and key == Qt.Key_Backtab:
            self.move_to_previous_cell()
            event.accept()
        elif table_has_focus and key in [Qt.Key_Up, Qt.Key_Down]:
            self._mark_manual_row_navigation()
            super().keyPressEvent(event)
        elif table_has_focus and key == Qt.Key_Escape:
            self.confirm_exit()
            event.accept()
        else:
            super().keyPressEvent(event)

    def force_focus_to_first_cell(self):
        if self.item_table.rowCount() > 0:
            self.item_table.setCurrentCell(0, COL_CODE)
            QTimer.singleShot(10, lambda: self._safe_edit_item(0, COL_CODE))

    def reconnect_load_estimate(self):
        try:
            self.voucher_edit.returnPressed.disconnect(self.safe_load_estimate)
        except (TypeError, RuntimeError) as exc:
            self.logger.debug(
                "Could not disconnect voucher returnPressed handler: %s", exc
            )
        self.voucher_edit.returnPressed.connect(self.safe_load_estimate)
