import traceback
from PyQt5.QtCore import QObject, pyqtSignal

class ItemImportManager(QObject):
    """Handles the actual item import process."""

    progress_updated = pyqtSignal(int, int)  # current, total
    status_updated = pyqtSignal(str)  # message
    import_finished = pyqtSignal(int, int, str)  # success_count, total_count, error_message (None if success)

    def __init__(self, db_manager):
        super().__init__()
        self.db_manager = db_manager
        self.cancel_requested = False

    def cancel_import(self):
        """Flags the import process to stop."""
        print("Import cancellation requested.")
        self.cancel_requested = True

    def import_from_file(self, file_path, import_settings):
        """Import items from the specified file using the provided settings."""
        self.cancel_requested = False
        imported_count = 0
        processed_count = 0
        total_items = 0

        try:
            # Extract settings
            delimiter = import_settings['delimiter']
            code_column = import_settings['code_column']
            name_column = import_settings['name_column']
            type_column = import_settings['type_column']
            rate_column = import_settings['rate_column']
            purity_column = import_settings['purity_column']
            skip_header = import_settings['skip_header']
            use_filter = import_settings['use_filter']
            wage_adjustment_factor_str = import_settings.get('wage_adjustment_factor', '') # Get adjustment factor
            duplicate_mode = import_settings['duplicate_mode']

            # Parse the adjustment factor once
            adjustment_op = None
            adjustment_val = None
            if wage_adjustment_factor_str and (wage_adjustment_factor_str.startswith('*') or wage_adjustment_factor_str.startswith('/')):
                try:
                    adjustment_op = wage_adjustment_factor_str[0]
                    adjustment_val = float(wage_adjustment_factor_str[1:])
                    if adjustment_op == '/' and adjustment_val == 0:
                         raise ValueError("Cannot divide by zero.")
                    print(f"Applying wage adjustment: {adjustment_op} {adjustment_val}")
                except (ValueError, IndexError):
                    raise ValueError(f"Invalid wage adjustment factor format: '{wage_adjustment_factor_str}'. Use *value or /value.")

            # Read the file
            # Try common encodings if utf-8 fails
            lines = []
            encodings_to_try = ['utf-8', 'cp1252', 'latin-1']
            for enc in encodings_to_try:
                try:
                    with open(file_path, 'r', encoding=enc) as f:
                        lines = f.readlines()
                    print(f"Successfully read file with encoding: {enc}")
                    break # Stop trying encodings if one works
                except UnicodeDecodeError:
                    print(f"Failed to decode file with {enc}, trying next...")
                    continue
                except Exception as e_read: # Catch other file reading errors
                     raise IOError(f"Could not read file '{file_path}': {e_read}") from e_read
            else: # If loop completes without break
                 raise UnicodeDecodeError(f"Could not decode file '{file_path}' with any attempted encoding.")

            # Filter lines based on settings
            filtered_lines = []
            
            # Skip first line if option is checked
            start_idx = 1 if skip_header and len(lines) > 0 else 0
            
            # Process lines
            for line in lines[start_idx:]:
                line = line.strip()
                if not line:
                    continue
                    
                if use_filter:
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

            total_items = len(filtered_lines)
            if total_items == 0:
                 raise ValueError("No valid item lines found in the file.")

            self.progress_updated.emit(0, total_items)
            self.status_updated.emit(f"Found {total_items} potential items. Starting import...")

            # Process items
            for i, line in enumerate(filtered_lines):
                processed_count = i + 1
                if self.cancel_requested:
                    self.status_updated.emit("Import cancelled by user.")
                    break # Exit the loop

                # Parse the line using configured column indices
                parts = [part.strip() for part in line.split(delimiter)]
                
                # Check if we have enough parts for all columns
                max_column = max(code_column, name_column, type_column, rate_column, purity_column)
                if len(parts) <= max_column:
                    self.status_updated.emit(f"Skipping line {i+1}: Not enough columns (needs {max_column+1}, has {len(parts)})")
                    continue

                try:
                    # Extract data using column indices from settings
                    item_code = parts[code_column].upper() # Ensure code is uppercase
                    item_name = parts[name_column]
                    wage_type = parts[type_column].upper() # Ensure type is uppercase
                    wage_rate_str = parts[rate_column]
                    silver_purity_str = parts[purity_column]

                    if not item_code: # Skip lines with no item code
                         self.status_updated.emit(f"Skipping line {i+1}: Missing item code.")
                         continue

                    # Convert wage rate to float
                    wage_rate_float = float(wage_rate_str)

                    # Convert Q-type wages from per kg to per gram
                    if wage_type == "Q":
                        wage_rate_float /= 1000.0

                    # Convert purity to float
                    purity_float = float(silver_purity_str)

                    # Apply wage adjustment factor if provided
                    if adjustment_op and adjustment_val is not None:
                        if adjustment_op == '*':
                            wage_rate_float *= adjustment_val
                        elif adjustment_op == '/':
                            wage_rate_float /= adjustment_val # Already checked for zero division

                    # Check if item exists
                    existing_item = self.db_manager.get_item_by_code(item_code)

                    # Handle based on duplicate mode
                    should_import = True
                    action = "Adding"

                    if existing_item:
                        if duplicate_mode == 0:  # SKIP
                            should_import = False
                            action = "Skipping duplicate"
                        elif duplicate_mode == 1:  # UPDATE
                            should_import = True
                            action = "Updating existing"
                        else:  # Default to SKIP for any other mode
                             should_import = False
                             action = "Skipping duplicate (unknown mode)"

                    self.status_updated.emit(f"{action}: {item_code} - {item_name}")

                    # Add or update item
                    success = False
                    if should_import:
                        if existing_item and duplicate_mode == 1:  # UPDATE
                            success = self.db_manager.update_item(
                                code=item_code,
                                name=item_name,
                                purity=purity_float,
                                wage_type=wage_type,
                                wage_rate=wage_rate_float
                            )
                        elif not existing_item:
                            success = self.db_manager.add_item(
                                code=item_code,
                                name=item_name,
                                purity=purity_float,
                                wage_type=wage_type,
                                wage_rate=wage_rate_float
                            )
                        else:  # Should be a skip
                             success = True  # Count skips as success

                        if success:
                            imported_count += 1
                        else:
                             self.status_updated.emit(f"Failed to save item: {item_code}")

                except ValueError as ve:
                    # Skip items with non-numeric values in rate/purity
                    self.status_updated.emit(f"Skipping line {i+1} ({parts[code_column] if code_column < len(parts) else 'unknown'}): Invalid numeric data ({ve})")
                    continue
                except IndexError:
                     self.status_updated.emit(f"Skipping line {i+1}: Index error accessing columns.")
                     continue
                except Exception as e_item:
                     self.status_updated.emit(f"Error processing line {i+1}: {e_item}")
                     continue  # Skip to next item on error

                # Update progress
                self.progress_updated.emit(processed_count, total_items)

            # Finish
            if self.cancel_requested:
                 # If cancelled, report counts up to the point of cancellation
                 self.import_finished.emit(imported_count, processed_count, "Import Cancelled")
            else:
                 self.import_finished.emit(imported_count, total_items, None)  # None indicates success

        except Exception as e:
            print(f"Import failed: {traceback.format_exc()}")
            self.status_updated.emit(f"Error: {str(e)}")
            # Emit finished signal with error message
            self.import_finished.emit(imported_count, processed_count or 1, str(e))