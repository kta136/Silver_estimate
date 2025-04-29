#!/usr/bin/env python
import sys
import os
import traceback
import logging

from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QShortcut,
                             QMenuBar, QMenu, QAction, QMessageBox, QDialog, QStatusBar)
from PyQt5.QtGui import QKeySequence, QFont
from PyQt5.QtCore import Qt, QSettings, QTimer # Import QSettings
import PyQt5.QtCore as QtCore

# Import the custom dialogs and modules
from custom_font_dialog import CustomFontDialog
from login_dialog import LoginDialog # Import the new login dialog
from estimate_entry import EstimateEntryWidget
from item_master import ItemMasterWidget
from database_manager import DatabaseManager
# from advanced_tools_dialog import AdvancedToolsDialog # Remove old import
from settings_dialog import SettingsDialog # Import the new settings dialog
from logger import setup_logging, qt_message_handler, LoggingStatusBar


class MainWindow(QMainWindow):
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
        self.setWindowTitle("Silver Estimation App v1.62") # Update version
        # self.setGeometry(100, 100, 1000, 700) # Remove fixed geometry
        # self.showFullScreen() # Start in true full screen
        # We need to show the window first before maximizing it
        # self.show() # This is implicitly called later by app.exec_() usually
        # Let's try setting the window state directly (Moved to end of __init__)
        # self.setWindowState(Qt.WindowMaximized)

        # Set up status bar *early* so it's available during DB setup
        self.statusBar = QStatusBar()
        self.setStatusBar(self.statusBar)
        # Create logging status bar wrapper
        self.logging_status = LoggingStatusBar(self.statusBar, self.logger)
        self.logging_status.show_message("Initializing...", 3000) # Initial message

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

        # Status bar is already set up
        self.statusBar.showMessage("Ready") # Update message after setup

        # Central widget
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.layout = QVBoxLayout(self.central_widget)

        # Initialize widgets, passing main window and db manager
        # Ensure db is initialized before creating widgets that need it
        if self.db:
            self.estimate_widget = EstimateEntryWidget(self.db, self) # Pass main window instance
            self.item_master_widget = ItemMasterWidget(self.db)

            # Add widgets to layout
            self.layout.addWidget(self.estimate_widget)
            self.layout.addWidget(self.item_master_widget)

            # Initially show estimate entry
            self.item_master_widget.hide()
            self.estimate_widget.show()
        else:
             # Handle case where db failed to initialize
             QMessageBox.critical(self, "Database Error", "Failed to initialize database. Application cannot continue.")
             # Again, exiting from here is tricky, maybe disable UI elements?
             # For now, just don't add the widgets.
             pass


        # Set up shortcuts (if needed)
