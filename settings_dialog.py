#!/usr/bin/env python
import traceback # Import traceback for error logging
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QTabWidget, QWidget, QDialogButtonBox, QGridLayout,
                             QFormLayout, QLabel, QPushButton, QSpinBox, QFontDialog, QMessageBox, QDoubleSpinBox,
                             QLineEdit, QGroupBox, QFileDialog, QCheckBox) # Added QCheckBox for logging settings
from PyQt5.QtCore import Qt, QSettings, pyqtSignal
from PyQt5.QtGui import QFont

# Import dependent dialogs and modules
from custom_font_dialog import CustomFontDialog
from table_font_size_dialog import TableFontSizeDialog
from login_dialog import LoginDialog # Needed for password verification/hashing
from item_export_manager import ItemExportManager # Import the new export manager

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
        self.tabs.addTab(self._create_print_tab(), "Printing") # Add Printing tab
        self.tabs.addTab(self._create_data_tab(), "Data Management") # Add Data tab
        self.tabs.addTab(self._create_security_tab(), "Security") # Add Security tab
        self.tabs.addTab(self._create_import_export_tab(), "Import/Export") # Add Import/Export tab
        self.tabs.addTab(self._create_logging_tab(), "Logging") # Add new Logging tab

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

    def _create_print_tab(self):
        """Create the Printing settings tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        form_layout = QFormLayout()
        form_layout.setSpacing(10)

        # --- Margins ---
        margins_label = QLabel("Page Margins (mm):")
        margins_layout = QGridLayout()
        self.margin_left_spin = QSpinBox()
        self.margin_top_spin = QSpinBox()
        self.margin_right_spin = QSpinBox()
        self.margin_bottom_spin = QSpinBox()
        for spin in [self.margin_left_spin, self.margin_top_spin, self.margin_right_spin, self.margin_bottom_spin]:
            spin.setRange(0, 50) # Allow 0-50mm margins
            spin.setSuffix(" mm")

        margins_layout.addWidget(QLabel("Left:"), 0, 0)
        margins_layout.addWidget(self.margin_left_spin, 0, 1)
        margins_layout.addWidget(QLabel("Top:"), 0, 2)
        margins_layout.addWidget(self.margin_top_spin, 0, 3)
        margins_layout.addWidget(QLabel("Right:"), 1, 0)
        margins_layout.addWidget(self.margin_right_spin, 1, 1)
        margins_layout.addWidget(QLabel("Bottom:"), 1, 2)
        margins_layout.addWidget(self.margin_bottom_spin, 1, 3)
        form_layout.addRow(margins_label, margins_layout)

        # --- Print Preview Zoom ---
        self.preview_zoom_spin = QDoubleSpinBox()
        self.preview_zoom_spin.setRange(0.1, 5.0) # 10% to 500%
        self.preview_zoom_spin.setSingleStep(0.1)
        self.preview_zoom_spin.setDecimals(2)
        self.preview_zoom_spin.setSuffix(" x") # Display as multiplier
        self.preview_zoom_spin.setToolTip("Default zoom factor for print preview (e.g., 1.0 = 100%, 1.25 = 125%)")
        form_layout.addRow("Preview Default Zoom:", self.preview_zoom_spin)

        # Load current values into controls
        self._load_print_settings_to_ui()

        layout.addLayout(form_layout)
        layout.addStretch()
        widget.setLayout(layout)
        return widget

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

    def _create_import_export_tab(self):
        """Create the Import/Export tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(15)

        # Import Section
        import_group = QGroupBox("Import Data")
        import_layout = QVBoxLayout(import_group)

        import_button = QPushButton("Import Item List...")
        import_button.setToolTip("Import items from a text or CSV file.")
        # Connect directly to the method already defined in MainWindow
        import_button.clicked.connect(self.main_window.show_import_dialog)
        import_layout.addWidget(import_button)
        import_layout.addStretch() # Push button to top if more controls are added later
        layout.addWidget(import_group)

        # Export Section
        export_group = QGroupBox("Export Data")
        export_layout = QVBoxLayout(export_group)
        export_button = QPushButton("Export Item List...")
        export_button.setToolTip("Export all items to a pipe-delimited text file.")
        export_button.clicked.connect(self._handle_export_items) # Connect to new handler
        export_layout.addWidget(export_button)
        export_layout.addStretch()
        layout.addWidget(export_group)

        layout.addStretch() # Push groups to the top
        return widget

    def _create_logging_tab(self):
        """Create the Logging settings tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Description label
        description = QLabel(
            "Configure how the application logs events and manages log files. "
            "Changes to these settings take effect immediately."
        )
        description.setWordWrap(True)
        description.setStyleSheet("margin-bottom: 10px;")
        layout.addWidget(description)
        
        # Debug mode section
        debug_group = QGroupBox("Debug Settings")
        debug_layout = QVBoxLayout(debug_group)
        
        # Debug mode checkbox
        self.debug_mode_checkbox = QCheckBox("Enable Debug Mode")
        self.debug_mode_checkbox.setToolTip("Enable detailed debug logging (may affect performance)")
        debug_mode = self.settings.value("logging/debug_mode", False, type=bool)
        self.debug_mode_checkbox.setChecked(debug_mode)
        debug_layout.addWidget(self.debug_mode_checkbox)
        
        # Debug mode description
        debug_desc = QLabel(
            "Debug mode captures detailed information about application operations. "
            "This is useful for troubleshooting but may affect performance."
        )
        debug_desc.setWordWrap(True)
        debug_desc.setStyleSheet("color: gray; font-size: 9pt; margin-left: 20px;")
        debug_layout.addWidget(debug_desc)
        
        # Log level toggles group
        log_levels_group = QGroupBox("Log Levels")
        log_levels_layout = QVBoxLayout(log_levels_group)
        
        # Normal logs (INFO)
        self.enable_info_checkbox = QCheckBox("Enable Normal Logs (INFO)")
        self.enable_info_checkbox.setToolTip("Log normal application events (INFO level)")
        enable_info = self.settings.value("logging/enable_info", True, type=bool)
        self.enable_info_checkbox.setChecked(enable_info)
        log_levels_layout.addWidget(self.enable_info_checkbox)
        
        # Critical logs (ERROR and CRITICAL)
        self.enable_critical_checkbox = QCheckBox("Enable Critical Logs (ERROR and CRITICAL)")
        self.enable_critical_checkbox.setToolTip("Log errors and critical issues")
        enable_critical = self.settings.value("logging/enable_critical", True, type=bool)
        self.enable_critical_checkbox.setChecked(enable_critical)
        log_levels_layout.addWidget(self.enable_critical_checkbox)
        
        # Debug logs
        self.enable_debug_checkbox = QCheckBox("Enable Debug Logs (when Debug Mode is on)")
        self.enable_debug_checkbox.setToolTip("Log detailed debug information (only when Debug Mode is enabled)")
        enable_debug = self.settings.value("logging/enable_debug", True, type=bool)
        self.enable_debug_checkbox.setChecked(enable_debug)
        log_levels_layout.addWidget(self.enable_debug_checkbox)
        
        # Log levels description
        levels_desc = QLabel(
            "You can enable or disable specific log levels. Critical logs are recommended "
            "to keep enabled for troubleshooting purposes."
        )
        levels_desc.setWordWrap(True)
        levels_desc.setStyleSheet("color: gray; font-size: 9pt; margin-top: 5px;")
        log_levels_layout.addWidget(levels_desc)
        
        # Auto cleanup group
        cleanup_group = QGroupBox("Automatic Log Cleanup")
        cleanup_layout = QVBoxLayout(cleanup_group)
        
        # Auto cleanup checkbox
        self.auto_cleanup_checkbox = QCheckBox("Automatically Delete Old Logs")
        self.auto_cleanup_checkbox.setToolTip("Automatically delete log files older than the specified number of days")
        auto_cleanup = self.settings.value("logging/auto_cleanup", False, type=bool)
        self.auto_cleanup_checkbox.setChecked(auto_cleanup)
        cleanup_layout.addWidget(self.auto_cleanup_checkbox)
        
        # Cleanup days spinbox
        cleanup_days_layout = QHBoxLayout()
        cleanup_days_layout.addWidget(QLabel("Keep logs for:"))
        self.cleanup_days_spin = QSpinBox()
        self.cleanup_days_spin.setRange(1, 365)
        self.cleanup_days_spin.setSuffix(" days")
        cleanup_days = self.settings.value("logging/cleanup_days", 1, type=int)
        self.cleanup_days_spin.setValue(cleanup_days)
        self.cleanup_days_spin.setEnabled(auto_cleanup)
        cleanup_days_layout.addWidget(self.cleanup_days_spin)
        cleanup_days_layout.addStretch()
        cleanup_layout.addLayout(cleanup_days_layout)
        
        # Cleanup description
        cleanup_desc = QLabel(
            "Automatic cleanup helps manage disk space by removing old log files. "
            "Cleanup occurs at midnight each day."
        )
        cleanup_desc.setWordWrap(True)
        cleanup_desc.setStyleSheet("color: gray; font-size: 9pt; margin-top: 5px;")
        cleanup_layout.addWidget(cleanup_desc)
        
        # Connect auto cleanup checkbox to enable/disable days spinbox
        self.auto_cleanup_checkbox.toggled.connect(self.cleanup_days_spin.setEnabled)
        
        # Manual cleanup button with layout
        manual_cleanup_layout = QHBoxLayout()
        self.manual_cleanup_button = QPushButton("Clean Up Logs Now...")
        self.manual_cleanup_button.setToolTip("Manually delete old log files")
        self.manual_cleanup_button.clicked.connect(self._handle_manual_log_cleanup)
        manual_cleanup_layout.addWidget(self.manual_cleanup_button)
        manual_cleanup_layout.addStretch()
        
        # Add all widgets to layout
        layout.addWidget(debug_group)
        layout.addWidget(log_levels_group)
        layout.addWidget(cleanup_group)
        layout.addLayout(manual_cleanup_layout)
        layout.addStretch()
        
        return widget
        

    def _create_security_tab(self):
        """Create the Security settings tab (Password Management)."""
        widget = QWidget()
        main_layout = QVBoxLayout(widget)
        main_layout.setSpacing(15)

        # --- Change Password Group ---
        password_group = QGroupBox("Change Passwords")
        group_layout = QFormLayout(password_group)
        group_layout.setSpacing(10)

        self.current_password_input = QLineEdit()
        self.current_password_input.setEchoMode(QLineEdit.Password)
        self.current_password_input.setPlaceholderText("Enter your current main password")
        group_layout.addRow("Current Password:", self.current_password_input)

        self.new_password_input = QLineEdit()
        self.new_password_input.setEchoMode(QLineEdit.Password)
        self.new_password_input.setPlaceholderText("Enter new main password")
        group_layout.addRow("New Main Password:", self.new_password_input)

        self.confirm_new_password_input = QLineEdit()
        self.confirm_new_password_input.setEchoMode(QLineEdit.Password)
        self.confirm_new_password_input.setPlaceholderText("Confirm new main password")
        group_layout.addRow("Confirm New Main:", self.confirm_new_password_input)

        group_layout.addRow(QLabel("-" * 40)) # Separator

        self.new_secondary_password_input = QLineEdit()
        self.new_secondary_password_input.setEchoMode(QLineEdit.Password)
        self.new_secondary_password_input.setPlaceholderText("Enter new secondary password")
        group_layout.addRow("New Secondary Password:", self.new_secondary_password_input)

        self.confirm_new_secondary_password_input = QLineEdit()
        self.confirm_new_secondary_password_input.setEchoMode(QLineEdit.Password)
        self.confirm_new_secondary_password_input.setPlaceholderText("Confirm new secondary password")
        group_layout.addRow("Confirm New Secondary:", self.confirm_new_secondary_password_input)

        self.change_password_button = QPushButton("Change Passwords")
        self.change_password_button.clicked.connect(self._handle_password_change)
        group_layout.addRow("", self.change_password_button) # Add button without label

        main_layout.addWidget(password_group)
        main_layout.addStretch()

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

    def _load_print_settings_to_ui(self):
        """Load current printing settings into the UI controls."""
        margins = self.settings.value("print/margins", defaultValue="10,2,10,2", type=str).split(',')
        if len(margins) == 4:
            try:
                self.margin_left_spin.setValue(int(margins[0]))
                self.margin_top_spin.setValue(int(margins[1]))
                self.margin_right_spin.setValue(int(margins[2]))
                self.margin_bottom_spin.setValue(int(margins[3]))
            except ValueError:
                print("Warning: Invalid margin format in settings.")
                # Keep default spinbox values
        else:
             print("Warning: Margin setting not found or invalid format.")

        default_zoom = 1.25
        zoom = self.settings.value("print/preview_zoom", defaultValue=default_zoom, type=float)
        self.preview_zoom_spin.setValue(zoom)


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

            # Save Printing Settings
            margins = f"{self.margin_left_spin.value()},{self.margin_top_spin.value()},{self.margin_right_spin.value()},{self.margin_bottom_spin.value()}"
            self.settings.setValue("print/margins", margins)
            print(f"Saved margins: {margins}")

            preview_zoom = self.preview_zoom_spin.value()
            self.settings.setValue("print/preview_zoom", preview_zoom)
            print(f"Saved preview zoom: {preview_zoom}")

            # Save logging settings
            self.settings.setValue("logging/debug_mode", self.debug_mode_checkbox.isChecked())
            self.settings.setValue("logging/enable_info", self.enable_info_checkbox.isChecked())
            self.settings.setValue("logging/enable_critical", self.enable_critical_checkbox.isChecked())
            self.settings.setValue("logging/enable_debug", self.enable_debug_checkbox.isChecked())
            self.settings.setValue("logging/auto_cleanup", self.auto_cleanup_checkbox.isChecked())
            self.settings.setValue("logging/cleanup_days", self.cleanup_days_spin.value())
            
            # Apply logging settings immediately
            from logger import reconfigure_logging
            reconfigure_logging()
            print("Logging settings applied.")

            # Save other settings...

            self.settings.sync()
            self.settings_applied.emit() # Emit signal
            print("Settings applied and saved.")
            # Optionally disable Apply button until changes are made again
            self.buttonBox.button(QDialogButtonBox.Apply).setEnabled(False)

        except Exception as e:
            QMessageBox.critical(self, "Error Applying Settings", f"Could not apply settings: {e}")
            print(f"Error applying settings: {traceback.format_exc()}")


    def _handle_password_change(self):
        """Handle the logic for changing both passwords."""
        current_password = self.current_password_input.text()
        new_main_pw = self.new_password_input.text()
        confirm_main_pw = self.confirm_new_password_input.text()
        new_secondary_pw = self.new_secondary_password_input.text()
        confirm_secondary_pw = self.confirm_new_secondary_password_input.text()

        # 1. Validate Current Password
        stored_main_hash = self.settings.value("security/password_hash")
        if not stored_main_hash or not LoginDialog.verify_password(stored_main_hash, current_password):
            QMessageBox.warning(self, "Password Change Failed", "Incorrect current password.")
            self.current_password_input.clear() # Clear field on error
            self.current_password_input.setFocus()
            return

        # 2. Validate New Main Password
        if not new_main_pw:
            QMessageBox.warning(self, "Password Change Failed", "New main password cannot be empty.")
            self.new_password_input.setFocus()
            return
        if new_main_pw != confirm_main_pw:
            QMessageBox.warning(self, "Password Change Failed", "New main passwords do not match.")
            self.confirm_new_password_input.clear()
            self.confirm_new_password_input.setFocus()
            return

        # 3. Validate New Secondary Password
        if not new_secondary_pw:
            QMessageBox.warning(self, "Password Change Failed", "New secondary password cannot be empty.")
            self.new_secondary_password_input.setFocus()
            return
        if new_secondary_pw != confirm_secondary_pw:
            QMessageBox.warning(self, "Password Change Failed", "New secondary passwords do not match.")
            self.confirm_new_secondary_password_input.clear()
            self.confirm_new_secondary_password_input.setFocus()
            return

        # 4. Validate Main vs Secondary
        if new_main_pw == new_secondary_pw:
            QMessageBox.warning(self, "Password Change Failed", "New main and secondary passwords must be different.")
            self.new_secondary_password_input.setFocus()
            return

        # 5. Hash New Passwords
        new_main_hash = LoginDialog.hash_password(new_main_pw)
        new_secondary_hash = LoginDialog.hash_password(new_secondary_pw)

        if not new_main_hash or not new_secondary_hash:
             QMessageBox.critical(self, "Password Change Error", "Failed to hash new passwords. Cannot save.")
             return

        # 6. Save New Hashes to QSettings
        try:
            self.settings.setValue("security/password_hash", new_main_hash)
            self.settings.setValue("security/backup_hash", new_secondary_hash) # Still use backup_hash key internally
            self.settings.sync()

            QMessageBox.information(self, "Success", "Passwords changed successfully.")
            # Clear fields after success
            self.current_password_input.clear()
            self.new_password_input.clear()
            self.confirm_new_password_input.clear()
            self.new_secondary_password_input.clear()
            self.confirm_new_secondary_password_input.clear()

            # Note: The database encryption key is derived from the *main* password.
            # If the main password changes, the user will need to use the *new* main password
            # the next time they start the application to decrypt the database.
            # The DatabaseManager needs to be re-initialized with the new password if the app continues running.
            # This is complex. A simpler approach might be to require an app restart after password change.
            QMessageBox.information(self, "Restart Required", "Please restart the application for the new main password to take effect for database access.")


        except Exception as e:
             QMessageBox.critical(self, "Password Change Error", f"Failed to save new password settings: {e}")
             print(f"Error saving new password hashes: {traceback.format_exc()}")

    def _handle_export_items(self):
        """Handle the Export Item List button click."""
        if not self.main_window or not hasattr(self.main_window, 'db') or not self.main_window.db:
             QMessageBox.warning(self, "Error", "Database connection not available.")
             return

        # Suggest a filename
        default_filename = "item_list_export.txt"
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Item List As",
            default_filename,
            "Text Files (*.txt);;CSV Files (*.csv);;All Files (*)"
        )

        if not file_path:
            return # User cancelled

        # Create and run the exporter
        exporter = ItemExportManager(self.main_window.db)
        # Connect the finished signal to show feedback
        exporter.export_finished.connect(self._on_export_finished)
        # Disable button during export? Maybe not necessary for quick operation.
        exporter.export_to_file(file_path)

    def _on_export_finished(self, success, message):
        """Show feedback message after export attempt."""
        if success:
            QMessageBox.information(self, "Export Successful", message)
        else:
            QMessageBox.critical(self, "Export Failed", message)
            
    def _handle_manual_log_cleanup(self):
        """Handle manual log cleanup button click."""
        from logger import cleanup_old_logs
        import logging
        
        # Get logger for this operation
        logger = logging.getLogger(__name__)
        
        # Ask for confirmation
        days = self.cleanup_days_spin.value()
        reply = QMessageBox.question(
            self,
            "Confirm Log Cleanup",
            f"This will permanently delete log files older than {days} day(s).\n\nContinue?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            try:
                logger.info(f"Manual log cleanup initiated for files older than {days} days")
                
                # Show busy cursor during cleanup
                from PyQt5.QtGui import QCursor
                from PyQt5.QtCore import Qt
                self.setCursor(QCursor(Qt.WaitCursor))
                
                # Run the cleanup
                removed_count = cleanup_old_logs(max_age_days=days)
                
                # Restore cursor
                self.unsetCursor()
                
                # Show results
                logger.info(f"Manual log cleanup completed: removed {removed_count} files")
                QMessageBox.information(
                    self,
                    "Log Cleanup Complete",
                    f"Successfully removed {removed_count} old log file(s)."
                )
            except Exception as e:
                # Restore cursor in case of error
                self.unsetCursor()
                
                # Log and show error
                logger.error(f"Manual log cleanup failed: {str(e)}", exc_info=True)
                QMessageBox.critical(
                    self,
                    "Log Cleanup Failed",
                    f"An error occurred during log cleanup: {str(e)}"
                )


    def accept(self):
        """Apply settings and close the dialog."""
        # Apply non-password settings first
        self.apply_settings()
        # Password changes are handled separately by the button click
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
            # Add dummy methods needed by the dialog
            self.show_import_dialog = lambda: print("Dummy Show Import Dialog")
            self.delete_all_estimates = lambda: print("Dummy Delete All Estimates")
            self.delete_all_data = lambda: print("Dummy Delete All Data")
            # Dummy db object for export handler check
            self.db = True # Or a dummy object with needed methods if exporter uses them directly


    app = QApplication(sys.argv)
    dummy_main = DummyMainWindow()
    dialog = SettingsDialog(dummy_main)
    dialog.exec_()
    sys.exit(app.exec_())