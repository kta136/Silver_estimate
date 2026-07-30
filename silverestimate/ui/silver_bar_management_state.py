"""State persistence helpers for silver-bar management."""

from __future__ import annotations

from contextlib import suppress
from datetime import datetime, timedelta

from PySide6.QtCore import Qt

from silverestimate.infrastructure.settings import (
    ApplicationSettings,
    SettingsKey,
    get_app_settings,
)

from ._host_proxy import HostProxy


class SilverBarManagementStateStore(HostProxy):
    """Persist and restore dialog state, filters, and navigation context."""

    def _settings(self) -> ApplicationSettings:
        return get_app_settings()

    def _save_table_sort_state(self, which, table):
        try:
            settings = self._settings()
            header = table.horizontalHeader()
            if which == "available":
                column_key = SettingsKey.UI_SILVER_BARS_AVAILABLE_SORT_COLUMN
                order_key = SettingsKey.UI_SILVER_BARS_AVAILABLE_SORT_ORDER
            elif which == "list":
                column_key = SettingsKey.UI_SILVER_BARS_LIST_SORT_COLUMN
                order_key = SettingsKey.UI_SILVER_BARS_LIST_SORT_ORDER
            else:
                raise ValueError(f"Unknown silver-bar table: {which}")
            settings.set(column_key, header.sortIndicatorSection())
            settings.set(order_key, int(header.sortIndicatorOrder()))
        except Exception as exc:
            self.logger.debug("Could not persist %s table sort state: %s", which, exc)

    def _save_ui_state(self):
        try:
            settings = self._settings()
            settings.set(
                SettingsKey.UI_SILVER_BARS_GEOMETRY,
                self.host.saveGeometry(),
            )
            if hasattr(self, "_splitter"):
                settings.set(
                    SettingsKey.UI_SILVER_BARS_SPLITTER,
                    self._splitter.saveState(),
                )
            settings.set(
                SettingsKey.UI_SILVER_BARS_AVAILABLE_COLUMNS,
                self._get_table_column_widths(self.available_bars_table),
            )
            settings.set(
                SettingsKey.UI_SILVER_BARS_LIST_COLUMNS,
                self._get_table_column_widths(self.list_bars_table),
            )
            self._save_table_sort_state("available", self.available_bars_table)
            self._save_table_sort_state("list", self.list_bars_table)
            settings.set(
                SettingsKey.UI_SILVER_BARS_WEIGHT_QUERY,
                self.weight_search_edit.text(),
            )
            settings.set(
                SettingsKey.UI_SILVER_BARS_CURRENT_LIST_ID,
                self.current_list_id,
            )
            settings.set(
                SettingsKey.UI_SILVER_BARS_DATE_RANGE,
                self.date_range_combo.currentText(),
            )
            settings.sync()
        except Exception as exc:
            self.logger.debug(
                "Failed to save silver bar dialog state: %s", exc, exc_info=True
            )

    def _restore_ui_state(self):
        try:
            settings = self._settings()
            geometry = settings.read(SettingsKey.UI_SILVER_BARS_GEOMETRY)
            if geometry:
                self.host.restoreGeometry(geometry)

            state = settings.read(SettingsKey.UI_SILVER_BARS_SPLITTER)
            if state and hasattr(self, "_splitter"):
                self._splitter.restoreState(state)
            if hasattr(self, "_splitter"):
                self._splitter.setOrientation(Qt.Orientation.Horizontal)

            if settings.contains(SettingsKey.UI_SILVER_BARS_DATE_RANGE):
                dr = settings.get_text(SettingsKey.UI_SILVER_BARS_DATE_RANGE)
                idx = self.date_range_combo.findText(dr)
                if idx >= 0:
                    self.date_range_combo.setCurrentIndex(idx)

            weight_query = settings.get_text(SettingsKey.UI_SILVER_BARS_WEIGHT_QUERY)
            self.weight_search_edit.setText(weight_query)

            if settings.contains(
                SettingsKey.UI_SILVER_BARS_AVAILABLE_SORT_COLUMN
            ) and settings.contains(SettingsKey.UI_SILVER_BARS_AVAILABLE_SORT_ORDER):
                av_col = settings.get_int(
                    SettingsKey.UI_SILVER_BARS_AVAILABLE_SORT_COLUMN
                )
                av_ord = settings.get_int(
                    SettingsKey.UI_SILVER_BARS_AVAILABLE_SORT_ORDER
                )
                self.available_bars_table.sortByColumn(av_col, Qt.SortOrder(av_ord))
            if settings.contains(
                SettingsKey.UI_SILVER_BARS_LIST_SORT_COLUMN
            ) and settings.contains(SettingsKey.UI_SILVER_BARS_LIST_SORT_ORDER):
                ls_col = settings.get_int(SettingsKey.UI_SILVER_BARS_LIST_SORT_COLUMN)
                ls_ord = settings.get_int(SettingsKey.UI_SILVER_BARS_LIST_SORT_ORDER)
                self.list_bars_table.sortByColumn(ls_col, Qt.SortOrder(ls_ord))
        except (AttributeError, RuntimeError, TypeError, ValueError) as exc:
            self.logger.debug(
                "Failed to restore silver bar dialog state: %s", exc, exc_info=True
            )

    def _restore_selected_list_from_settings(self):
        try:
            settings = self._settings()
            saved_id = settings.read(SettingsKey.UI_SILVER_BARS_CURRENT_LIST_ID)
            if saved_id is None:
                return
            saved_id_int = saved_id
            if isinstance(saved_id, (str, int, float, bytes, bytearray)):
                with suppress(ValueError):
                    saved_id_int = int(saved_id)
            idx = self.list_combo.findData(saved_id_int)
            if idx >= 0:
                self.list_combo.setCurrentIndex(idx)
        except Exception as exc:
            self.logger.debug("Could not restore selected silver bar list: %s", exc)

    def _get_table_column_widths(self, table):
        try:
            header = table.horizontalHeader()
            return [header.sectionSize(i) for i in range(table.model().columnCount())]
        except Exception as exc:
            self.logger.debug("Could not capture table column widths: %s", exc)
            return None

    def _apply_table_column_widths(self, table, widths):
        try:
            if not widths:
                return
            header = table.horizontalHeader()
            for index, width in enumerate(widths):
                if (
                    index < table.model().columnCount()
                    and isinstance(width, int)
                    and width > 0
                ):
                    header.resizeSection(index, width)
        except Exception as exc:
            self.logger.debug("Could not apply stored table widths: %s", exc)

    def _restore_table_column_widths(self):
        try:
            settings = self._settings()
            available = settings.get_list(SettingsKey.UI_SILVER_BARS_AVAILABLE_COLUMNS)
            list_cols = settings.get_list(SettingsKey.UI_SILVER_BARS_LIST_COLUMNS)
            self._apply_table_column_widths(self.available_bars_table, available)
            self._apply_table_column_widths(self.list_bars_table, list_cols)
        except Exception as exc:
            self.logger.debug("Could not restore table column widths: %s", exc)

    def _current_date_range(self):
        try:
            text = self.date_range_combo.currentText()
        except Exception as exc:
            self.logger.debug("Could not read date range combo value: %s", exc)
            return None
        now = datetime.now()
        if text == "Today":
            start = datetime(now.year, now.month, now.day)
            end = now
        elif text == "Last 7 days":
            start = now - timedelta(days=7)
            end = now
        elif text == "Last 30 days":
            start = now - timedelta(days=30)
            end = now
        elif text == "This Month":
            start = datetime(now.year, now.month, 1)
            end = now
        else:
            return None
        return (start.strftime("%Y-%m-%d %H:%M:%S"), end.strftime("%Y-%m-%d %H:%M:%S"))

    def _find_main_window(self):
        try:
            widget = self.host.parent()
            while widget is not None:
                if hasattr(widget, "show_estimate") and hasattr(widget, "stack"):
                    return widget
                widget = widget.parent()
        except Exception as exc:
            self.logger.debug(
                "Could not resolve main window from silver bar dialog: %s", exc
            )
        return None

    def _is_embedded(self):
        try:
            main_window = self._find_main_window()
            if not main_window:
                return False
            stack = getattr(main_window, "stack", None)
            if stack is None:
                return False
            return stack.indexOf(self.host) != -1
        except (AttributeError, RuntimeError, TypeError) as exc:
            self.logger.debug("Could not determine embedded silver bar state: %s", exc)
            return False

    def _navigate_back_to_estimate(self):
        try:
            main_window = self._find_main_window()
            if main_window and hasattr(main_window, "show_estimate"):
                main_window.show_estimate()
        except Exception as exc:
            self.logger.debug("Could not navigate back to estimate view: %s", exc)
