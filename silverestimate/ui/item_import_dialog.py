from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                            QPushButton, QFileDialog, QRadioButton,
                            QButtonGroup, QProgressBar, QMessageBox,
                            QTableWidget, QTableWidgetItem, QComboBox,
                            QSpinBox, QGroupBox, QCheckBox, QLineEdit,
                            QWidget, QGridLayout)
from PyQt5.QtCore import Qt, pyqtSignal

class ItemImportDialog(QDialog):
    """Dialog for importing items from text files."""

    importStarted = pyqtSignal(str, dict)  # filepath, import_settings

    # Duplicate handling modes
    SKIP = 0
    UPDATE = 1
    ASK = 2  # Note: ASK mode is not fully implemented

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Import Item List")
        self.setMinimumWidth(600)
        self.setMinimumHeight(600)
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # File selection
        file_layout = QHBoxLayout()
        file_layout.addWidget(QLabel("File:"))
        self.file_label = QLabel("No file selected")
        file_layout.addWidget(self.file_label, 1)  # Add stretch
        
        self.browse_button = QPushButton("Browse...")
        self.browse_button.clicked.connect(self.browse_file)
        file_layout.addWidget(self.browse_button)
        layout.addLayout(file_layout)
        
        # ---- Add parser configuration options ----
        config_group = QGroupBox("Parser Configuration")
        config_layout = QVBoxLayout(config_group)
        
        # Delimiter selection
        delimiter_layout = QHBoxLayout()
        delimiter_layout.addWidget(QLabel("Delimiter:"))
        
        self.delimiter_combo = QComboBox()
        self.delimiter_combo.addItems(["|", ",", ";", "Tab", "Space", "Custom"])
        self.delimiter_combo.setCurrentText("|")  # Default for TBOOK.TXT
        self.delimiter_combo.currentTextChanged.connect(self.delimiter_changed)
        delimiter_layout.addWidget(self.delimiter_combo)
        
        # Custom delimiter input (initially hidden)
        self.custom_delimiter = QLineEdit()
        self.custom_delimiter.setMaximumWidth(50)
        self.custom_delimiter.setPlaceholderText("e.g. :")
        self.custom_delimiter.setVisible(False)
        self.custom_delimiter.textChanged.connect(lambda: self.preview_file_data(self.file_label.text()))
        delimiter_layout.addWidget(self.custom_delimiter)
        
        delimiter_layout.addStretch()
        config_layout.addLayout(delimiter_layout)
        
        # Column mapping
        column_layout = QHBoxLayout()
        column_layout.addWidget(QLabel("Column Indices (starting from 0):"))
        config_layout.addLayout(column_layout)
        
        # Create a grid for column mappings
        columns_grid = QGridLayout()
        columns_grid.addWidget(QLabel("Code:"), 0, 0)
        self.code_column = QSpinBox()
        self.code_column.setValue(0)  # Default to 0
        self.code_column.valueChanged.connect(lambda: self.preview_file_data(self.file_label.text()))
        columns_grid.addWidget(self.code_column, 0, 1)

        columns_grid.addWidget(QLabel("Name:"), 0, 2)
        self.name_column = QSpinBox()
        self.name_column.setValue(1)  # Default to 1
        self.name_column.valueChanged.connect(lambda: self.preview_file_data(self.file_label.text()))
        columns_grid.addWidget(self.name_column, 0, 3)

        columns_grid.addWidget(QLabel("Wage Type:"), 1, 0)
        self.wage_type_column = QSpinBox()
        self.wage_type_column.setValue(3)  # Default to 3 (assuming common order)
        self.wage_type_column.valueChanged.connect(lambda: self.preview_file_data(self.file_label.text()))
        columns_grid.addWidget(self.wage_type_column, 1, 1)

        columns_grid.addWidget(QLabel("Wage Rate:"), 1, 2)
        self.wage_rate_column = QSpinBox()
        self.wage_rate_column.setValue(4)  # Default to 4 (assuming common order)
        self.wage_rate_column.valueChanged.connect(lambda: self.preview_file_data(self.file_label.text()))
        columns_grid.addWidget(self.wage_rate_column, 1, 3)

        columns_grid.addWidget(QLabel("Purity %:"), 2, 0)
        self.purity_column = QSpinBox()
        self.purity_column.setValue(2)  # Default to 2 (assuming common order)
        self.purity_column.valueChanged.connect(lambda: self.preview_file_data(self.file_label.text()))
        columns_grid.addWidget(self.purity_column, 2, 1)
        
        config_layout.addLayout(columns_grid)

        # Wage Rate Adjustment
        adjustment_layout = QHBoxLayout()
        adjustment_layout.addWidget(QLabel("Wage Rate Adjustment:"))
        self.wage_adjustment_input = QLineEdit()
        self.wage_adjustment_input.setPlaceholderText("e.g., *1.1 or /1000 (optional)")
        self.wage_adjustment_input.setToolTip("Apply a calculation to the parsed wage rate.\nExample: '*1.1' to increase by 10%, '/1000' to convert kg to g.\nLeave blank for no adjustment.")
        self.wage_adjustment_input.textChanged.connect(lambda: self.preview_file_data(self.file_label.text()))
        adjustment_layout.addWidget(self.wage_adjustment_input)
        config_layout.addLayout(adjustment_layout)


        # Additional options
        options_layout = QHBoxLayout()
        
        self.skip_header_check = QCheckBox("Skip first line")
        self.skip_header_check.setChecked(False)
        self.skip_header_check.stateChanged.connect(lambda: self.preview_file_data(self.file_label.text()))
        options_layout.addWidget(self.skip_header_check)
        
        self.use_filter_check = QCheckBox("Filter lines (requires numeric index + period)")
        self.use_filter_check.setChecked(False) # Default to unchecked
        self.use_filter_check.stateChanged.connect(lambda: self.preview_file_data(self.file_label.text()))
        options_layout.addWidget(self.use_filter_check)
        
        config_layout.addLayout(options_layout)
        
        # Add the config group to main layout
        layout.addWidget(config_group)
        
        # Add preview table
        preview_layout = QVBoxLayout()
        preview_header = QHBoxLayout()
        preview_header.addWidget(QLabel("File Data Preview:"))
        
        self.refresh_preview = QPushButton("Refresh Preview")
        self.refresh_preview.clicked.connect(lambda: self.preview_file_data(self.file_label.text()))
        self.refresh_preview.setEnabled(False)
        preview_header.addWidget(self.refresh_preview)
        
        preview_layout.addLayout(preview_header)
        
        self.preview_table = QTableWidget()
        self.preview_table.setColumnCount(5)
        self.preview_table.setHorizontalHeaderLabels(["Item Code", "Item Name", "Wage Type", "Wage Rate", "Purity %"])
        self.preview_table.setMinimumHeight(200)
        self.preview_table.setAlternatingRowColors(True)
        for i in range(4):  # Set column widths
            self.preview_table.setColumnWidth(i, 100)
        self.preview_table.horizontalHeader().setStretchLastSection(True)
        self.preview_table.setVisible(False)
        preview_layout.addWidget(self.preview_table)
        
        layout.addLayout(preview_layout)
        
        # Existing duplicate handling options (modified to be more compact)
        dupes_group = QGroupBox("Duplicate Handling")
        dupes_layout = QHBoxLayout(dupes_group)
        
        self.skip_radio = QRadioButton("Skip (keep existing)")
        self.update_radio = QRadioButton("Update (replace with imported)")
        
        self.duplicate_group = QButtonGroup(self)
        self.duplicate_group.addButton(self.skip_radio, self.SKIP)
        self.duplicate_group.addButton(self.update_radio, self.UPDATE)
        
        self.skip_radio.setChecked(True)
        
        dupes_layout.addWidget(self.skip_radio)
        dupes_layout.addWidget(self.update_radio)
        layout.addWidget(dupes_group)
        
        # Progress section
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)
        
        self.status_label = QLabel("")
        layout.addWidget(self.status_label)
        
        # Buttons section
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        self.import_button = QPushButton("Import")
        self.import_button.clicked.connect(self.start_import)
        self.import_button.setEnabled(False)
        
        self.close_button = QPushButton("Close")
        self.close_button.clicked.connect(self.reject)
        
        button_layout.addWidget(self.import_button)
        button_layout.addWidget(self.close_button)
        layout.addLayout(button_layout)

    def delimiter_changed(self, text):
        """Handle changes to the delimiter selection."""
        # If custom is selected, show the custom input field
        self.custom_delimiter.setVisible(text == "Custom")
        
        # Update preview if we have a file
        if self.file_label.text() != "No file selected":
            self.preview_file_data(self.file_label.text())

    def get_current_delimiter(self):
        """Get the currently selected delimiter."""
        delimiter = self.delimiter_combo.currentText()
        
        if delimiter == "Tab":
            return "\t"
        elif delimiter == "Space":
            return " "
        elif delimiter == "Custom":
            custom = self.custom_delimiter.text()
            return custom if custom else "|"  # Fallback to | if empty
        else:
            return delimiter

    def browse_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Item List File", "",
            "Text Files (*.txt);;CSV Files (*.csv);;All Files (*)"
        )
        
        if file_path:
            self.file_label.setText(file_path)
            self.import_button.setEnabled(True)
            self.refresh_preview.setEnabled(True)
            self.preview_file_data(file_path)

    def preview_file_data(self, file_path):
        """Parse and display a preview of the file data."""
        if file_path == "No file selected":
            return
        
        try:
            # Read the file
            encodings_to_try = ['utf-8', 'cp1252', 'latin-1']
            lines = []
            
            for enc in encodings_to_try:
                try:
                    with open(file_path, 'r', encoding=enc) as f:
                        lines = f.readlines()
                    self.status_label.setText(f"File read successfully with encoding: {enc}")
                    break
                except UnicodeDecodeError:
                    continue
                except Exception as e:
                    self.status_label.setText(f"Error reading file: {str(e)}")
                    return
                    
            if not lines:
                self.status_label.setText("Could not read file with any encoding.")
                return
            
            # Filter lines based on settings
            filtered_lines = []
            
            # Get current delimiter
            delimiter = self.get_current_delimiter()
            
            # Skip first line if option is checked
            start_idx = 1 if self.skip_header_check.isChecked() and len(lines) > 0 else 0
            
            # Process lines
            for line in lines[start_idx:]:
                line = line.strip()
                if not line:
                    continue
                    
                if self.use_filter_check.isChecked():
                    # Apply filtering for items (numeric index + period)
                    parts = line.split(delimiter, 1)
                    if len(parts) > 0:
                        first_part = parts[0].strip()
                        if first_part.endswith('.') and first_part[:-1].strip().isdigit():
                            filtered_lines.append(line)
                else:
                    # No filtering, just check if line contains the delimiter
                    if delimiter in line:
                        filtered_lines.append(line)
            
            # Update the preview table
            self.preview_table.setRowCount(min(10, len(filtered_lines)))  # Show up to 10 rows
            self.preview_table.setVisible(True)
            
            # Get column indices
            code_idx = self.code_column.value()
            name_idx = self.name_column.value()
            type_idx = self.wage_type_column.value()
            rate_idx = self.wage_rate_column.value()
            purity_idx = self.purity_column.value()
            
            max_columns = max(code_idx, name_idx, type_idx, rate_idx, purity_idx) + 1
            
            # Fill the table
            for row, line in enumerate(filtered_lines[:10]):  # Only first 10 lines
                parts = [part.strip() for part in line.split(delimiter)]
                
                # Skip if not enough parts
                if len(parts) < max_columns:
                    for col in range(5):
                        self.preview_table.setItem(row, col, QTableWidgetItem("PARSING ERROR"))
                    continue
                
                # Extract values
                try:
                    code = parts[code_idx] if code_idx < len(parts) else "ERROR"
                    name = parts[name_idx] if name_idx < len(parts) else "ERROR"
                    wage_type = parts[type_idx] if type_idx < len(parts) else "ERROR"
                    wage_rate = parts[rate_idx] if rate_idx < len(parts) else "ERROR"
                    purity = parts[purity_idx] if purity_idx < len(parts) else "ERROR"
                    
                    # Show conversion for Q-type wages
                    rate_display = wage_rate
                    if wage_type == "Q":
                        try:
                            rate_float = float(wage_rate)
                            # Apply Q-type conversion first for display
                            if wage_type == "Q":
                                rate_float /= 1000.0
                            rate_display = f"{rate_float:.3f}" # Show initially converted rate

                            # Apply adjustment factor for display preview
                            factor_str = self.wage_adjustment_input.text().strip()
                            if factor_str and (factor_str.startswith('*') or factor_str.startswith('/')):
                                try:
                                    op = factor_str[0]
                                    val = float(factor_str[1:])
                                    adjusted_rate = rate_float
                                    if op == '*':
                                        adjusted_rate *= val
                                    elif op == '/' and val != 0:
                                        adjusted_rate /= val
                                    elif op == '/' and val == 0:
                                         adjusted_rate = float('inf') # Indicate error

                                    rate_display += f" → {adjusted_rate:.3f} ({factor_str})" # Show adjusted rate
                                except (ValueError, IndexError):
                                    rate_display += " (Invalid Adj.)" # Indicate bad factor format
                        except ValueError:
                             rate_display = wage_rate + " (Invalid Rate)" # Indicate bad original rate
                    
                    # Set items
                    self.preview_table.setItem(row, 0, QTableWidgetItem(code))
                    self.preview_table.setItem(row, 1, QTableWidgetItem(name))
                    self.preview_table.setItem(row, 2, QTableWidgetItem(wage_type))
                    self.preview_table.setItem(row, 3, QTableWidgetItem(rate_display))
                    self.preview_table.setItem(row, 4, QTableWidgetItem(purity))
                    
                except Exception as e:
                    self.status_label.setText(f"Error parsing line {row+1}: {str(e)}")
                    for col in range(5):
                        self.preview_table.setItem(row, col, QTableWidgetItem("ERROR"))
            
            # Update status
            total_items = len(filtered_lines)
            self.status_label.setText(f"File preview: Found {total_items} valid items using delimiter '{delimiter}'")
            
        except Exception as e:
            self.status_label.setText(f"Error previewing file: {str(e)}")
            self.preview_table.setVisible(False)

    def start_import(self):
        """Start the import process with the current settings."""
        file_path = self.file_label.text()
        if file_path == "No file selected":
            QMessageBox.warning(self, "No File", "Please select a file to import.")
            return
        
        # Collect all parsing settings
        import_settings = {
            'delimiter': self.get_current_delimiter(),
            'code_column': self.code_column.value(),
            'name_column': self.name_column.value(),
            'type_column': self.wage_type_column.value(),
            'rate_column': self.wage_rate_column.value(),
            'purity_column': self.purity_column.value(),
            'skip_header': self.skip_header_check.isChecked(),
            'use_filter': self.use_filter_check.isChecked(),
            'wage_adjustment_factor': self.wage_adjustment_input.text().strip(), # Add adjustment factor
            'duplicate_mode': self.duplicate_group.checkedId()
        }

        # Show progress bar
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(True)
        self.status_label.setText("Starting import...")
        
        # Update UI state
        self.import_button.setEnabled(False)
        self.refresh_preview.setEnabled(False)
        self.browse_button.setEnabled(False)
        self.close_button.setText("Cancel")
        
        # Emit signal with file path and settings
        self.importStarted.emit(file_path, import_settings)

    def update_progress(self, value, maximum):
        """Update the progress bar."""
        self.progress_bar.setMaximum(maximum)
        self.progress_bar.setValue(value)

    def update_status(self, message):
        """Update the status message."""
        self.status_label.setText(message)

    def import_finished(self, success_count, total_count, error_message=None):
        """Called when the import process completes."""
        # Ensure progress bar is full
        if total_count > 0:
            self.progress_bar.setValue(total_count)
        
        # Reset UI state
        self.import_button.setEnabled(True)
        self.refresh_preview.setEnabled(True)
        self.browse_button.setEnabled(True)
        self.close_button.setText("Close")
        
        if error_message:
            self.update_status(f"Import failed: {error_message}")
            QMessageBox.critical(self, "Import Error", 
                               f"An error occurred during import:\n{error_message}")
        else:
            self.update_status(f"Import complete: {success_count} of {total_count} items processed.")
            QMessageBox.information(
                self,
                "Import Complete",
                f"Successfully processed {success_count} out of {total_count} items based on selected mode."
            )