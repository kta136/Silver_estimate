"""Factory helpers for composing the main window runtime."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Optional


@dataclass(frozen=True)
class MainWindowRuntime:
    """Concrete services, controllers, and widgets attached to the main window."""

    settings_service: Any
    navigation_service: Any
    commands: Any
    navigation_controller: Any
    live_rate_controller: Any
    estimate_widget: Any


def build_main_window_runtime(
    *,
    main_window: Any,
    db_manager: Any,
    logger: Optional[logging.Logger] = None,
    settings_service: Any = None,
) -> MainWindowRuntime:
    """Construct the main-window collaborators using the current app wiring."""
    from silverestimate.controllers.live_rate_controller import LiveRateController
    from silverestimate.controllers.navigation_controller import NavigationController
    from silverestimate.services.estimate_repository import DatabaseEstimateRepository
    from silverestimate.services.main_commands import MainCommands
    from silverestimate.services.navigation_service import NavigationService
    from silverestimate.services.settings_service import SettingsService
    from silverestimate.ui.estimate_entry import EstimateEntryWidget

    resolved_logger = logger or logging.getLogger(__name__)
    resolved_settings = settings_service or SettingsService()
    navigation_service = NavigationService(
        main_window,
        main_window.stack,
        logger=resolved_logger,
    )
    commands = MainCommands(main_window, db_manager, logger=resolved_logger)
    navigation_controller = NavigationController(
        main_window=main_window,
        navigation_service=navigation_service,
        commands=commands,
        logger=resolved_logger,
    )
    live_rate_controller = LiveRateController(
        parent=main_window,
        widget_getter=lambda: getattr(main_window, "estimate_widget", None),
        status_callback=main_window.show_status_message,
        logger=resolved_logger,
    )
    repository = DatabaseEstimateRepository(db_manager)
    estimate_widget = EstimateEntryWidget(db_manager, main_window, repository)
    return MainWindowRuntime(
        settings_service=resolved_settings,
        navigation_service=navigation_service,
        commands=commands,
        navigation_controller=navigation_controller,
        live_rate_controller=live_rate_controller,
        estimate_widget=estimate_widget,
    )


def create_main_window(*, db_manager: Any, logger: Optional[logging.Logger] = None):
    """Create a fully wired main window for application startup."""
    from silverestimate.ui.main_window import MainWindow

    return MainWindow(
        db_manager=db_manager,
        logger=logger,
        runtime_builder=build_main_window_runtime,
    )


__all__ = [
    "MainWindowRuntime",
    "build_main_window_runtime",
    "create_main_window",
]
