#!/usr/bin/env python
import sys
import os
import traceback
import logging

from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QMenuBar, QMenu, QAction, QMessageBox, QDialog, QStatusBar,
                             QLabel, QStackedWidget, QToolBar, QActionGroup, QInputDialog)
from PyQt5.QtGui import QKeySequence
from PyQt5.QtCore import Qt, QTimer
import PyQt5.QtCore as QtCore

# Import the custom dialogs and modules
from silverestimate.ui.estimate_entry import EstimateEntryWidget
from silverestimate.persistence.database_manager import DatabaseManager
# from advanced_tools_dialog import AdvancedToolsDialog # Remove old import
# Lazy imports: ItemMasterWidget, SettingsDialog, SilverBarHistoryDialog
from silverestimate.services.auth_service import run_authentication, perform_data_wipe
from silverestimate.services.live_rate_service import LiveRateService
from silverestimate.services.main_commands import MainCommands
from silverestimate.services.navigation_service import NavigationService
from silverestimate.services.settings_service import SettingsService
from silverestimate.ui.font_dialogs import adjust_table_font_size, choose_print_font
from silverestimate.infrastructure.logger import setup_logging, qt_message_handler
from silverestimate.ui.message_bar import MessageBar
from silverestimate.infrastructure.app_constants import APP_TITLE, APP_VERSION, SETTINGS_ORG, SETTINGS_APP, DB_PATH

class StartupError(RuntimeError):
    """Raised when the main window cannot complete initialization."""
    pass