#        self.setup_shortcuts()

        # Set window state to maximized at the very end of initialization
        self.setWindowState(Qt.WindowMaximized)

    def setup_database_with_password(self, password):
        """Initialize the DatabaseManager with the provided password."""
        try:
            self.logger.info("Setting up database connection")
            # DatabaseManager now handles getting/creating salt internally via QSettings
            self.db = DatabaseManager('database/estimation.db', password=password)
            # setup_database is called within DatabaseManager's __init__
            self.logging_status.show_message("Database connected securely.", 3000)
            self.logger.info("Database connected successfully")
        except Exception as e:
            self.logger.critical(f"Failed to connect to encrypted database: {str(e)}", exc_info=True)
            QMessageBox.critical(self, "Database Error", f"Failed to connect to encrypted database: {e}\nApplication might not function correctly.")
            self.db = None # Ensure db is None if setup fails

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

        # Exit action
        file_menu.addSeparator()
        exit_action = QAction("E&xit", self)
        exit_action.setShortcut("Alt+X")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # Tools menu
        tools_menu = menu_bar.addMenu("&Tools")

        # Silver bar management (Keep this directly in the menu)
        silver_bars_action = QAction("&Silver Bar Management", self)
        silver_bars_action.setStatusTip("Add, view, transfer, or assign silver bars to lists")
        silver_bars_action.triggered.connect(self.show_silver_bars)
        tools_menu.addAction(silver_bars_action)

        tools_menu.addSeparator()

        # Settings Dialog Action (Replaces Advanced Tools)
        settings_action = QAction("&Settings...", self)
        settings_action.setStatusTip("Configure application settings")
        settings_action.triggered.connect(self.show_settings_dialog) # Connect to new method
        tools_menu.addAction(settings_action)

        # Removed Import Item List action from here
        # tools_menu.addSeparator()
        # import_item_action = QAction(...)
        # tools_menu.addAction(import_item_action)

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
        """Switch to Estimate Entry screen."""
        self.item_master_widget.hide()
        self.estimate_widget.show()

    def show_item_master(self):
        """Switch to Item Master screen."""
        self.estimate_widget.hide()
        self.item_master_widget.show()

    def delete_all_data(self): # Renamed method
        """Drop and recreate all database tables, effectively deleting all data."""
        # Use QMessageBox.warning for more emphasis
        reply = QMessageBox.warning(self, "CONFIRM DELETE ALL DATA", # Changed title
                                     "Are you absolutely sure you want to delete ALL data?\n"
                                     "This includes all items, estimates, silver bars, and lists.\n"
                                     "THIS ACTION CANNOT BE UNDONE.", # Updated message
                                     QMessageBox.Yes | QMessageBox.Cancel, QMessageBox.Cancel) # Changed buttons

        if reply == QMessageBox.Yes:
            try:
                # Use the drop_tables method instead of removing the file
                success = self.db.drop_tables() # This method drops all tables

                if success:
                    # Recreate tables
                    self.db.setup_database()

                    # Refresh the widgets to reflect empty state
                    self.item_master_widget.load_items()
                    self.estimate_widget.clear_form(confirm=False) # Clear estimate form without confirmation

                    QMessageBox.information(self, "Success", "All data has been deleted successfully.") # Updated success message
                else:
                    QMessageBox.critical(self, "Error", "Failed to delete all data (dropping tables failed).") # Updated error message
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to delete all data: {str(e)}") # Updated error message

    def delete_all_estimates(self):
        """Handle the 'Delete All Estimates' action."""
        reply = QMessageBox.warning(self, "Confirm Delete All Estimates",
                                     "Are you absolutely sure you want to delete ALL estimates?\n"
                                     "This action cannot be undone.",
                                     QMessageBox.Yes | QMessageBox.Cancel, QMessageBox.Cancel)

        if reply == QMessageBox.Yes:
            try:
                success = self.db.delete_all_estimates()
                if success:
                    QMessageBox.information(self, "Success", "All estimates have been deleted successfully.")
                    # Clear the current estimate form as well
                    if hasattr(self, 'estimate_widget'):
                        self.estimate_widget.clear_form(confirm=False)
                else:
                    QMessageBox.critical(self, "Error", "Failed to delete all estimates (database error).")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"An unexpected error occurred: {str(e)}")

    def show_silver_bars(self):  # Keep this method name for consistency
        """Show silver bar management dialog."""
        # Import the MODIFIED dialog class
        from silver_bar_management import SilverBarDialog
        try:
            self.logger.info("Opening Silver Bar Management dialog")
            silver_dialog = SilverBarDialog(self.db, self)
            silver_dialog.exec_()
        except Exception as e:
            self.logger.error(f"Failed to open Silver Bar Management: {str(e)}", exc_info=True)
            QMessageBox.critical(self, "Error", f"Failed to open Silver Bar Management: {e}")

    def show_estimate_history(self):
        """Show estimate history dialog."""
        from estimate_history import EstimateHistoryDialog
        # Pass db_manager, the explicit main_window_ref (self), and parent (self)
        history_dialog = EstimateHistoryDialog(self.db, main_window_ref=self, parent=self)
        if history_dialog.exec_() == QDialog.Accepted:
            voucher_no = history_dialog.selected_voucher
            if voucher_no:
                self.estimate_widget.voucher_edit.setText(voucher_no)
                self.estimate_widget.load_estimate()
                self.show_estimate()

    def show_about(self):
        """Show about dialog."""
        QMessageBox.about(self, "About Silver Estimation App",
                          "Silver Estimation App\n\n"
                          "Version 1.61\n\n" # Make sure this matches window title
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
            print(f"Stored print font: {self.print_font.family()}, Size: {getattr(self.print_font, 'float_size', self.print_font.pointSize())}pt, Bold={self.print_font.bold()}") # For debugging

    # Removed apply_font_settings as we no longer apply to UI directly from here

    def load_settings(self):
        """Load application settings, including font."""
        settings = QSettings("YourCompany", "SilverEstimateApp") # Use consistent names
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
        settings = QSettings("YourCompany", "SilverEstimateApp") # Use consistent names
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
        settings = QSettings("YourCompany", "SilverEstimateApp")
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
                 print("Warning: Estimate widget or apply method not found.")

    # --- Method to show the new Settings dialog ---
    def show_settings_dialog(self):
        """Show the centralized settings dialog."""
        dialog = SettingsDialog(main_window_ref=self, parent=self)
        # Connect the signal if needed for immediate UI updates beyond fonts
        # dialog.settings_applied.connect(self.handle_settings_applied)
        dialog.exec_()
    # Removed show_advanced_tools_dialog method

    def show_import_dialog(self):
        """Show the item import dialog and handle the import process."""
        from item_import_dialog import ItemImportDialog
        from item_import_manager import ItemImportManager

        # Only allow if user is authenticated and DB is available
        if not hasattr(self, 'db') or not self.db:
            QMessageBox.warning(self, "Authentication Required",
                               "Database is not connected. Please log in first.")
            return

        # Create dialog and import manager
        dialog = ItemImportDialog(self)
        # Pass the authenticated DatabaseManager instance
        manager = ItemImportManager(self.db)

        # --- Signal Connections ---
        # Start import when dialog requests it (pass file path and settings dict)
        dialog.importStarted.connect(manager.import_from_file) # Manager now expects dict

        # Update dialog UI based on manager progress/status
        manager.progress_updated.connect(dialog.update_progress)
        manager.status_updated.connect(dialog.update_status)
        manager.import_finished.connect(dialog.import_finished)

        # Handle dialog close/cancel: If rejected, request manager to stop
        dialog.rejected.connect(manager.cancel_import) # Connect reject signal

        # --- Execute Dialog ---
        dialog.exec_() # Show the dialog modally

        # --- Post-Import Actions ---
        # Refresh item master table if it's currently visible to show new/updated items
        if hasattr(self, 'item_master_widget') and self.item_master_widget.isVisible():
            print("Refreshing Item Master list after import.")
            self.item_master_widget.load_items()

        # Clean up manager object (optional, depends if it holds resources)
        # In this case, it's likely fine to let it be garbage collected.


# --- Authentication and Data Wipe Logic ---

def run_authentication(logger=None):
    """
    Handles the authentication process using LoginDialog.
    Returns the password on success, 'wipe' if wipe requested, or None on failure/cancel.
    
    Args:
        logger: Logger instance for authentication events
    """
    logger = logger or logging.getLogger(__name__)
    logger.info("Starting authentication process")
    
    settings = QSettings("YourCompany", "SilverEstimateApp")
    password_hash = settings.value("security/password_hash")
    backup_hash = settings.value("security/backup_hash")
    # Salt is handled internally by DatabaseManager now

    if password_hash and backup_hash:
        # --- Existing User: Show Login Dialog ---
        logger.debug("Found existing password hashes, showing login dialog")
        login_dialog = LoginDialog(is_setup=False)
        result = login_dialog.exec_()

        if result == QDialog.Accepted:
            # Check if reset was requested FIRST
            if login_dialog.was_reset_requested():
                logger.warning("Data wipe requested via reset button")
                return 'wipe' # Request data wipe via reset button

            # If not reset, proceed with password verification
            entered_password = login_dialog.get_password()
            # Verify against main password
            if LoginDialog.verify_password(password_hash, entered_password):
                logger.info("Authentication successful")
                return entered_password # Success!
            # Verify against secondary password
            elif LoginDialog.verify_password(backup_hash, entered_password):
                logger.warning("Secondary password used - triggering data wipe")
                return 'wipe' # Internal signal to trigger data wipe
            else:
                logger.warning("Authentication failed: incorrect password")
                QMessageBox.warning(None, "Login Failed", "Incorrect password.")
                return None # Incorrect password
        else:
            logger.info("Login cancelled by user")
            return None # Login cancelled

    else:
        # --- First Run: Show Setup Dialog ---
        # No need to check config file here, just check if hashes exist in QSettings
        logger.info("Password hashes not found in settings. Starting first-time setup.")
        setup_dialog = LoginDialog(is_setup=True)
        result = setup_dialog.exec_()

        if result == QDialog.Accepted:
            logger.info("First-time setup completed")
            password = setup_dialog.get_password()
            backup_password = setup_dialog.get_backup_password()

            # Hash passwords using passlib (via static method in LoginDialog)
            hashed_password = LoginDialog.hash_password(password)
            hashed_backup = LoginDialog.hash_password(backup_password) # Hash secondary password

            if not hashed_password or not hashed_backup:
                 logger.error("Failed to hash passwords during setup")
                 QMessageBox.critical(None, "Setup Error", "Failed to hash passwords.")
                 return None # Hashing failed

            # Salt is generated and saved internally by DatabaseManager on first init
            # Save hashes to QSettings
            settings = QSettings("YourCompany", "SilverEstimateApp") # Need settings object here
            settings.setValue("security/password_hash", hashed_password)
            settings.setValue("security/backup_hash", hashed_backup) # Store secondary hash
            settings.sync() # Ensure they are saved immediately

            logger.info("Passwords created and stored successfully")
            QMessageBox.information(None, "Setup Complete", "Passwords created successfully.")
            # Return the new password. Salt will be handled by DB Manager.
            return password
        else:
            logger.info("Setup cancelled by user")
            return None # Setup cancelled

def perform_data_wipe(db_path='database/estimation.db', logger=None):
    """
    Performs the data wipe operation: deletes the *encrypted* database file
    and clears password hashes and the database salt from QSettings.
    Returns True on success, False on failure.
    
    Args:
        db_path: Path to the encrypted database file
        logger: Logger instance for data wipe events
    """
    logger = logger or logging.getLogger(__name__)
    # This function is triggered internally by entering the secondary password
    # or clicking the explicit Reset button.
    logger.warning(f"Initiating data wipe for encrypted database: {db_path}")
    try:
        # Ensure any potential database connection is closed (though it shouldn't be open yet)

        # Delete the *encrypted* database file
        if os.path.exists(db_path):
            os.remove(db_path)
            logger.info(f"Successfully deleted encrypted database file: {db_path}")
        else:
            logger.warning(f"Encrypted database file not found (already deleted?): {db_path}")

        # Clear password hashes AND the database salt from settings
        settings = QSettings("YourCompany", "SilverEstimateApp")
        settings.remove("security/password_hash")
        settings.remove("security/backup_hash")
        settings.remove("security/db_salt") # CRITICAL: Remove the salt!
        settings.sync()
        logger.info("Cleared password hashes and database salt from application settings.")

        # Removed user notification for successful wipe to make it silent
        # QMessageBox.information(None, "Data Wipe Complete", ...)
        logger.info("Data wipe successful (silent to user).")
        return True
    except Exception as e:
        # Still show critical error if wipe fails
        error_message = f"A critical error occurred during data wipe: {e}"
        logger.critical(error_message, exc_info=True)
        QMessageBox.critical(None, "Data Wipe Error", error_message)
        return False


# --- Main Application Execution ---

if __name__ == "__main__":
    try:
        # Initialize logging before anything else
        import os
        from pathlib import Path
        from logger import get_log_config, setup_logging, LogCleanupScheduler
        
        # Ensure logs directory exists
        logs_dir = Path("logs")
        logs_dir.mkdir(exist_ok=True)
        
        # Get logging configuration
        log_config = get_log_config()
        
        # Initialize logging with configuration
        logger = setup_logging(
            app_name="silver_app",
            log_dir=log_config['log_dir'],
            debug_mode=log_config['debug_mode'],
            enable_info=log_config['enable_info'],
            enable_error=log_config['enable_error'],
            enable_debug=log_config['enable_debug']
        )
        
        # Log startup information
        logger.info(f"Silver Estimation App v1.62 starting")
        logger.debug(f"Logging configuration: {log_config}")
        
        # Initialize cleanup scheduler if enabled
        cleanup_scheduler = None
        if log_config['auto_cleanup']:
            try:
                cleanup_scheduler = LogCleanupScheduler(
                    log_dir=log_config['log_dir'],
                    cleanup_days=log_config['cleanup_days']
                )
                cleanup_scheduler.start()
                logger.info(f"Log cleanup scheduler initialized with {log_config['cleanup_days']} days retention")
            except Exception as e:
                logger.error(f"Failed to initialize log cleanup scheduler: {e}", exc_info=True)
                # Continue without cleanup scheduler
        
        # Set up Qt message redirection
        QtCore.qInstallMessageHandler(qt_message_handler)
        logger.debug("Qt message handler installed")
        
        # Create the application object early for dialogs
        # Required for QSettings and QMessageBox before MainWindow exists
        logger.debug("Creating QApplication instance")
        app = QApplication(sys.argv)

        # --- Authentication Step ---
        auth_result = run_authentication(logger)

        if auth_result == 'wipe':
            # --- Perform Data Wipe ---
            logger.warning("Data wipe requested, performing wipe operation")
            if perform_data_wipe(db_path='database/estimation.db', logger=logger): # Only need DB path now
                # Exit cleanly after successful wipe. User needs to restart manually.
                logger.info("Exiting application after successful data wipe.")
                sys.exit(0)
            else:
                # Wipe failed, critical error. Exit with error status.
                logger.critical("Exiting application due to data wipe failure.")
                sys.exit(1)

        elif auth_result: # Password provided (login or setup successful)
            # --- Start Main Application ---
            password = auth_result # auth_result is just the password now
            logger.info("Authentication successful, initializing main window")
            # Pass password to main window. DB Manager handles salt.
            main_window = MainWindow(password=password, logger=logger)

            # Check if MainWindow initialization and DB setup were successful
            # setup_database_with_password is called within MainWindow.__init__
            if main_window.db: # Check if db object was successfully created
                # Show the window (maximized state is set in __init__)
                logger.info("Showing main application window")
                main_window.show()
                # Enter the Qt main event loop
                logger.debug("Entering Qt main event loop")
                exit_code = app.exec_()
                
                # Clean up resources on exit
                logger.debug("Cleaning up resources before exit")
                
                # Stop log cleanup scheduler if running
                if cleanup_scheduler is not None:
                    logger.debug("Stopping log cleanup scheduler")
                    cleanup_scheduler.stop()
                
                # Close DB connection cleanly on exit
                if hasattr(main_window, 'db') and main_window.db:
                    logger.debug("Closing database connection on exit")
                    main_window.db.close() # Ensure close is called
                
                logger.info(f"Application exiting with code {exit_code}")
                sys.exit(exit_code)
            else:
                # MainWindow init failed (likely DB issue shown in its init)
                logger.critical("Exiting application due to MainWindow initialization failure (Database connection?).")
                sys.exit(1)

        else: # Authentication failed or cancelled
            logger.info("Authentication failed or was cancelled by the user. Exiting.")
            sys.exit(0) # Exit cleanly without error
            
    except Exception as e:
        # Catch any unhandled exceptions during startup
        try:
            logger.critical("Unhandled exception during application startup", exc_info=True)
        except:
            # If logging fails, fall back to print
            print(f"CRITICAL ERROR: {str(e)}")
            print(traceback.format_exc())
        
        # Show error to user
        QMessageBox.critical(None, "Fatal Error",
                            f"The application encountered a fatal error and cannot continue.\n\n"
                            f"Error: {str(e)}")
        sys.exit(1)
