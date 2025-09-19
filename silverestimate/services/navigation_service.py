"""Navigation service to manage view switching and history dialogs."""
from __future__ import annotations

import logging
from typing import Optional

from PyQt5.QtWidgets import QMessageBox, QDialog


class NavigationService:
    """Handle main-window navigation, lazy view creation, and dialogs."""

    def __init__(self, main_window, stack_widget, logger: Optional[logging.Logger] = None) -> None:
        self.main_window = main_window
        self.stack = stack_widget
        self.db = getattr(main_window, 'db', None)
        self._logger = logger or logging.getLogger(__name__)

    def update_db(self, db_manager) -> None:
        self.db = db_manager

    # --- Entry Points --------------------------------------------------
    def show_estimate(self) -> None:
        widget = getattr(self.main_window, 'estimate_widget', None)
        if widget is None:
            self._logger.error("Cannot show estimate: estimate_widget is not available")
            QMessageBox.critical(
                self.main_window,
                "Error",
                "Estimate entry is not available. Please restart the application.",
            )
            return
        self._switch_widget(widget)
        self._sync_actions(
            nav=getattr(self.main_window, 'nav_estimate_action', None),
            menu=getattr(self.main_window, '_menu_estimate_action', None),
            view=getattr(self.main_window, '_view_estimate_action', None),
        )

    def show_item_master(self) -> None:
        widget = getattr(self.main_window, 'item_master_widget', None)
        if widget is None:
            try:
                from item_master import ItemMasterWidget

                self._logger.info("Creating ItemMasterWidget on demand...")
                widget = ItemMasterWidget(self.db, self.main_window)
                setattr(self.main_window, 'item_master_widget', widget)
                if self.stack:
                    self.stack.addWidget(widget)
            except Exception as exc:
                self._logger.error("Failed to create ItemMasterWidget: %s", exc, exc_info=True)
                QMessageBox.critical(
                    self.main_window,
                    "Error",
                    f"Item master could not be initialized: {exc}",
                )
                return
        self._switch_widget(widget)
        self._sync_actions(
            nav=getattr(self.main_window, 'nav_item_master_action', None),
            menu=getattr(self.main_window, '_menu_item_master_action', None),
            view=getattr(self.main_window, '_view_item_master_action', None),
        )

    def show_silver_bars(self) -> None:
        if not self._ensure_db():
            return
        widget = getattr(self.main_window, 'silver_bar_widget', None)
        if widget is None:
            try:
                from silver_bar_management import SilverBarDialog

                self._logger.info("Creating SilverBar view on demand...")
                widget = SilverBarDialog(self.db, self.main_window)
                setattr(self.main_window, 'silver_bar_widget', widget)
                if self.stack:
                    self.stack.addWidget(widget)
            except Exception as exc:
                self._logger.error("Failed to create SilverBar view: %s", exc, exc_info=True)
                QMessageBox.critical(
                    self.main_window,
                    "Error",
                    f"Silver Bar Management could not be initialized: {exc}",
                )
                return
        self._switch_widget(widget)
        try:
            widget.load_available_bars()
            widget.load_bars_in_selected_list()
        except Exception:
            pass
        self._sync_actions(
            nav=getattr(self.main_window, 'nav_silver_action', None),
            menu=getattr(self.main_window, '_menu_silver_action', None),
            view=getattr(self.main_window, '_view_silver_bars_action', None),
        )

    def show_silver_bar_history(self) -> None:
        if not self._ensure_db():
            return
        try:
            from silver_bar_history import SilverBarHistoryDialog

            self._logger.info("Opening Silver Bar History dialog")
            dialog = SilverBarHistoryDialog(self.db, self.main_window)
            dialog.exec_()
        except Exception as exc:
            self._logger.error("Error opening Silver Bar History: %s", exc, exc_info=True)
            QMessageBox.critical(
                self.main_window,
                "Error",
                f"Failed to open Silver Bar History: {exc}",
            )

    def show_estimate_history(self) -> None:
        widget = getattr(self.main_window, 'estimate_widget', None)
        if widget is None:
            self._logger.error("Cannot show estimate history: estimate_widget is not available")
            QMessageBox.critical(
                self.main_window,
                "Error",
                "Estimate entry is not available. Please restart the application.",
            )
            return
        try:
            from estimate_history import EstimateHistoryDialog

            history_dialog = EstimateHistoryDialog(
                self.db, main_window_ref=self.main_window, parent=self.main_window
            )
            if history_dialog.exec_() == QDialog.Accepted:
                voucher_no = history_dialog.selected_voucher
                if voucher_no:
                    widget.voucher_edit.setText(voucher_no)
                    if hasattr(widget, 'safe_load_estimate'):
                        widget.safe_load_estimate()
                    else:
                        widget.load_estimate()
                    self.show_estimate()
        except Exception as exc:
            self._logger.error("Error opening estimate history: %s", exc, exc_info=True)
            QMessageBox.critical(
                self.main_window,
                "Load Error",
                f"Failed to open estimate history: {exc}",
            )

    # --- Helpers -------------------------------------------------------
    def _switch_widget(self, widget) -> None:
        if self.stack:
            self.stack.setCurrentWidget(widget)

    def _sync_actions(self, *, nav=None, menu=None, view=None) -> None:
        for action in (nav, menu, view):
            try:
                if action is not None:
                    action.setChecked(True)
            except Exception:
                pass

    def _ensure_db(self) -> bool:
        if not self.db:
            self._logger.error("Database connection is not available")
            QMessageBox.critical(
                self.main_window,
                "Error",
                "Database connection is not available. Please restart the application.",
            )
            return False
        return True
