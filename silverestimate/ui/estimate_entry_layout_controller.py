"""Layout and settings controller for estimate entry."""

from __future__ import annotations

import os
from typing import Any, Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QHBoxLayout,
    QMenu,
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
from .icons import get_icon
from .modern_components import BottomStatusStrip, polish_dense_table


class EstimateEntryLayoutController:
    """Own layout wiring, totals placement, and persisted UI preferences."""

    def __init__(self, host: Any) -> None:
        self.host = host

    _totals_panel_sidebar: TotalsPanel | None
    _totals_panel_bottom: TotalsPanel | None

    def _setup_ui(self):
        self.host.setObjectName("EstimateEntryRoot")
        self.host.setStyleSheet(ESTIMATE_ENTRY_STYLESHEET)

        layout = QVBoxLayout(self.host)
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)

        header_container = QWidget()
        header_container.setObjectName("EstimateHeaderContainer")
        header_container.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        header_layout = QHBoxLayout(header_container)
        header_layout.setContentsMargins(8, 4, 8, 4)
        header_layout.setSpacing(6)

        self.host.toolbar = VoucherToolbar()
        self.host.toolbar.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        header_layout.addWidget(self.host.toolbar, 5)

        self.host.primary_actions = PrimaryActionsBar(shortcut_parent=self.host)
        self.host.primary_actions.setSizePolicy(
            QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed
        )
        header_layout.addWidget(self.host.primary_actions)

        self.host.secondary_actions = SecondaryActionsBar(shortcut_parent=self.host)
        self.host.secondary_actions.setVisible(False)
        self.host.secondary_actions.setSizePolicy(
            QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed
        )
        header_layout.addWidget(self.host.secondary_actions)

        self.host.estimate_tools_button = QToolButton()
        self.host.estimate_tools_button.setObjectName("EstimateToolsButton")
        self.host.estimate_tools_button.setText("Tools")
        self.host.estimate_tools_button.setIcon(get_icon("tools", widget=self.host))
        self.host.estimate_tools_button.setPopupMode(
            QToolButton.ToolButtonPopupMode.InstantPopup
        )
        self.host.estimate_tools_button.setToolButtonStyle(
            Qt.ToolButtonStyle.ToolButtonTextBesideIcon
        )
        self.host.estimate_tools_button.setToolTip("Estimate row and silver-bar tools")
        self.host.estimate_tools_button.setMenu(self._build_estimate_tools_menu())
        header_layout.addWidget(self.host.estimate_tools_button)
        layout.addWidget(header_container, 0)

        self.host._content_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.host._content_splitter.setChildrenCollapsible(False)
        self.host._content_splitter.setOpaqueResize(True)

        self.host.item_table = EstimateTableView()
        self.host.item_table.host_widget = self.host
        polish_dense_table(
            self.host.item_table,
            row_height=26,
            header_height=28,
            show_grid=True,
            hide_vertical_header=False,
        )
        self.host.item_table.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        self.host._content_splitter.addWidget(self.host.item_table)

        self.host._totals_position = self._read_totals_position_setting()
        layout_mode = (
            "horizontal" if self.host._totals_position == "bottom" else "sidebar"
        )
        self.host.totals_panel = self._create_totals_panel(layout_mode)
        self._place_totals_panel(
            self.host._content_splitter, self.host._totals_position
        )

        layout.addWidget(self.host._content_splitter, 1)
        self.host.bottom_status_strip = BottomStatusStrip(self.host)
        self.host.bottom_status_strip.set_left_items(
            [
                "Ctrl+S Save",
                "Ctrl+P Print",
                "Ctrl+N New",
                "Ctrl+H History",
                "Ctrl+D Delete Row",
                "Ctrl+R Return",
                "Ctrl+B Silver Bar",
                "PgUp/PgDn Rows",
            ]
        )
        layout.addWidget(self.host.bottom_status_strip, 0)
        layout.setStretch(0, 0)
        layout.setStretch(1, 1)
        layout.setStretch(2, 0)

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

        self._sync_live_rate_card_placement(self.host._totals_position)

        self._bind_totals_panel_labels()

        self.host.unsaved_badge = self.host.toolbar.unsaved_badge
        self.host.status_message_label = self.host.toolbar.status_message_label
        self._update_bottom_status_strip()

        try:
            model = self.host.item_table.model()
            model.rowsInserted.connect(lambda *_: self._update_bottom_status_strip())
            model.rowsRemoved.connect(lambda *_: self._update_bottom_status_strip())
            model.modelReset.connect(lambda *_: self._update_bottom_status_strip())
        except (AttributeError, RuntimeError, TypeError) as exc:
            self.host.logger.debug(
                "Failed to bind bottom status strip table updates: %s", exc
            )

    def _build_estimate_tools_menu(self) -> QMenu:
        menu = QMenu(self.host)

        self.host.command_history_action = QAction(
            get_icon("history", widget=self.host), "Estimate History", menu
        )
        menu.addAction(self.host.command_history_action)

        self.host.command_settings_action = QAction(
            get_icon("settings", widget=self.host), "Application Settings", menu
        )
        menu.addAction(self.host.command_settings_action)
        menu.addSeparator()

        delete_row = QAction(
            get_icon("delete_row", widget=self.host, color="#dc2626"),
            "Delete Current Row",
            menu,
        )
        delete_row.triggered.connect(
            self.host.secondary_actions.delete_row_clicked.emit
        )
        menu.addAction(delete_row)
        menu.addSeparator()

        return_mode = QAction(
            get_icon("return_mode", widget=self.host, color="#2563eb"),
            "Return Mode",
            menu,
        )
        return_mode.setCheckable(True)
        return_mode.triggered.connect(
            lambda _checked=False: self.host.return_toggle_button.click()
        )
        menu.addAction(return_mode)

        silver_bar_mode = QAction(
            get_icon("bar_mode", widget=self.host, color="#0f766e"),
            "Silver Bar Mode",
            menu,
        )
        silver_bar_mode.setCheckable(True)
        silver_bar_mode.triggered.connect(
            lambda _checked=False: self.host.silver_bar_toggle_button.click()
        )
        menu.addAction(silver_bar_mode)
        menu.addSeparator()

        balance = QAction(
            get_icon("balance", widget=self.host), "Add Last Balance", menu
        )
        balance.triggered.connect(self.host.secondary_actions.last_balance_clicked.emit)
        menu.addAction(balance)

        bars = QAction(
            get_icon("silver_bars", widget=self.host), "Silver Bar Manager", menu
        )
        bars.triggered.connect(self.host.secondary_actions.silver_bars_clicked.emit)
        menu.addAction(bars)

        refresh = QAction(
            get_icon("refresh", widget=self.host, color="#0f766e"),
            "Refresh Live Rate",
            menu,
        )
        refresh.triggered.connect(self.host.secondary_actions.refresh_rate_clicked.emit)
        menu.addAction(refresh)
        menu.addSeparator()

        delete_estimate = QAction(
            get_icon("delete_estimate", widget=self.host, color="#dc2626"),
            "Delete Current Estimate",
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

    def _update_bottom_status_strip(self) -> None:
        strip = getattr(self.host, "bottom_status_strip", None)
        if strip is None:
            return
        try:
            rows = self.host.item_table.rowCount()
        except Exception:
            rows = 0
        try:
            user = os.environ.get("USERNAME") or os.environ.get("USER") or "-"
        except Exception:
            user = "-"
        last_saved = getattr(self.host, "_last_saved_status", "-")
        strip.set_right_items(
            [f"Rows: {rows}", f"Last Saved: {last_saved}", f"User: {user}"]
        )

    def refresh_bottom_status(self) -> None:
        self._update_bottom_status_strip()

    def _show_settings_from_command_bar(self) -> None:
        main_window = getattr(self.host, "main_window", None)
        opener = getattr(main_window, "show_settings_dialog", None)
        if callable(opener):
            opener()

    def _move_live_rate_card_to_summary_top(self) -> None:
        sidebar_panel = getattr(self.host, "totals_panel", None)
        live_rate_card = getattr(
            self.host.secondary_actions, "live_rate_container", None
        )
        if (
            sidebar_panel is None
            or sidebar_panel.layout_mode != "sidebar"
            or live_rate_card is None
        ):
            return
        live_rate_card.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        try:
            sidebar_panel.set_sidebar_top_widget(live_rate_card)
        except (AttributeError, RuntimeError, TypeError) as exc:
            self.host.logger.debug("Failed to move live-rate card to sidebar: %s", exc)
            return

        live_rate_divider = getattr(
            self.host.secondary_actions, "live_rate_divider", None
        )
        if live_rate_divider is not None:
            live_rate_divider.setVisible(False)

    def _sync_live_rate_card_placement(self, totals_position: str) -> None:
        normalized = self._normalize_totals_position(totals_position)
        if normalized == "bottom":
            if hasattr(self.host.secondary_actions, "show_live_rate_in_header"):
                self.host.secondary_actions.show_live_rate_in_header(show_divider=True)
            return

        self._move_live_rate_card_to_summary_top()

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

    def _wire_component_signals(self):
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
        panel = getattr(self.host, "totals_panel", None)
        if (
            panel is not None
            and isValid(panel)
            and (panel is not source_panel or panel.section_order() != normalized)
        ):
            panel.set_section_order(normalized)
        self.host._totals_section_order = list(normalized)
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
        sender = self.host.sender()
        source_panel = sender if isinstance(sender, TotalsPanel) else None
        self._apply_totals_section_order(order, persist=True, source_panel=source_panel)

    def _apply_totals_position(self, position: str, *, persist: bool = True) -> None:
        normalized = self._normalize_totals_position(position)
        splitter_obj = getattr(self.host, "_content_splitter", None)
        if splitter_obj is None or not isValid(splitter_obj):
            return
        splitter = splitter_obj

        desired_mode = "horizontal" if normalized == "bottom" else "sidebar"
        current_panel = self.host.totals_panel
        if current_panel.layout_mode != desired_mode:
            section_order = current_panel.section_order()
            if current_panel.layout_mode == "sidebar":
                current_panel.set_sidebar_top_widget(None)
            current_panel.setParent(None)
            current_panel.deleteLater()
            self.host.totals_panel = self._create_totals_panel(desired_mode)
            self.host.totals_panel.set_section_order(section_order)

        self._place_totals_panel(splitter, normalized)

        self._sync_live_rate_card_placement(normalized)
        self._bind_totals_panel_labels()
        self.host.totals_controller.calculate_totals()
        self.host._totals_position = normalized

        if persist:
            try:
                self._settings().set(
                    SettingsKey.UI_ESTIMATE_TOTALS_POSITION,
                    normalized,
                )
            except (AttributeError, RuntimeError, TypeError, ValueError) as exc:
                self.host.logger.debug(
                    "Failed to save totals position setting: %s", exc
                )

    def _load_totals_position_setting(self) -> None:
        self._apply_totals_position(self._read_totals_position_setting(), persist=False)

    def _read_totals_position_setting(self) -> str:
        try:
            saved = self._settings().get_text(
                SettingsKey.UI_ESTIMATE_TOTALS_POSITION,
                "right",
            )
        except AttributeError, RuntimeError, TypeError, ValueError:
            saved = "right"
        return self._normalize_totals_position(saved)

    def _create_totals_panel(self, layout_mode: str) -> TotalsPanel:
        panel = TotalsPanel(layout_mode=layout_mode)
        if layout_mode == "sidebar":
            panel.setSizePolicy(
                QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding
            )
            panel.setMinimumWidth(275)
            panel.setMaximumWidth(420)
            self.host._totals_panel_sidebar = panel
            self.host._totals_panel_bottom = None
        else:
            panel.setSizePolicy(
                QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum
            )
            panel.setMinimumWidth(0)
            panel.setMaximumWidth(16777215)
            panel.setMaximumHeight(280)
            self.host._totals_panel_sidebar = None
            self.host._totals_panel_bottom = panel

        section_order = getattr(self.host, "_totals_section_order", None)
        if section_order:
            panel.set_section_order(section_order)
        breakdown_size = getattr(self.host, "_breakdown_font_size", None)
        if breakdown_size is not None:
            panel.set_breakdown_font_size(breakdown_size)
        final_size = getattr(self.host, "_final_calc_font_size", None)
        if final_size is not None:
            panel.set_final_calc_font_size(final_size)
        panel.section_order_changed.connect(self._on_totals_section_order_changed)
        return panel

    def _place_totals_panel(
        self, splitter: QSplitter, normalized_position: str
    ) -> None:
        panel = self.host.totals_panel
        if normalized_position == "bottom":
            splitter.setOrientation(Qt.Orientation.Vertical)
            splitter.insertWidget(0, self.host.item_table)
            splitter.insertWidget(1, panel)
            splitter.setStretchFactor(0, 1)
            splitter.setStretchFactor(1, 0)
            splitter.setSizes([860, 200])
            return

        splitter.setOrientation(Qt.Orientation.Horizontal)
        if normalized_position == "left":
            splitter.insertWidget(0, panel)
            splitter.insertWidget(1, self.host.item_table)
            splitter.setStretchFactor(0, 0)
            splitter.setStretchFactor(1, 1)
            splitter.setSizes([320, 1060])
        else:
            splitter.insertWidget(0, self.host.item_table)
            splitter.insertWidget(1, panel)
            splitter.setStretchFactor(0, 1)
            splitter.setStretchFactor(1, 0)
            splitter.setSizes([1060, 320])

    def _on_totals_position_requested(self, position: str) -> None:
        self._apply_totals_position(position, persist=True)

    def apply_totals_position(self, position: str) -> bool:
        try:
            self._apply_totals_position(position, persist=True)
            return True
        except Exception as exc:
            self.host.logger.warning("Failed to apply totals position: %s", exc)
            return False

    def connect_signals(self, skip_load_estimate: bool = False):
        if not skip_load_estimate:
            self.host.voucher_edit.returnPressed.connect(
                self.host.workflow_controller.safe_load_estimate
            )

        self.host.silver_rate_spin.valueChanged.connect(
            self.host.workflow_controller._handle_silver_rate_changed
        )

        if hasattr(self.host, "note_edit"):
            self.host.note_edit.textEdited.connect(self.host._mark_unsaved)
        if hasattr(self.host, "date_edit"):
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

        self.host._programmatic_resizing = True
        try:
            for col in range(table.columnCount()):
                stretch = is_stretch_column(col)
                table.set_column_stretch(col, stretch=stretch)
                if not stretch and col in widths:
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
        header_width = metrics.horizontalAdvance(str(header_text)) + 28
        hint_width = table.sizeHintForColumn(column) + 16
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
                header_width = metrics.horizontalAdvance(str(header_text)) + 28
                hint_width = table.sizeHintForColumn(col) + 16
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
            9,
            minimum=5,
            maximum=24,
        )
        self.apply_table_font_size(size)

    def _load_breakdown_font_size_setting(self):
        size = self._settings().get_int(
            SettingsKey.UI_BREAKDOWN_FONT_SIZE,
            9,
            minimum=5,
            maximum=24,
        )
        self.apply_breakdown_font_size(size)

    def _load_final_calc_font_size_setting(self):
        size = self._settings().get_int(
            SettingsKey.UI_FINAL_CALC_FONT_SIZE,
            10,
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
            self.host.item_table.setFont(font)
            model = self.host.item_table.model()
            invalidate_style_cache = getattr(model, "invalidate_style_cache", None)
            if callable(invalidate_style_cache):
                invalidate_style_cache()
            row_height = max(24, min(32, size_i + 17))
            self.host.item_table.verticalHeader().setDefaultSectionSize(row_height)
            self.host.item_table.verticalHeader().setMinimumSectionSize(
                max(22, row_height - 2)
            )
            self.host.item_table.horizontalHeader().setFixedHeight(
                max(26, min(34, row_height + 2))
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
            self.host._breakdown_font_size = size_i
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
            self.host._final_calc_font_size = size_i
            self.host.totals_panel.set_final_calc_font_size(size_i)
            return True
        except Exception as exc:
            self.host.logger.warning(
                "Failed to apply final calculation font size: %s", exc
            )
            return False
