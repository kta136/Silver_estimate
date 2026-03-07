"""Layout and settings controller for estimate entry."""

from __future__ import annotations

from typing import Optional, cast

from PyQt5 import sip
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QHBoxLayout,
    QSizePolicy,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from silverestimate.infrastructure.settings import get_app_settings

from ._host_proxy import HostProxy
from .estimate_entry_components import (
    EstimateTableView,
    PrimaryActionsBar,
    SecondaryActionsBar,
    TotalsPanel,
    VoucherToolbar,
)
from .estimate_entry_theme import ESTIMATE_ENTRY_STYLESHEET
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
    CodeDelegate,
    NumericDelegate,
)


class EstimateEntryLayoutController(HostProxy):
    """Own layout wiring, totals placement, and persisted UI preferences."""

    def _setup_ui(self):
        self.host.setObjectName("EstimateEntryRoot")
        self.host.setStyleSheet(ESTIMATE_ENTRY_STYLESHEET)

        layout = QVBoxLayout(self.host)
        layout.setSpacing(6)
        layout.setContentsMargins(0, 0, 0, 0)

        header_container = QWidget()
        header_container.setObjectName("EstimateHeaderContainer")
        header_layout = QHBoxLayout(header_container)
        header_layout.setContentsMargins(8, 8, 8, 8)
        header_layout.setSpacing(8)

        self.toolbar = VoucherToolbar()
        self.toolbar.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        header_layout.addWidget(self.toolbar, 5)

        actions_panel = QWidget()
        actions_panel.setObjectName("EstimateHeaderActions")
        actions_panel_layout = QHBoxLayout(actions_panel)
        actions_panel_layout.setContentsMargins(0, 0, 0, 0)
        actions_panel_layout.setSpacing(8)

        self.primary_actions = PrimaryActionsBar(shortcut_parent=self.host)
        self.primary_actions.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        actions_panel_layout.addWidget(self.primary_actions)

        self.secondary_actions = SecondaryActionsBar(shortcut_parent=self.host)
        self.secondary_actions.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        actions_panel_layout.addWidget(self.secondary_actions)

        header_layout.addWidget(actions_panel, 4)
        layout.addWidget(header_container, 0)

        self._content_splitter = QSplitter(Qt.Horizontal)
        self._content_splitter.setChildrenCollapsible(False)
        self._content_splitter.setOpaqueResize(True)

        self.item_table = EstimateTableView()
        self.item_table.host_widget = self.host
        self.item_table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._content_splitter.addWidget(self.item_table)

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
        layout.setStretch(0, 0)
        layout.setStretch(1, 1)

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
        sidebar_panel = getattr(self, "_totals_panel_sidebar", None)
        live_rate_card = getattr(self.secondary_actions, "live_rate_container", None)
        if sidebar_panel is None or live_rate_card is None:
            return
        try:
            sidebar_panel.set_sidebar_top_widget(live_rate_card)
        except (AttributeError, RuntimeError, TypeError) as exc:
            self.logger.debug("Failed to move live-rate card to sidebar: %s", exc)
            return

        live_rate_divider = getattr(self.secondary_actions, "live_rate_divider", None)
        if live_rate_divider is not None:
            live_rate_divider.setVisible(False)

    def _sync_live_rate_card_placement(self, totals_position: str) -> None:
        normalized = self._normalize_totals_position(totals_position)
        sidebar_panel = getattr(self, "_totals_panel_sidebar", None)
        if sidebar_panel is None:
            return

        if normalized == "bottom":
            try:
                sidebar_panel.set_sidebar_top_widget(None)
            except (AttributeError, RuntimeError, TypeError):
                pass
            if hasattr(self.secondary_actions, "show_live_rate_in_header"):
                self.secondary_actions.show_live_rate_in_header(show_divider=True)
            return

        self._move_live_rate_card_to_summary_top()

    def _setup_table_delegates(self):
        code_delegate = CodeDelegate(parent=self.item_table)
        numeric_delegate = NumericDelegate(parent=self.item_table)
        self.item_table.setItemDelegateForColumn(COL_CODE, code_delegate)
        self.item_table.setItemDelegateForColumn(COL_GROSS, numeric_delegate)
        self.item_table.setItemDelegateForColumn(COL_POLY, numeric_delegate)
        self.item_table.setItemDelegateForColumn(COL_PURITY, numeric_delegate)
        self.item_table.setItemDelegateForColumn(COL_WAGE_RATE, numeric_delegate)
        self.item_table.setItemDelegateForColumn(COL_PIECES, numeric_delegate)

        self.item_table.setColumnWidth(COL_CODE, 82)
        self.item_table.setColumnWidth(COL_GROSS, 80)
        self.item_table.setColumnWidth(COL_POLY, 80)
        self.item_table.setColumnWidth(4, 82)
        self.item_table.setColumnWidth(COL_PURITY, 80)
        self.item_table.setColumnWidth(COL_WAGE_RATE, 82)
        self.item_table.setColumnWidth(COL_PIECES, 60)
        self.item_table.setColumnWidth(8, 82)
        self.item_table.setColumnWidth(9, 82)
        self.item_table.setColumnWidth(10, 78)

        header = self.item_table.horizontalHeader()
        header.sectionResized.connect(self._on_item_table_section_resized)

    def _wire_component_signals(self):
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
        self.mode_indicator_label = self.toolbar.mode_indicator_label

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
            except (AttributeError, RuntimeError, TypeError, ValueError) as exc:
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
        except (AttributeError, RuntimeError, TypeError, ValueError):
            saved = default_order
        self._apply_totals_section_order(saved, persist=False)

    def _on_totals_section_order_changed(self, order) -> None:
        sender = self.host.sender()
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
                sidebar_panel.setParent(cast(QWidget, None))
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
                bottom_panel.setParent(cast(QWidget, None))
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
            except (AttributeError, RuntimeError, TypeError, ValueError) as exc:
                self.logger.debug("Failed to save totals position setting: %s", exc)

    def _load_totals_position_setting(self) -> None:
        default_position = "right"
        try:
            saved = self._settings().value(
                "ui/estimate_totals_position",
                defaultValue=default_position,
                type=str,
            )
        except (AttributeError, RuntimeError, TypeError, ValueError):
            saved = default_position
        self._apply_totals_position(saved, persist=False)

    def _on_totals_position_requested(self, position: str) -> None:
        self._apply_totals_position(position, persist=True)

    def apply_totals_position(self, position: str) -> bool:
        try:
            self._apply_totals_position(position, persist=True)
            return True
        except Exception as exc:
            self.logger.warning("Failed to apply totals position: %s", exc)
            return False

    def connect_signals(self, skip_load_estimate: bool = False):
        if not skip_load_estimate:
            self.voucher_edit.returnPressed.connect(self.safe_load_estimate)

        self.silver_rate_spin.valueChanged.connect(self._handle_silver_rate_changed)

        if hasattr(self, "note_edit"):
            self.note_edit.textEdited.connect(self._mark_unsaved)
        if hasattr(self, "date_edit"):
            self.date_edit.dateChanged.connect(self._mark_unsaved)

        self.item_table.cellClicked.connect(self.cell_clicked)
        self.item_table.itemSelectionChanged.connect(self.selection_changed)
        self.item_table.currentCellChanged.connect(self.current_cell_changed)

        self.return_toggle_button.clicked.connect(self.toggle_return_mode)
        self.silver_bar_toggle_button.clicked.connect(self.toggle_silver_bar_mode)

    def _settings(self):
        return get_app_settings()

    def _read_column_autofit_mode_setting(self) -> str:
        try:
            raw = self._settings().value(
                "ui/estimate_table_autofit_mode",
                defaultValue="explicit",
                type=str,
            )
        except (AttributeError, RuntimeError, TypeError, ValueError):
            raw = "explicit"
        mode = str(raw or "").strip().lower()
        if mode not in {"explicit", "continuous"}:
            mode = "explicit"
        return mode

    def _is_continuous_column_autofit_enabled(self) -> bool:
        return bool(
            self._auto_fit_columns_by_content
            and self._column_autofit_mode == "continuous"
        )

    def _column_width_limits(self) -> dict[int, tuple[int, int]]:
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

    def _default_column_widths(self) -> dict[int, int]:
        return {
            COL_CODE: 82,
            COL_GROSS: 80,
            COL_POLY: 80,
            COL_NET_WT: 82,
            COL_PURITY: 80,
            COL_WAGE_RATE: 82,
            COL_PIECES: 60,
            COL_WAGE_AMT: 82,
            COL_FINE_WT: 82,
            COL_TYPE: 78,
        }

    def _apply_non_autofit_column_layout(
        self, saved_widths: dict[int, int] | None = None
    ) -> None:
        table = getattr(self, "item_table", None)
        if table is None or sip.isdeleted(table):
            return

        widths = dict(self._default_column_widths())
        if isinstance(saved_widths, dict):
            for col, width in saved_widths.items():
                if col == COL_ITEM_NAME:
                    continue
                if isinstance(col, int) and isinstance(width, int):
                    widths[col] = width

        self._programmatic_resizing = True
        try:
            for col in range(table.columnCount()):
                stretch = col == COL_ITEM_NAME
                table.set_column_stretch(col, stretch=stretch)
                if not stretch and col in widths:
                    table.setColumnWidth(col, widths[col])
        except (AttributeError, RuntimeError, TypeError, ValueError) as exc:
            self.logger.debug("Failed to apply non-autofit column layout: %s", exc)
        finally:
            self._programmatic_resizing = False

    def _ensure_column_can_fit_content(self, column: int) -> None:
        if self._is_continuous_column_autofit_enabled():
            return
        if column == COL_ITEM_NAME:
            return

        table = getattr(self, "item_table", None)
        if table is None or sip.isdeleted(table):
            return
        if column < 0 or column >= table.columnCount():
            return

        model = table.model()
        if model is None or sip.isdeleted(model):
            return

        limits = self._column_width_limits()
        min_width, max_width = limits.get(column, (60, 700))
        metrics = table.fontMetrics()
        header_text = model.headerData(column, Qt.Horizontal, Qt.DisplayRole) or ""
        header_width = metrics.horizontalAdvance(str(header_text)) + 28
        hint_width = table.sizeHintForColumn(column) + 16
        target_width = max(min_width, min(max_width, max(header_width, hint_width)))
        current_width = table.columnWidth(column)
        if target_width <= current_width:
            return

        self._programmatic_resizing = True
        try:
            table.setColumnWidth(column, int(target_width))
        except (AttributeError, RuntimeError, TypeError, ValueError) as exc:
            self.logger.debug("Failed to expand column %s for content: %s", column, exc)
        finally:
            self._programmatic_resizing = False

    def _schedule_columns_autofit(
        self,
        columns: Optional[list[int]] = None,
        *,
        delay_ms: int = 70,
        force: bool = False,
    ) -> None:
        if not force and not self._is_continuous_column_autofit_enabled():
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
        except (AttributeError, RuntimeError, TypeError, ValueError) as exc:
            self.logger.debug("Failed to schedule column auto-fit: %s", exc)

    def _apply_pending_column_autofit(self) -> None:
        if not self._is_table_valid():
            return

        table = self.item_table
        columns = sorted(self._pending_autofit_columns)
        self._pending_autofit_columns.clear()
        if not columns:
            if not self._is_continuous_column_autofit_enabled():
                return
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
        except (AttributeError, RuntimeError, TypeError, ValueError) as exc:
            self.logger.debug("Failed to auto-fit columns by content: %s", exc)
        finally:
            self._programmatic_resizing = False

    def _save_column_widths_setting(self):
        if self._auto_fit_columns_by_content:
            return
        try:
            widths = [
                str(self.item_table.columnWidth(i) if i != COL_ITEM_NAME else -1)
                for i in range(self.item_table.columnCount())
            ]
            self._settings().setValue(
                "ui/estimate_table_column_widths", ",".join(widths)
            )
        except (AttributeError, RuntimeError, TypeError, ValueError) as exc:
            self.logger.debug("Failed to save column widths setting: %s", exc)

    def _load_column_widths_setting(self):
        if self._is_continuous_column_autofit_enabled():
            self._programmatic_resizing = True
            try:
                for col in range(self.item_table.columnCount()):
                    self.item_table.set_column_stretch(col, stretch=False)
            finally:
                self._programmatic_resizing = False
            self._schedule_columns_autofit(delay_ms=0, force=True)
            return

        saved_widths: dict[int, int] = {}
        val = self._settings().value("ui/estimate_table_column_widths", type=str)
        if val:
            try:
                widths = [int(w) for w in val.split(",")]
                for i, w in enumerate(widths):
                    if (
                        i < self.item_table.columnCount()
                        and i != COL_ITEM_NAME
                        and w > 0
                    ):
                        saved_widths[i] = w
            except (TypeError, ValueError) as exc:
                self.logger.debug("Failed to restore column widths setting: %s", exc)
        self._apply_non_autofit_column_layout(saved_widths)

    def _on_item_table_section_resized(self, idx, old, new):
        del old, new
        if not self._programmatic_resizing and idx != COL_ITEM_NAME:
            self._column_save_timer.start()

    def _auto_stretch_item_name(self):
        if self._auto_fit_columns_by_content:
            return
        table = getattr(self, "item_table", None)
        if table is None or sip.isdeleted(table):
            return
        current_widths = {
            col: table.columnWidth(col)
            for col in range(table.columnCount())
            if col != COL_ITEM_NAME
        }
        self._apply_non_autofit_column_layout(current_widths)

    def _reset_columns_layout(self):
        if self._is_continuous_column_autofit_enabled():
            self._schedule_columns_autofit(delay_ms=0, force=True)
            return
        self._settings().remove("ui/estimate_table_column_widths")
        self._apply_non_autofit_column_layout()

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
            row_height = max(28, min(38, size_i + 20))
            self.item_table.verticalHeader().setDefaultSectionSize(row_height)
            self.item_table.verticalHeader().setMinimumSectionSize(
                max(26, row_height - 2)
            )
            self._schedule_columns_autofit(delay_ms=0, force=True)
            self.item_table.viewport().update()
            return True
        except Exception as exc:
            self.logger.warning("Failed to apply table font size: %s", exc)
            return False

    def apply_breakdown_font_size(self, size: int) -> bool:
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
