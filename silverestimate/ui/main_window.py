"""Main application window shell and runtime bootstrap."""

from __future__ import annotations

import logging
import os
import sys
import time
from typing import TYPE_CHECKING, Any, Callable

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import (
    QApplication,
    QMainWindow,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from silverestimate.infrastructure.main_window_runtime import (
    MainWindowRuntime,
    build_main_window_runtime,
)

if TYPE_CHECKING:
    MainWindowRuntimeBuilder = Callable[..., MainWindowRuntime]
else:
    MainWindowRuntimeBuilder = Callable[..., Any]


class MainWindow(QMainWindow):
    """Main application window for the SilverEstimate app."""

    def __init__(
        self,
        db_manager,
        logger=None,
        *,
        settings_service=None,
        runtime_builder: MainWindowRuntimeBuilder = build_main_window_runtime,
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

        self.db = db_manager
        self.settings_service = settings_service
        self._runtime_builder = runtime_builder
        self._taskbar_icon_handle = None
        self._pending_status_message = None
        self.item_master_widget = None
        self.silver_bar_widget = None

        self._configure_window_shell()

        try:
            runtime = self._runtime_builder(
                main_window=self,
                db_manager=self.db,
                logger=self.logger,
                settings_service=self.settings_service,
            )
            self._attach_runtime(runtime)
            self.navigation_controller.initialize()
            self._initialize_estimate_widget()
            self._initialize_live_rate()
            self._deliver_pending_status_message()
            self._apply_initial_window_state()
            self.logger.debug(
                "[perf] startup.main_window_ready_ms=%.2f t_unix=%.6f",
                (time.perf_counter() - self._startup_started_at) * 1000.0,
                time.time(),
            )
            QTimer.singleShot(0, self._log_first_idle_tick)
        except Exception as exc:
            self.logger.critical("Failed to initialize widgets: %s", exc, exc_info=True)
            raise StartupError(
                f"Failed to initialize application widgets: {exc}"
            ) from exc

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

        default_font = QApplication.font()
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

        self._geometry_restored = False
        try:
            self._geometry_restored = self.settings_service.restore_geometry(self)
        except Exception as exc:
            self.logger.debug("Failed to restore window geometry: %s", exc)
        if not self._geometry_restored:
            self.resize(1280, 800)

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
            if hasattr(self.db, "on_flush_queued"):

                def _on_flush_q():
                    QTimer.singleShot(
                        0,
                        lambda: self.estimate_widget.show_inline_status(
                            "Saving.", 1000, "info"
                        ),
                    )

                def _on_flush_done():
                    QTimer.singleShot(
                        0, lambda: self.estimate_widget.show_inline_status("", 0)
                    )

                self.db.on_flush_queued = _on_flush_q
                self.db.on_flush_done = _on_flush_done
        except Exception as callback_error:
            self.logger.debug("Could not hook flush callbacks: %s", callback_error)

        QTimer.singleShot(250, self._start_item_cache_preload)

        self.logger.info("Widgets initialized successfully")
        self.logger.debug(
            "[perf] startup.main_window_widgets_ready_ms=%.2f t_unix=%.6f",
            (time.perf_counter() - self._startup_started_at) * 1000.0,
            time.time(),
        )
        try:
            self.show_status_message("Ready", 2000, level="info")
        except Exception:
            pass

    def _initialize_live_rate(self) -> None:
        try:
            self.live_rate_controller.initialize()
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
            self.setWindowState(self.windowState() | Qt.WindowMaximized)
        except Exception as exc:
            self.logger.debug(
                "Failed to apply maximized window state: %s",
                exc,
                exc_info=True,
            )

    def _log_first_idle_tick(self) -> None:
        try:
            self.logger.debug(
                "[perf] startup.main_window_first_idle_ms=%.2f t_unix=%.6f",
                (time.perf_counter() - self._startup_started_at) * 1000.0,
                time.time(),
            )
        except Exception:
            pass

    def _start_item_cache_preload(self) -> None:
        try:
            if hasattr(self.db, "start_preload_item_cache"):
                self.db.start_preload_item_cache()
        except Exception as preload_error:
            self.logger.debug("Item cache preload failed: %s", preload_error)

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
        except Exception:
            pass

    def refresh_live_rate_now(self):
        controller = getattr(self, "live_rate_controller", None)
        if controller:
            return controller.refresh_now()
        return None

    def reconfigure_rate_visibility_from_settings(self):
        controller = getattr(self, "live_rate_controller", None)
        if not controller:
            return True
        return controller.apply_visibility_settings()

    def reconfigure_rate_timer_from_settings(self):
        controller = getattr(self, "live_rate_controller", None)
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
            except Exception:
                pass

        self.logger.info("Application closing")
        try:
            self.settings_service.save_geometry(self)
        except Exception:
            pass
        controller = getattr(self, "live_rate_controller", None)
        if controller:
            try:
                controller.shutdown()
            except Exception:
                pass
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
        except Exception:
            pass
        try:
            app = QApplication.instance()
            if app:
                app.quit()
        except Exception:
            pass
        super().closeEvent(event)

    def show_settings_dialog(self):
        """Show the centralized settings dialog."""
        from silverestimate.ui.settings_dialog import SettingsDialog

        dialog = SettingsDialog(main_window_ref=self, parent=self)
        dialog.exec_()

    def show_import_dialog(self):
        return self.commands.import_items()


__all__ = ["MainWindow"]
