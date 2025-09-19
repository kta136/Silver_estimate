#!/usr/bin/env python
import sys
import os
import traceback
import logging

from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QMenuBar, QMenu, QAction, QMessageBox, QDialog, QStatusBar,
                             QLabel, QStackedWidget, QToolBar, QActionGroup, QInputDialog)
from PyQt5.QtGui import QKeySequence, QFont
from PyQt5.QtCore import Qt, QTimer, QSettings
import PyQt5.QtCore as QtCore

# Import the custom dialogs and modules
from custom_font_dialog import CustomFontDialog
from estimate_entry import EstimateEntryWidget
from database_manager import DatabaseManager
# from advanced_tools_dialog import AdvancedToolsDialog # Remove old import
# Lazy imports: ItemMasterWidget, SettingsDialog, SilverBarHistoryDialog
from silverestimate.services.auth_service import run_authentication, perform_data_wipe
from silverestimate.services.live_rate_service import LiveRateService
from silverestimate.services.main_commands import MainCommands
from silverestimate.services.navigation_service import NavigationService
from silverestimate.services.settings_service import SettingsService
from logger import setup_logging, qt_message_handler
from message_bar import MessageBar
from app_constants import APP_TITLE, APP_VERSION, SETTINGS_ORG, SETTINGS_APP, DB_PATH

