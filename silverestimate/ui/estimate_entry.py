#!/usr/bin/env python
from PyQt5.QtWidgets import QWidget, QShortcut, QTableWidgetItem, QMessageBox
from PyQt5.QtCore import Qt, QTimer, QSignalBlocker
from PyQt5.QtGui import QKeySequence
from silverestimate.infrastructure.settings import get_app_settings
from .estimate_entry_ui import (
    EstimateUI,
    NumericDelegate,
    COL_CODE,
    COL_ITEM_NAME,
    COL_GROSS,
    COL_POLY,
    COL_PURITY,
    COL_WAGE_RATE,
    COL_PIECES,
)
from .estimate_entry_logic import EstimateLogic
from .inline_status import InlineStatusController
from .view_models import EstimateEntryViewModel
from silverestimate.presenter import EstimateEntryPresenter

class EstimateEntryWidget(QWidget, EstimateUI, EstimateLogic):
    """Widget for silver estimate entry and management.

    Combines UI and logic, uses validation delegate, interacts with status bar.
    """

    def __init__(self, db_manager, main_window, repository):  # Accept main_window and presenter repository
        super().__init__()
        # Explicitly call EstimateLogic.__init__() to initialize the logger
        EstimateLogic.__init__(self)

        # Set up database manager and main window reference
        self.db_manager = db_manager
        self.presenter = EstimateEntryPresenter(self, repository)
        self.main_window = main_window # Store reference
        # Flag to prevent loading estimates during initialization
        self.initializing = True
        self._loading_estimate = False

        # Initialize tracking variables
        # Use COL_CODE for initialization consistency
        self.current_row = -1
        self.current_column = COL_CODE

        self.processing_cell = False
        self.return_mode = False
        self.silver_bar_mode = False
        self.view_model = EstimateEntryViewModel()
        self.view_model.set_modes(
            return_mode=self.return_mode,
            silver_bar_mode=self.silver_bar_mode,
        )

        # Set up UI (this creates self.item_table)
        self.setup_ui(self)

        # Hybrid column sizing state
        self._use_stretch_for_item_name = False
        self._programmatic_resizing = False
        # Debounce timer for saving column layout
        from PyQt5.QtCore import QTimer as _QTimer
        self._column_save_timer = _QTimer(self)
        self._column_save_timer.setSingleShot(True)
        self._column_save_timer.setInterval(350)
        self._column_save_timer.timeout.connect(self._save_column_widths_setting)

        # Restore any saved column widths for the item table (enables stretch if none saved)
        self._load_column_widths_setting()

        # If stretching is active (no saved widths), do an initial auto-stretch after layout
        if self._use_stretch_for_item_name:
            QTimer.singleShot(0, self._auto_stretch_item_name)

        # --- Set Delegates for Table Validation ---
        numeric_delegate = NumericDelegate(parent=self.item_table)

        # Apply the delegate to relevant numeric columns using constants
        self.item_table.setItemDelegateForColumn(COL_GROSS, numeric_delegate)
        self.item_table.setItemDelegateForColumn(COL_POLY, numeric_delegate)
        self.item_table.setItemDelegateForColumn(COL_PURITY, numeric_delegate)
        self.item_table.setItemDelegateForColumn(COL_WAGE_RATE, numeric_delegate)
        self.item_table.setItemDelegateForColumn(COL_PIECES, numeric_delegate)
        # -------------------------------------------

        # Make sure we start with exactly one empty row
        self.clear_all_rows()
        self.add_empty_row()  # This now focuses correctly

        # Generate a new voucher number before signals hook up to avoid unintended loads
        if self.presenter is None:
            self.logger.error("Presenter unavailable for initial voucher generation.")
        else:
            try:
                self.presenter.generate_voucher(silent=True)
                self.logger.info("Generated new voucher silently.")
                if hasattr(self, "delete_estimate_button"):
                    try:
                        self.delete_estimate_button.setEnabled(False)
                    except Exception:
                        pass
                self._estimate_loaded = False
            except Exception as exc:
                self.logger.error(
                    "Error generating voucher number silently: %s", exc, exc_info=True
                )

        # Connect signals after initialization; skip load on startup
        self.connect_signals(skip_load_estimate=True)

        # Connect the load button to the safe_load_estimate method
        self.load_button.clicked.connect(self.safe_load_estimate)

        # Set initializing flag to false after setup is complete
        self.initializing = False

        # Allow pressing Enter/Tab in the voucher field to trigger loading
        # Delay signal connection to prevent premature loads during initialization
        QTimer.singleShot(100, self.reconnect_load_estimate)

        # Column width persistence is hooked in UI setup via header.sectionResized
        # Debounced totals recalculation timer (improves UI responsiveness)
        self._totals_timer = QTimer(self)
        self._totals_timer.setSingleShot(True)
        self._totals_timer.setInterval(100)  # 80–120ms works well
        self._totals_timer.timeout.connect(self.calculate_totals)

        # Set up keyboard shortcuts
        self.delete_row_shortcut = QShortcut(QKeySequence("Ctrl+D"), self)
        self.delete_row_shortcut.activated.connect(self.delete_current_row)

        # Fix stray space in shortcut definition
        self.return_toggle_shortcut = QShortcut(QKeySequence("Ctrl+R"), self)
        self.return_toggle_shortcut.activated.connect(self.toggle_return_mode)

        self.silver_bar_toggle_shortcut = QShortcut(QKeySequence("Ctrl+B"), self)
        self.silver_bar_toggle_shortcut.activated.connect(self.toggle_silver_bar_mode)

        # Do not bind Save/Print here to avoid shortcut conflicts; rely on MainWindow menu actions

        self.history_shortcut = QShortcut(QKeySequence("Ctrl+H"), self)
        self.history_shortcut.activated.connect(self.show_history)

        self.new_shortcut = QShortcut(QKeySequence("Ctrl+N"), self)
        self.new_shortcut.activated.connect(self.clear_form)

        # Force focus to the first cell (Code column) after initialization
        QTimer.singleShot(100, self.force_focus_to_first_cell)

        # Load initial table font size
        self._load_table_font_size_setting()

        # Load initial breakdown and final calculation font sizes
        self._load_breakdown_font_size_setting()
        self._load_final_calc_font_size_setting()

        self._status_helper = InlineStatusController(
            parent=self,
            label_getter=lambda: getattr(self, "status_message_label", None),
            logger=self.logger,
        )
        self._on_unsaved_state_changed(False)
        self._update_mode_tooltip()

    # --- Add helper to show status messages via main window ---
    def show_status(self, message, timeout=3000, level='info'):
        self._status_helper.show(message, timeout=timeout, level=level)

    def show_inline_status(self, message, timeout=3000, level='info'):
        self._status_helper.show(message, timeout=timeout, level=level)

    def has_unsaved_changes(self) -> bool:
        """Return True when the estimate form has unsaved edits."""
        return bool(getattr(self, "_unsaved_changes", False))

    def _on_unsaved_state_changed(self, dirty: bool) -> None:
        """Update visual cues when the unsaved state changes."""
        badge = getattr(self, "unsaved_badge", None)
        if badge is not None:
            if dirty:
                badge.setText("● Unsaved changes")
                badge.setVisible(True)
            else:
                badge.clear()
                badge.setVisible(False)
        main_win = getattr(self, "main_window", None)
        if main_win and hasattr(main_win, "setWindowModified"):
            try:
                main_win.setWindowModified(bool(dirty))
            except Exception:
                pass

    def _update_mode_tooltip(self) -> None:
        label = getattr(self, "mode_indicator_label", None)
        if label is None:
            return
        if getattr(self, "return_mode", False):
            mode = "Return Items"
        elif getattr(self, "silver_bar_mode", False):
            mode = "Silver Bars"
        else:
            mode = "Regular Items"
        tip = (
            f"Current mode: {mode}\n"
            "Ctrl+R: Return Items\n"
            "Ctrl+B: Silver Bars"
        )
        try:
            label.setToolTip(tip)
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
            # Use constant
            self.item_table.setCurrentCell(0, COL_CODE)
            self.current_row = 0
            self.current_column = COL_CODE # Use constant
            if self.item_table.item(0, COL_CODE): # Use constant
                self.item_table.editItem(self.item_table.item(0, COL_CODE)) # Use constant

    # ... (rest of EstimateEntryWidget methods remain the same,
    #      as they inherit the constant-updated logic from EstimateLogic) ...
    def clear_all_rows(self):
        """Clear all rows from the table."""
        # Block signals while clearing
        self.item_table.blockSignals(True)
        while self.item_table.rowCount() > 0:
            self.item_table.removeRow(0)
        self.item_table.blockSignals(False)
        self.current_row = -1 # Reset position
        self.current_column = -1

    def toggle_return_mode(self):
        """Toggle return item entry mode and update UI."""
        # If switching TO return mode, ensure silver bar mode is OFF
        if not self.return_mode and self.silver_bar_mode:
            self.silver_bar_mode = False
            self.silver_bar_toggle_button.setChecked(False)
            # Use the tooltip text directly if needed, or just reset
            self.silver_bar_toggle_button.setText("🥈 Silver Bars (Ctrl+B)")
            self.silver_bar_toggle_button.setStyleSheet("""
                QPushButton {
                    background-color: palette(button);
                    border: 1px solid palette(mid);
                    border-radius: 4px;
                    font-weight: normal;
                    color: palette(buttonText);
                    padding: 4px 8px;
                }
                QPushButton:hover {
                    background-color: palette(light);
                }
            """)
            # Mode label updated below

        # Toggle the mode
        self.return_mode = not self.return_mode
        self.return_toggle_button.setChecked(self.return_mode)

        # Update button appearance and Mode Label
        if self.return_mode:
            self.return_toggle_button.setText("↩ Return Items Mode ACTIVE (Ctrl+R)")
            self.return_toggle_button.setStyleSheet("""
                QPushButton {
                    background-color: #e8f4fd;
                    border: 2px solid #0066cc;
                    border-radius: 4px;
                    font-weight: bold;
                    color: #003d7a;
                    padding: 4px 8px;
                }
                QPushButton:hover {
                    background-color: #d6eafc;
                }
            """)
            self.mode_indicator_label.setText("Mode: Return Items")
            self.mode_indicator_label.setStyleSheet("font-weight: bold; color: #0066cc;")
            self.show_status("Return Items mode activated", 2000)
        else:
            self.return_toggle_button.setText("↩ Return Items (Ctrl+R)")
            self.return_toggle_button.setStyleSheet("""
                QPushButton {
                    background-color: palette(button);
                    border: 1px solid palette(mid);
                    border-radius: 4px;
                    font-weight: normal;
                    color: palette(buttonText);
                    padding: 4px 8px;
                }
                QPushButton:hover {
                    background-color: palette(light);
                }
            """)
            # Only reset mode label if silver bar mode is also off
            if not self.silver_bar_mode:
                 self.mode_indicator_label.setText("Mode: Regular")
                 self.mode_indicator_label.setStyleSheet("""
                     font-weight: bold; 
                     color: palette(windowText);
                     background-color: palette(window);
                     border: 1px solid palette(mid);
                     border-radius: 3px;
                     padding: 2px 6px;
                 """)
            self.show_status("Return Items mode deactivated", 2000)

        # Update the current or next empty row's type column visually
        self._refresh_empty_row_type()
        self.focus_on_empty_row(update_visuals=True)
        self._update_view_model_modes()
        self._update_mode_tooltip()
        self._mark_unsaved()

    def toggle_silver_bar_mode(self):
        """Toggle silver bar entry mode and update UI."""
        # If switching TO silver bar mode, ensure return mode is OFF
        if not self.silver_bar_mode and self.return_mode:
            self.return_mode = False
            self.return_toggle_button.setChecked(False)
            self.return_toggle_button.setText("↩ Return Items (Ctrl+R)")
            self.return_toggle_button.setStyleSheet("""
                QPushButton {
                    background-color: palette(button);
                    border: 1px solid palette(mid);
                    border-radius: 4px;
                    font-weight: normal;
                    color: palette(buttonText);
                    padding: 4px 8px;
                }
                QPushButton:hover {
                    background-color: palette(light);
                }
            """)
             # Mode label updated below

        # Toggle the mode
        self.silver_bar_mode = not self.silver_bar_mode
        self.silver_bar_toggle_button.setChecked(self.silver_bar_mode)

        # Update button appearance and Mode Label
        if self.silver_bar_mode:
            self.silver_bar_toggle_button.setText("🥈 Silver Bar Mode ACTIVE (Ctrl+B)")
            self.silver_bar_toggle_button.setStyleSheet("""
                QPushButton {
                    background-color: #fff4e6;
                    border: 2px solid #cc6600;
                    border-radius: 4px;
                    font-weight: bold;
                    color: #994d00;
                    padding: 4px 8px;
                }
                QPushButton:hover {
                    background-color: #ffe6cc;
                }
            """)
            self.mode_indicator_label.setText("Mode: Silver Bars")
            self.mode_indicator_label.setStyleSheet("font-weight: bold; color: #cc6600;")
            self.show_status("Silver Bars mode activated", 2000)
        else:
            self.silver_bar_toggle_button.setText("🥈 Silver Bars (Ctrl+B)")
            self.silver_bar_toggle_button.setStyleSheet("""
                QPushButton {
                    background-color: palette(button);
                    border: 1px solid palette(mid);
                    border-radius: 4px;
                    font-weight: normal;
                    color: palette(buttonText);
                    padding: 4px 8px;
                }
                QPushButton:hover {
                    background-color: palette(light);
                }
            """)
            # Only reset mode label if return mode is also off
            if not self.return_mode:
                 self.mode_indicator_label.setText("Mode: Regular")
                 self.mode_indicator_label.setStyleSheet("""
                     font-weight: bold; 
                     color: palette(windowText);
                     background-color: palette(window);
                     border: 1px solid palette(mid);
                     border-radius: 3px;
                     padding: 2px 6px;
                 """)
            self.show_status("Silver Bars mode deactivated", 2000)

        # Update the current or next empty row's type column visually
        self._refresh_empty_row_type()
        self.focus_on_empty_row(update_visuals=True)
        self._update_view_model_modes()
        self._update_mode_tooltip()
        self._mark_unsaved()

    def _refresh_empty_row_type(self):
        """Ensure the empty row reflects the active mode."""
        try:
            table = self.item_table
            for row in range(table.rowCount()):
                code_item = table.item(row, COL_CODE)
                if code_item and code_item.text().strip():
                    continue
                type_item = table.item(row, COL_TYPE)
                if type_item is None:
                    type_item = QTableWidgetItem("")
                    type_item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
                    table.setItem(row, COL_TYPE, type_item)
                table.blockSignals(True)
                try:
                    self._update_row_type_visuals_direct(type_item)
                    type_item.setTextAlignment(Qt.AlignCenter)
                finally:
                    table.blockSignals(False)
        except Exception:
            self.logger.debug('Failed to refresh empty row type', exc_info=True)

    def focus_on_empty_row(self, update_visuals=False):
        """Find and focus the first empty row's code column. Optionally update its type visuals."""
        empty_row_index = -1
        for row in range(self.item_table.rowCount()):
            code_item = self.item_table.item(row, 0)
            if not code_item or not code_item.text().strip():
                empty_row_index = row
                break

        if empty_row_index != -1:
            if update_visuals:
                # Delegate logic to the logic class method
                 self._update_row_type_visuals(empty_row_index)
                 self.calculate_totals() # Recalculate if visuals/type might change interpretation
            self.focus_on_code_column(empty_row_index)
        else:
            # No empty row found, add one
            self.add_empty_row() # This sets visuals and focuses

    def keyPressEvent(self, event):
        """Handle key press events for navigation and shortcuts."""
        key = event.key()
        modifiers = event.modifiers()

        # Enforce code entry before any navigation from the row
        try:
            nav_keys = {
                Qt.Key_Up, Qt.Key_Down, Qt.Key_Left, Qt.Key_Right,
                Qt.Key_PageUp, Qt.Key_PageDown, Qt.Key_Home, Qt.Key_End,
                Qt.Key_Tab, Qt.Key_Backtab, Qt.Key_Return, Qt.Key_Enter
            }
            if key in nav_keys and hasattr(self, 'current_row') and self.current_row >= 0:
                from .estimate_entry_ui import COL_CODE as _COL_CODE
                def _is_code_empty(r):
                    itm = self.item_table.item(r, _COL_CODE)
                    return (not itm) or (not itm.text().strip())
                if _is_code_empty(self.current_row):
                    # Always force focus back to Code on empty
                    self.show_status("Enter item code first", 1500)
                    self.focus_on_code_column(self.current_row)
                    event.accept()
                    return
        except Exception:
            pass

        # --- Shortcut Handlers (already connected via QShortcut, but can intercept here too) ---
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

        # --- Standard Navigation ---
        if key in [Qt.Key_Up, Qt.Key_Down, Qt.Key_Left, Qt.Key_Right, Qt.Key_PageUp, Qt.Key_PageDown, Qt.Key_Home, Qt.Key_End]:
             super().keyPressEvent(event) # Let QTableWidget handle standard navigation
             return

        # --- Enter/Tab Key Navigation ---
        if key in [Qt.Key_Return, Qt.Key_Enter, Qt.Key_Tab]:
            # Delegate navigation logic to the logic class method
            self.move_to_next_cell()
            event.accept()
            return
        if key == Qt.Key_Backtab: # Shift+Tab
            # Delegate navigation logic to the logic class method
            self.move_to_previous_cell()
            event.accept()
            return

        # --- Escape Key ---
        if key == Qt.Key_Escape:
            # Delegate exit confirmation to the logic class method (or main window)
            self.confirm_exit()
            event.accept()
            return

        # Let the parent handle other key events (like character input)
        super().keyPressEvent(event)

    # --- Column Width Persistence ---
    def _settings(self):
        return get_app_settings()

    def _save_column_widths_setting(self):
        try:
            if not hasattr(self, 'item_table'):
                return
            header = self.item_table.horizontalHeader()
            # Save binary header state (preferred)
            try:
                state = header.saveState()
                self._settings().setValue("ui/estimate_table_header_state", state)
            except Exception:
                pass
            # Also persist legacy CSV widths for backward compatibility
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
            # Try to restore binary header state first
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

            # Legacy CSV fallback
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

            # Nothing restored → enable stretch mode for Item Name
            self._use_stretch_for_item_name = True
        except Exception:
            pass

    def _on_item_table_section_resized(self, logicalIndex, oldSize, newSize):
        # Ignore programmatic resizes
        if getattr(self, '_programmatic_resizing', False):
            return
        # User resized any column → disable stretch mode going forward
        if getattr(self, '_use_stretch_for_item_name', False):
            self._use_stretch_for_item_name = False
        # Debounce save of column layout
        try:
            self._column_save_timer.stop()
            self._column_save_timer.start()
        except Exception:
            # Fallback to immediate save if timer fails
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
        # Sum widths of all columns except Item Name
        count = table.columnCount()
        other_sum = 0
        for i in range(count):
            if i == COL_ITEM_NAME:
                continue
            other_sum += table.columnWidth(i)
        # Account for vertical scrollbar if visible
        try:
            if table.verticalScrollBar().isVisible():
                other_sum += table.verticalScrollBar().width()
        except Exception:
            pass
        # Minimal width for item name
        min_width = 150
        leftover = max(min_width, viewport_width - other_sum - 4)
        self._programmatic_resizing = True
        table.setColumnWidth(COL_ITEM_NAME, leftover)
        self._programmatic_resizing = False

    def closeEvent(self, event):
        # Save column widths on close
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
            # Clear saved states
            self._settings().remove("ui/estimate_table_header_state")
            self._settings().remove("ui/estimate_table_column_widths")
            # Re-enable stretch mode and auto-apply
            self._use_stretch_for_item_name = True
            self._auto_stretch_item_name()
            # Inform user subtly
            self.show_status("Column layout reset", 2000)
        except Exception:
            pass

    # --- Font Size Handling ---
    def _apply_table_font_size(self, size):
        """Applies the selected font size to the item table. Called by MainWindow."""
        if hasattr(self, 'item_table'):
            # Import QFont if not already imported at the top
            from PyQt5.QtGui import QFont
            font = self.item_table.font() # Get current font
            font.setPointSize(size)      # Set new point size
            self.item_table.setFont(font)
            # Adjust row heights and column widths if necessary (optional)
            self.item_table.resizeRowsToContents()
            # self.item_table.resizeColumnsToContents() # Might make columns too wide
            # Saving is now handled by MainWindow

    def _load_table_font_size_setting(self):
        """Loads the table font size from settings and applies it on init."""
        settings = get_app_settings()
        # Use a reasonable default font size (e.g., 9)
        # Define default min/max here in case spinbox doesn't exist yet or range changes
        default_size = 9
        min_size = 7
        max_size = 16
        size = settings.value("ui/table_font_size", defaultValue=default_size, type=int)
        # Clamp value to a reasonable range
        size = max(min_size, min(size, max_size))

        # Apply the loaded/default size initially
        # Need to ensure item_table exists before applying
        if hasattr(self, 'item_table'):
             self._apply_table_font_size(size)
        else:
             # Should not happen if called at end of __init__, but as fallback:
             import logging
             logging.getLogger(__name__).warning("item_table not ready during font size load.")

    # --- Totals (Regular/Return/Silver Bar) font size handling ---
    def _apply_breakdown_font_size(self, size):
        """Apply font size to totals breakdown numeric labels (bottom-left)."""
        try:
            labels = [
                getattr(self, name, None) for name in [
                    'overall_gross_label', 'overall_poly_label',
                    'total_gross_label', 'total_net_label', 'total_fine_label',
                    'return_gross_label', 'return_net_label', 'return_fine_label',
                    'bar_gross_label', 'bar_net_label', 'bar_fine_label'
                ]
            ]
            for lbl in labels:
                if lbl is not None:
                    f = lbl.font()
                    f.setPointSize(int(size))
                    lbl.setFont(f)
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"Failed to apply breakdown font size: {e}")

    def _load_breakdown_font_size_setting(self):
        settings = get_app_settings()
        default_size = 9
        min_size = 7
        max_size = 16
        size = settings.value("ui/breakdown_font_size", defaultValue=default_size, type=int)
        size = max(min_size, min(size, max_size))
        self._apply_breakdown_font_size(size)

    # --- Final Calculation font size handling ---
    def _apply_final_calc_font_size(self, size):
        """Apply font size to Final Calculation numeric labels (right side)."""
        try:
            labels = [getattr(self, name, None) for name in [
                'net_fine_label', 'net_wage_label', 'grand_total_label'
            ]]
            for lbl in labels:
                if lbl is not None:
                    f = lbl.font()
                    f.setPointSize(int(size))
                    lbl.setFont(f)
            # Ensure stylesheet for grand total does not pin font-size
            if hasattr(self, 'grand_total_label') and self.grand_total_label is not None:
                # Preserve bold + color but drop any fixed font-size
                self.grand_total_label.setStyleSheet("font-weight: bold; color: blue;")
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"Failed to apply final calculation font size: {e}")

    def _load_final_calc_font_size_setting(self):
        settings = get_app_settings()
        default_size = 10
        min_size = 8
        max_size = 20
        size = settings.value("ui/final_calc_font_size", defaultValue=default_size, type=int)
        size = max(min_size, min(size, max_size))
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

        # Use only the safe wrapper; returnPressed triggers editingFinished.
        self.voucher_edit.editingFinished.connect(self.safe_load_estimate)

        import logging
        logging.getLogger(__name__).debug("Reconnected voucher load handlers.")

    def safe_load_estimate(self):
        """Safely load an estimate, catching any exceptions to prevent crashes."""
        if getattr(self, "_loading_estimate", False):
            self.logger.debug("Load request ignored; voucher load already in progress.")
            return
        # Skip loading during initialization to prevent startup crashes
        if hasattr(self, 'initializing') and self.initializing:
            self.logger.debug("Skipping load_estimate during initialization")
            return
        # Additional guard: Don't auto-load the generated voucher number on startup
        voucher_text = self.voucher_edit.text().strip()
        if not voucher_text:
            return  # No voucher number entered, nothing to load
        if self.has_unsaved_changes():
            reply = QMessageBox.question(
                self,
                "Discard Unsaved Changes?",
                "You have unsaved changes. Loading another estimate will discard them.\n\nContinue?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if reply != QMessageBox.Yes:
                self._status("Load cancelled; current estimate left unchanged.", 2500)
                try:
                    self.voucher_edit.setFocus()
                    self.voucher_edit.selectAll()
                except Exception:
                    pass
                self._loading_estimate = False
                return

        self._loading_estimate = True

        blocker = QSignalBlocker(self.voucher_edit)
        try:
            # Call the actual load_estimate method
            self.load_estimate()

        except Exception as e:
            # Log the error but don't crash the application
            self.logger.error(f"Error in safe_load_estimate: {str(e)}", exc_info=True)
            self._status(f"Error loading estimate: {str(e)}", 5000)

            # Show error message to user
            QMessageBox.critical(self, "Load Error",
                                f"An error occurred while loading the estimate: {str(e)}\n\n"
                                "Your changes have not been saved.")
        finally:
            del blocker
            self._loading_estimate = False

    # Removed _save_table_font_size_setting as saving is handled by MainWindow

