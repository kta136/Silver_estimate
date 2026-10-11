"""Layout and settings controller for estimate entry."""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional, cast

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (
    QAbstractButton,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMenu,
    QMenuBar,
    QSizePolicy,
    QSplitter,
    QToolButton,
    QVBoxLayout,
    QWidget,
)
from shiboken6 import isValid

from silverestimate.infrastructure.settings import (
    ApplicationSettings,
    SettingsKey,
    get_app_settings,
)

from .appearance import header_height, set_table_font
from .estimate_entry_components import (
    EstimateTableView,
    PrimaryActionsBar,
    SecondaryActionsBar,
    TotalsPanel,
    VoucherToolbar,
)
from .estimate_entry_logic.column_specs import (
    EDITOR_CODE,
    EDITOR_NUMERIC,
    column_width_limits,
    columns_for_editor_type,
    default_column_widths,
    is_stretch_column,
)
from .estimate_entry_theme import ESTIMATE_ENTRY_STYLESHEET
from .estimate_entry_ui import (
    CodeDelegate,
    NumericDelegate,
)
from .estimate_entry_workflow_controller import ROW_UNDO_SHORTCUT
from .icons import get_icon
from .modern_components import polish_dense_table
from .title_bar import TitleMenuBar

if TYPE_CHECKING:
    from .estimate_entry import EstimateEntryWidget

# Auto-recovery states the user has to act on, in plain words.
_RECOVERY_NOTICES = {
    "Available": "Unfinished estimate can be recovered (More)",
    "Update failed": "Auto-recovery copy not updated",
    "Removal failed": "Auto-recovery copy not removed",
    "Recovery needs attention": "Auto-recovery needs attention",
}


