"""State persistence helpers for silver-bar management."""

from __future__ import annotations

from datetime import datetime, timedelta

from PyQt5.QtCore import Qt

from silverestimate.infrastructure.settings import get_app_settings

from ._host_proxy import HostProxy


class SilverBarManagementStateStore(HostProxy):
    """Persist and restore dialog state, filters, and navigation context."""

    def _settings(self):
        return get_app_settings()

    def _save_table_sort_state(self, which, table):
        try:
            settings = self._settings()
            header = table.horizontalHeader()
            settings.setValue(
                f"ui/silver_bars/{which}_sort_col", header.sortIndicatorSection()
            )
            settings.setValue(
                f"ui/silver_bars/{which}_sort_order", int(header.sortIndicatorOrder())
            )
        except Exception as exc:
            self.logger.debug("Could not persist %s table sort state: %s", which, exc)

    def _save_ui_state(self):
        try:
            settings = self._settings()
            settings.setValue("ui/silver_bars/geometry", self.host.saveGeometry())
            if hasattr(self, "_splitter"):
                settings.setValue("ui/silver_bars/splitter_h", self._splitter.saveState())
            settings.setValue(
                "ui/silver_bars/available_cols",
                self._get_table_column_widths(self.available_bars_table),
            )
            settings.setValue(
                "ui/silver_bars/list_cols",
                self._get_table_column_widths(self.list_bars_table),
            )
            self._save_table_sort_state("available", self.available_bars_table)
            self._save_table_sort_state("list", self.list_bars_table)
            settings.setValue("ui/silver_bars/weight_query", self.weight_search_edit.text())
            settings.setValue("ui/silver_bars/current_list_id", self.current_list_id)
            settings.setValue(
                "ui/silver_bars/weight_tol", float(self.weight_tol_spin.value())
            )
            settings.setValue(
                "ui/silver_bars/purity_min", float(self.purity_min_spin.value())
            )
            settings.setValue(
                "ui/silver_bars/purity_max", float(self.purity_max_spin.value())
            )
            settings.setValue(
                "ui/silver_bars/date_range", self.date_range_combo.currentText()
            )
            settings.setValue(
                "ui/silver_bars/auto_refresh",
                bool(self.auto_refresh_checkbox.isChecked()),
            )
            settings.sync()
        except Exception as exc:
            self.logger.debug("Failed to save silver bar dialog state: %s", exc, exc_info=True)

    def _restore_ui_state(self):
        try:
            settings = self._settings()
            geometry = settings.value("ui/silver_bars/geometry")
            if geometry:
                self.host.restoreGeometry(geometry)

            state = settings.value("ui/silver_bars/splitter_h")
            if state and hasattr(self, "_splitter"):
                self._splitter.restoreState(state)
            if hasattr(self, "_splitter"):
                self._splitter.setOrientation(Qt.Horizontal)

            tol = settings.value("ui/silver_bars/weight_tol")
            if tol is not None:
                self.weight_tol_spin.setValue(float(tol))

            pmin = settings.value("ui/silver_bars/purity_min")
            pmax = settings.value("ui/silver_bars/purity_max")
            if pmin is not None:
                self.purity_min_spin.setValue(float(pmin))
            if pmax is not None:
                self.purity_max_spin.setValue(float(pmax))

            dr = settings.value("ui/silver_bars/date_range")
            if isinstance(dr, str):
                idx = self.date_range_combo.findText(dr)
                if idx >= 0:
                    self.date_range_combo.setCurrentIndex(idx)

            auto_refresh = settings.value("ui/silver_bars/auto_refresh")
            if isinstance(auto_refresh, bool):
                self.auto_refresh_checkbox.setChecked(auto_refresh)
            elif isinstance(auto_refresh, str):
                self.auto_refresh_checkbox.setChecked(auto_refresh.lower() == "true")

            weight_query = settings.value("ui/silver_bars/weight_query")
            if isinstance(weight_query, str):
                self.weight_search_edit.setText(weight_query)

            av_col = settings.value("ui/silver_bars/available_sort_col", type=int)
            av_ord = settings.value("ui/silver_bars/available_sort_order", type=int)
            if av_col is not None and av_ord is not None:
                self.available_bars_table.sortByColumn(
                    int(av_col), Qt.SortOrder(int(av_ord))
                )
            ls_col = settings.value("ui/silver_bars/list_sort_col", type=int)
            ls_ord = settings.value("ui/silver_bars/list_sort_order", type=int)
            if ls_col is not None and ls_ord is not None:
                self.list_bars_table.sortByColumn(
                    int(ls_col), Qt.SortOrder(int(ls_ord))
                )
        except (AttributeError, RuntimeError, TypeError, ValueError) as exc:
            self.logger.debug(
                "Failed to restore silver bar dialog state: %s", exc, exc_info=True
            )

    def _restore_selected_list_from_settings(self):
        try:
            settings = self._settings()
            saved_id = settings.value("ui/silver_bars/current_list_id")
            if saved_id is None:
                return
            try:
                saved_id_int = int(saved_id)
            except (TypeError, ValueError):
                saved_id_int = saved_id
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
                if index < table.model().columnCount() and isinstance(width, int) and width > 0:
                    header.resizeSection(index, width)
        except Exception as exc:
            self.logger.debug("Could not apply stored table widths: %s", exc)

    def _restore_table_column_widths(self):
        try:
            settings = self._settings()
            available = settings.value("ui/silver_bars/available_cols", type=list)
            list_cols = settings.value("ui/silver_bars/list_cols", type=list)
            self._apply_table_column_widths(self.available_bars_table, available)
            self._apply_table_column_widths(self.list_bars_table, list_cols)
        except Exception as exc:
            self.logger.debug("Could not restore table column widths: %s", exc)

    def _toggle_auto_refresh(self, checked: bool):
        try:
            if checked:
                self._auto_refresh_timer.start()
            else:
                self._auto_refresh_timer.stop()
        except Exception as exc:
            self.logger.debug("Failed to toggle auto refresh: %s", exc)

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
            self.logger.debug("Could not resolve main window from silver bar dialog: %s", exc)
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
