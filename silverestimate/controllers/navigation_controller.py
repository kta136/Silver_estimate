"""Controller responsible for building menus and navigation actions."""

from __future__ import annotations

import logging
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QActionGroup, QKeySequence
from PySide6.QtWidgets import QMenuBar

from silverestimate.ui.icons import get_icon


class NavigationController:
    """Encapsulate MainWindow menu wiring."""

    def __init__(
        self,
        *,
        main_window,
        navigation_service,
        commands,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        self._main_window = main_window
        self._navigation_service = navigation_service
        self._commands = commands
        self._logger = logger or logging.getLogger(__name__)

    def initialize(self) -> None:
        self._build_menu_bar()

    # --- Slots exposed to the window ----------------------------------

    def show_estimate(self):
        return self._navigation_service.show_estimate()

    def show_item_master(self):
        return self._navigation_service.show_item_master()

    def show_silver_bars(self):
        return self._navigation_service.show_silver_bars()

    def show_silver_bar_history(self):
        return self._navigation_service.show_silver_bar_history()

    def show_estimate_history(self):
        return self._navigation_service.show_estimate_history()

    def show_sales_report(self):
        return self._navigation_service.show_sales_report()

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

    def show_keyboard_shortcuts(self):
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
        print_action.triggered.connect(window.commands.print_estimate)
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
        for action, slot in (
            (view_estimate_action, self.show_estimate),
            (view_item_master_action, self.show_item_master),
            (view_sales_report_action, self.show_sales_report),
        ):
            action.setCheckable(True)
            screens.addAction(action)
            action.triggered.connect(slot)
            view_menu.addAction(action)
        view_estimate_action.setChecked(True)

        # --- Tools: windows that open over the current screen -------------
        tools_menu = menu_bar.addMenu("&Tools")
        estimate = getattr(window, "estimate_widget", None)
        estimate_menu = getattr(estimate, "estimate_tools_menu", None)
        if estimate_menu is not None:
            tools_menu.addMenu(estimate_menu)
            tools_menu.addSeparator()

        silver_bars_action = self._action(
            "&Silver Bars...",
            icon="silver_bars",
            tip="Build, print and issue silver bar lists",
        )
        silver_bars_action.triggered.connect(self.show_silver_bars)
        tools_menu.addAction(silver_bars_action)

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

        # Handles NavigationService uses to mark the open screen.
        window._menu_estimate_action = view_estimate_action
        window._menu_item_master_action = view_item_master_action
        window._menu_silver_action = silver_bars_action
        window._view_estimate_action = view_estimate_action
        window._view_item_master_action = view_item_master_action
        window._view_sales_report_action = view_sales_report_action
