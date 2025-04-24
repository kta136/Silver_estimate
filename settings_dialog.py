#!/usr/bin/env python
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QTabWidget, QWidget, QDialogButtonBox,
                             QFormLayout, QLabel, QPushButton, QSpinBox, QFontDialog, QMessageBox)
from PyQt5.QtCore import Qt, QSettings, pyqtSignal
from PyQt5.QtGui import QFont

# Import dependent dialogs (initially)
from custom_font_dialog import CustomFontDialog
from table_font_size_dialog import TableFontSizeDialog

class SettingsDialog(QDialog):
    """Centralized dialog for application settings."""
    # Signal to indicate settings that require application restart or redraw
    settings_applied = pyqtSignal()

    def __init__(self, main_window_ref, parent=None):
        super().__init__(parent)
        self.main_window = main_window_ref # Store reference to main window
        self.setWindowTitle("Application Settings")
        self.setMinimumWidth(500)

        # Load current settings
        self.settings = QSettings("YourCompany", "SilverEstimateApp")

        # Store temporary font objects for editing
        self._current_print_font = self._load_print_font_setting()
        self._current_table_font_size = self._load_table_font_size_setting()
        # Add more settings variables as needed

        # Create tab widget
        self.tabs = QTabWidget()

        # Add tabs
        self.tabs.addTab(self._create_ui_tab(), "User Interface")
        # self.tabs.addTab(self._create_business_tab(), "Business Logic") # Placeholder
        # self.tabs.addTab(self._create_print_tab(), "Printing") # Placeholder
        self.tabs.addTab(self._create_data_tab(), "Data Management") # Add Data tab

        # Buttons
        # Add Help button later if needed
        self.buttonBox = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel | QDialogButtonBox.Apply) # Store as self.buttonBox
        self.buttonBox.accepted.connect(self.accept)
        self.buttonBox.rejected.connect(self.reject)
        self.buttonBox.button(QDialogButtonBox.Apply).clicked.connect(self.apply_settings)
        # Disable Apply button initially (optional, enable when settings change)
        # self.buttonBox.button(QDialogButtonBox.Apply).setEnabled(False)

        # Layout
        layout = QVBoxLayout()
        layout.addWidget(self.tabs)
        layout.addWidget(self.buttonBox) # Use self.buttonBox here
        self.setLayout(layout)

    # --- Tab Creation Methods ---

    def _create_ui_tab(self):
        """Create the User Interface settings tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        form_layout = QFormLayout()
        form_layout.setSpacing(10)

        # Print Font
        self.print_font_button = QPushButton("Configure Print Font...")
        self.print_font_button.setToolTip("Set font family, size, and style for printed estimates")
        self.print_font_label = QLabel(self._get_font_display_text(self._current_print_font)) # Show current setting
        self.print_font_button.clicked.connect(self._show_print_font_dialog)
        font_layout = QHBoxLayout()
        font_layout.addWidget(self.print_font_label)
        font_layout.addWidget(self.print_font_button)
        form_layout.addRow("Print Font:", font_layout)

        # Table Font Size
        self.table_font_size_spin = QSpinBox()
        self.table_font_size_spin.setRange(7, 16) # Keep range consistent
        self.table_font_size_spin.setValue(self._current_table_font_size)
        self.table_font_size_spin.setToolTip("Set font size for the main estimate entry table (7-16pt)")
        form_layout.addRow("Estimate Table Font Size:", self.table_font_size_spin)

        # Add more UI settings here...

        layout.addLayout(form_layout)
        layout.addStretch() # Push settings to the top
        widget.setLayout(layout)
        return widget

    # def _create_business_tab(self): ...
    # def _create_print_tab(self): ...

    def _create_data_tab(self):
        """Create the Data Management settings tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(15)

        description = QLabel(
            "<b>WARNING:</b> These actions permanently delete data and cannot be undone. "
            "Ensure you have backups if necessary."
        )
        description.setWordWrap(True)
        description.setStyleSheet("color: red;")
        layout.addWidget(description)

        button_layout = QHBoxLayout()

        self.delete_estimates_button = QPushButton("Delete All Estimates...")
        self.delete_estimates_button.setToolTip("Deletes all estimate headers and line items.")
        self.delete_estimates_button.setStyleSheet("color: orange;")
        self.delete_estimates_button.clicked.connect(self.main_window.delete_all_estimates)
        button_layout.addWidget(self.delete_estimates_button)

        self.delete_all_data_button = QPushButton("DELETE ALL DATA")
        self.delete_all_data_button.setToolTip("Deletes ALL items, estimates, bars, lists, etc.")
        self.delete_all_data_button.setStyleSheet("color: red; font-weight: bold;")
        self.delete_all_data_button.clicked.connect(self.main_window.delete_all_data)
        button_layout.addWidget(self.delete_all_data_button)

        layout.addLayout(button_layout)
        layout.addStretch() # Push buttons up
        widget.setLayout(layout)
        return widget

    # --- Helper Methods ---

    def _get_font_display_text(self, font):
        """Generate display text for a QFont object."""
        if not font: return "Default"
        size = getattr(font, 'float_size', font.pointSizeF()) # Use float size if available
        style = " Bold" if font.bold() else ""
        return f"{font.family()}, {size:.1f}pt{style}"

    def _load_print_font_setting(self):
        """Loads the print font from QSettings."""
        # Reusing logic similar to MainWindow.load_settings
        default_font = QFont("Courier New", 7) # Sensible default for print
        default_font.float_size = 7.0

        font_family = self.settings.value("font/family", default_font.family(), type=str)
        font_size_float = self.settings.value("font/size_float", default_font.float_size, type=float)
        font_bold = self.settings.value("font/bold", default_font.bold(), type=bool)

        # Ensure minimum size
        font_size_float = max(5.0, font_size_float)

        loaded_font = QFont(font_family, int(round(font_size_float)))
        loaded_font.setBold(font_bold)
        loaded_font.float_size = font_size_float
        return loaded_font

    def _load_table_font_size_setting(self):
        """Loads the table font size from QSettings."""
        default_size = 9
        min_size = 7
        max_size = 16
        size = self.settings.value("ui/table_font_size", defaultValue=default_size, type=int)
        return max(min_size, min(size, max_size)) # Clamp value

    def _show_print_font_dialog(self):
        """Show the custom print font dialog."""
        # Use the temporary font object for editing
        dialog = CustomFontDialog(self._current_print_font, self)
        if dialog.exec_() == QDialog.Accepted:
            self._current_print_font = dialog.get_selected_font()
            self.print_font_label.setText(self._get_font_display_text(self._current_print_font))

    # --- Apply/Save/Accept/Reject ---

    def apply_settings(self):
        """Save currently selected settings and apply immediate changes."""
        print("Applying settings...") # Debug
        try:
            # Save Print Font
            font_to_save = self._current_print_font
            float_size = getattr(font_to_save, 'float_size', float(font_to_save.pointSize()))
            self.settings.setValue("font/family", font_to_save.family())
            self.settings.setValue("font/size_float", float(float_size))
            self.settings.setValue("font/bold", bool(font_to_save.bold()))
            # Apply immediately to main window's print_font attribute
            self.main_window.print_font = font_to_save
            print(f"Applied print font: {self._get_font_display_text(font_to_save)}")

            # Save Table Font Size
            new_table_size = self.table_font_size_spin.value()
            self.settings.setValue("ui/table_font_size", new_table_size)
            # Apply immediately by calling main window's method (which applies to estimate widget)
            if hasattr(self.main_window, 'estimate_widget') and hasattr(self.main_window.estimate_widget, '_apply_table_font_size'):
                 self.main_window.estimate_widget._apply_table_font_size(new_table_size)
                 print(f"Applied table font size: {new_table_size}pt")
            else:
                 print("Warning: Could not apply table font size immediately.")

            # Save other settings...

            self.settings.sync()
            self.settings_applied.emit() # Emit signal
            print("Settings applied and saved.")
            # Optionally disable Apply button until changes are made again
            self.buttonBox.button(QDialogButtonBox.Apply).setEnabled(False)

        except Exception as e:
            QMessageBox.critical(self, "Error Applying Settings", f"Could not apply settings: {e}")
            print(f"Error applying settings: {traceback.format_exc()}")


    def accept(self):
        """Apply settings and close the dialog."""
        self.apply_settings()
        super().accept()

    def reject(self):
        """Close the dialog without applying changes since last Apply/Load."""
        print("Settings dialog rejected.") # Debug
        super().reject()

# Example usage for testing
if __name__ == '__main__':
    from PyQt5.QtWidgets import QApplication, QMainWindow
    import sys

    class DummyMainWindow(QMainWindow):
        def __init__(self):
            super().__init__()
            self.print_font = QFont("Arial", 10) # Dummy attribute
            self.estimate_widget = QWidget() # Dummy widget
            self.estimate_widget._apply_table_font_size = lambda size: print(f"Dummy Apply Table Font: {size}")

    app = QApplication(sys.argv)
    dummy_main = DummyMainWindow()
    dialog = SettingsDialog(dummy_main)
    dialog.exec_()
    sys.exit(app.exec_())