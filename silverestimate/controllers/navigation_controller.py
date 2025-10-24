"""Controller responsible for building menus and navigation actions."""
from __future__ import annotations

import logging
from typing import Optional

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QKeySequence
from PyQt5.QtWidgets import QAction, QActionGroup, QMenuBar, QMessageBox

from silverestimate.infrastructure.app_constants import APP_VERSION


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

    def show_about(self):
        QMessageBox.about(
            self._main_window,
            "About Silver Estimation App",
            "Silver Estimation App\n\n"
            f"Version {APP_VERSION}\n\n"
            "A comprehensive tool for managing silver estimations, "
            "item inventory, and silver bars.\n\n"
            "c 2023-2025 Silver Estimation App",
        )

    def refresh_live_rate(self):
        controller = getattr(self._main_window, "live_rate_controller", None)
        if controller:
            controller.refresh_now()

    def delete_all_data(self):
        return self._commands.delete_all_data()

    def delete_all_estimates(self):
        return self._commands.delete_all_estimates()

    # --- Builders ------------------------------------------------------

    def _build_menu_bar(self) -> None:
        menu_bar: QMenuBar = self._main_window.menuBar()

        file_menu = menu_bar.addMenu("&File")

        estimate_action = QAction("&Estimate Entry", self._main_window)
        estimate_action.setShortcut("Alt+E")
        estimate_action.triggered.connect(self.show_estimate)
        file_menu.addAction(estimate_action)

        item_master_action = QAction("&Item Master", self._main_window)
        item_master_action.setShortcut("Alt+I")
        item_master_action.triggered.connect(self.show_item_master)
        file_menu.addAction(item_master_action)

        file_menu.addSeparator()

        save_action = QAction("&Save", self._main_window)
        save_action.setShortcut(QKeySequence.Save)
        save_action.setShortcutContext(Qt.ApplicationShortcut)
        save_action.triggered.connect(self._main_window.commands.save_estimate)
        file_menu.addAction(save_action)

        print_action = QAction("&Print", self._main_window)
        print_action.setShortcut(QKeySequence.Print)
        print_action.setShortcutContext(Qt.ApplicationShortcut)
        print_action.triggered.connect(self._main_window.commands.print_estimate)
        file_menu.addAction(print_action)

        file_menu.addSeparator()

        exit_action = QAction("E&xit", self._main_window)
        exit_action.setShortcut(QKeySequence.Quit)
        exit_action.triggered.connect(self._main_window.close)
        file_menu.addAction(exit_action)

        tools_menu = menu_bar.addMenu("&Tools")

        silver_bars_action = QAction("&Silver Bar Management", self._main_window)
        silver_bars_action.setStatusTip("Add, view, transfer, or assign silver bars to lists")
        silver_bars_action.triggered.connect(self.show_silver_bars)
        tools_menu.addAction(silver_bars_action)

        silver_history_action = QAction("Silver Bar &History", self._main_window)
        silver_history_action.setStatusTip("View history of all silver bars and issued lists")
        silver_history_action.triggered.connect(self.show_silver_bar_history)
        tools_menu.addAction(silver_history_action)

        tools_menu.addSeparator()

        settings_action = QAction("&Settings...", self._main_window)
        settings_action.setStatusTip("Configure application settings")
        settings_action.triggered.connect(self._main_window.show_settings_dialog)
        tools_menu.addAction(settings_action)

        refresh_rate_action = QAction("Refresh Live Rate Now", self._main_window)
        refresh_rate_action.setStatusTip("Fetch the latest live silver rate immediately")
        refresh_rate_action.triggered.connect(self.refresh_live_rate)
        tools_menu.addAction(refresh_rate_action)
        self._main_window.refresh_rate_action = refresh_rate_action

        view_menu = menu_bar.addMenu("&View")
        view_group = QActionGroup(self._main_window)
        view_group.setExclusive(True)

        view_estimate_action = QAction("&Estimate Entry", self._main_window, checkable=True)
        view_item_master_action = QAction("&Item Master", self._main_window, checkable=True)
        view_silver_bars_action = QAction("&Silver Bars", self._main_window, checkable=True)

        view_group.addAction(view_estimate_action)
        view_group.addAction(view_item_master_action)
        view_group.addAction(view_silver_bars_action)

        view_estimate_action.setChecked(True)

        view_estimate_action.triggered.connect(self.show_estimate)
        view_item_master_action.triggered.connect(self.show_item_master)
        view_silver_bars_action.triggered.connect(self.show_silver_bars)

        view_menu.addAction(view_estimate_action)
        view_menu.addAction(view_item_master_action)
        view_menu.addAction(view_silver_bars_action)

        reports_menu = menu_bar.addMenu("&Reports")
        history_action = QAction("Estimate &History", self._main_window)
        history_action.triggered.connect(self.show_estimate_history)
        reports_menu.addAction(history_action)

        help_menu = menu_bar.addMenu("&Help")
        about_action = QAction("&About", self._main_window)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)

        # Synchronization handles for NavigationService
        self._main_window._menu_estimate_action = estimate_action
        self._main_window._menu_item_master_action = item_master_action
        self._main_window._menu_silver_action = silver_bars_action
        self._main_window._view_estimate_action = view_estimate_action
        self._main_window._view_item_master_action = view_item_master_action
        self._main_window._view_silver_bars_action = view_silver_bars_action
