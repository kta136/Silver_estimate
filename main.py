#!/usr/bin/env python
import sys
import os
import traceback

from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QShortcut,
                             QMenuBar, QMenu, QAction, QMessageBox, QDialog, QStatusBar) # Removed QFontDialog
from PyQt5.QtGui import QKeySequence, QFont
from PyQt5.QtCore import Qt, QSettings

# Import the custom dialog
from custom_font_dialog import CustomFontDialog

from estimate_entry import EstimateEntryWidget
from item_master import ItemMasterWidget
from database_manager import DatabaseManager


class MainWindow(QMainWindow):
    """Main application window for the Silver Estimation App."""

    def __init__(self):
        super().__init__()

        # Set up the database
        self.db = DatabaseManager('database/estimation.db')
        self.db.setup_database()

        # Initialize UI
        self.setWindowTitle("Silver Estimation App")
        self.setGeometry(100, 100, 1000, 700)

        # Set up menu bar
        self.setup_menu_bar()

        # Load settings (including font) before setting up UI elements that use them
        self.load_settings()

        # Set up status bar
        self.statusBar = QStatusBar()
        self.setStatusBar(self.statusBar)
        self.statusBar.showMessage("Ready") # Initial message

        # Central widget
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.layout = QVBoxLayout(self.central_widget)

        # Initialize widgets, passing main window to EstimateEntryWidget
        self.estimate_widget = EstimateEntryWidget(self.db, self) # Pass main window instance
        self.item_master_widget = ItemMasterWidget(self.db)

        # Add widgets to layout
        self.layout.addWidget(self.estimate_widget)
        self.layout.addWidget(self.item_master_widget)

        # Initially show estimate entry
        self.item_master_widget.hide()
        self.estimate_widget.show()

        # Set up shortcuts
#        self.setup_shortcuts()

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

        # Database actions
        db_reset_action = QAction("&Reset Database Tables", self)
        db_reset_action.triggered.connect(self.reset_database)
        tools_menu.addAction(db_reset_action)

        # Silver bar management
        silver_bars_action = QAction("&Silver Bar Management", self)  # Keep original name maybe?
        silver_bars_action.setStatusTip("Add, view, transfer, or assign silver bars to lists")
        silver_bars_action.triggered.connect(self.show_silver_bars)  # Connect to MainWindow's method
        tools_menu.addAction(silver_bars_action)

        # Font settings action
        tools_menu.addSeparator()
        font_action = QAction("&Print Font Settings...", self) # Renamed for clarity
        font_action.setStatusTip("Change font settings for printing estimates")
        font_action.triggered.connect(self.show_font_dialog)
        tools_menu.addAction(font_action)

        # Table Font Size action
        table_font_action = QAction("&Table Font Size...", self)
        table_font_action.setStatusTip("Change font size for the estimate entry table")
        table_font_action.triggered.connect(self.show_table_font_size_dialog) # Connect to new handler
        tools_menu.addAction(table_font_action)

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

    def reset_database(self):
        """Drop and recreate all database tables."""
        reply = QMessageBox.question(self, "Reset Database",
                                     "Are you sure you want to reset the database? This will delete ALL data.",
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)

        if reply == QMessageBox.Yes:
            try:
                # Use the drop_tables method instead of removing the file
                success = self.db.drop_tables()

                if success:
                    # Recreate tables
                    self.db.setup_database()

                    # Refresh the widgets
                    self.item_master_widget.load_items()
                    self.estimate_widget.clear_form()

                    QMessageBox.information(self, "Success", "Database tables have been reset successfully.")
                else:
                    QMessageBox.critical(self, "Error", "Failed to reset database tables.")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to reset database: {str(e)}")

    def show_silver_bars(self):  # Keep this method name for consistency
        """Show silver bar management dialog."""
        # Import the MODIFIED dialog class
        from silver_bar_management import SilverBarDialog
        try:
            silver_dialog = SilverBarDialog(self.db, self)
            silver_dialog.exec_()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to open Silver Bar Management: {e}")
            print(traceback.format_exc())

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
                          "Version 1.12\n\n"
                          "A comprehensive tool for managing silver estimations, "
                          "item inventory, and silver bars.\n\n"
                          "© 2023 Silver Estimation App")

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


if __name__ == "__main__":
    # Create the application
    app = QApplication(sys.argv)

    # Create and show the main window
    main_window = MainWi    ndow()

    # No longer applying font settings globally on startup
    # main_window.apply_font_settings(main_window.print_font) # Removed this line

    main_window.show()

    # Run the application
    sys.exit(app.exec_())
