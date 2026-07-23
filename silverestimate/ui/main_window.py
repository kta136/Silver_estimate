"""Main application window shell and runtime bootstrap."""

from __future__ import annotations

import logging
import os
import sys
import time
from typing import TYPE_CHECKING, Any, Callable, Optional, Protocol

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont, QIcon
from PySide6.QtWidgets import (
    QApplication,
    QLabel,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from silverestimate.infrastructure.main_window_runtime import (
    MainWindowRuntime,
    build_main_window_runtime,
)

if TYPE_CHECKING:
    from silverestimate.controllers.live_rate_controller import LiveRateController
    from silverestimate.services.settings_service import SettingsService

    MainWindowRuntimeBuilder = Callable[..., MainWindowRuntime]
else:
    MainWindowRuntimeBuilder = Callable[..., Any]


class MainWindowDatabase(Protocol):
    """Narrow database surface used by the main window shell."""

    def close(self) -> None: ...

    def set_flush_status_callbacks(
        self,
        *,
        on_queued: Optional[Callable[[], None]] = None,
        on_done: Optional[Callable[[], None]] = None,
    ) -> None: ...


class MainWindow(QMainWindow):
    """Main application window for the SilverEstimate app."""

    def __init__(
        self,
        db_manager: MainWindowDatabase,
        logger=None,
        *,
        settings_service: Optional["SettingsService"] = None,
        runtime_builder: MainWindowRuntimeBuilder = build_main_window_runtime,
        defer_runtime: bool = False,
    ):
        super().__init__()

        from silverestimate.infrastructure.application import StartupError

        if db_manager is None:
            raise StartupError(
                "Database manager not provided. Cannot start application."
            )

        self.logger = logger or logging.getLogger(__name__)
        self.logger.info("Initializing MainWindow")
        self._startup_started_at = time.perf_counter()
        self._startup_started_unix = time.time()
        self.logger.debug(
            "[perf] startup.main_window_init_start t_unix=%.6f",
            self._startup_started_unix,
        )

        self.db: MainWindowDatabase = db_manager
        self.settings_service = settings_service
        self._runtime_builder = runtime_builder
        self._defer_runtime = bool(defer_runtime)
        self._runtime_initialized = False
        self._runtime_initialization_scheduled = False
        self._runtime_initialization_failed = False
        self._runtime_services_initialized = False
        self._runtime_services_initialization_scheduled = False
        self._shell_shown_logged = False
        self._closing = False
        self._taskbar_icon_handle: int | None = None
        self._pending_status_message: Optional[tuple[str, int, str]] = None
        self.item_master_widget = None
        self.silver_bar_widget = None
        self.live_rate_controller: Optional["LiveRateController"] = None

        self._configure_window_shell()
        self._apply_initial_window_state()

        shell_ready_ms = (time.perf_counter() - self._startup_started_at) * 1000.0
        self.logger.info(
            '[telemetry] {"metric":"startup.main_window_shell_ready_ms",'
            '"duration_ms":%.3f}',
            shell_ready_ms,
        )
        if not self._defer_runtime:
            self._initialize_runtime()

    def _initialize_runtime(self) -> None:
        if (
            self._runtime_initialized
            or self._runtime_initialization_failed
            or self._closing
        ):
            return

        try:
            runtime = self._runtime_builder(
                main_window=self,
                db_manager=self.db,
                logger=self.logger,
                settings_service=self.settings_service,
            )
            self._attach_runtime(runtime)
            self._initialize_estimate_widget()
            self._remove_loading_page()
            self._runtime_initialized = True
            ready_ms = (time.perf_counter() - self._startup_started_at) * 1000.0
            self.logger.debug(
                "[perf] startup.main_window_ready_ms=%.2f t_unix=%.6f",
                ready_ms,
                time.time(),
            )
            self.logger.info(
                '[telemetry] {"metric":"startup.main_window_ready_ms",'
                '"duration_ms":%.3f}',
                ready_ms,
            )
            QTimer.singleShot(0, self._log_first_idle_tick)
            if self._defer_runtime:
                self._runtime_services_initialization_scheduled = True
                QTimer.singleShot(100, self._initialize_runtime_services)
            else:
                self._initialize_runtime_services()
        except Exception as exc:
            self._runtime_initialization_failed = True
            self.logger.critical("Failed to initialize widgets: %s", exc, exc_info=True)
            message = f"Failed to initialize application widgets: {exc}"
            if not self._defer_runtime:
                from silverestimate.infrastructure.application import StartupError

                raise StartupError(message) from exc
            self._loading_label.setText(
                "The application workspace could not be initialized."
            )
            QMessageBox.critical(self, "Initialization Error", message)
            app = QApplication.instance()
            if app is not None:
                QTimer.singleShot(0, app.quit)

    def _initialize_runtime_services(self) -> None:
        """Finish nonessential startup work after the entry surface is interactive."""
        if self._runtime_services_initialized or self._closing:
            return

        try:
            self.navigation_controller.initialize()
        except Exception as exc:
            self.logger.warning(
                "Navigation menu initialization failed: %s", exc, exc_info=True
            )
        self._initialize_live_rate()
        self._deliver_pending_status_message()
        self._runtime_services_initialized = True
        services_ready_ms = (time.perf_counter() - self._startup_started_at) * 1000.0
        self.logger.info(
            '[telemetry] {"metric":"startup.main_window_services_ready_ms",'
            '"duration_ms":%.3f}',
            services_ready_ms,
        )

    def _configure_window_shell(self) -> None:
        from silverestimate.infrastructure.app_constants import APP_TITLE
        from silverestimate.infrastructure.paths import get_asset_path
        from silverestimate.infrastructure.windows_integration import apply_taskbar_icon
        from silverestimate.services.settings_service import SettingsService

        self.settings_service = self.settings_service or SettingsService()

        try:
            icon_path = get_asset_path("assets", "icons", "silverestimate.ico")
            if icon_path.exists():
                icon = QIcon(str(icon_path))
                self.setWindowIcon(icon)
                if sys.platform == "win32":
                    try:
                        hwnd = int(self.winId())
                    except Exception:
                        hwnd = 0
                    self._taskbar_icon_handle = apply_taskbar_icon(
                        hwnd, icon_path, logger=self.logger
                    )
            else:
                self.logger.debug("Window icon not found at %s", icon_path)
        except Exception as exc:
            self.logger.debug("Failed to apply window icon: %s", exc)

        self.setWindowTitle(f"{APP_TITLE}[*]")

        default_font = QFont("Arial", 8)
        try:
            self.print_font = self.settings_service.load_print_font(default_font)
        except Exception as exc:
            self.logger.warning("Failed to load print font settings: %s", exc)
            self.print_font = default_font

        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self._root_layout = QVBoxLayout(self.central_widget)
        self.stack = QStackedWidget(self.central_widget)
        self._root_layout.addWidget(self.stack)

        self._configure_loading_page()

        self._geometry_restored = False
        try:
            self._geometry_restored = self.settings_service.restore_geometry(self)
        except Exception as exc:
            self.logger.debug("Failed to restore window geometry: %s", exc)
        if not self._geometry_restored:
            self.resize(1280, 800)

    def _configure_loading_page(self) -> None:
        """Create the lightweight, explicit startup state shown before input is ready."""
        self._loading_page: QWidget | None = QWidget(self.stack)
        self._loading_page.setObjectName("StartupShell")
        loading_layout = QVBoxLayout(self._loading_page)
        self._loading_label = QLabel(
            "Loading the estimate workspace…\nInput will be ready shortly.",
            self._loading_page,
        )
        self._loading_label.setObjectName("StartupShellMessage")
        self._loading_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        loading_layout.addWidget(self._loading_label)
        self._loading_progress = QProgressBar(self._loading_page)
        self._loading_progress.setObjectName("StartupShellProgress")
        self._loading_progress.setRange(0, 0)
        self._loading_progress.setTextVisible(False)
        self._loading_progress.setMaximumWidth(420)
        self._loading_progress.setAccessibleName("Loading estimate workspace")
        loading_layout.addWidget(
            self._loading_progress, alignment=Qt.AlignmentFlag.AlignHCenter
        )
        self.stack.addWidget(self._loading_page)
        self.stack.setCurrentWidget(self._loading_page)

    def _remove_loading_page(self) -> None:
        loading_page = getattr(self, "_loading_page", None)
        if loading_page is None:
            return
        self.stack.removeWidget(loading_page)
        loading_page.deleteLater()
        self._loading_page = None

    def showEvent(self, event) -> None:
        super().showEvent(event)
        if self._shell_shown_logged:
            return
        self._shell_shown_logged = True
        shown_ms = (time.perf_counter() - self._startup_started_at) * 1000.0
        self.logger.info(
            '[telemetry] {"metric":"startup.main_window_shell_shown_ms",'
            '"duration_ms":%.3f}',
            shown_ms,
        )

    def paintEvent(self, event) -> None:
        super().paintEvent(event)
        if (
            self._defer_runtime
            and not self._runtime_initialized
            and not self._runtime_initialization_scheduled
            and not self._runtime_initialization_failed
            and not self._closing
        ):
            self._runtime_initialization_scheduled = True
            QTimer.singleShot(0, self._initialize_runtime)

    def _attach_runtime(self, runtime: MainWindowRuntime) -> None:
        self.settings_service = runtime.settings_service
        self.navigation_service = runtime.navigation_service
        self.commands = runtime.commands
        self.navigation_controller = runtime.navigation_controller
        self.live_rate_controller = runtime.live_rate_controller
        self.estimate_widget = runtime.estimate_widget

    def _initialize_estimate_widget(self) -> None:
        self.logger.info("Attaching EstimateEntryWidget")
        self.logger.info("Deferring ItemMasterWidget creation (lazy-load)")
        self.logger.info("Deferring SilverBar view creation (lazy-load)")

        self.stack.addWidget(self.estimate_widget)
        self.stack.setCurrentWidget(self.estimate_widget)

        try:
            self.db.set_flush_status_callbacks(
                on_queued=self._handle_flush_queued,
                on_done=self._handle_flush_done,
            )
        except Exception as callback_error:
            self.logger.debug("Could not hook flush callbacks: %s", callback_error)

        self.logger.info("Widgets initialized successfully")
        self.logger.debug(
            "[perf] startup.main_window_widgets_ready_ms=%.2f t_unix=%.6f",
            (time.perf_counter() - self._startup_started_at) * 1000.0,
            time.time(),
        )
        try:
            self.show_status_message("Ready", 2000, level="info")
        except Exception as exc:
            self.logger.debug("Failed to show initial status message: %s", exc)

    def _initialize_live_rate(self) -> None:
        controller = self.live_rate_controller
        if controller is None:
            return
        try:
            controller.initialize()
        except Exception as rate_error:
            self.logger.debug(
                "Live rate initialization failed: %s",
                rate_error,
                exc_info=True,
            )

    def _deliver_pending_status_message(self) -> None:
        pending = getattr(self, "_pending_status_message", None)
        if not pending:
            return
        self._pending_status_message = None
        try:
            self.show_status_message(*pending)
        except Exception as exc:
            self.logger.debug(
                "Failed to deliver pending status message: %s",
                exc,
                exc_info=True,
            )

    def _apply_initial_window_state(self) -> None:
        if self._geometry_restored:
            return
        try:
            self.setWindowState(self.windowState() | Qt.WindowState.WindowMaximized)
        except Exception as exc:
            self.logger.debug(
                "Failed to apply maximized window state: %s",
                exc,
                exc_info=True,
            )

    def _log_first_idle_tick(self) -> None:
        try:
            first_idle_ms = (time.perf_counter() - self._startup_started_at) * 1000.0
            self.logger.debug(
                "[perf] startup.main_window_first_idle_ms=%.2f t_unix=%.6f",
                first_idle_ms,
                time.time(),
            )
            self.logger.info(
                '[telemetry] {"metric":"startup.main_window_first_idle_ms",'
                '"duration_ms":%.3f}',
                first_idle_ms,
            )
        except Exception as exc:
            self.logger.debug("Failed to record first idle tick metric: %s", exc)

    def _handle_flush_queued(self) -> None:
        QTimer.singleShot(
            0,
            lambda: self.estimate_widget.show_inline_status("Saving.", 1000, "info"),
        )

    def _handle_flush_done(self) -> None:
        QTimer.singleShot(0, lambda: self.estimate_widget.show_inline_status("", 0))

    def show_status_message(
        self, message: str, timeout: int = 3000, level: str = "info"
    ) -> None:
        """Display a transient status message inline within the estimate view."""
        widget = getattr(self, "estimate_widget", None)
        show_inline = getattr(widget, "show_inline_status", None)
        if callable(show_inline):
            try:
                show_inline(message, timeout=timeout, level=level)
            except Exception as exc:
                self.logger.debug("Failed to show inline status message: %s", exc)
            return
        self._pending_status_message = (message, timeout, level)
        try:
            self.logger.info("Status: %s", message)
        except Exception as exc:
            self.logger.debug("Failed to log status message: %s", exc)

    def refresh_live_rate_now(self):
        controller = self.live_rate_controller
        if controller:
            return controller.refresh_now()
        return None

    def reconfigure_rate_visibility_from_settings(self):
        controller = self.live_rate_controller
        if not controller:
            return True
        return controller.apply_visibility_settings()

    def reconfigure_rate_timer_from_settings(self):
        controller = self.live_rate_controller
        if controller:
            controller.apply_timer_settings()

    def show_estimate(self):
        return self.navigation_controller.show_estimate()

    def show_item_master(self):
        return self.navigation_controller.show_item_master()

    def show_silver_bars(self):
        return self.navigation_controller.show_silver_bars()

    def delete_all_data(self, *args, **kwargs):
        del args, kwargs
        return self.navigation_controller.delete_all_data()

    def delete_all_estimates(self, *args, **kwargs):
        del args, kwargs
        return self.navigation_controller.delete_all_estimates()

    def show_silver_bar_history(self):
        return self.navigation_controller.show_silver_bar_history()

    def show_estimate_history(self):
        return self.navigation_controller.show_estimate_history()

    def show_about(self):
        return self.navigation_controller.show_about()

    def closeEvent(self, event):
        """Handle window close event."""
        estimate_widget = getattr(self, "estimate_widget", None)
        if estimate_widget and hasattr(estimate_widget, "confirm_exit"):
            try:
                if not estimate_widget.confirm_exit():
                    event.ignore()
                    return
            except Exception as exc:
                self.logger.debug("Estimate exit confirmation failed: %s", exc)

        self._closing = True
        self.logger.info("Application closing")
        try:
            settings_service = self.settings_service
            if settings_service is not None:
                settings_service.save_geometry(self)
        except Exception as exc:
            self.logger.debug("Failed to save window geometry: %s", exc)
        controller = self.live_rate_controller
        if controller:
            try:
                controller.shutdown()
            except Exception as exc:
                self.logger.debug("Failed to shut down live-rate controller: %s", exc)
        if hasattr(self, "db") and self.db:
            self.logger.debug("Closing database connection")
            self.db.close()
        if sys.platform == "win32" and self._taskbar_icon_handle:
            from silverestimate.infrastructure.windows_integration import (
                destroy_icon_handle,
            )

            destroy_icon_handle(self._taskbar_icon_handle, logger=self.logger)
            self._taskbar_icon_handle = None
        try:
            if sys.platform == "win32" and os.environ.get("SILVER_SHOW_CONSOLE") != "1":
                from silverestimate.infrastructure.windows_integration import (
                    hide_console_window,
                )

                hide_console_window()
        except Exception as exc:
            self.logger.debug("Failed to hide console window during shutdown: %s", exc)
        try:
            app = QApplication.instance()
            if app:
                app.quit()
        except Exception as exc:
            self.logger.debug("Failed to quit QApplication cleanly: %s", exc)
        super().closeEvent(event)

    def show_settings_dialog(self):
        """Show the centralized settings dialog."""
        from silverestimate.ui.settings_dialog import SettingsDialog

        dialog = SettingsDialog(main_window_ref=self, parent=self)
        dialog.exec()

    def show_catalog_restore_dialog(self):
        return self.commands.restore_item_catalog()

    def show_catalog_backup_dialog(self):
        return self.commands.create_item_catalog_backup()


__all__ = ["MainWindow"]
