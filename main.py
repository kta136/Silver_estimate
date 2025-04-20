#!/usr/bin/env python
import sys
import os
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QShortcut,
                             QMenuBar, QMenu, QAction, QMessageBox, QDialog, QStatusBar) # Added QStatusBar
from PyQt5.QtGui import QKeySequence
from PyQt5.QtCore import Qt

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
        silver_bars_action = QAction("&Silver Bar Management", self)
        silver_bars_action.triggered.connect(self.show_silver_bars)
        tools_menu.addAction(silver_bars_action)

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

    def show_silver_bars(self):
        """Show silver bar management dialog."""
        from silver_bar_management import SilverBarDialog
        silver_dialog = SilverBarDialog(self.db, self)
        silver_dialog.exec_()

    def show_estimate_history(self):
        """Show estimate history dialog."""
        from estimate_history import EstimateHistoryDialog
        history_dialog = EstimateHistoryDialog(self.db, self)
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
                          "Version 1.0\n\n"
                          "A comprehensive tool for managing silver estimations, "
                          "item inventory, and silver bars.\n\n"
                          "© 2023 Silver Estimation App")


if __name__ == "__main__":
    # Create the application
    app = QApplication(sys.argv)

    # Create and show the main window
    main_window = MainWindow()
    main_window.show()

    # Run the application
    sys.exit(app.exec_())
