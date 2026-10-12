"""Build the main window's menus and switch between its screens."""

from __future__ import annotations

import logging
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QActionGroup, QKeySequence
from PySide6.QtWidgets import QMenuBar, QMessageBox

from silverestimate.ui.icons import get_icon
from silverestimate.ui.message_dialogs import with_details


class NavigationController:
    """Own the menus, lazy screen creation and screen switching."""

    def __init__(
        self,
        *,
        main_window,
        commands,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        self._main_window = main_window
        self._stack = getattr(main_window, "stack", None)
        self._db = getattr(main_window, "db", None)
        self._commands = commands
        self._logger = logger or logging.getLogger(__name__)

    def initialize(self) -> None:
        self._build_menu_bar()

    # --- Screens and dialogs -------------------------------------------
    def show_estimate(self) -> None:
        widget = getattr(self._main_window, "estimate_widget", None)
        if widget is None:
            self._logger.error("Cannot show estimate: estimate_widget is not available")
            QMessageBox.critical(
                self._main_window,
                "Estimate Entry Unavailable",
                "Estimate entry is not available. Please restart the application.",
            )
            return
        if not self._switch_widget(widget):
            return
        self._sync_actions(
            nav=getattr(self._main_window, "nav_estimate_action", None),
            menu=getattr(self._main_window, "_menu_estimate_action", None),
            view=getattr(self._main_window, "_view_estimate_action", None),
        )

    def show_item_master(self) -> None:
        widget = getattr(self._main_window, "item_master_widget", None)
        if widget is None:
            try:
                from silverestimate.ui.item_master import ItemMasterWidget

                self._logger.info("Creating ItemMasterWidget on demand...")
                widget = ItemMasterWidget(self._db, self._main_window)
                self._main_window.item_master_widget = widget
                if self._stack:
                    self._stack.addWidget(widget)
            except Exception as exc:
                self._logger.error(
                    "Failed to create ItemMasterWidget: %s", exc, exc_info=True
                )
                QMessageBox.critical(
                    self._main_window,
                    "Item Master Unavailable",
                    with_details("Item Master could not be opened.", exc),
                )
                return
        if not self._switch_widget(widget):
            return
        self._sync_actions(
            nav=getattr(self._main_window, "nav_item_master_action", None),
            menu=getattr(self._main_window, "_menu_item_master_action", None),
            view=getattr(self._main_window, "_view_item_master_action", None),
        )

    def show_silver_bars(self, list_id: int | None = None) -> None:
        """Open the Silver Bars screen, building it only now.

        It is discarded again when the user leaves it, so it holds nothing
        (no searches, no loaded bars) while another screen is open.
        """
        if not self._ensure_db():
            return
        widget = self._silver_bar_widget()
        created = widget is None
        if widget is None:
            try:
                from silverestimate.ui.silver_bar_management import SilverBarWidget

                self._logger.info("Creating the Silver Bars screen on demand...")
                widget = SilverBarWidget(self._db, self._main_window)
                widget.close_requested.connect(self.show_estimate)
                self._main_window.silver_bar_widget = widget
                if self._stack:
                    self._stack.addWidget(widget)
            except Exception as exc:
                self._logger.error("Failed to open Silver Bars: %s", exc, exc_info=True)
                self._discard_silver_bars()
                QMessageBox.critical(
                    self._main_window,
                    "Silver Bars Unavailable",
                    with_details("Silver Bars could not be opened.", exc),
                )
                return
        if not self._switch_widget(widget):
            if created:
                self._discard_silver_bars()
            return
        self._sync_actions(
            view=getattr(self._main_window, "_view_silver_bars_action", None)
        )
        if list_id is not None:
            widget.open_list(list_id)

    def _silver_bar_widget(self):
        return getattr(self._main_window, "silver_bar_widget", None)

    def _discard_silver_bars(self) -> None:
        """Close the Silver Bars screen and let go of it."""
        widget = self._silver_bar_widget()
        if widget is None:
            return
        self._main_window.silver_bar_widget = None
        try:
            widget.shutdown()
        finally:
            if self._stack:
                self._stack.removeWidget(widget)
            widget.deleteLater()

    def show_sales_report(self) -> None:
        if not self._ensure_db():
            return
        widget = getattr(self._main_window, "sales_report_widget", None)
        if widget is None:
            try:
                from silverestimate.ui.sales_report import SalesReportWidget

                widget = SalesReportWidget(self._db, self._main_window)
                widget.voucher_requested.connect(self.open_sales_voucher)
                self._main_window.sales_report_widget = widget
                if self._stack:
                    self._stack.addWidget(widget)
            except Exception as exc:
                self._logger.error(
                    "Could not open sales report: %s", exc, exc_info=True
                )
                QMessageBox.critical(
                    self._main_window,
                    "Sales Reports Unavailable",
                    with_details("Sales Reports could not be opened.", exc),
                )
                return
        already_current = self._stack and self._stack.currentWidget() is widget
        if not self._switch_widget(widget):
            return
        if already_current:
            widget.refresh()
        self._sync_actions(
            view=getattr(self._main_window, "_view_sales_report_action", None)
        )

    def open_sales_voucher(self, voucher_no: str) -> None:
        widget = getattr(self._main_window, "estimate_widget", None)
        if widget is not None and widget.open_saved_estimate(voucher_no):
            self.show_estimate()

    def show_silver_bar_history(self) -> None:
        if not self._ensure_db():
            return
        try:
            from silverestimate.ui.silver_bar_history import SilverBarHistoryDialog

            self._logger.info("Opening Silver Bar History dialog")
            dialog = SilverBarHistoryDialog(self._db, self._main_window)
            dialog.exec()
            selected_list_id = dialog.selected_list_id
            dialog.deleteLater()
            if selected_list_id is not None:
                self.show_silver_bars(list_id=selected_list_id)
        except Exception as exc:
            self._logger.error(
                "Error opening Silver Bar History: %s", exc, exc_info=True
            )
            QMessageBox.critical(
                self._main_window,
                "Silver Bar History Unavailable",
                with_details("Silver Bar History could not be opened.", exc),
            )

    def show_estimate_history(self) -> None:
        widget = getattr(self._main_window, "estimate_widget", None)
        if widget is None:
            self._logger.error(
                "Cannot show estimate history: estimate_widget is not available"
            )
            QMessageBox.critical(
                self._main_window,
                "Estimate Entry Unavailable",
                "Estimate entry is not available. Please restart the application.",
            )
            return
        try:
            show_history = getattr(widget, "show_history", None)
            if not callable(show_history):
                QMessageBox.critical(
                    self._main_window,
                    "Estimate History Unavailable",
                    "Estimate history cannot be opened from this view.",
                )
                return
            show_history()
            self.show_estimate()
        except Exception as exc:
            self._logger.error("Error opening estimate history: %s", exc, exc_info=True)
            QMessageBox.critical(
                self._main_window,
                "Estimate History Unavailable",
                with_details("Estimate history could not be opened.", exc),
            )

    # --- Screen-switching helpers --------------------------------------
    def _switch_widget(self, widget) -> bool:
        if not self._stack:
            return True
        current = self._stack.currentWidget()
        leaving = current is not widget
        silver_bars = self._silver_bar_widget()
        if leaving:
            guard = getattr(current, "confirm_discard_edits", None)
            if callable(guard) and not guard():
                return False
            busy = silver_bars is not None and not silver_bars.can_close()
            if busy and current is silver_bars:
                return False
        self._stack.setCurrentWidget(widget)
        if leaving and current is silver_bars:
            self._discard_silver_bars()
        return True

    def _sync_actions(self, *, nav=None, menu=None, view=None) -> None:
        for action in (nav, menu, view):
            try:
                if action is not None:
                    action.setChecked(True)
            except Exception as exc:
                self._logger.debug("Failed to sync navigation action state: %s", exc)

    def _ensure_db(self) -> bool:
        if not self._db:
            self._logger.error("Database connection is not available")
            QMessageBox.critical(
                self._main_window,
                "Database Unavailable",
                "The database is not available. Please restart the application.",
            )
            return False
        return True

    # --- Menu commands -------------------------------------------------

    def show_about(self):
        from silverestimate.ui.about_dialog import AboutDialog

        dialog = AboutDialog(self._main_window)
        try:
            dialog.exec()
        finally:
            dialog.deleteLater()

    def refresh_live_rate(self):
        controller = getattr(self._main_window, "live_rate_controller", None)
        if controller:
            controller.refresh_now()

    def _open_silver_bars(self):
        """The Silver Bars screen, when it is the one on show."""
        widget = self._silver_bar_widget()
        if widget is not None and self._stack and self._stack.currentWidget() is widget:
            return widget
        return None

    def print_open_screen(self) -> None:
        """File > Print prints what is on show: the list, or else the estimate."""
        silver_bars = self._open_silver_bars()
        if silver_bars is not None:
            silver_bars.print_selected_list()
        else:
            self._commands.print_estimate()

    def show_keyboard_shortcuts(self):
        silver_bars = self._open_silver_bars()
        if silver_bars is not None:
            silver_bars.show_keyboard_help()
            return
        from silverestimate.ui.shortcuts_dialog import ShortcutsDialog

        dialog = ShortcutsDialog(parent=self._main_window)
        try:
            dialog.exec()
        finally:
            dialog.deleteLater()

    def new_estimate(self):
        widget = getattr(self._main_window, "estimate_widget", None)
        if widget is None:
            return
        self.show_estimate()
        widget.clear_form()

    def delete_all_data(self):
        return self._commands.delete_all_data()

    def delete_all_estimates(self):
        return self._commands.delete_all_estimates()

    def delete_vouchers_by_range(self):
        return self._commands.delete_vouchers_by_range()

    # --- Builders ------------------------------------------------------

    def _action(self, text: str, *, icon: str = "", tip: str = "") -> QAction:
        action = QAction(text, self._main_window)
        if icon:
            action.setIcon(get_icon(icon, widget=self._main_window))
        if tip:
            action.setStatusTip(tip)
        return action

    def _build_menu_bar(self) -> None:
        """Build the menus; each destination appears in exactly one of them."""
        window = self._main_window
        menu_bar: QMenuBar = window.menuBar()

        # --- File: what you do to the open estimate -----------------------
        file_menu = menu_bar.addMenu("&File")
        # Ctrl+N belongs to the estimate screen's own shortcut, so the menu
        # shows the key without registering it a second time.
        new_action = self._action("&New Estimate\tCtrl+N", icon="new")
        new_action.triggered.connect(self.new_estimate)
        file_menu.addAction(new_action)

        save_action = self._action("&Save", icon="save")
        save_action.setShortcut(QKeySequence.StandardKey.Save)
        save_action.setShortcutContext(Qt.ShortcutContext.WindowShortcut)
        save_action.triggered.connect(window.commands.save_estimate)
        file_menu.addAction(save_action)

        print_action = self._action("&Print", icon="print")
        print_action.setShortcut(QKeySequence.StandardKey.Print)
        print_action.setShortcutContext(Qt.ShortcutContext.WindowShortcut)
        print_action.triggered.connect(self.print_open_screen)
        file_menu.addAction(print_action)

        file_menu.addSeparator()
        exit_action = self._action("E&xit", icon="exit")
        exit_action.setShortcut(QKeySequence.StandardKey.Quit)
        exit_action.triggered.connect(window.close)
        file_menu.addAction(exit_action)

        # --- View: the screens; a mark shows which one is open ------------
        # No icons here: an icon takes the place of the mark in a menu.
        view_menu = menu_bar.addMenu("&View")
        screens = QActionGroup(window)
        screens.setExclusive(True)

        view_estimate_action = self._action("&Estimate Entry")
        view_estimate_action.setShortcut("Alt+E")
        view_item_master_action = self._action("&Item Master")
        view_item_master_action.setShortcut("Alt+I")
        view_sales_report_action = self._action(
            "Sales &Reports",
            tip="Daily, monthly and item-wise sale and return weights",
        )
        view_sales_report_action.setShortcut("Alt+R")
        view_silver_bars_action = self._action(
            "Silver &Bars",
            tip="Build, print and issue silver bar lists",
        )
        view_silver_bars_action.setShortcut("Alt+B")
        for action, slot in (
            (view_estimate_action, self.show_estimate),
            (view_item_master_action, self.show_item_master),
            (view_sales_report_action, self.show_sales_report),
            (view_silver_bars_action, self.show_silver_bars),
        ):
            action.setCheckable(True)
            screens.addAction(action)
            # triggered passes "checked", which no screen takes as an argument.
            action.triggered.connect(lambda _checked=False, show=slot: show())
            view_menu.addAction(action)
        view_estimate_action.setChecked(True)

        # --- Tools: windows that open over the current screen -------------
        tools_menu = menu_bar.addMenu("&Tools")
        estimate = getattr(window, "estimate_widget", None)
        estimate_menu = getattr(estimate, "estimate_tools_menu", None)
        if estimate_menu is not None:
            tools_menu.addMenu(estimate_menu)
            tools_menu.addSeparator()

        settings_action = self._action(
            "Se&ttings...", icon="settings", tip="Configure the application"
        )
        settings_action.triggered.connect(window.show_settings_dialog)
        tools_menu.addAction(settings_action)

        refresh_rate_action = self._action(
            "&Refresh Live Rate",
            icon="refresh",
            tip="Fetch the latest live silver rate now",
        )
        refresh_rate_action.triggered.connect(self.refresh_live_rate)
        tools_menu.addAction(refresh_rate_action)
        window.refresh_rate_action = refresh_rate_action

        # --- History: saved records ----------------------------------------
        # Alt+S, not Alt+I: that key already opens the Item Master.
        history_menu = menu_bar.addMenu("Hi&story")
        history_action = self._action(
            "&Estimate History...\tCtrl+H",
            icon="history",
            tip="Find, open, print or delete saved estimates",
        )
        history_action.triggered.connect(self.show_estimate_history)
        history_menu.addAction(history_action)
        silver_history_action = self._action(
            "&Silver Bar History...",
            icon="silver_history",
            tip="Every silver bar and issued list",
        )
        silver_history_action.triggered.connect(self.show_silver_bar_history)
        history_menu.addAction(silver_history_action)

        # --- Help -------------------------------------------------------------
        help_menu = menu_bar.addMenu("&Help")
        shortcuts_action = self._action("&Keyboard Shortcuts")
        shortcuts_action.setShortcut("F1")
        shortcuts_action.triggered.connect(self.show_keyboard_shortcuts)
        help_menu.addAction(shortcuts_action)
        help_menu.addSeparator()
        about_action = self._action("&About", icon="about")
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)

        # Handles used to mark the open screen.
        window._menu_estimate_action = view_estimate_action
        window._menu_item_master_action = view_item_master_action
        window._view_estimate_action = view_estimate_action
        window._view_item_master_action = view_item_master_action
        window._view_sales_report_action = view_sales_report_action
        window._view_silver_bars_action = view_silver_bars_action
