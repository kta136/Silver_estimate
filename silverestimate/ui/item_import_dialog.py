from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import (
    QAbstractItemView,
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QRadioButton,
    QSpinBox,
    QTableView,
    QVBoxLayout,
)

from silverestimate.services.item_import_parser import should_include_line
from silverestimate.ui.models import ItemImportPreviewRow, ItemImportPreviewTableModel
from silverestimate.ui.shared_screen_theme import build_management_screen_stylesheet


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
        self.setObjectName("ItemImportDialog")
        self.setStyleSheet(
            build_management_screen_stylesheet(
                root_selector="QDialog#ItemImportDialog",
                card_names=["ItemImportHeaderCard"],
                title_label="ItemImportTitleLabel",
                subtitle_label="ItemImportSubtitleLabel",
                field_label="ItemImportFieldLabel",
                primary_button="ItemImportPrimaryButton",
                secondary_button="ItemImportSecondaryButton",
                input_selectors=["QLineEdit", "QComboBox", "QSpinBox"],
                include_table=True,
                extra_rules="""
                QGroupBox {
                    background-color: #ffffff;
                    border: 1px solid #d8e1ec;
                    border-radius: 12px;
                    color: #0f172a;
                    font-weight: 700;
                    margin-top: 12px;
                    padding: 12px;
                }
                QGroupBox::title {
                    subcontrol-origin: margin;
                    left: 10px;
                    padding: 0 4px;
                }
                QProgressBar {
                    background-color: #e2e8f0;
                    border: 1px solid #cbd5e1;
                    border-radius: 8px;
                    color: #0f172a;
                    min-height: 18px;
                    text-align: center;
                }
                QProgressBar::chunk {
                    background-color: #0f766e;
                    border-radius: 7px;
                }
                QLabel#ItemImportStatusLabel {
                    color: #475569;
                    font-size: 9pt;
                }
                """,
            )
        )
        self._last_import_summary = None
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        header_card = QGroupBox(self)
        header_card.setObjectName("ItemImportHeaderCard")
        header_layout = QVBoxLayout(header_card)
        header_layout.setContentsMargins(12, 12, 12, 12)
        header_layout.setSpacing(2)
        title = QLabel("Import Item List")
        title.setObjectName("ItemImportTitleLabel")
        header_layout.addWidget(title)
        subtitle = QLabel(
            "Preview a source file, tune parsing rules, and import item master rows safely."
        )
        subtitle.setObjectName("ItemImportSubtitleLabel")
        subtitle.setWordWrap(True)
        header_layout.addWidget(subtitle)
        layout.addWidget(header_card)

        # File selection
        file_layout = QHBoxLayout()
        file_field_label = QLabel("File")
        file_field_label.setObjectName("ItemImportFieldLabel")
        file_layout.addWidget(file_field_label)
        self.file_label = QLabel("No file selected")
        file_layout.addWidget(self.file_label, 1)  # Add stretch

        self.browse_button = QPushButton("Browse...")
        self.browse_button.setObjectName("ItemImportSecondaryButton")
        self.browse_button.clicked.connect(self.browse_file)
        file_layout.addWidget(self.browse_button)
        layout.addLayout(file_layout)

        # ---- Add parser configuration options ----
        config_group = QGroupBox("Parser Configuration")
        config_layout = QVBoxLayout(config_group)

        # Delimiter selection
        delimiter_layout = QHBoxLayout()
        delimiter_label = QLabel("Delimiter")
        delimiter_label.setObjectName("ItemImportFieldLabel")
        delimiter_layout.addWidget(delimiter_label)

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
        self.custom_delimiter.textChanged.connect(
            lambda: self.preview_file_data(self.file_label.text())
        )
        delimiter_layout.addWidget(self.custom_delimiter)

        delimiter_layout.addStretch()
        config_layout.addLayout(delimiter_layout)

        # Column mapping
        column_layout = QHBoxLayout()
        columns_label = QLabel("Column Indices (starting from 0)")
        columns_label.setObjectName("ItemImportFieldLabel")
        column_layout.addWidget(columns_label)
        config_layout.addLayout(column_layout)

        # Create a grid for column mappings
        columns_grid = QGridLayout()
        code_label = QLabel("Code")
        code_label.setObjectName("ItemImportFieldLabel")
        columns_grid.addWidget(code_label, 0, 0)
        self.code_column = QSpinBox()
        self.code_column.setValue(0)  # Default to 0
        self.code_column.valueChanged.connect(
            lambda: self.preview_file_data(self.file_label.text())
        )
        columns_grid.addWidget(self.code_column, 0, 1)

        name_label = QLabel("Name")
        name_label.setObjectName("ItemImportFieldLabel")
        columns_grid.addWidget(name_label, 0, 2)
        self.name_column = QSpinBox()
        self.name_column.setValue(1)  # Default to 1
        self.name_column.valueChanged.connect(
            lambda: self.preview_file_data(self.file_label.text())
        )
        columns_grid.addWidget(self.name_column, 0, 3)

        wage_type_label = QLabel("Wage Type")
        wage_type_label.setObjectName("ItemImportFieldLabel")
        columns_grid.addWidget(wage_type_label, 1, 0)
        self.wage_type_column = QSpinBox()
        self.wage_type_column.setValue(3)  # Default to 3 (assuming common order)
        self.wage_type_column.valueChanged.connect(
            lambda: self.preview_file_data(self.file_label.text())
        )
        columns_grid.addWidget(self.wage_type_column, 1, 1)

        wage_rate_label = QLabel("Wage Rate")
        wage_rate_label.setObjectName("ItemImportFieldLabel")
        columns_grid.addWidget(wage_rate_label, 1, 2)
        self.wage_rate_column = QSpinBox()
        self.wage_rate_column.setValue(4)  # Default to 4 (assuming common order)
        self.wage_rate_column.valueChanged.connect(
            lambda: self.preview_file_data(self.file_label.text())
        )
        columns_grid.addWidget(self.wage_rate_column, 1, 3)

        purity_label = QLabel("Purity %")
        purity_label.setObjectName("ItemImportFieldLabel")
        columns_grid.addWidget(purity_label, 2, 0)
        self.purity_column = QSpinBox()
        self.purity_column.setValue(2)  # Default to 2 (assuming common order)
        self.purity_column.valueChanged.connect(
            lambda: self.preview_file_data(self.file_label.text())
        )
        columns_grid.addWidget(self.purity_column, 2, 1)

        config_layout.addLayout(columns_grid)

        # Wage Rate Adjustment
        adjustment_layout = QHBoxLayout()
        adjustment_label = QLabel("Wage Rate Adjustment")
        adjustment_label.setObjectName("ItemImportFieldLabel")
        adjustment_layout.addWidget(adjustment_label)
        self.wage_adjustment_input = QLineEdit()
        self.wage_adjustment_input.setPlaceholderText("e.g., *1.1 or /1000 (optional)")
        self.wage_adjustment_input.setToolTip(
            "Apply a calculation to the parsed wage rate.\nExample: '*1.1' to increase by 10%, '/1000' to convert kg to g.\nLeave blank for no adjustment."
        )
        self.wage_adjustment_input.textChanged.connect(
            lambda: self.preview_file_data(self.file_label.text())
        )
        adjustment_layout.addWidget(self.wage_adjustment_input)
        config_layout.addLayout(adjustment_layout)

        # Additional options
        options_layout = QHBoxLayout()

        self.skip_header_check = QCheckBox("Skip first line")
        self.skip_header_check.setChecked(False)
        self.skip_header_check.stateChanged.connect(
            lambda: self.preview_file_data(self.file_label.text())
        )
        options_layout.addWidget(self.skip_header_check)

        self.use_filter_check = QCheckBox(
            "Filter lines (requires numeric index + period)"
        )
        self.use_filter_check.setChecked(False)  # Default to unchecked
        self.use_filter_check.stateChanged.connect(
            lambda: self.preview_file_data(self.file_label.text())
        )
        options_layout.addWidget(self.use_filter_check)

        config_layout.addLayout(options_layout)

        # Add the config group to main layout
        layout.addWidget(config_group)

        # Add preview table
        preview_layout = QVBoxLayout()
        preview_header = QHBoxLayout()
        preview_title = QLabel("File Data Preview")
        preview_title.setObjectName("ItemImportFieldLabel")
        preview_header.addWidget(preview_title)

        self.refresh_preview = QPushButton("Refresh Preview")
        self.refresh_preview.setObjectName("ItemImportSecondaryButton")
        self.refresh_preview.clicked.connect(
            lambda: self.preview_file_data(self.file_label.text())
        )
        self.refresh_preview.setEnabled(False)
        preview_header.addWidget(self.refresh_preview)

        preview_layout.addLayout(preview_header)

        self.preview_table = QTableView(self)
        self.preview_model = ItemImportPreviewTableModel(self.preview_table)
        self.preview_table.setModel(self.preview_model)
        self.preview_table.setMinimumHeight(200)
        self.preview_table.setAlternatingRowColors(True)
        self.preview_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.preview_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.preview_table.setSelectionMode(QAbstractItemView.SingleSelection)
        for i in range(4):  # Set column widths
            self.preview_table.setColumnWidth(i, 100)
        self.preview_table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.Stretch
        )
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
        self.status_label.setObjectName("ItemImportStatusLabel")
        layout.addWidget(self.status_label)

        # Buttons section
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        self.import_button = QPushButton("Import")
        self.import_button.setObjectName("ItemImportPrimaryButton")
        self.import_button.clicked.connect(self.start_import)
        self.import_button.setEnabled(False)

        self.close_button = QPushButton("Close")
        self.close_button.setObjectName("ItemImportSecondaryButton")
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
            self,
            "Select Item List File",
            "",
            "Text Files (*.txt);;CSV Files (*.csv);;All Files (*)",
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
            encodings_to_try = ["utf-8", "cp1252", "latin-1"]
            lines = []

            for enc in encodings_to_try:
                try:
                    with open(file_path, "r", encoding=enc) as f:
                        lines = f.readlines()
                    self.status_label.setText(
                        f"File read successfully with encoding: {enc}"
                    )
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
            start_idx = (
                1 if self.skip_header_check.isChecked() and len(lines) > 0 else 0
            )

            # Process lines
            for line in lines[start_idx:]:
                line = line.strip()
                if not line:
                    continue

                if should_include_line(
                    line,
                    delimiter=delimiter,
                    use_filter=self.use_filter_check.isChecked(),
                ):
                    filtered_lines.append(line)

            # Update the preview table
            rows = self._build_preview_rows(filtered_lines, delimiter)
            self.preview_model.set_rows(rows)
            self.preview_table.setVisible(True)

            # Update status
            total_items = len(filtered_lines)
            self.status_label.setText(
                f"File preview: Found {total_items} valid items using delimiter '{delimiter}'"
            )

        except Exception as e:
            self.status_label.setText(f"Error previewing file: {str(e)}")
            self.preview_table.setVisible(False)

    def _build_preview_rows(self, filtered_lines, delimiter):
        rows = []
        code_idx = self.code_column.value()
        name_idx = self.name_column.value()
        type_idx = self.wage_type_column.value()
        rate_idx = self.wage_rate_column.value()
        purity_idx = self.purity_column.value()
        max_columns = max(code_idx, name_idx, type_idx, rate_idx, purity_idx) + 1

        for row_index, line in enumerate(filtered_lines[:10]):
            parts = [part.strip() for part in line.split(delimiter)]
            if len(parts) < max_columns:
                rows.append(self._error_preview_row("PARSING ERROR"))
                continue

            try:
                code = parts[code_idx] if code_idx < len(parts) else "ERROR"
                name = parts[name_idx] if name_idx < len(parts) else "ERROR"
                wage_type = parts[type_idx] if type_idx < len(parts) else "ERROR"
                wage_rate = parts[rate_idx] if rate_idx < len(parts) else "ERROR"
                purity = parts[purity_idx] if purity_idx < len(parts) else "ERROR"
                rows.append(
                    ItemImportPreviewRow(
                        code=code,
                        name=name,
                        wage_type=wage_type,
                        wage_rate=self._format_preview_rate(wage_type, wage_rate),
                        purity=purity,
                    )
                )
            except Exception as e:
                self.status_label.setText(
                    f"Error parsing line {row_index + 1}: {str(e)}"
                )
                rows.append(self._error_preview_row("ERROR"))
        return rows

    def _format_preview_rate(self, wage_type, wage_rate):
        rate_display = wage_rate
        if wage_type != "Q":
            return rate_display

        try:
            rate_float = float(wage_rate) / 1000.0
        except ValueError:
            return wage_rate + " (Invalid Rate)"

        rate_display = f"{rate_float:.3f}"
        factor_str = self.wage_adjustment_input.text().strip()
        if not factor_str or not (
            factor_str.startswith("*") or factor_str.startswith("/")
        ):
            return rate_display

        try:
            op = factor_str[0]
            val = float(factor_str[1:])
            adjusted_rate = rate_float
            if op == "*":
                adjusted_rate *= val
            elif op == "/" and val != 0:
                adjusted_rate /= val
            elif op == "/" and val == 0:
                adjusted_rate = float("inf")
            return f"{rate_display} → {adjusted_rate:.3f} ({factor_str})"
        except (ValueError, IndexError):
            return rate_display + " (Invalid Adj.)"

    @staticmethod
    def _error_preview_row(text):
        return ItemImportPreviewRow(
            code=text,
            name=text,
            wage_type=text,
            wage_rate=text,
            purity=text,
        )

    def start_import(self):
        """Start the import process with the current settings."""
        file_path = self.file_label.text()
        if file_path == "No file selected":
            QMessageBox.warning(self, "No File", "Please select a file to import.")
            return
        self._last_import_summary = None

        # Collect all parsing settings
        import_settings = {
            "delimiter": self.get_current_delimiter(),
            "code_column": self.code_column.value(),
            "name_column": self.name_column.value(),
            "type_column": self.wage_type_column.value(),
            "rate_column": self.wage_rate_column.value(),
            "purity_column": self.purity_column.value(),
            "skip_header": self.skip_header_check.isChecked(),
            "use_filter": self.use_filter_check.isChecked(),
            "wage_adjustment_factor": self.wage_adjustment_input.text().strip(),  # Add adjustment factor
            "duplicate_mode": self.duplicate_group.checkedId(),
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

    def set_import_summary(self, summary):
        """Store latest summary emitted by the import manager."""
        if isinstance(summary, dict):
            self._last_import_summary = dict(summary)

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
            QMessageBox.critical(
                self,
                "Import Error",
                f"An error occurred during import:\n{error_message}",
            )
        else:
            summary = self._last_import_summary or {}
            inserted = int(summary.get("inserted", 0))
            updated = int(summary.get("updated", 0))
            skipped = int(summary.get("skipped", 0))
            errors = int(summary.get("errors", 0))
            self.update_status(
                f"Import complete: {success_count} of {total_count} rows processed "
                f"(inserted={inserted}, updated={updated}, skipped={skipped}, errors={errors})."
            )
            QMessageBox.information(
                self,
                "Import Complete",
                "Import completed.\n\n"
                f"Processed rows: {success_count} / {total_count}\n"
                f"Inserted: {inserted}\n"
                f"Updated: {updated}\n"
                f"Skipped: {skipped}\n"
                f"Errors: {errors}",
            )
