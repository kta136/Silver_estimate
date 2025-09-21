# Estimate Loading Fix: Technical Details

This document provides technical details about the fix implemented to resolve the issue where the Silver Estimation App would crash on startup when items were present in the database.

## Issue Description

The application would crash on startup when items were present in the database. The crash occurred during the initialization sequence when the application tried to load an estimate with a newly generated voucher number.

## Root Cause Analysis

The root cause was identified as a signal-slot connection issue during initialization:

1. During the `EstimateEntryWidget.__init__` method, a new voucher number was generated using `generate_voucher()`
2. The `voucher_edit.editingFinished` signal was connected to the `load_estimate` method
3. Setting the voucher number triggered the `editingFinished` signal
4. This caused `load_estimate` to be called with a non-existent voucher number
5. When items were present in the database, the application would crash while trying to process the database results

## Code Changes

### 1. Modified `connect_signals` in `silverestimate/ui/estimate_entry_logic.py`

Added a parameter to skip connecting the load_estimate signal:

```python
def connect_signals(self, skip_load_estimate=False):
    """Connect UI signals to their handlers."""
    # Connect header signals - use safe_load_estimate if available
    if not skip_load_estimate:
        if hasattr(self, 'safe_load_estimate'):
            self.voucher_edit.editingFinished.connect(self.safe_load_estimate)
        else:
            # Fallback to direct connection if safe method not available
            self.voucher_edit.editingFinished.connect(self.load_estimate)
            
    # Other signal connections remain unchanged
    self.silver_rate_spin.valueChanged.connect(self.calculate_totals)
    
    # Connect Last Balance button
    if hasattr(self, 'last_balance_button'):
        self.last_balance_button.clicked.connect(self.show_last_balance_dialog)

    # Connect table signals
    self.item_table.cellClicked.connect(self.cell_clicked)
    self.item_table.itemSelectionChanged.connect(self.selection_changed)
    self.item_table.cellChanged.connect(self.handle_cell_changed)
```

### 2. Added `initializing` Flag in `silverestimate/ui/estimate_entry.py`

Added a flag to prevent loading estimates during initialization:

```python
def __init__(self, db_manager, main_window):
    super().__init__()
    # Explicitly call EstimateLogic.__init__() to initialize the logger
    EstimateLogic.__init__(self)

    # Set up database manager and main window reference
    self.db_manager = db_manager
    self.main_window = main_window
    
    # Flag to prevent loading estimates during initialization
    self.initializing = True

    # Rest of initialization code...
    
    # Set initializing flag to false after setup is complete
    self.initializing = False
```

### 3. Added `generate_voucher_silent` Method in `silverestimate/ui/estimate_entry.py`

Created a method to generate voucher numbers without triggering signals:

```python
def generate_voucher_silent(self):
    """Generate a new voucher number without triggering signals."""
    try:
        # Get a new voucher number from the database
        voucher_no = self.db_manager.generate_voucher_no()
        
        # Temporarily block signals from the voucher edit field
        self.voucher_edit.blockSignals(True)
        
        # Set the voucher number
        self.voucher_edit.setText(voucher_no)
        
        # Unblock signals
        self.voucher_edit.blockSignals(False)
        
        self.logger.info(f"Generated new voucher silently: {voucher_no}")
    except Exception as e:
        self.logger.error(f"Error generating voucher number silently: {str(e)}", exc_info=True)
        # Don't show error message during initialization
```

### 4. Modified `safe_load_estimate` in `silverestimate/ui/estimate_entry.py`

Updated to check the initializing flag:

```python
def safe_load_estimate(self):
    """Safely load an estimate, catching any exceptions to prevent crashes."""
    # Skip loading during initialization to prevent startup crashes
    if hasattr(self, 'initializing') and self.initializing:
        self.logger.debug("Skipping load_estimate during initialization")
        return
        
    try:
        # Temporarily disconnect the signal to prevent recursive calls
        try:
            self.voucher_edit.editingFinished.disconnect(self.safe_load_estimate)
        except TypeError:
            pass  # It wasn't connected, which is fine
            
        # Call the actual load_estimate method
        self.load_estimate()
        
    except Exception as e:
        # Log the error but don't crash the application
        self.logger.error(f"Error in safe_load_estimate: {str(e)}", exc_info=True)
        self._status(f"Error loading estimate: {str(e)}", 5000)
        
        # Show error message to user
        QMessageBox.critical(self, "Load Error",
                            f"An error occurred while loading the estimate: {str(e)}\n\n"
                            "Your changes have not been saved.")
    finally:
        # Reconnect the signal
        try:
            # Ensure it's not connected multiple times
            self.voucher_edit.editingFinished.disconnect(self.safe_load_estimate)
        except TypeError:
            pass  # It wasn't connected, which is fine
            
        self.voucher_edit.editingFinished.connect(self.safe_load_estimate)
```

