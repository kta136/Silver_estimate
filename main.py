#!/usr/bin/env python
import logging
import sys

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import (
    QApplication,
    QMainWindow,
    QMessageBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

# Import the custom dialogs and modules
from silverestimate.controllers.live_rate_controller import LiveRateController
from silverestimate.controllers.navigation_controller import NavigationController
from silverestimate.infrastructure.app_constants import APP_TITLE
from silverestimate.infrastructure.application import ApplicationBuilder, StartupError
from silverestimate.infrastructure.paths import get_asset_path
from silverestimate.infrastructure.windows_integration import (
    apply_taskbar_icon,
    destroy_icon_handle,
)
from silverestimate.services.estimate_repository import DatabaseEstimateRepository
from silverestimate.services.main_commands import MainCommands
from silverestimate.services.navigation_service import NavigationService
from silverestimate.services.settings_service import SettingsService
from silverestimate.ui.estimate_entry import EstimateEntryWidget
from silverestimate.ui.font_dialogs import adjust_table_font_size, choose_print_font


class MainWindow(QMainWindow):
    # Thread-safe signal to apply fetched rates on the UI thread

    """Main application window for the Silver Estimation App."""

    def __init__(self, db_manager, logger=None):
        super().__init__()

        self.logger = logger or logging.getLogger(__name__)
        self.logger.info("Initializing MainWindow")

        if db_manager is None:
            raise StartupError("Database manager not provided. Cannot start application.")

        self.db = db_manager
        self.settings_service = SettingsService()
        self._taskbar_icon_handle = None

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
            if self.logger:
                self.logger.debug("Failed to apply window icon: %s", exc)

        self.setWindowTitle(f"{APP_TITLE}[*]")
        # self.setGeometry(100, 100, 1000, 700) # Remove fixed geometry
        # self.showFullScreen() # Start in true full screen
        # We need to show the window first before maximizing it
        # self.show() # This is implicitly called later by app.exec_() usually
        # Let's try setting the window state directly (Moved to end of __init__)
        # self.setWindowState(Qt.WindowMaximized)

        self._pending_status_message = None

        default_font = QApplication.font()
        try:
            self.print_font = self.settings_service.load_print_font(default_font)
        except Exception as exc:
            self.logger.warning("Failed to load print font settings: %s", exc)
            self.print_font = default_font

        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.layout = QVBoxLayout(self.central_widget)
        self.stack = QStackedWidget(self.central_widget)
        self.layout.addWidget(self.stack)

        self.navigation_service = NavigationService(self, self.stack, logger=self.logger)
        self.commands = MainCommands(self, self.db, logger=self.logger)

        self.navigation_controller = NavigationController(
            main_window=self,
            navigation_service=self.navigation_service,
            commands=self.commands,
            logger=self.logger,
        )

        self.live_rate_controller = LiveRateController(
            parent=self,
            widget_getter=lambda: getattr(self, 'estimate_widget', None),
            status_callback=self.show_status_message,
            logger=self.logger,
        )

        self.navigation_controller.initialize()

        try:
            self.logger.info("Creating EstimateEntryWidget...")
            repository = DatabaseEstimateRepository(self.db)
            self.estimate_widget = EstimateEntryWidget(self.db, self, repository)

            self.logger.info("Deferring ItemMasterWidget creation (lazy-load)")
            self.item_master_widget = None
            self.logger.info("Deferring SilverBar view creation (lazy-load)")
            self.silver_bar_widget = None

            self.stack.addWidget(self.estimate_widget)
            self.stack.setCurrentWidget(self.estimate_widget)

            try:
                if hasattr(self.db, 'on_flush_queued'):
                    def _on_flush_q():
                        QTimer.singleShot(0, lambda: self.estimate_widget.show_inline_status("Saving.", 1000, 'info'))

                    def _on_flush_done():
                        QTimer.singleShot(0, lambda: self.estimate_widget.show_inline_status("", 0))

                    self.db.on_flush_queued = _on_flush_q
                    self.db.on_flush_done = _on_flush_done
            except Exception as callback_error:
                self.logger.debug("Could not hook flush callbacks: %s", callback_error)

            try:
                if hasattr(self.db, 'start_preload_item_cache'):
                    self.db.start_preload_item_cache()
            except Exception as preload_error:
                self.logger.debug("Item cache preload failed: %s", preload_error)

            self.logger.info("Widgets initialized successfully")
            try:
                self.show_status_message("Ready", 2000, level='info')
            except Exception:
                pass

            try:
                self.live_rate_controller.initialize()
            except Exception as rate_error:
                if self.logger:
                    self.logger.debug("Live rate initialization failed: %s", rate_error, exc_info=True)

            pending = getattr(self, '_pending_status_message', None)
            if pending:
                self._pending_status_message = None
                try:
                    self.show_status_message(*pending)
                except Exception as exc:
                    if self.logger:
                        self.logger.debug("Failed to deliver pending status message: %s", exc, exc_info=True)

            try:
                self.setWindowState(self.windowState() | Qt.WindowMaximized)
            except Exception as exc:
                if self.logger:
                    self.logger.debug("Failed to apply maximized window state: %s", exc, exc_info=True)
        except Exception as exc:
            self.logger.critical("Failed to initialize widgets: %s", exc, exc_info=True)
            raise StartupError(f"Failed to initialize application widgets: {exc}") from exc

    # --- File menu action handlers ---
    def file_save_estimate(self, *args, **kwargs):
        return self.commands.save_estimate()

    def file_print_estimate(self, *args, **kwargs):
        return self.commands.print_estimate()

    def show_status_message(self, message: str, timeout: int = 3000, level: str = 'info') -> None:
        """Display a transient status message inline within the estimate view."""
        widget = getattr(self, 'estimate_widget', None)
        show_inline = getattr(widget, 'show_inline_status', None)
        if callable(show_inline):
            try:
                show_inline(message, timeout=timeout, level=level)
            except Exception as exc:
                if self.logger:
                    self.logger.debug("Failed to show inline status message: %s", exc)
            return
        self._pending_status_message = (message, timeout, level)
        if self.logger:
            try:
                self.logger.info("Status: %s", message)
            except Exception:
                pass
    def refresh_live_rate_now(self):
        controller = getattr(self, 'live_rate_controller', None)
        if controller:
            return controller.refresh_now()
        return None

    def reconfigure_rate_visibility_from_settings(self):
        controller = getattr(self, 'live_rate_controller', None)
        if not controller:
            return True
        return controller.apply_visibility_settings()

    def reconfigure_rate_timer_from_settings(self):
        controller = getattr(self, 'live_rate_controller', None)
        if controller:
            controller.apply_timer_settings()

    def show_estimate(self):
        return self.navigation_controller.show_estimate()


    def show_item_master(self):
        return self.navigation_controller.show_item_master()


    def show_silver_bars(self):
        return self.navigation_controller.show_silver_bars()


    def delete_all_data(self, *args, **kwargs):
        return self.navigation_controller.delete_all_data()

    def delete_all_estimates(self, *args, **kwargs):
        return self.navigation_controller.delete_all_estimates()

    def show_silver_bar_history(self):
        return self.navigation_controller.show_silver_bar_history()


    def show_estimate_history(self):
        return self.navigation_controller.show_estimate_history()


    def show_about(self):
        return self.navigation_controller.show_about()

    # --- Methods called by Advanced Tools Dialog ---
    def show_font_dialog(self):
        """Show the font selection dialog and store the chosen print font."""
        self.print_font = choose_print_font(
            parent=self,
            settings=self.settings_service,
            current_font=self.print_font,
            logger=self.logger,
        )

    # Removed apply_font_settings as we no longer apply to UI directly from here

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
        # Persist window geometry/state
        try:
            self.settings_service.save_geometry(self)
        except Exception:
            pass
        controller = getattr(self, 'live_rate_controller', None)
        if controller:
            try:
                controller.shutdown()
            except Exception:
                pass
        # Close the database connection properly
        if hasattr(self, 'db') and self.db:
            self.logger.debug("Closing database connection")
            self.db.close()
        if sys.platform == "win32" and self._taskbar_icon_handle:
            destroy_icon_handle(self._taskbar_icon_handle, logger=self.logger)
            self._taskbar_icon_handle = None
        # Optional: Add confirmation dialog if needed
        super().closeEvent(event)

    def show_table_font_size_dialog(self):
        """Show dialog to change estimate table font size."""
        apply_callback = None
        if hasattr(self, 'estimate_widget') and hasattr(self.estimate_widget, '_apply_table_font_size'):
            apply_callback = self.estimate_widget._apply_table_font_size

        new_size = adjust_table_font_size(
            parent=self,
            settings=self.settings_service,
            apply_callback=apply_callback,
            logger=self.logger,
        )

        if new_size is not None and apply_callback is None:
            self.logger.warning("Estimate widget or apply method not found.")

    # --- Method to show the new Settings dialog ---
    def show_settings_dialog(self):
        """Show the centralized settings dialog."""
        from silverestimate.ui.settings_dialog import SettingsDialog
        dialog = SettingsDialog(main_window_ref=self, parent=self)
        # Connect the signal if needed for immediate UI updates beyond fonts
        # dialog.settings_applied.connect(self.handle_settings_applied)
        dialog.exec_()
    # Removed show_advanced_tools_dialog method

    def show_import_dialog(self):
        return self.commands.import_items()



# --- Application entry point ---

def main() -> int:
    """Start the SilverEstimate application and return the exit code."""
    builder = ApplicationBuilder(main_window_factory=MainWindow)
    return builder.run()


if __name__ == "__main__":
    sys.exit(main())