class MainWindow(QMainWindow):
    # Thread-safe signal to apply fetched rates on the UI thread

    """Main application window for the Silver Estimation App."""

    def __init__(self, password=None, logger=None): # Add password and logger arguments
        super().__init__()
        
        # Set up logging
        self.logger = logger or logging.getLogger(__name__)
        self.logger.info("Initializing MainWindow")

        self.settings_service = SettingsService()

        if not password:
            raise StartupError("Password not provided. Cannot start application.")

        # Defer database setup until password is known
        self.db = None
        self._password = password  # Store password temporarily

        # Initialize UI
        self.setWindowTitle(APP_TITLE)
        # self.setGeometry(100, 100, 1000, 700) # Remove fixed geometry
        # self.showFullScreen() # Start in true full screen
        # We need to show the window first before maximizing it
        # self.show() # This is implicitly called later by app.exec_() usually
        # Let's try setting the window state directly (Moved to end of __init__)
        # self.setWindowState(Qt.WindowMaximized)

        # Top message bar (created but not added to layout; inline status is preferred)
        self.message_bar = MessageBar(self)

        # Setup database now that a valid password is available
        self.setup_database_with_password(self._password)

        # Set up menu bar
        self.setup_menu_bar()

        # Load settings (including font) before setting up UI elements that use them
        default_font = QApplication.font()
        try:
            self.print_font = self.settings_service.load_print_font(default_font)
        except Exception as exc:
            self.logger.warning("Failed to load print font settings: %s", exc)
            self.print_font = default_font

        # Ensure any QMainWindow footer status bar is hidden to free space
        try:
            sb = QMainWindow.statusBar(self)  # creates if not exists
            if sb:
                sb.hide()
        except Exception:
            pass

        # Initial user-facing message will be shown inline after widgets are ready

        # Central widget
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.layout = QVBoxLayout(self.central_widget)
        # Navigation stack for primary views
        self.stack = QStackedWidget(self.central_widget)
        # Insert just the main stack (inline status lives in header area)
        self.layout.addWidget(self.stack)

        self.navigation_service = NavigationService(self, self.stack, logger=self.logger)

        self.commands = MainCommands(self, self.db, logger=self.logger)





        # Initialize widgets, passing main window and db manager
        # Ensure db is initialized before creating widgets that need it
        if self.db:
            try:
                # Create widgets with robust error handling
                self.logger.info("Creating EstimateEntryWidget...")
                self.estimate_widget = EstimateEntryWidget(self.db, self) # Pass main window instance
                
                # Lazy-load Item Master on demand (rarely used)
                self.logger.info("Deferring ItemMasterWidget creation (lazy-load)")
                self.item_master_widget = None
                # Lazy-load Silver Bar Management view on demand
                self.logger.info("Deferring SilverBar view creation (lazy-load)")
                self.silver_bar_widget = None

                # Add Estimate view to navigation stack
                self.stack.addWidget(self.estimate_widget)

                # Initially show estimate entry
                self.stack.setCurrentWidget(self.estimate_widget)

                # Hook DB flush callbacks to inline status in the estimate view
                try:
                    if hasattr(self.db, 'on_flush_queued'):
                        def _on_flush_q():
                            QTimer.singleShot(0, lambda: self.estimate_widget.show_inline_status("Saving…", 1000, 'info'))
                        def _on_flush_done():
                            QTimer.singleShot(0, lambda: self.estimate_widget.show_inline_status("", 0))
                        self.db.on_flush_queued = _on_flush_q
                        self.db.on_flush_done = _on_flush_done
                except Exception as _cb_e:
                    self.logger.debug(f"Could not hook flush callbacks: {_cb_e}")

                # Preload item cache off the UI thread for faster code lookups
                try:
                    if hasattr(self.db, 'start_preload_item_cache'):
                        self.db.start_preload_item_cache()
                except Exception as _pre_e:
                    self.logger.debug(f"Item cache preload failed: {_pre_e}")
                
                self.logger.info("Widgets initialized successfully")
                # Now that widgets exist, show initial Ready status inline
                try:
                    self.show_status_message("Ready", 2000, level='info')
                except Exception:
                    pass

                # Configure and start live rate updates
                try:
                    # Apply visibility first, then timer setup per settings
                    self.reconfigure_rate_visibility_from_settings()
                    self._setup_live_rate_timer()
                    # Trigger an initial fetch shortly after UI is ready
                    QTimer.singleShot(500, self.refresh_live_rate_now)
                    try:
                        self.logger.info("Scheduled initial live-rate fetch (500ms)")
                    except Exception:
                        pass
                except Exception as _rate_e:
                    self.logger.debug(f"Live rate timer init failed: {_rate_e}")
            except Exception as e:
                # Catch any exceptions during widget initialization
                self.logger.critical(f"Failed to initialize widgets: {str(e)}", exc_info=True)
                QMessageBox.critical(self, "Initialization Error",
                                    f"Failed to initialize application widgets: {str(e)}\n\n"
                                    "The application may not function correctly.")
                
                # Create placeholder widgets to prevent crashes
                self.logger.info("Creating placeholder widgets...")
                placeholder = QWidget()
                placeholder_layout = QVBoxLayout(placeholder)
                error_label = QLabel("Application initialization error. Please restart the application.")
                error_label.setStyleSheet("color: red; font-weight: bold; font-size: 14px;")
                placeholder_layout.addWidget(error_label)
                
                # Add placeholder to layout
                self.layout.addWidget(placeholder)
                
                # Store None for the widgets to prevent attribute errors
                self.estimate_widget = None
                self.item_master_widget = None
        else:
             # Handle case where db failed to initialize
             self.logger.critical("Database initialization failed. Cannot create widgets.")
             QMessageBox.critical(self, "Database Error", "Failed to initialize database. Application cannot continue.")
             
             # Create placeholder widget with error message
             placeholder = QWidget()
             placeholder_layout = QVBoxLayout(placeholder)
             error_label = QLabel("Database connection failed. Please restart the application.")
             error_label.setStyleSheet("color: red; font-weight: bold; font-size: 14px;")
             placeholder_layout.addWidget(error_label)
             
             # Add placeholder to layout
             self.layout.addWidget(placeholder)
             
             # Store None for the widgets to prevent attribute errors
             self.estimate_widget = None
             self.item_master_widget = None


        # Set up shortcuts (if needed)
