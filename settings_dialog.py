#!/usr/bin/env python
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QPushButton, QGroupBox, QGridLayout, QLabel, QComboBox) # Added QComboBox
from PyQt5.QtCore import Qt, QSettings # Added QSettings

class SettingsDialog(QDialog):
    """Dialog to host various application settings and actions."""

    def __init__(self, main_window, parent=None):
        super().__init__(parent)
        self.main_window = main_window # Store reference to main window

        self.setWindowTitle("Application Settings")
        self.setMinimumWidth(400)
        self.setModal(True) # Make it modal

        layout = QVBoxLayout(self)

        # --- Theme Settings Group ---
        theme_group = QGroupBox("Theme Settings")
        theme_layout = QGridLayout() # Use grid for label + combo

        theme_layout.addWidget(QLabel("Select Theme:"), 0, 0)
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["Modern Light", "Classic Blue"])
        self.theme_combo.currentIndexChanged.connect(self._theme_changed)
        theme_layout.addWidget(self.theme_combo, 0, 1)

        theme_group.setLayout(theme_layout)
        layout.addWidget(theme_group)

        # --- Font Settings Group ---
        font_group = QGroupBox("Font Settings")
        font_layout = QVBoxLayout()

        self.print_font_button = QPushButton("&Print Font Settings...") # Added &
        self.print_font_button.setToolTip("Change font settings for printing estimates")
        self.print_font_button.clicked.connect(self.main_window.show_font_dialog) # Connect to main window method
        font_layout.addWidget(self.print_font_button)

        self.table_font_button = QPushButton("&Table Font Size...") # Added &
        self.table_font_button.setToolTip("Change font size for the estimate entry table")
        self.table_font_button.clicked.connect(self.main_window.show_table_font_size_dialog) # Connect to main window method
        font_layout.addWidget(self.table_font_button)

        font_group.setLayout(font_layout)
        layout.addWidget(font_group)

        # --- Data Management Group ---
        data_group = QGroupBox("Data Management")
        data_layout = QVBoxLayout()

        self.delete_estimates_button = QPushButton("Delete All &Estimates...") # Added &
        self.delete_estimates_button.setToolTip("WARNING: Deletes all saved estimates!")
        self.delete_estimates_button.clicked.connect(self.main_window.delete_all_estimates) # Connect to main window method
        data_layout.addWidget(self.delete_estimates_button)

        self.delete_all_button = QPushButton("&DELETE ALL DATA") # Added &
        self.delete_all_button.setToolTip("WARNING: Deletes all items, estimates, bars, and lists!")
        # Styling for emphasis (optional, might not look great on all themes)
        self.delete_all_button.setStyleSheet("QPushButton { color: red; font-weight: bold; }")
        self.delete_all_button.clicked.connect(self.main_window.delete_all_data) # Connect to main window method
        data_layout.addWidget(self.delete_all_button)

        data_group.setLayout(data_layout)
        layout.addWidget(data_group)

        # --- Close Button ---
        self.close_button = QPushButton("&Close") # Added &
        self.close_button.clicked.connect(self.accept) # Close the dialog
        layout.addWidget(self.close_button, alignment=Qt.AlignRight)

        self.setLayout(layout)

        # Load initial theme setting
        self._load_initial_theme()

    def _load_initial_theme(self):
        """Sets the combo box based on the currently saved theme."""
        # Access settings through main_window or directly if preferred
        settings = QSettings("YourCompany", "SilverEstimateApp")
        current_theme = settings.value("ui/theme", "Modern Light")
        if current_theme == "Classic Blue":
            self.theme_combo.setCurrentIndex(1)
        else:
            self.theme_combo.setCurrentIndex(0)

    def _theme_changed(self):
        """Handles theme selection change."""
        selected_theme = self.theme_combo.currentText()
        # Call main window's method to apply and save
        if hasattr(self.main_window, 'apply_theme'):
            self.main_window.apply_theme(selected_theme)
        else:
            print("Error: MainWindow does not have apply_theme method.")