### 5. Modified `load_estimate` in `silverestimate/ui/estimate_entry_logic.py`

Updated to check the initializing flag:

```python
def load_estimate(self):
    """Load an existing estimate by voucher number."""
    # Skip loading during initialization to prevent startup crashes
    if hasattr(self, 'initializing') and self.initializing:
        self.logger.debug("Skipping load_estimate during initialization")
        return
        
    # Check if database manager is available
    if not hasattr(self, 'db_manager') or self.db_manager is None:
        self.logger.error("Cannot load estimate: database manager is not available")
        QMessageBox.critical(self, "Error", "Database connection is not available. Please restart the application.")
        return
        
    # Get voucher number
    try:
        voucher_no = self.voucher_edit.text().strip()
    except Exception as e:
        self.logger.error(f"Error getting voucher number: {str(e)}", exc_info=True)
        QMessageBox.critical(self, "Error", f"Error accessing voucher field: {str(e)}")
        return
        
    if not voucher_no:
        return # No warning if field just cleared

    self.logger.info(f"Loading estimate {voucher_no}...")
    self._status(f"Loading estimate {voucher_no}...", 2000)
    
    # Get estimate data with error handling
    try:
        estimate_data = self.db_manager.get_estimate_by_voucher(voucher_no)
        if not estimate_data:
            self.logger.warning(f"Estimate voucher '{voucher_no}' not found")
            QMessageBox.warning(self, "Load Error", f"Estimate voucher '{voucher_no}' not found.")
            self._status(f"Estimate {voucher_no} not found.", 4000)
            return
            
        # Log the structure of the estimate data for debugging
        self.logger.debug(f"Estimate data structure: header keys: {list(estimate_data['header'].keys())}")
        self.logger.debug(f"Estimate items count: {len(estimate_data['items'])}")
    except Exception as e:
        self.logger.error(f"Error retrieving estimate {voucher_no}: {str(e)}", exc_info=True)
        QMessageBox.critical(self, "Database Error", f"Error retrieving estimate {voucher_no}: {str(e)}")
        self._status(f"Error retrieving estimate {voucher_no}", 4000)
        return
```

### 6. UI Changes in `silverestimate/ui/estimate_entry_ui.py`

Removed the "Generate" button and added a "Load" button:

```python
def _setup_header_form(self, widget):
    """Set up the header form for voucher details."""
    self.mode_indicator_label = QLabel("Mode: Regular Items")
    self.mode_indicator_label.setStyleSheet("font-weight: bold; color: green;")
    self.mode_indicator_label.setToolTip("Indicates whether Return Items or Silver Bar entry mode is active.")

    form_layout = QGridLayout()
    form_layout.addWidget(QLabel("Voucher No:"), 0, 0)
    self.voucher_edit = QLineEdit()
    self.voucher_edit.setMaximumWidth(150)
    self.voucher_edit.setToolTip("Enter an existing voucher number to load or leave blank for a new estimate.")
    form_layout.addWidget(self.voucher_edit, 0, 1)
    self.load_button = QPushButton("Load")
    self.load_button.setToolTip("Load the estimate with the entered voucher number.")
    form_layout.addWidget(self.load_button, 0, 2)
    
    # Rest of the form setup...
```

### 7. Initialization Changes in `silverestimate/ui/estimate_entry.py`

Modified the initialization sequence:

```python
# Generate a voucher number when the widget is first created
# Do this BEFORE connecting signals to avoid triggering load_estimate
self.generate_voucher_silent()

# Connect signals AFTER setting delegates and generating voucher
# But DO NOT connect the load_estimate signal at startup
self.connect_signals(skip_load_estimate=True)

# Connect the load button to the safe_load_estimate method
self.load_button.clicked.connect(self.safe_load_estimate)

# Generate a new voucher number automatically at startup
# This is now done silently without the generate button
self.generate_voucher_silent()

# Set initializing flag to false after setup is complete
self.initializing = False
```

## Testing

The fix was tested by:

1. Starting the application with an empty database
2. Adding items to the database
3. Restarting the application to verify it doesn't crash
4. Entering existing and non-existent voucher numbers
5. Using the "Load" button to load estimates

## Conclusion

The implemented fix addresses the root cause of the crash by:

1. Preventing automatic loading of estimates during initialization
2. Adding explicit user control over when estimates are loaded
3. Improving error handling to prevent crashes
4. Providing clear feedback to the user

These changes make the application more stable and user-friendly while maintaining all existing functionality.