#        self.setup_shortcuts()

        # Restore window geometry/state if available; otherwise maximize
        try:
            restored = self.settings_service.restore_geometry(self)
            if not restored:
                self.setWindowState(Qt.WindowMaximized)
        except Exception:
            # Fall back to maximized if restore fails
            self.setWindowState(Qt.WindowMaximized)

    def show_status_message(self, message, timeout=3000, level='info'):
        """Show a transient message inline next to Mode when possible."""
        # Prefer inline status on the active Estimate view
        try:
            if hasattr(self, 'estimate_widget') and self.estimate_widget is not None:
                if hasattr(self.estimate_widget, 'show_inline_status'):
                    self.estimate_widget.show_inline_status(message, timeout, level)
                    return
        except Exception:
            pass
        # No inline target yet; skip showing tAo avoid UI flicker

    # --- Live Rate Integration ---

    def _ensure_live_rate_service(self):

        if not hasattr(self, 'live_rate_service') or self.live_rate_service is None:

            self.live_rate_service = LiveRateService(parent=self, logger=self.logger)

            self.live_rate_service.rate_updated.connect(self._apply_live_rate)



    def _setup_live_rate_timer(self):

        """Initialize or reconfigure the live rate service based on settings."""

        self._ensure_live_rate_service()

        try:

            self.live_rate_service.stop()

        except Exception:

            pass

        self.live_rate_service.start()



    def reconfigure_rate_timer_from_settings(self):

        """Public hook to update the live-rate cadence when settings change."""

        try:

            self._setup_live_rate_timer()

            self.refresh_live_rate_now()

        except Exception as exc:

            self.logger.debug(f"Failed to reconfigure rate timer: {exc}")



    def refresh_live_rate_now(self):

        """Trigger an immediate live-rate refresh via the service."""

        try:

            self._ensure_live_rate_service()

            self.live_rate_service.refresh_now()

        except Exception as exc:

            self.logger.debug(f"Live rate refresh failed: {exc}")


    def _apply_live_rate(self, broadcast_rate, api_rate, market_open):

        """Slot executed on the UI thread when the live-rate service emits new data."""

        self.logger.info("Live-rate UI apply: entered")

        estimate_widget = getattr(self, 'estimate_widget', None)
        if estimate_widget is None:
            self.logger.debug("Live-rate apply skipped: estimate widget not ready")
            return

        rate_value = broadcast_rate
        source = 'broadcast'
        if rate_value is None:
            rate_value = api_rate
            source = 'api'

        if rate_value is None:
            self.logger.warning(
                "Live-rate apply: no rate available (broadcast=%s, api=%s)",
                broadcast_rate,
                api_rate,
            )
            label = getattr(estimate_widget, 'live_rate_value_label', None)
            if label is not None:
                try:
                    label.setText("N/A /g")
                except Exception:
                    pass
            self.show_status_message("Live rate unavailable", 3000, level='warning')
            return

        try:
            rate_float = float(rate_value)
        except (TypeError, ValueError):
            self.logger.warning(
                "Live-rate apply: invalid rate value %r from %s",
                rate_value,
                source,
            )
            self.show_status_message("Live rate invalid", 3000, level='warning')
            return

        label = getattr(estimate_widget, 'live_rate_value_label', None)
        if label is not None:
            try:
                from PyQt5.QtCore import QLocale

                locale = QLocale.system()
                gram_rate = rate_float / 1000.0
                display_value = locale.toCurrencyString(gram_rate)
                display_value = f"{display_value} /g"
            except Exception:
                display_value = f"Rs {round(rate_float / 1000.0, 2)} /g"
            try:
                label.setText(display_value)
            except Exception as exc:
                self.logger.debug("Live-rate apply: failed to update label: %s", exc)

        self.logger.info(
            "Live-rate applied from %s: %s per kg (open=%s)",
            source,
            rate_float,
            market_open,
        )
        status_text = "Live rate updated (per-g preview)" if market_open else "Live rate (market closed, per-g preview)"
        status_level = 'info' if market_open else 'warning'
        self.show_status_message(status_text, 3000, level=status_level)
        self.logger.debug("Live-rate preview applied without altering silver_rate_spin")


    def reconfigure_rate_visibility_from_settings(self):
        """Show/Hide live rate UI and enable/disable manual refresh based on settings."""
        live_enabled = self.settings_service.get("rates/live_enabled", True, type=bool)
        if live_enabled is None:
            live_enabled = True
        try:
            if hasattr(self, 'estimate_widget') and self.estimate_widget is not None:
                if hasattr(self.estimate_widget, 'live_rate_label') and self.estimate_widget.live_rate_label is not None:
                    self.estimate_widget.live_rate_label.setVisible(live_enabled)
                if hasattr(self.estimate_widget, 'live_rate_value_label') and self.estimate_widget.live_rate_value_label is not None:
                    self.estimate_widget.live_rate_value_label.setVisible(live_enabled)
            # Toggle manual refresh action if present
            if hasattr(self, 'refresh_rate_action') and self.refresh_rate_action is not None:
                self.refresh_rate_action.setEnabled(live_enabled)
        except Exception:
            pass

    # --- File menu action handlers ---
    def file_save_estimate(self, *args, **kwargs):
        return self.commands.save_estimate()

    def file_print_estimate(self, *args, **kwargs):
        return self.commands.print_estimate()

    def setup_database_with_password(self, password):
        """Initialize the DatabaseManager with the provided password."""
        try:
            self.logger.info("Setting up database connection")

            import os
            os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

            try:
                from silverestimate.persistence.database_manager import DatabaseManager as DM
                enc_path = DB_PATH
                candidate = DM.check_recovery_candidate(enc_path)
                if candidate:
                    self.logger.warning(
                        "Found newer temporary DB candidate for recovery: %s", candidate
                    )
                    message = (
                        "A newer unsaved database state was found from a previous session.\n"
                        "Would you like to recover it now?"
                    )
                    reply = QMessageBox.question(
                        self,
                        "Recover Unsaved Data",
                        message,
                        QMessageBox.Yes | QMessageBox.No,
                        QMessageBox.Yes,
                    )
                    if reply == QMessageBox.Yes:
                        if DM.recover_encrypt_plain_to_encrypted(
                            candidate,
                            enc_path,
                            password,
                            logger=self.logger,
                        ):
                            self.logger.info("Recovery successful. Proceeding with startup.")
                        else:
                            self.logger.error("Recovery failed. Proceeding with last encrypted state.")
            except Exception as recovery_exc:
                self.logger.error("Recovery check failed: %s", recovery_exc, exc_info=True)

            self.db = DatabaseManager(DB_PATH, password=password)
            if hasattr(self, 'navigation_service') and self.navigation_service:
                self.navigation_service.update_db(self.db)

            if hasattr(self, 'commands') and self.commands:
                self.commands.update_db(self.db)

            self.show_status_message("Database connected securely.", 3000, level='info')
            self.logger.info("Database connected successfully")
        except Exception as exc:
            self.db = None
            self.logger.critical("Failed to connect to encrypted database: %s", exc, exc_info=True)

            error_details = (
                f"Failed to connect to encrypted database: {exc}\n\n"
                "This could be due to:\n"
                "- Incorrect password\n"
                "- Corrupted database file\n"
                "- Missing permissions\n\n"
                "The application cannot continue without a valid database connection."
            )
            raise StartupError(error_details) from exc

    def setup_menu_bar(self):
        """Set up the main menu bar."""
        menu_bar = self.menuBar()

        # File menu
        file_menu = menu_bar.addMenu("&File")

        # Estimate action
        estimate_action = QAction("&Estimate Entry", self)
        estimate_action.setShortcut("Alt+E")
        estimate_action.triggered.connect(self.show_estimate)
        file_menu.addAction(estimate_action)

        # Item master action
        item_master_action = QAction("&Item Master", self)
        item_master_action.setShortcut("Alt+I")
        item_master_action.triggered.connect(self.show_item_master)
        file_menu.addAction(item_master_action)

        # Standard actions for current estimate
        file_menu.addSeparator()
        from PyQt5.QtGui import QKeySequence
        save_action = QAction("&Save", self)
        save_action.setShortcut(QKeySequence.Save)
        save_action.setShortcutContext(Qt.ApplicationShortcut)
        save_action.triggered.connect(self.file_save_estimate)
        file_menu.addAction(save_action)

        print_action = QAction("&Print", self)
        print_action.setShortcut(QKeySequence.Print)
        print_action.setShortcutContext(Qt.ApplicationShortcut)
        print_action.triggered.connect(self.file_print_estimate)
        file_menu.addAction(print_action)

        # Exit action
        file_menu.addSeparator()
        exit_action = QAction("E&xit", self)
        exit_action.setShortcut(QKeySequence.Quit)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # Tools menu
        tools_menu = menu_bar.addMenu("&Tools")

        # Silver bar management (also accessible in View/Toolbar)
        silver_bars_action = QAction("&Silver Bar Management", self)
        silver_bars_action.setStatusTip("Add, view, transfer, or assign silver bars to lists")
        silver_bars_action.triggered.connect(self.show_silver_bars)
        tools_menu.addAction(silver_bars_action)

        # Silver bar history
        silver_history_action = QAction("Silver Bar &History", self)
        silver_history_action.setStatusTip("View history of all silver bars and issued lists")
        silver_history_action.triggered.connect(self.show_silver_bar_history)
        tools_menu.addAction(silver_history_action)

        tools_menu.addSeparator()

        # Settings Dialog Action (Replaces Advanced Tools)
        settings_action = QAction("&Settings...", self)
        settings_action.setStatusTip("Configure application settings")
        settings_action.triggered.connect(self.show_settings_dialog) # Connect to new method
        tools_menu.addAction(settings_action)

        # Manual live-rate refresh for troubleshooting
        self.refresh_rate_action = QAction("Refresh Live Rate Now", self)
        self.refresh_rate_action.setStatusTip("Fetch the latest live silver rate immediately")
        self.refresh_rate_action.triggered.connect(self.refresh_live_rate_now)
        tools_menu.addAction(self.refresh_rate_action)

        # Removed Import Item List action from here
        # tools_menu.addSeparator()
        # import_item_action = QAction(...)
        # tools_menu.addAction(import_item_action)

        # View menu (switch primary views)
        view_menu = menu_bar.addMenu("&View")
        view_group = QActionGroup(self)
        view_group.setExclusive(True)

        self._view_estimate_action = QAction("&Estimate Entry", self, checkable=True)
        self._view_item_master_action = QAction("&Item Master", self, checkable=True)
        self._view_silver_bars_action = QAction("&Silver Bars", self, checkable=True)
        view_group.addAction(self._view_estimate_action)
        view_group.addAction(self._view_item_master_action)
        view_group.addAction(self._view_silver_bars_action)

        # Initial state reflects initial view
        self._view_estimate_action.setChecked(True)

        self._view_estimate_action.triggered.connect(self.show_estimate)
        self._view_item_master_action.triggered.connect(self.show_item_master)
        self._view_silver_bars_action.triggered.connect(self.show_silver_bars)

        view_menu.addAction(self._view_estimate_action)
        view_menu.addAction(self._view_item_master_action)
        view_menu.addAction(self._view_silver_bars_action)

        # Reports menu
        reports_menu = menu_bar.addMenu("&Reports")

        # Estimate history
        history_action = QAction("Estimate &History", self)
        history_action.triggered.connect(self.show_estimate_history)
        reports_menu.addAction(history_action)

        # Help menu
        help_menu = menu_bar.addMenu("&Help")

        # About action
        about_action = QAction("&About", self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)

        # Keep references for sync with toolbar
        self._menu_estimate_action = estimate_action
        self._menu_item_master_action = item_master_action
        self._menu_silver_action = silver_bars_action

    def setup_navigation_toolbar(self):
        """Create a persistent toolbar to switch between primary views."""
        try:
            toolbar = QToolBar("Navigation", self)
            toolbar.setMovable(False)
            toolbar.setAllowedAreas(Qt.TopToolBarArea)
            self.addToolBar(Qt.TopToolBarArea, toolbar)

            # Exclusive selection between two views
            group = QActionGroup(self)
            group.setExclusive(True)

            self.nav_estimate_action = QAction("Estimate Entry", self, checkable=True)
            self.nav_item_master_action = QAction("Item Master", self, checkable=True)
            self.nav_silver_action = QAction("Silver Bars", self, checkable=True)

            group.addAction(self.nav_estimate_action)
            group.addAction(self.nav_item_master_action)
            group.addAction(self.nav_silver_action)

            # Initial state -> Estimate view
            self.nav_estimate_action.setChecked(True)

            # Wire actions
            self.nav_estimate_action.triggered.connect(self.show_estimate)
            self.nav_item_master_action.triggered.connect(self.show_item_master)
            self.nav_silver_action.triggered.connect(self.show_silver_bars)

            toolbar.addAction(self.nav_estimate_action)
            toolbar.addAction(self.nav_item_master_action)
            toolbar.addAction(self.nav_silver_action)

            # Prefer text-only for clarity (icons can be added later)
            toolbar.setToolButtonStyle(Qt.ToolButtonTextOnly)

            self._nav_toolbar = toolbar
        except Exception as e:
            self.logger.warning(f"Failed to create navigation toolbar: {e}")

    #def setup_shortcuts(self):
      #  """Set up keyboard shortcuts."""
        # Alt+E for Estimate Entry
        #self.shortcut_estimate = QShortcut(QKeySequence("Alt+E"), self)
        #self.shortcut_estimate.activated.connect(self.show_estimate)

        # Alt+I for Item Master
        #self.shortcut_item = QShortcut(QKeySequence("Alt+I"), self)
        #self.shortcut_item.activated.connect(self.show_item_master)

        # Alt+X for Exit
        #self.shortcut_exit = QShortcut(QKeySequence("Alt+X"), self)
        #self.shortcut_exit.activated.connect(self.close)

    def show_estimate(self):
        return self.navigation_service.show_estimate()


    def show_item_master(self):
        return self.navigation_service.show_item_master()


    def show_silver_bars(self):
        return self.navigation_service.show_silver_bars()


    def delete_all_data(self, *args, **kwargs):
        return self.commands.delete_all_data()

    def delete_all_estimates(self, *args, **kwargs):
        return self.commands.delete_all_estimates()

    def show_silver_bar_history(self):
        return self.navigation_service.show_silver_bar_history()


    def show_estimate_history(self):
        return self.navigation_service.show_estimate_history()


    def show_about(self):
        """Show about dialog."""
        QMessageBox.about(self, "About Silver Estimation App",
                          "Silver Estimation App\n\n"
                          f"Version {APP_VERSION}\n\n" # Make sure this matches window title
                          "A comprehensive tool for managing silver estimations, "
                          "item inventory, and silver bars.\n\n"
                          "© 2023-2025 Silver Estimation App") # Update copyright year maybe

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
        self.logger.info("Application closing")
        # Persist window geometry/state
        try:
            self.settings_service.save_geometry(self)
        except Exception:
            pass
        # Close the database connection properly
        if hasattr(self, 'db') and self.db:
            self.logger.debug("Closing database connection")
            self.db.close()
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
    logger = None
    app = None
    cleanup_scheduler = None
    main_window = None
    try:
        from pathlib import Path
        from silverestimate.infrastructure.logger import get_log_config, setup_logging, LogCleanupScheduler

        logs_dir = Path("logs")
        logs_dir.mkdir(exist_ok=True)

        log_config = get_log_config()
        logger = setup_logging(
            app_name="silver_app",
            log_dir=log_config['log_dir'],
            debug_mode=log_config['debug_mode'],
            enable_info=log_config['enable_info'],
            enable_error=log_config['enable_error'],
            enable_debug=log_config['enable_debug']
        )
        logger.info(f"{APP_TITLE} starting")
        logger.debug(f"Logging configuration: {log_config}")

        if log_config.get('auto_cleanup'):
            try:
                cleanup_scheduler = LogCleanupScheduler(
                    log_dir=log_config['log_dir'],
                    cleanup_days=log_config['cleanup_days']
                )
                cleanup_scheduler.start()
                logger.info(
                    "Log cleanup scheduler initialized with %s days retention",
                    log_config['cleanup_days']
                )
            except Exception as exc:
                logger.error("Failed to initialize log cleanup scheduler: %s", exc, exc_info=True)

        QtCore.qInstallMessageHandler(qt_message_handler)
        logger.debug("Qt message handler installed")

        for attr in (Qt.AA_EnableHighDpiScaling, Qt.AA_UseHighDpiPixmaps):
            try:
                QApplication.setAttribute(attr)
            except Exception as exc:
                if logger:
                    logger.warning("Failed to set Qt attribute %s: %s", attr, exc)

        logger.debug("Creating QApplication instance")
        app = QApplication.instance() or QApplication(sys.argv)

        try:
            auth_result = run_authentication(logger)
        except Exception as auth_exc:
            logger.critical("Authentication failed with error: %s", auth_exc, exc_info=True)
            QMessageBox.critical(
                None,
                "Authentication Error",
                f"Failed to authenticate: {auth_exc}\n\nThe application will now exit."
            )
            return 1

        if auth_result == 'wipe':
            logger.warning("Data wipe requested, performing wipe operation")
            try:
                if perform_data_wipe(db_path=DB_PATH, logger=logger):
                    logger.info("Exiting application after successful data wipe")
                    return 0
                logger.critical("Exiting application due to data wipe failure")
                return 1
            except Exception as wipe_exc:
                logger.critical("Data wipe failed with error: %s", wipe_exc, exc_info=True)
                QMessageBox.critical(
                    None,
                    "Data Wipe Error",
                    f"Failed to wipe data: {wipe_exc}\n\nThe application will now exit."
                )
                return 1

        if not auth_result:
            logger.info("Authentication failed or was cancelled by the user. Exiting.")
            return 0

        password = auth_result
        logger.info("Authentication successful, initializing main window")

        try:
            main_window = MainWindow(password=password, logger=logger)
        except StartupError as exc:
            logger.critical("Failed to initialize main window: %s", exc, exc_info=True)
            QMessageBox.critical(
                None,
                "Initialization Error",
                str(exc),
            )
            return 1

        logger.info("Showing main application window")
        main_window.show()
        logger.debug("Entering Qt main event loop")
        exit_code = app.exec_()
        logger.info("Application exiting with code %s", exit_code)
        return exit_code

    except Exception as exc:
        if logger:
            logger.critical("Unhandled exception during application startup", exc_info=True)
        else:
            print(f"CRITICAL ERROR: {exc}")
            print(traceback.format_exc())
        try:
            QMessageBox.critical(
                None,
                "Fatal Error",
                f"The application encountered a fatal error and cannot continue.\n\nError: {exc}"
            )
        except Exception:
            pass
        return 1

    finally:
        if cleanup_scheduler is not None:
            try:
                cleanup_scheduler.stop()
            except Exception as exc:
                if logger:
                    logger.debug("Failed to stop cleanup scheduler: %s", exc)
        if main_window and getattr(main_window, 'db', None):
            try:
                main_window.db.close()
            except Exception as exc:
                if logger:
                    logger.debug("Failed to close database on exit: %s", exc)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print(f"CRITICAL STARTUP ERROR: {exc}")
        print(traceback.format_exc())
        try:
            QMessageBox.critical(
                None,
                "Fatal Error",
                f"The application encountered a fatal error and cannot continue.\n\nError: {exc}"
            )
        except Exception:
            pass
        sys.exit(1)