class EstimateEntryLayoutController:
    """Own layout wiring, the side panel, and persisted UI preferences."""

    def __init__(self, host: EstimateEntryWidget) -> None:
        self.host = host

    def _setup_ui(self):
        self.host.setObjectName("EstimateEntryRoot")
        self.host.setStyleSheet(ESTIMATE_ENTRY_STYLESHEET)

        layout = QVBoxLayout(self.host)
        layout.setSpacing(4)
        layout.setContentsMargins(6, 4, 6, 4)

        self.host.toolbar = VoucherToolbar()
        self.host.primary_actions = PrimaryActionsBar(shortcut_parent=self.host)
        self.host.primary_actions.setSizePolicy(
            QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed
        )

        # Never shown itself: the side panel shows its buttons.
        self.host.secondary_actions = SecondaryActionsBar(
            self.host, shortcut_parent=self.host
        )
        self.host.secondary_actions.hide()

        # Status badge and Save/Print/New. The strip moves into the window's
        # menu bar while this screen is shown; without one it stays above the
        # table.
        strip = QWidget()
        strip.setObjectName("EstimateCommandStrip")
        strip.setStyleSheet(ESTIMATE_ENTRY_STYLESHEET)
        strip_layout = QHBoxLayout(strip)
        strip_layout.setContentsMargins(0, 1, 4, 1)
        strip_layout.setSpacing(6)
        strip_layout.addWidget(self.host.toolbar.unsaved_badge)
        strip_layout.addWidget(self.host.primary_actions)
        self.host.primary_actions.save_button.setText("Save  Ctrl+S")
        self.host.command_strip = strip
        self._command_strip_menu_bar: QMenuBar | None = None
        layout.addWidget(strip, 0, Qt.AlignmentFlag.AlignRight)

        self.host.estimate_tools_menu = self._build_estimate_tools_menu()
        self.host.estimate_tools_menu.setTitle("Estimate Actions")

        self.host._content_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.host._content_splitter.setChildrenCollapsible(False)
        self.host._content_splitter.setOpaqueResize(True)
        self.host._content_splitter.setHandleWidth(10)

        self.host.item_table = EstimateTableView()
        self.host.item_table.host_widget = self.host
        polish_dense_table(
            self.host.item_table,
            row_height=32,
            header_height=36,
            show_grid=True,
            hide_vertical_header=False,
        )
        self.host.item_table.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        self.host._content_splitter.addWidget(self.host.item_table)

        # The side panel: voucher fields, totals and actions, right of the table.
        self.host.totals_panel = self._create_totals_panel()
        self.host._content_splitter.addWidget(self.host.totals_panel)
        self.host._content_splitter.setStretchFactor(0, 1)
        self.host._content_splitter.setStretchFactor(1, 0)
        self.host._content_splitter.setSizes([1060, 320])

        layout.addWidget(self.host._content_splitter, 1)

        self.host.voucher_edit = self.host.toolbar.voucher_edit
        self.host.date_edit = self.host.toolbar.date_edit
        self.host.note_edit = self.host.toolbar.note_edit
        self.host.silver_rate_spin = self.host.toolbar.silver_rate_spin
        self.host.load_button = self.host.toolbar.load_button

        self.host.save_button = self.host.primary_actions.save_button
        self.host.print_button = self.host.primary_actions.print_button
        self.host.clear_button = self.host.primary_actions.new_button
        self.host.delete_estimate_button = (
            self.host.secondary_actions.delete_estimate_button
        )
        self.host.history_button = self.host.secondary_actions.history_button

        self.host.delete_row_button = self.host.secondary_actions.delete_row_button
        self.host.return_toggle_button = (
            self.host.secondary_actions.return_toggle_button
        )
        self.host.silver_bar_toggle_button = (
            self.host.secondary_actions.silver_bar_toggle_button
        )
        self.host.last_balance_button = self.host.secondary_actions.last_balance_button
        self.host.silver_bars_button = self.host.secondary_actions.silver_bars_button
        self.host.live_rate_value_label = (
            self.host.secondary_actions.live_rate_value_label
        )
        self.host.live_rate_meta_label = (
            self.host.secondary_actions.live_rate_meta_label
        )
        self.host.refresh_rate_button = self.host.secondary_actions.refresh_rate_button

        self._place_sidebar_actions()
        self._place_voucher_fields()

        self._bind_totals_panel_labels()

        self.host.unsaved_badge = self.host.toolbar.unsaved_badge
        self.host.status_message_label = self.host.toolbar.status_message_label
        self._update_status_line()

        try:
            model = self.host.item_table.model()
            model.rowsInserted.connect(lambda *_: self._update_status_line())
            model.rowsRemoved.connect(lambda *_: self._update_status_line())
            model.modelReset.connect(lambda *_: self._update_status_line())
        except (AttributeError, RuntimeError, TypeError) as exc:
            self.host.logger.debug("Failed to bind status line table updates: %s", exc)

    def _place_sidebar_actions(self) -> None:
        actions = QFrame(self.host)
        actions.setObjectName("EstimateSidebarActions")
        grid = QGridLayout(actions)
        grid.setContentsMargins(0, 2, 0, 0)
        grid.setSpacing(6)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)

        more_button = QToolButton(actions)
        more_button.setObjectName("EstimateMoreButton")
        more_button.setText("More")
        more_button.setToolTip("More estimate actions")
        more_button.setMenu(self.host.estimate_tools_menu)
        more_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        SecondaryActionsBar.fit_panel_button(more_button)
        self.host.estimate_more_button = more_button

        actions_bar = self.host.secondary_actions
        buttons: tuple[QAbstractButton, ...] = (
            actions_bar.last_balance_button,
            actions_bar.history_button,
            actions_bar.silver_bars_button,
            more_button,
            actions_bar.delete_row_button,
            actions_bar.delete_estimate_button,
        )
        for index, button in enumerate(buttons):
            grid.addWidget(button, index // 2, index % 2)
            button.show()

        status = QLabel(self.host)
        status.setObjectName("SidebarStatusText")
        status.setWordWrap(True)
        self.host.sidebar_status_label = status
        self.host.sidebar_actions = actions
        panel = self.host.totals_panel
        panel.sidebar_actions_layout.addWidget(actions)
        panel.sidebar_footer_layout.addWidget(status)
        actions.show()
        status.show()

    def _place_voucher_fields(self) -> None:
        """Put the voucher fields, live rate and mode switch atop the side panel."""
        toolbar = self.host.toolbar
        toolbar.set_rate_companion(self.host.secondary_actions.live_rate_container)
        self.host.totals_panel.set_sidebar_top_widgets([toolbar, toolbar.mode_selector])
        toolbar.show()
        toolbar.mode_selector.show()

    def show_command_strip(self, visible: bool) -> None:
        """Dock Save/Print/New in the menu bar while the estimate screen shows."""
        strip = getattr(self.host, "command_strip", None)
        if strip is None or not isValid(strip):
            return
        main_window = getattr(self.host, "main_window", None)
        menu_bar_getter = getattr(main_window, "menuBar", None)
        menu_bar = menu_bar_getter() if callable(menu_bar_getter) else None
        if not isinstance(menu_bar, QMenuBar):
            return
        if visible:
            if self._command_strip_menu_bar is None:
                root_layout = self.host.layout()
                if root_layout is not None:
                    root_layout.removeWidget(strip)
                self._command_strip_menu_bar = menu_bar
            strip_layout = strip.layout()
            if isinstance(menu_bar, TitleMenuBar) and strip_layout is not None:
                # In the title bar the menu bar ends under the window's own
                # buttons, and it is taller than the strip.
                clear = menu_bar.caption_buttons_width()
                strip_layout.setContentsMargins(0, 1, 4 + clear, 1)
                strip.setMinimumHeight(menu_bar.row_height())
            menu_bar.setCornerWidget(strip, Qt.Corner.TopRightCorner)
            strip.show()
        elif self._command_strip_menu_bar is menu_bar:
            if menu_bar.cornerWidget(Qt.Corner.TopRightCorner) is strip:
                menu_bar.setCornerWidget(cast(QWidget, None), Qt.Corner.TopRightCorner)
            strip.hide()

    def _build_estimate_tools_menu(self) -> QMenu:
        menu = QMenu(self.host)

        self.host.command_history_action = QAction(
            get_icon("history", widget=self.host), "Estimate History...\tCtrl+H", menu
        )
        menu.addAction(self.host.command_history_action)

        self.host.command_settings_action = QAction(
            get_icon("settings", widget=self.host), "Settings...", menu
        )
        menu.addAction(self.host.command_settings_action)
        menu.addSeparator()

        delete_row = QAction(
            get_icon("delete_row", widget=self.host, color="#dc2626"),
            "Delete Current Row\tCtrl+D",
            menu,
        )
        delete_row.triggered.connect(
            self.host.secondary_actions.delete_row_clicked.emit
        )
        menu.addAction(delete_row)
        self.host.command_undo_row_action = QAction("Undo Last Row Deletion", menu)
        self.host.command_undo_row_action.setShortcut(QKeySequence(ROW_UNDO_SHORTCUT))
        self.host.command_undo_row_action.setShortcutContext(
            Qt.ShortcutContext.WidgetWithChildrenShortcut
        )
        self.host.addAction(self.host.command_undo_row_action)
        self.host.command_undo_row_action.setEnabled(False)
        self.host.command_undo_row_action.triggered.connect(
            self.host.workflow_controller.undo_row_deletion
        )
        menu.addAction(self.host.command_undo_row_action)
        recovery = self.host.draft_recovery
        if recovery is not None:
            recover_action = QAction("Recover Unfinished Estimate...", menu)
            recover_action.triggered.connect(recovery.offer_recovery)
            menu.addAction(recover_action)
        menu.addSeparator()

        return_mode = QAction(
            get_icon("return_mode", widget=self.host, color="#007f89"),
            "Return Mode\tCtrl+R",
            menu,
        )
        return_mode.setCheckable(True)
        return_mode.triggered.connect(
            lambda _checked=False: self.host.return_toggle_button.click()
        )
        menu.addAction(return_mode)

        silver_bar_mode = QAction(
            get_icon("bar_mode", widget=self.host, color="#007f89"),
            "Silver Bar Mode\tCtrl+B",
            menu,
        )
        silver_bar_mode.setCheckable(True)
        silver_bar_mode.triggered.connect(
            lambda _checked=False: self.host.silver_bar_toggle_button.click()
        )
        menu.addAction(silver_bar_mode)
        menu.addSeparator()

        balance = QAction(
            get_icon("balance", widget=self.host), "Last Balance...", menu
        )
        balance.triggered.connect(self.host.secondary_actions.last_balance_clicked.emit)
        menu.addAction(balance)

        bars = QAction(
            get_icon("silver_bars", widget=self.host), "Silver Bars...", menu
        )
        bars.triggered.connect(self.host.secondary_actions.silver_bars_clicked.emit)
        menu.addAction(bars)

        refresh = QAction(
            get_icon("refresh", widget=self.host, color="#007f89"),
            "Refresh Live Rate",
            menu,
        )
        refresh.triggered.connect(self.host.secondary_actions.refresh_rate_clicked.emit)
        menu.addAction(refresh)
        menu.addSeparator()

        delete_estimate = QAction(
            get_icon("delete_estimate", widget=self.host, color="#dc2626"),
            "Delete Estimate...",
            menu,
        )
        delete_estimate.triggered.connect(
            self.host.secondary_actions.delete_estimate_clicked.emit
        )
        menu.addAction(delete_estimate)

        def sync_menu_state() -> None:
            return_mode.setChecked(bool(self.host.return_toggle_button.isChecked()))
            silver_bar_mode.setChecked(
                bool(self.host.silver_bar_toggle_button.isChecked())
            )
            delete_estimate.setEnabled(
                bool(self.host.delete_estimate_button.isEnabled())
            )

        menu.aboutToShow.connect(sync_menu_state)
        return menu

    def _update_status_line(self) -> None:
        """Show the row count, last save and any recovery notice in the side panel."""
        try:
            rows = self.host.item_table.rowCount()
        except Exception:
            rows = 0
        last_saved = self.host._last_saved_status
        recovery = self.host.draft_recovery
        recovery_status = str(recovery.status) if recovery is not None else ""
        # Routine auto-recovery states stay in the tooltips; only a state the
        # user has to act on takes room in the side panel.
        notice = _RECOVERY_NOTICES.get(recovery_status)
        tooltip = "Current estimate status"
        if recovery_status:
            tooltip += f"\nAuto-recovery copy: {recovery_status}"
        badge = getattr(self.host, "unsaved_badge", None)
        if badge is not None and isValid(badge):
            badge.setToolTip(tooltip)
        sidebar_status = getattr(self.host, "sidebar_status_label", None)
        if sidebar_status is not None and isValid(sidebar_status):
            sidebar_items = [f"Rows: {rows}", f"Last saved: {last_saved}"]
            if notice:
                sidebar_items.append(notice)
            sidebar_status.setText(" · ".join([*sidebar_items, "F1 Shortcuts"]))
            sidebar_status.setToolTip(tooltip)

    def refresh_status_line(self) -> None:
        self._update_status_line()

    def _show_settings_from_command_bar(self) -> None:
        main_window = getattr(self.host, "main_window", None)
        opener = getattr(main_window, "show_settings_dialog", None)
        if callable(opener):
            opener()

    def _setup_table_delegates(self):
        code_delegate = CodeDelegate(parent=self.host.item_table)
        numeric_delegate = NumericDelegate(parent=self.host.item_table)
        code_delegate.advance_requested.connect(
            self.host.table_controller.move_to_next_cell
        )
        numeric_delegate.reverse_requested.connect(
            self.host.table_controller.move_to_previous_cell
        )
        numeric_delegate.manual_row_navigation_requested.connect(
            self.host.table_controller._mark_manual_row_navigation
        )

        for column in columns_for_editor_type(EDITOR_CODE, editable_only=True):
            self.host.item_table.setItemDelegateForColumn(column, code_delegate)
        for column in columns_for_editor_type(EDITOR_NUMERIC, editable_only=True):
            self.host.item_table.setItemDelegateForColumn(column, numeric_delegate)

        for column, width in self._default_column_widths().items():
            self.host.item_table.setColumnWidth(
                column, self._bounded_column_width(column, width)
            )

        header = self.host.item_table.horizontalHeader()
        header.sectionResized.connect(self._on_item_table_section_resized)

    def _choose_entry_mode(self, index: int) -> None:
        actions = self.host.secondary_actions
        if actions.return_toggle_button.isChecked() != (index == 1):
            actions.return_toggle_button.click()
        if actions.silver_bar_toggle_button.isChecked() != (index == 2):
            actions.silver_bar_toggle_button.click()
        self._sync_mode_selector()

    def _sync_mode_selector(self) -> None:
        actions = self.host.secondary_actions
        self.host.toolbar.set_mode_index(
            1
            if actions.return_toggle_button.isChecked()
            else 2
            if actions.silver_bar_toggle_button.isChecked()
            else 0
        )

    def _wire_component_signals(self):
        self.host.toolbar.mode_selected.connect(self._choose_entry_mode)
        for button in (
            self.host.return_toggle_button,
            self.host.silver_bar_toggle_button,
        ):
            button.toggled.connect(lambda *_: self._sync_mode_selector())
        self.host.toolbar.load_clicked.connect(
            self.host.workflow_controller.safe_load_estimate
        )

        self.host.primary_actions.save_clicked.connect(
            self.host.workflow_controller.save_estimate
        )
        self.host.primary_actions.print_clicked.connect(
            self.host.workflow_controller.print_estimate
        )
        self.host.primary_actions.new_clicked.connect(
            self.host.workflow_controller.clear_form
        )

        self.host.secondary_actions.delete_row_clicked.connect(
            self.host.workflow_controller.delete_current_row
        )
        self.host.secondary_actions.last_balance_clicked.connect(
            self.host.workflow_controller.show_last_balance_dialog
        )
        self.host.secondary_actions.history_clicked.connect(
            self.host.workflow_controller.show_history
        )
        self.host.secondary_actions.silver_bars_clicked.connect(
            self.host.workflow_controller.show_silver_bars
        )
        self.host.secondary_actions.refresh_rate_clicked.connect(
            self.host.workflow_controller.refresh_silver_rate
        )
        self.host.secondary_actions.delete_estimate_clicked.connect(
            self.host.workflow_controller.delete_current_estimate
        )
        self.host.command_history_action.triggered.connect(
            self.host.workflow_controller.show_history
        )
        self.host.command_settings_action.triggered.connect(
            self._show_settings_from_command_bar
        )

        self.host.item_table.cell_edited.connect(
            self.host.table_controller._on_table_cell_edited
        )
        self.host.item_table.column_layout_reset_requested.connect(
            self._reset_columns_layout
        )
        self.host.item_table.row_deleted.connect(
            self.host.table_controller._on_table_row_delete_requested
        )
        self.host.item_table.history_requested.connect(
            self.host.workflow_controller.show_history
        )
        # The right-click menu offers the same undo as the More menu.
        self.host.item_table.undo_row_action = self.host.command_undo_row_action

    def _bind_totals_panel_labels(self) -> None:
        self.host.mode_indicator_label = self.host.toolbar.mode_indicator_label

        self.host.overall_gross_label = self.host.totals_panel.overall_gross_label
        self.host.overall_poly_label = self.host.totals_panel.overall_poly_label
        self.host.total_gross_label = self.host.totals_panel.total_gross_label
        self.host.total_net_label = self.host.totals_panel.total_net_label
        self.host.total_fine_label = self.host.totals_panel.total_fine_label
        self.host.return_gross_label = self.host.totals_panel.return_gross_label
        self.host.return_net_label = self.host.totals_panel.return_net_label
        self.host.return_fine_label = self.host.totals_panel.return_fine_label
        self.host.bar_gross_label = self.host.totals_panel.bar_gross_label
        self.host.bar_net_label = self.host.totals_panel.bar_net_label
        self.host.bar_fine_label = self.host.totals_panel.bar_fine_label
        self.host.net_fine_label = self.host.totals_panel.net_fine_label
        self.host.net_wage_label = self.host.totals_panel.net_wage_label
        self.host.grand_total_label = self.host.totals_panel.grand_total_label

    def _normalize_totals_section_order(self, order) -> list[str]:
        return TotalsPanel.normalize_section_order(order)

    def _apply_totals_section_order(self, order, *, persist: bool = True) -> None:
        normalized = self._normalize_totals_section_order(order)
        self.host.totals_panel.set_section_order(normalized)
        # A reordered panel rebuilds its cards, and so its value labels.
        self._bind_totals_panel_labels()

        if persist:
            try:
                self._settings().set(
                    SettingsKey.UI_ESTIMATE_TOTALS_SECTION_ORDER,
                    ",".join(normalized),
                )
            except (AttributeError, RuntimeError, TypeError, ValueError) as exc:
                self.host.logger.debug(
                    "Failed to save totals section order setting: %s", exc
                )

    def _load_totals_section_order_setting(self) -> None:
        default_order = ",".join(TotalsPanel.default_section_order())
        try:
            saved = self._settings().get_text(
                SettingsKey.UI_ESTIMATE_TOTALS_SECTION_ORDER,
                default_order,
            )
        except AttributeError, RuntimeError, TypeError, ValueError:
            saved = default_order
        self._apply_totals_section_order(saved, persist=False)

    def _on_totals_section_order_changed(self, order) -> None:
        self._apply_totals_section_order(order, persist=True)

    def _create_totals_panel(self) -> TotalsPanel:
        panel = TotalsPanel()
        panel.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        panel.setMinimumWidth(280)
        panel.setMaximumWidth(440)
        panel.section_order_changed.connect(self._on_totals_section_order_changed)
        return panel

    def connect_signals(self, skip_load_estimate: bool = False):
        if not skip_load_estimate:
            self.host.voucher_edit.returnPressed.connect(
                self.host.workflow_controller.safe_load_estimate
            )

        self.host.silver_rate_spin.valueChanged.connect(
            self.host.workflow_controller._handle_silver_rate_changed
        )

        self.host.note_edit.textEdited.connect(self.host._mark_unsaved)
        self.host.date_edit.dateChanged.connect(self.host._mark_unsaved)

        self.host.item_table.cellClicked.connect(
            self.host.table_controller.cell_clicked
        )
        self.host.item_table.itemSelectionChanged.connect(
            self.host.table_controller.selection_changed
        )
        self.host.item_table.currentCellChanged.connect(
            self.host.table_controller.current_cell_changed
        )

        self.host.return_toggle_button.clicked.connect(
            self.host.workflow_controller.toggle_return_mode
        )
        self.host.silver_bar_toggle_button.clicked.connect(
            self.host.workflow_controller.toggle_silver_bar_mode
        )

    def _settings(self) -> ApplicationSettings:
        return get_app_settings()

    def _read_column_autofit_mode_setting(self) -> str:
        try:
            raw = self._settings().get_text(
                SettingsKey.UI_ESTIMATE_TABLE_AUTOFIT_MODE,
                "explicit",
            )
        except AttributeError, RuntimeError, TypeError, ValueError:
            raw = "explicit"
        mode = str(raw or "").strip().lower()
        if mode not in {"explicit", "continuous"}:
            mode = "explicit"
        return mode

    def _is_continuous_column_autofit_enabled(self) -> bool:
        return bool(
            self.host._auto_fit_columns_by_content
            and self.host._column_autofit_mode == "continuous"
        )

    def _column_width_limits(self) -> dict[int, tuple[int, int]]:
        return column_width_limits()

    def _default_column_widths(self) -> dict[int, int]:
        return default_column_widths()

    def _bounded_column_width(self, column: int, width: int) -> int:
        min_width, max_width = self._column_width_limits().get(column, (60, 700))
        return max(min_width, min(max_width, int(width)))

    def _apply_non_autofit_column_layout(
        self, saved_widths: dict[int, int] | None = None
    ) -> None:
        table = getattr(self.host, "item_table", None)
        if table is None or not isValid(table):
            return

        widths = dict(self._default_column_widths())
        if isinstance(saved_widths, dict):
            for col, width in saved_widths.items():
                if is_stretch_column(col):
                    continue
                if isinstance(col, int) and isinstance(width, int):
                    widths[col] = self._bounded_column_width(col, width)

        stretch_column = next(
            col for col in range(table.columnCount()) if is_stretch_column(col)
        )
        minimum = self._column_width_limits()[stretch_column][0]
        remaining = table.viewport().width() - sum(
            self._bounded_column_width(col, widths[col])
            for col in range(table.columnCount())
            if col != stretch_column and col in widths
        )
        self.host._programmatic_resizing = True
        try:
            for col in range(table.columnCount()):
                stretch = is_stretch_column(col) and remaining >= minimum
                table.set_column_stretch(col, stretch=stretch)
                if col == stretch_column and not stretch:
                    table.setColumnWidth(col, minimum)
                elif not stretch and col in widths:
                    table.setColumnWidth(
                        col, self._bounded_column_width(col, widths[col])
                    )
        except (AttributeError, RuntimeError, TypeError, ValueError) as exc:
            self.host.logger.debug("Failed to apply non-autofit column layout: %s", exc)
        finally:
            self.host._programmatic_resizing = False

    def _ensure_column_can_fit_content(self, column: int) -> None:
        if self._is_continuous_column_autofit_enabled():
            return
        if is_stretch_column(column):
            return

        table = getattr(self.host, "item_table", None)
        if table is None or not isValid(table):
            return
        if column < 0 or column >= table.columnCount():
            return

        model = table.model()
        if model is None or not isValid(model):
            return

        limits = self._column_width_limits()
        min_width, max_width = limits.get(column, (60, 700))
        metrics = table.fontMetrics()
        header_text = (
            model.headerData(
                column, Qt.Orientation.Horizontal, Qt.ItemDataRole.DisplayRole
            )
            or ""
        )
        header_width = metrics.horizontalAdvance(str(header_text)) + 12
        hint_width = table.sizeHintForColumn(column) + 2
        target_width = max(min_width, min(max_width, max(header_width, hint_width)))
        current_width = table.columnWidth(column)
        if target_width <= current_width:
            return

        self.host._programmatic_resizing = True
        try:
            table.setColumnWidth(column, int(target_width))
        except (AttributeError, RuntimeError, TypeError, ValueError) as exc:
            self.host.logger.debug(
                "Failed to expand column %s for content: %s", column, exc
            )
        finally:
            self.host._programmatic_resizing = False

    def grow_columns_to_content(self) -> None:
        """Widen any column whose text no longer fits; never shrink one.

        Cell edits already do this for the edited column. Rows filled in by
        code (an item lookup, the row type, a restored draft) need it too.
        """
        table = getattr(self.host, "item_table", None)
        if table is None or not isValid(table):
            return
        for column in range(table.columnCount()):
            self._ensure_column_can_fit_content(column)

    def _schedule_columns_autofit(
        self,
        columns: Optional[list[int]] = None,
        *,
        delay_ms: int = 70,
        force: bool = False,
    ) -> None:
        if not force and not self._is_continuous_column_autofit_enabled():
            return
        table = getattr(self.host, "item_table", None)
        if table is None or not isValid(table):
            return

        if columns is None:
            self.host._pending_autofit_columns.update(range(table.columnCount()))
        else:
            for col in columns:
                if isinstance(col, int) and 0 <= col < table.columnCount():
                    self.host._pending_autofit_columns.add(col)

        if not self.host._pending_autofit_columns:
            return

        try:
            self.host._column_autofit_timer.setInterval(max(0, int(delay_ms)))
            self.host._column_autofit_timer.start()
        except (AttributeError, RuntimeError, TypeError, ValueError) as exc:
            self.host.logger.debug("Failed to schedule column auto-fit: %s", exc)

    def _apply_pending_column_autofit(self) -> None:
        if not self.host.table_controller._is_table_valid():
            return

        table = self.host.item_table
        columns = sorted(self.host._pending_autofit_columns)
        self.host._pending_autofit_columns.clear()
        if not columns:
            if not self._is_continuous_column_autofit_enabled():
                return
            columns = list(range(table.columnCount()))

        model = table.model()
        if model is None or not isValid(model):
            return

        metrics = table.fontMetrics()
        limits = self._column_width_limits()

        self.host._programmatic_resizing = True
        try:
            for col in columns:
                if col < 0 or col >= table.columnCount():
                    continue

                header_text = (
                    model.headerData(
                        col, Qt.Orientation.Horizontal, Qt.ItemDataRole.DisplayRole
                    )
                    or ""
                )
                header_width = metrics.horizontalAdvance(str(header_text)) + 12
                hint_width = table.sizeHintForColumn(col) + 2
                target_width = max(header_width, hint_width)

                min_width, max_width = limits.get(col, (60, 700))
                target_width = max(min_width, min(max_width, int(target_width)))

                current_width = table.columnWidth(col)
                if abs(current_width - target_width) >= 2:
                    table.setColumnWidth(col, target_width)
        except (AttributeError, RuntimeError, TypeError, ValueError) as exc:
            self.host.logger.debug("Failed to auto-fit columns by content: %s", exc)
        finally:
            self.host._programmatic_resizing = False

    def _save_column_widths_setting(self):
        if self.host._auto_fit_columns_by_content:
            return
        try:
            widths = [
                str(
                    self.host.item_table.columnWidth(i)
                    if not is_stretch_column(i)
                    else -1
                )
                for i in range(self.host.item_table.columnCount())
            ]
            self._settings().set(
                SettingsKey.UI_ESTIMATE_TABLE_COLUMN_WIDTHS,
                ",".join(widths),
            )
        except (AttributeError, RuntimeError, TypeError, ValueError) as exc:
            self.host.logger.debug("Failed to save column widths setting: %s", exc)

    def _load_column_widths_setting(self):
        if self._is_continuous_column_autofit_enabled():
            self.host._programmatic_resizing = True
            try:
                for col in range(self.host.item_table.columnCount()):
                    self.host.item_table.set_column_stretch(col, stretch=False)
            finally:
                self.host._programmatic_resizing = False
            self._schedule_columns_autofit(delay_ms=0, force=True)
            return

        saved_widths: dict[int, int] = {}
        val = self._settings().get_text(SettingsKey.UI_ESTIMATE_TABLE_COLUMN_WIDTHS)
        if val:
            try:
                widths = [int(w) for w in val.split(",")]
                saved_widths = {
                    i: w
                    for i, w in enumerate(widths)
                    if (
                        i < self.host.item_table.columnCount()
                        and not is_stretch_column(i)
                        and w > 0
                    )
                }
            except (TypeError, ValueError) as exc:
                self.host.logger.debug(
                    "Failed to restore column widths setting: %s", exc
                )
        self._apply_non_autofit_column_layout(saved_widths)

    def _on_item_table_section_resized(self, idx, old, new):
        del old
        if self.host._programmatic_resizing or is_stretch_column(idx):
            return

        bounded_width = self._bounded_column_width(idx, new)
        if bounded_width != new:
            self.host._programmatic_resizing = True
            try:
                self.host.item_table.setColumnWidth(idx, bounded_width)
            finally:
                self.host._programmatic_resizing = False
            return

        self.host._column_save_timer.start()

    def _auto_stretch_item_name(self):
        if self.host._auto_fit_columns_by_content:
            return
        table = getattr(self.host, "item_table", None)
        if table is None or not isValid(table):
            return
        current_widths = {
            col: table.columnWidth(col)
            for col in range(table.columnCount())
            if not is_stretch_column(col)
        }
        self._apply_non_autofit_column_layout(current_widths)

    def _reset_columns_layout(self):
        if self._is_continuous_column_autofit_enabled():
            self._schedule_columns_autofit(delay_ms=0, force=True)
            return
        self._settings().remove(SettingsKey.UI_ESTIMATE_TABLE_COLUMN_WIDTHS)
        self._apply_non_autofit_column_layout()

    def _load_table_font_size_setting(self):
        size = self._settings().get_int(
            SettingsKey.UI_TABLE_FONT_SIZE,
            11,
            minimum=5,
            maximum=24,
        )
        self.apply_table_font_size(size)

    def _load_breakdown_font_size_setting(self):
        size = self._settings().get_int(
            SettingsKey.UI_BREAKDOWN_FONT_SIZE,
            11,
            minimum=5,
            maximum=24,
        )
        self.apply_breakdown_font_size(size)

    def _load_final_calc_font_size_setting(self):
        size = self._settings().get_int(
            SettingsKey.UI_FINAL_CALC_FONT_SIZE,
            16,
            minimum=5,
            maximum=24,
        )
        self.apply_final_calc_font_size(size)

    def apply_table_font_size(self, size: int) -> bool:
        try:
            size_i = int(size)
        except TypeError, ValueError:
            self.host.logger.warning("Invalid table font size value: %r", size)
            return False
        size_i = max(7, min(16, size_i))
        try:
            font = self.host.item_table.font()
            font.setPointSize(size_i)
            set_table_font(self.host.item_table, font)
            model = self.host.item_table.model()
            invalidate_style_cache = getattr(model, "invalidate_style_cache", None)
            if callable(invalidate_style_cache):
                invalidate_style_cache()
            row_height = max(
                24,
                self.host.item_table.fontMetrics().height()
                + (
                    12
                    if self._settings().get_text(SettingsKey.UI_ROW_DENSITY, "compact")
                    == "comfortable"
                    else 4
                ),
            )
            self.host.item_table.verticalHeader().setDefaultSectionSize(row_height)
            self.host.item_table.verticalHeader().setMinimumSectionSize(
                max(22, row_height - 2)
            )
            self.host.item_table.horizontalHeader().setFixedHeight(
                max(row_height + 2, header_height(self.host.item_table, 26))
            )
            self._schedule_columns_autofit(delay_ms=0, force=True)
            self.host.item_table.viewport().update()
            return True
        except Exception as exc:
            self.host.logger.warning("Failed to apply table font size: %s", exc)
            return False

    def apply_breakdown_font_size(self, size: int) -> bool:
        try:
            size_i = int(size)
        except TypeError, ValueError:
            self.host.logger.warning("Invalid breakdown font size value: %r", size)
            return False
        size_i = max(7, min(16, size_i))
        try:
            self.host.totals_panel.set_breakdown_font_size(size_i)
            return True
        except Exception as exc:
            self.host.logger.warning("Failed to apply breakdown font size: %s", exc)
            return False

    def apply_final_calc_font_size(self, size: int) -> bool:
        try:
            size_i = int(size)
        except TypeError, ValueError:
            self.host.logger.warning(
                "Invalid final calculation font size value: %r", size
            )
            return False
        size_i = max(8, min(20, size_i))
        try:
            self.host.totals_panel.set_final_calc_font_size(size_i)
            return True
        except Exception as exc:
            self.host.logger.warning(
                "Failed to apply final calculation font size: %s", exc
            )
            return False