class MainWindow(QMainWindow):
    # Thread-safe signal to apply fetched rates on the UI thread
    """Main application window for the Silver Estimation App."""

    def __init__(self, password=None, logger=None): # Add password and logger arguments
        super().__init__()
        
        # Set up logging
        self.logger = logger or logging.getLogger(__name__)
        self.logger.info("Initializing MainWindow")

        # Defer database setup until password is known
        self.db = None
        self._password = password # Store password temporarily

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

        # Setup database *after* getting password (if provided)
        if self._password:
            # Pass only password, DB Manager handles salt via QSettings
            self.setup_database_with_password(self._password)
        else:
            # Handle case where no password was provided (e.g., error or cancelled login)
            # For now, show an error and potentially exit.
            QMessageBox.critical(self, "Authentication Error", "Password not provided. Cannot start application.")
            # We might want to exit gracefully here, but QMainWindow doesn't easily allow exiting from __init__
            # Let's prevent further UI setup.
            return # Stop further initialization

        # Set up menu bar
        self.setup_menu_bar()

        # Load settings (including font) before setting up UI elements that use them
        self.load_settings() # Password hashes will be loaded/checked elsewhere (login dialog)

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
            settings = QSettings(SETTINGS_ORG, SETTINGS_APP)
            restored = False
            geo = settings.value("ui/main_geometry")
            if geo is not None:
                self.restoreGeometry(geo)
                restored = True
            state = settings.value("ui/main_state")
            if state is not None:
                self.restoreState(state)
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

    def reconfigure_rate_visibility_from_settings(self):
        """Show/Hide live rate UI and enable/disable manual refresh based on settings."""
        settings = QSettings(SETTINGS_ORG, SETTINGS_APP)
        live_enabled = settings.value("rates/live_enabled", True, type=bool)
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

            # Ensure database directory exists
            import os
            os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

            # Startup recovery: if a previous temp DB exists and is newer than encrypted, offer recovery
            try:
                from database_manager import DatabaseManager as DM
                enc_path = DB_PATH
                candidate = DM.check_recovery_candidate(enc_path)
                if candidate:
                    self.logger.warning(f"Found newer temporary DB candidate for recovery: {candidate}")
                    reply = QMessageBox.question(
                        self,
                        "Recover Unsaved Data",
                        "A newer unsaved database state was found from a previous session.\n"
                        "Would you like to recover it now?",
                        QMessageBox.Yes | QMessageBox.No,
                        QMessageBox.Yes
                    )
                    if reply == QMessageBox.Yes:
                        if DM.recover_encrypt_plain_to_encrypted(candidate, enc_path, password, logger=self.logger):
                            self.logger.info("Recovery successful. Proceeding with startup.")
                        else:
                            self.logger.error("Recovery failed. Proceeding with last encrypted state.")
            except Exception as re:
                self.logger.error(f"Recovery check failed: {re}", exc_info=True)

            # DatabaseManager now handles getting/creating salt internally via QSettings
            self.db = DatabaseManager(DB_PATH, password=password)
            if hasattr(self, 'navigation_service') and self.navigation_service:
                self.navigation_service.update_db(self.db)

            if hasattr(self, 'commands') and self.commands:
                self.commands.update_db(self.db)

            # setup_database is called within DatabaseManager's __init__
            self.show_status_message("Database connected securely.", 3000, level='info')
            self.logger.info("Database connected successfully")
            
            return True
        except Exception as e:
            self.logger.critical(f"Failed to connect to encrypted database: {str(e)}", exc_info=True)
            
            # Show a more detailed error message
            error_details = f"Failed to connect to encrypted database: {e}\n\n"
            error_details += "This could be due to:\n"
            error_details += "- Incorrect password\n"
            error_details += "- Corrupted database file\n"
            error_details += "- Missing permissions\n\n"
            error_details += "The application will continue with limited functionality."
            
            QMessageBox.critical(self, "Database Error", error_details)
            
            self.db = None # Ensure db is None if setup fails
            return False

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
        # Use the currently stored print_font to initialize the dialog
        # Ensure the float_size attribute exists on it from loading/previous setting
        if not hasattr(self.print_font, 'float_size'):
             # If missing (e.g., first run before saving), initialize from pointSize
             self.print_font.float_size = float(self.print_font.pointSize())

        dialog = CustomFontDialog(self.print_font, self)
        # Connect the custom signal
        # dialog.fontSelected.connect(self.handle_font_selected) # Alternative way

        if dialog.exec_() == QDialog.Accepted:
            selected_font = dialog.get_selected_font()
            # The dialog ensures min size 5.0 internally via spinbox range
            # Store the selected font for printing, don't apply to UI
            self.print_font = selected_font
            self.save_settings(selected_font) # Pass the selected font to save
            self.logger.debug(
                f"Stored print font: {self.print_font.family()}, Size: {getattr(self.print_font, 'float_size', self.print_font.pointSize())}pt, Bold={self.print_font.bold()}"
            )

    # Removed apply_font_settings as we no longer apply to UI directly from here

    def load_settings(self):
        """Load application settings, including font."""
        settings = QSettings(SETTINGS_ORG, SETTINGS_APP) # Use consistent names
        default_family = QApplication.font().family()
        default_size = float(QApplication.font().pointSize())
        default_bold = QApplication.font().bold()

        # Read values explicitly checking types
        font_family_raw = settings.value("font/family")
        font_size_raw = settings.value("font/size_float")
        font_bold_raw = settings.value("font/bold")

        font_family = font_family_raw if isinstance(font_family_raw, str) else default_family
        # Use the type hint in settings.value for loading float
        font_size_float = settings.value("font/size_float", default_size, type=float)
        # Explicit boolean conversion check
        if isinstance(font_bold_raw, str): # Handle 'true'/'false' strings if saved that way
             font_bold = font_bold_raw.lower() == 'true'
        elif isinstance(font_bold_raw, bool):
             font_bold = font_bold_raw
        else: # Fallback for other types or None
             font_bold = default_bold

        # Ensure minimum size on load
        if font_size_float < 5.0:
            font_size_float = 5.0

        # Create the font using the integer size for QFont, but store the float size
        loaded_font = QFont(font_family, int(round(font_size_float)))
        loaded_font.setBold(font_bold)
        loaded_font.float_size = font_size_float # Store the float size

        # Apply the loaded font settings during initialization
        # We need to ensure widgets exist before applying.
        # Applying here might be too early. Let's apply after widgets are created.
        # Store the loaded font settings for printing
        self.print_font = loaded_font


    def save_settings(self, font_to_save):
        """Save application settings, specifically the print font."""
        settings = QSettings(SETTINGS_ORG, SETTINGS_APP) # Use consistent names
        # Use the font passed (which is intended for printing)
        float_size = getattr(font_to_save, 'float_size', float(font_to_save.pointSize()))
        # Ensure we save as float
        settings.setValue("font/family", font_to_save.family())
        settings.setValue("font/size_float", float(float_size)) # Explicitly save as float
        settings.setValue("font/bold", bool(font_to_save.bold())) # Explicitly save as bool
        settings.sync() # Ensure settings are written immediately

    def closeEvent(self, event):
        """Handle window close event."""
        self.logger.info("Application closing")
        # Persist window geometry/state
        try:
            settings = QSettings(SETTINGS_ORG, SETTINGS_APP)
            settings.setValue("ui/main_geometry", self.saveGeometry())
            settings.setValue("ui/main_state", self.saveState())
            settings.sync()
        except Exception:
            pass
        # Close the database connection properly
        if hasattr(self, 'db') and self.db:
            self.logger.debug("Closing database connection")
            self.db.close()
        # Optional: Add confirmation dialog if needed
        # self.save_settings() # Save settings on close if desired, though saving after change is often better
        super().closeEvent(event)

    def show_table_font_size_dialog(self):
        """Show dialog to change estimate table font size."""
        from table_font_size_dialog import TableFontSizeDialog
        from PyQt5.QtGui import QFont
        from PyQt5.QtCore import QSettings

        # 1. Load current setting
        settings = QSettings(SETTINGS_ORG, SETTINGS_APP)
        current_size = settings.value("ui/table_font_size", defaultValue=9, type=int)

        # 2. Show dialog
        dialog = TableFontSizeDialog(current_size=current_size, parent=self)
        if dialog.exec_() == QDialog.Accepted:
            new_size = dialog.get_selected_size()

            # 3. Save new setting
            settings.setValue("ui/table_font_size", new_size)
            settings.sync()

            # 4. Apply to estimate widget's table (if widget exists)
            if hasattr(self, 'estimate_widget') and hasattr(self.estimate_widget, '_apply_table_font_size'):
                self.estimate_widget._apply_table_font_size(new_size)
            else:
                 self.logger.warning("Estimate widget or apply method not found.")

    # --- Method to show the new Settings dialog ---
    def show_settings_dialog(self):
        """Show the centralized settings dialog."""
        from settings_dialog import SettingsDialog
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
        from logger import get_log_config, setup_logging, LogCleanupScheduler

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

        main_window = MainWindow(password=password, logger=logger)
        if not getattr(main_window, 'db', None):
            logger.critical("Failed to initialize database connection during startup")
            QMessageBox.critical(
                None,
                "Initialization Error",
                "Failed to initialize database connection.\n\nThe application will now exit."
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


