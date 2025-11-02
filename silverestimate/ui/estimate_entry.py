#!/usr/bin/env python
"""Estimate entry widget - refactored to use component architecture."""
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QHeaderView, QFrame, QShortcut, QMessageBox, QSizePolicy
)
from PyQt5.QtCore import Qt, QTimer, QSignalBlocker
from PyQt5.QtGui import QKeySequence
from silverestimate.infrastructure.settings import get_app_settings
from .estimate_entry_components import VoucherToolbar, PrimaryActionsBar, SecondaryActionsBar, TotalsPanel, EstimateTableView
from .estimate_entry_ui import NumericDelegate, COL_CODE, COL_ITEM_NAME, COL_GROSS, COL_POLY, COL_PURITY, COL_WAGE_RATE, COL_PIECES
from .estimate_entry_logic import EstimateLogic
from .inline_status import InlineStatusController
from .view_models import EstimateEntryViewModel
from silverestimate.presenter import EstimateEntryPresenter


class EstimateEntryWidget(QWidget, EstimateLogic):
    """Widget for silver estimate entry and management.

    Refactored to use component architecture while maintaining compatibility
    with EstimateLogic mixins. Uses VoucherToolbar, ModeSwitcher, and TotalsPanel
    components. Table remains QTableWidget for now (migration deferred to Phase 4).
    """

    def __init__(self, db_manager, main_window, repository):
        super().__init__()
        EstimateLogic.__init__(self)

        # Core dependencies
        self.db_manager = db_manager
        self.main_window = main_window
        self.presenter = EstimateEntryPresenter(self, repository)

        # State flags
        self.initializing = True
        self._loading_estimate = False
        self._estimate_loaded = False
        self.processing_cell = False
        self.current_row = -1
        self.current_column = COL_CODE

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

        # Set up UI with components
        self._setup_ui()

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

        # Status helper (needed before clear_all_rows)
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
                self.primary_actions.enable_delete_estimate(False)
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

    def _setup_ui(self):
        """Set up the user interface using components."""
        layout = QVBoxLayout(self)
        layout.setSpacing(5)

        # Toolbar component (voucher metadata form)
        self.toolbar = VoucherToolbar()
        layout.addWidget(self.toolbar)

        # Separator
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        layout.addWidget(line)
        layout.addSpacing(8)

        # Action bars side-by-side (Primary on left, Secondary on right)
        actions_layout = QHBoxLayout()
        actions_layout.setSpacing(10)

        # Primary actions bar (Save, Print, New, Delete, History)
        self.primary_actions = PrimaryActionsBar()
        actions_layout.addWidget(self.primary_actions, stretch=1)

        # Secondary actions bar (mode switcher, buttons, live rate)
        self.secondary_actions = SecondaryActionsBar()
        actions_layout.addWidget(self.secondary_actions, stretch=2)

        layout.addLayout(actions_layout)
        layout.addSpacing(8)

        # Create table using EstimateTableView component
        self.item_table = EstimateTableView()
        layout.addWidget(self.item_table)

        # Totals panel component
        self.totals_panel = TotalsPanel()
        layout.addWidget(self.totals_panel)

        # Expose toolbar widgets for EstimateLogic compatibility
        self.voucher_edit = self.toolbar.voucher_edit
        self.date_edit = self.toolbar.date_edit
        self.note_edit = self.toolbar.note_edit
        self.silver_rate_spin = self.toolbar.silver_rate_spin
        self.load_button = self.toolbar.load_button

        # Expose primary actions bar widgets
        self.save_button = self.primary_actions.save_button
        self.print_button = self.primary_actions.print_button
        self.clear_button = self.primary_actions.new_button
        self.delete_estimate_button = self.primary_actions.delete_estimate_button
        self.history_button = self.primary_actions.history_button

        # Expose secondary actions bar widgets
        self.delete_row_button = self.secondary_actions.delete_row_button
        self.return_toggle_button = self.secondary_actions.return_button
        self.silver_bar_toggle_button = self.secondary_actions.silver_bar_button
        self.last_balance_button = self.secondary_actions.last_balance_button
        self.silver_bars_button = self.secondary_actions.silver_bars_button
        self.live_rate_label = self.secondary_actions.live_rate_label
        self.live_rate_value_label = self.secondary_actions.live_rate_value_label
        self.live_rate_meta_label = self.secondary_actions.live_rate_meta_label
        self.refresh_rate_button = self.secondary_actions.refresh_rate_button

        # Use toolbar's visible mode indicator (secondary_actions has hidden one)
        self.mode_indicator_label = self.toolbar.mode_indicator_label

        # Expose totals panel widgets for EstimateLogic
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

        # Unsaved badge from toolbar
        self.unsaved_badge = self.toolbar.unsaved_badge

        # Status message label from toolbar
        self.status_message_label = self.toolbar.status_message_label

    def _setup_table_delegates(self):
        """Set up input delegates for table validation."""
        numeric_delegate = NumericDelegate(parent=self.item_table)
        self.item_table.setItemDelegateForColumn(COL_GROSS, numeric_delegate)
        self.item_table.setItemDelegateForColumn(COL_POLY, numeric_delegate)
        self.item_table.setItemDelegateForColumn(COL_PURITY, numeric_delegate)
        self.item_table.setItemDelegateForColumn(COL_WAGE_RATE, numeric_delegate)
        self.item_table.setItemDelegateForColumn(COL_PIECES, numeric_delegate)

        # Set up column widths
        self.item_table.setColumnWidth(COL_CODE, 80)
        self.item_table.setColumnWidth(COL_GROSS, 85)
        self.item_table.setColumnWidth(COL_POLY, 85)
        self.item_table.setColumnWidth(4, 85)  # Net Wt
        self.item_table.setColumnWidth(COL_PURITY, 80)
        self.item_table.setColumnWidth(COL_WAGE_RATE, 80)
        self.item_table.setColumnWidth(COL_PIECES, 60)
        self.item_table.setColumnWidth(8, 85)  # Wage Amt
        self.item_table.setColumnWidth(9, 85)  # Fine Wt
        self.item_table.setColumnWidth(10, 80)  # Type

        # Wire header signals
        header = self.item_table.horizontalHeader()
        header.setContextMenuPolicy(Qt.CustomContextMenu)
        header.customContextMenuRequested.connect(self._show_header_context_menu)
        header.sectionResized.connect(self._on_item_table_section_resized)

    def _wire_component_signals(self):
        """Wire component signals to handlers."""
        # Toolbar signals
        self.toolbar.load_clicked.connect(self.safe_load_estimate)

        # Primary actions bar signals
        self.primary_actions.save_clicked.connect(self.save_estimate)
        self.primary_actions.print_clicked.connect(self.print_estimate)
        self.primary_actions.new_clicked.connect(self.clear_form)
        self.primary_actions.delete_estimate_clicked.connect(self.delete_current_estimate)
        self.primary_actions.history_clicked.connect(self.show_history)

        # Secondary actions bar signals
        self.secondary_actions.delete_row_clicked.connect(self.delete_current_row)
        # Connect buttons directly to mixin toggle methods (bypass component signals)
        self.return_toggle_button.clicked.connect(self.toggle_return_mode)
        self.silver_bar_toggle_button.clicked.connect(self.toggle_silver_bar_mode)
        self.secondary_actions.last_balance_clicked.connect(self._on_last_balance_clicked)
        self.secondary_actions.silver_bars_clicked.connect(self._on_silver_bars_clicked)
        self.secondary_actions.refresh_rate_clicked.connect(self._on_refresh_rate_clicked)

        # EstimateTableView signals - wire to adapters that convert to QTableWidget-style signals
        self.item_table.cell_edited.connect(self._on_table_cell_edited)
        # The EstimateTableView handles Ctrl+D and Ctrl+H internally via shortcuts

    def _on_last_balance_clicked(self):
        """Handle last balance button click."""
        # This will be connected to the actual implementation in EstimateLogic
        if hasattr(self, 'add_last_balance'):
            self.add_last_balance()

    def _on_silver_bars_clicked(self):
        """Handle silver bars button click."""
        # This will be connected to the actual implementation via main window
        if self.main_window and hasattr(self.main_window, 'show_silver_bars_management'):
            self.main_window.show_silver_bars_management()

    def _on_refresh_rate_clicked(self):
        """Handle refresh rate button click."""
        # This will be connected to LiveRateController via main window
        if self.main_window and hasattr(self.main_window, 'refresh_live_rate'):
            self.main_window.refresh_live_rate()

    def _on_table_cell_edited(self, row: int, column: int):
        """Adapter method to handle cell edits from EstimateTableView.

        Converts from the Model/View signal to what the mixins expect.
        """
        # The mixins expect handle_cell_changed to be called
        # We need to trigger it with the appropriate cell
        if hasattr(self, 'handle_cell_changed'):
            # QTableView uses model indices, mixins expect QTableWidgetItem behavior
            # Call handle_cell_changed which will process the edit
            self.handle_cell_changed(row, column)

    def connect_signals(self, skip_load_estimate: bool = False) -> None:
        """Override base connect_signals to work with QTableView instead of QTableWidget.

        Args:
            skip_load_estimate: If True, skip connecting load estimate signal
        """
        # Connect non-table signals using parent implementation
        if not skip_load_estimate:
            if hasattr(self, "safe_load_estimate"):
                self.voucher_edit.editingFinished.connect(self.safe_load_estimate)
            else:
                self.voucher_edit.editingFinished.connect(self.load_estimate)

        self.silver_rate_spin.valueChanged.connect(self._handle_silver_rate_changed)

        if hasattr(self, "last_balance_button"):
            self.last_balance_button.clicked.connect(self.show_last_balance_dialog)
        if hasattr(self, "note_edit"):
            self.note_edit.textEdited.connect(self._mark_unsaved)
        if hasattr(self, "date_edit"):
            self.date_edit.dateChanged.connect(self._mark_unsaved)

        # NOTE: QTableView signals are different from QTableWidget signals
        # EstimateTableView provides cell_edited signal instead of cellChanged
        # cellClicked, itemSelectionChanged, currentCellChanged not available in QTableView
        # These are handled via the model's dataChanged signals and view's selection model

        self.save_button.clicked.connect(self.save_estimate)
        self.clear_button.clicked.connect(self.clear_form)
        self.print_button.clicked.connect(self.print_estimate)
        self.return_toggle_button.clicked.connect(self.toggle_return_mode)
        self.silver_bar_toggle_button.clicked.connect(self.toggle_silver_bar_mode)

        if hasattr(self, "history_button"):
            self.history_button.clicked.connect(self.show_history)
        if hasattr(self, "silver_bars_button"):
            self.silver_bars_button.clicked.connect(self.show_silver_bars)
        if hasattr(self, "refresh_rate_button"):
            self.refresh_rate_button.clicked.connect(self.refresh_silver_rate)

        if hasattr(self, "delete_estimate_button"):
            self.delete_estimate_button.clicked.connect(self.delete_current_estimate)
            try:
                self.delete_estimate_button.setEnabled(False)
            except Exception:
                pass

    def _setup_keyboard_shortcuts(self):
        """Set up keyboard shortcuts.

        Note: Ctrl+R, Ctrl+B, Ctrl+D, and Ctrl+H are handled by SecondaryActionsBar.
        Only setting up shortcuts not handled by components.
        """
        # Ctrl+N - New estimate
        self.new_shortcut = QShortcut(QKeySequence("Ctrl+N"), self)
        self.new_shortcut.activated.connect(self.clear_form)

    # Helper methods for status and unsaved changes
    def show_status(self, message, timeout=3000, level='info'):
        """Show status message."""
        self._status_helper.show(message, timeout=timeout, level=level)

    def show_inline_status(self, message, timeout=3000, level='info'):
        """Show inline status message."""
        self._status_helper.show(message, timeout=timeout, level=level)

    def has_unsaved_changes(self) -> bool:
        """Return True when the estimate form has unsaved edits."""
        return bool(getattr(self, "_unsaved_changes", False))

    def _on_unsaved_state_changed(self, dirty: bool) -> None:
        """Update visual cues when the unsaved state changes."""
        self.toolbar.show_unsaved_badge(dirty)
        if self.main_window and hasattr(self.main_window, "setWindowModified"):
            try:
                self.main_window.setWindowModified(bool(dirty))
            except Exception:
                pass

    def _update_mode_tooltip(self) -> None:
        """Update mode label tooltip."""
        if self.return_mode:
            mode = "Return Items"
        elif self.silver_bar_mode:
            mode = "Silver Bars"
        else:
            mode = "Regular Items"
        tip = (
            f"Current mode: {mode}\n"
            "Ctrl+R: Return Items\n"
            "Ctrl+B: Silver Bars"
        )
        try:
            self.mode_indicator_label.setToolTip(tip)
        except Exception:
            pass

    def request_totals_recalc(self):
        """Request a debounced totals recomputation."""
        try:
            self._totals_timer.start()
        except Exception:
            try:
                self.calculate_totals()
            except Exception:
                pass

    def force_focus_to_first_cell(self):
        """Force the cursor to the first cell (code column) and start editing."""
        if self.item_table.rowCount() > 0:
            self.item_table.setCurrentCell(0, COL_CODE)
            self.current_row = 0
            self.current_column = COL_CODE
            if self.item_table.item(0, COL_CODE):
                self.item_table.editItem(self.item_table.item(0, COL_CODE))

    def clear_all_rows(self):
        """Clear all rows from the table."""
        self.item_table.blockSignals(True)
        while self.item_table.rowCount() > 0:
            self.item_table.removeRow(0)
        self.item_table.blockSignals(False)
        self.current_row = -1
        self.current_column = -1

    # Column width persistence methods
    def _settings(self):
        return get_app_settings()

    def _save_column_widths_setting(self):
        try:
            if not hasattr(self, 'item_table'):
                return
            header = self.item_table.horizontalHeader()
            try:
                state = header.saveState()
                self._settings().setValue("ui/estimate_table_header_state", state)
            except Exception:
                pass
            try:
                count = self.item_table.columnCount()
                widths = [str(max(30, self.item_table.columnWidth(i))) for i in range(count)]
                value = ",".join(widths)
                self._settings().setValue("ui/estimate_table_column_widths", value)
            except Exception:
                pass
        except Exception:
            pass

    def _load_column_widths_setting(self):
        try:
            if not hasattr(self, 'item_table'):
                return
            header = self.item_table.horizontalHeader()
            restored = False
            try:
                state = self._settings().value("ui/estimate_table_header_state")
                if state:
                    self._programmatic_resizing = True
                    restored = bool(header.restoreState(state))
                    self._programmatic_resizing = False
            except Exception:
                restored = False
            if restored:
                self._use_stretch_for_item_name = False
                return

            value = self._settings().value("ui/estimate_table_column_widths", type=str)
            if value:
                parts = [p.strip() for p in str(value).split(',') if p.strip().isdigit()]
                if parts:
                    count = min(self.item_table.columnCount(), len(parts))
                    self._use_stretch_for_item_name = False
                    self._programmatic_resizing = True
                    for i in range(count):
                        w = int(parts[i])
                        w = max(30, min(2000, w))
                        self.item_table.setColumnWidth(i, w)
                    self._programmatic_resizing = False
                    return

            self._use_stretch_for_item_name = True
        except Exception:
            pass

    def _on_item_table_section_resized(self, logicalIndex, oldSize, newSize):
        if getattr(self, '_programmatic_resizing', False):
            return
        if getattr(self, '_use_stretch_for_item_name', False):
            self._use_stretch_for_item_name = False
        try:
            self._column_save_timer.stop()
            self._column_save_timer.start()
        except Exception:
            self._save_column_widths_setting()

    def resizeEvent(self, event):
        try:
            if getattr(self, '_use_stretch_for_item_name', False):
                self._auto_stretch_item_name()
        except Exception:
            pass
        super().resizeEvent(event)

    def _auto_stretch_item_name(self):
        """Auto-size the Item Name column to fill remaining space while in stretch mode."""
        if not hasattr(self, 'item_table'):
            return
        table = self.item_table
        viewport_width = table.viewport().width()
        if viewport_width <= 0:
            return
        count = table.columnCount()
        other_sum = 0
        for i in range(count):
            if i == COL_ITEM_NAME:
                continue
            other_sum += table.columnWidth(i)
        try:
            if table.verticalScrollBar().isVisible():
                other_sum += table.verticalScrollBar().width()
        except Exception:
            pass
        min_width = 150
        leftover = max(min_width, viewport_width - other_sum - 4)
        self._programmatic_resizing = True
        table.setColumnWidth(COL_ITEM_NAME, leftover)
        self._programmatic_resizing = False

    def closeEvent(self, event):
        self._save_column_widths_setting()
        super().closeEvent(event)

    def _show_header_context_menu(self, pos):
        try:
            header = self.item_table.horizontalHeader()
            from PyQt5.QtWidgets import QMenu
            menu = QMenu(self)
            reset_action = menu.addAction("Reset Column Layout")
            action = menu.exec_(header.mapToGlobal(pos))
            if action == reset_action:
                self._reset_columns_layout()
        except Exception:
            pass

    def _reset_columns_layout(self):
        try:
            self._settings().remove("ui/estimate_table_header_state")
            self._settings().remove("ui/estimate_table_column_widths")
            self._use_stretch_for_item_name = True
            self._auto_stretch_item_name()
            self.show_status("Column layout reset", 2000)
        except Exception:
            pass

    # Font size methods
    def _apply_table_font_size(self, size):
        """Applies the selected font size to the item table."""
        if hasattr(self, 'item_table'):
            from PyQt5.QtGui import QFont
            font = self.item_table.font()
            font.setPointSize(size)
            self.item_table.setFont(font)
            self.item_table.resizeRowsToContents()

    def _load_table_font_size_setting(self):
        """Loads the table font size from settings and applies it on init."""
        settings = get_app_settings()
        size = settings.value("ui/table_font_size", defaultValue=9, type=int)
        size = max(7, min(size, 16))
        if hasattr(self, 'item_table'):
            self._apply_table_font_size(size)

    def _apply_breakdown_font_size(self, size):
        """Apply font size to totals breakdown."""
        if hasattr(self, 'totals_panel'):
            self.totals_panel.set_breakdown_font_size(size)

    def _load_breakdown_font_size_setting(self):
        """Load breakdown font size from settings."""
        settings = get_app_settings()
        size = settings.value("ui/breakdown_font_size", defaultValue=9, type=int)
        size = max(7, min(size, 16))
        self._apply_breakdown_font_size(size)

    def _apply_final_calc_font_size(self, size):
        """Apply font size to final calculation."""
        if hasattr(self, 'totals_panel'):
            self.totals_panel.set_final_calc_font_size(size)

    def _load_final_calc_font_size_setting(self):
        """Load final calculation font size from settings."""
        settings = get_app_settings()
        size = settings.value("ui/final_calc_font_size", defaultValue=10, type=int)
        size = max(8, min(size, 20))
        self._apply_final_calc_font_size(size)

    def reconnect_load_estimate(self):
        """Reconnect keyboard-triggered loading for the voucher field."""
        try:
            self.voucher_edit.editingFinished.disconnect(self.safe_load_estimate)
        except TypeError:
            pass
        try:
            self.voucher_edit.editingFinished.disconnect(self.load_estimate)
        except TypeError:
            pass
        self.voucher_edit.editingFinished.connect(self.safe_load_estimate)

    def safe_load_estimate(self):
        """Safely load an estimate, catching any exceptions to prevent crashes."""
        if getattr(self, "_loading_estimate", False):
            self.logger.debug("Load request ignored; voucher load already in progress.")
            return
        if hasattr(self, 'initializing') and self.initializing:
            self.logger.debug("Skipping load_estimate during initialization")
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
                self.show_status("Load cancelled; current estimate left unchanged.", 2500)
                try:
                    self.voucher_edit.setFocus()
                    self.voucher_edit.selectAll()
                except Exception:
                    pass
                return

        self._loading_estimate = True
        blocker = QSignalBlocker(self.voucher_edit)
        try:
            self.load_estimate()
        except Exception as e:
            self.logger.error(f"Error in safe_load_estimate: {str(e)}", exc_info=True)
            self.show_status(f"Error loading estimate: {str(e)}", 5000)
            QMessageBox.critical(
                self, "Load Error",
                f"An error occurred while loading the estimate: {str(e)}\n\n"
                "Your changes have not been saved."
            )
        finally:
            del blocker
            self._loading_estimate = False

    def keyPressEvent(self, event):
        """Handle key press events for navigation and shortcuts."""
        key = event.key()
        modifiers = event.modifiers()

        # Enforce code entry before navigation
        try:
            nav_keys = {
                Qt.Key_Up, Qt.Key_Down, Qt.Key_Left, Qt.Key_Right,
                Qt.Key_PageUp, Qt.Key_PageDown, Qt.Key_Home, Qt.Key_End,
                Qt.Key_Tab, Qt.Key_Backtab, Qt.Key_Return, Qt.Key_Enter
            }
            if key in nav_keys and hasattr(self, 'current_row') and self.current_row >= 0:
                def _is_code_empty(r):
                    itm = self.item_table.item(r, COL_CODE)
                    return (not itm) or (not itm.text().strip())
                if _is_code_empty(self.current_row):
                    self.show_status("Enter item code first", 1500)
                    self.focus_on_code_column(self.current_row)
                    event.accept()
                    return
        except Exception:
            pass

        # Shortcut handlers
        if modifiers == Qt.ControlModifier:
            if key == Qt.Key_R:
                self.toggle_return_mode()
                event.accept()
                return
            elif key == Qt.Key_B:
                self.toggle_silver_bar_mode()
                event.accept()
                return
            elif key == Qt.Key_D:
                self.delete_current_row()
                event.accept()
                return

        # Standard navigation
        if key in [Qt.Key_Up, Qt.Key_Down, Qt.Key_Left, Qt.Key_Right,
                   Qt.Key_PageUp, Qt.Key_PageDown, Qt.Key_Home, Qt.Key_End]:
            super().keyPressEvent(event)
            return

        # Enter/Tab navigation
        if key in [Qt.Key_Return, Qt.Key_Enter, Qt.Key_Tab]:
            self.move_to_next_cell()
            event.accept()
            return
        if key == Qt.Key_Backtab:
            self.move_to_previous_cell()
            event.accept()
            return

        # Escape key
        if key == Qt.Key_Escape:
            self.confirm_exit()
            event.accept()
            return

        super().keyPressEvent(event)
