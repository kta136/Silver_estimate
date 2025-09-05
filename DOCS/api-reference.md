# API Reference - Silver Estimation App

## Core Classes

### DatabaseManager (database_manager.py)

#### Constructor
```python
DatabaseManager(db_path: str, password: str)
```
- `db_path`: Path to encrypted database file
- `password`: User password for key derivation

#### Key Methods

##### Encryption/Decryption
```python
_encrypt_db() -> bool
    """Encrypts temporary DB to permanent file."""
    
_decrypt_db() -> str
    """Decrypts DB to temporary file. Returns status."""
    
_derive_key(password: str, salt: bytes) -> bytes
    """Derives encryption key using PBKDF2."""
```

##### Schema Management
```python
setup_database() -> None
    """Creates/updates database schema."""
    
_check_schema_version() -> int
    """Returns current schema version."""
    
_update_schema_version(new_version: int) -> bool
    """Updates schema version in database."""
```

##### Item Operations
```python
add_item(code: str, name: str, purity: float, 
         wage_type: str, wage_rate: float) -> bool
    """Adds new item to catalog."""
    
update_item(code: str, name: str, purity: float,
           wage_type: str, wage_rate: float) -> bool
    """Updates existing item."""
    
get_item_by_code(code: str) -> sqlite3.Row
    """Retrieves item by code."""
    
search_items(search_term: str) -> List[sqlite3.Row]
    """Searches items by code or name."""
```

##### Estimate Operations
```python
save_estimate_with_returns(voucher_no: str, date: str, 
                          silver_rate: float, regular_items: List[dict],
                          return_items: List[dict], totals: dict) -> bool
    """Saves complete estimate with all item types."""
    
get_estimate_by_voucher(voucher_no: str) -> dict
    """Retrieves estimate with header and items."""
    
delete_single_estimate(voucher_no: str) -> bool
    """Deletes estimate and associated data."""
```

##### Silver Bar Operations
```python
add_silver_bar(estimate_voucher_no: str, weight: float, 
               purity: float) -> int
    """Creates new silver bar record."""
    
assign_bar_to_list(bar_id: int, list_id: int, 
                   note: str = None) -> bool
    """Assigns bar to list."""
    
create_silver_bar_list(note: str = None) -> int
    """Creates new silver bar list."""
```

### EstimateEntryWidget (estimate_entry.py)

#### Constructor
```python
EstimateEntryWidget(db_manager: DatabaseManager, 
                    main_window: QMainWindow)
```

#### Key Methods

##### UI Setup
```python
connect_signals() -> None
    """Connects UI signals to handlers."""
    
add_empty_row() -> None
    """Adds new row to item table."""
```

##### Calculation Logic
```python
calculate_net_weight() -> None
    """Calculates net weight for current row."""
    
calculate_fine() -> None
    """Calculates fine weight based on purity."""
    
calculate_wage() -> None
    """Calculates wage based on type and rate."""
    
calculate_totals() -> None
    """Updates all summary totals."""
```

##### Data Operations
```python
save_estimate() -> None
    """Saves current estimate to database."""
    
load_estimate() -> None
    """Loads estimate by voucher number."""
    
clear_form(confirm: bool = True) -> None
    """Resets form for new estimate."""
```

##### Navigation
```python
move_to_next_cell() -> None
    """Navigates to next editable cell."""
    
move_to_previous_cell() -> None
    """Navigates to previous editable cell."""
```

### PrintManager (print_manager.py)

#### Constructor
```python
PrintManager(db_manager: DatabaseManager, 
             print_font: QFont = None)
```

#### Key Methods

```python
print_estimate(voucher_no: str, parent_widget: QWidget = None) -> bool
    """Generates print preview for estimate."""
    
print_silver_bars(status_filter: str = None, 
                 parent_widget: QWidget = None) -> bool
    """Prints silver bar inventory."""
    
print_silver_bar_list_details(list_info: dict, 
                             bars_in_list: List[dict],
                             parent_widget: QWidget = None) -> bool
    """Prints specific silver bar list."""
```

### ItemMasterWidget (item_master.py)

#### Constructor
```python
ItemMasterWidget(db_manager: DatabaseManager, 
                 main_window: QMainWindow = None)
```

#### Key Methods

```python
load_items(search_term: str = None) -> None
    """Loads items into table."""
    
add_item() -> None
    """Adds new item from form data."""
    
update_item() -> None
    """Updates selected item."""
    
delete_item() -> None
    """Deletes selected item."""
```

### SilverBarDialog (silver_bar_management.py)

#### Constructor
```python
SilverBarDialog(db_manager: DatabaseManager, 
                parent: QWidget = None)
```

#### Key Methods

```python
load_available_bars() -> None
    """Loads unassigned silver bars."""
    
load_lists() -> None
    """Populates list selection."""
    
create_new_list() -> None
    """Creates new silver bar list."""
    
add_selected_to_list() -> None
    """Assigns bars to current list."""
```

### LoginDialog (login_dialog.py)

#### Constructor
```python
LoginDialog(is_setup: bool = False, parent: QWidget = None)
```

#### Key Methods

```python
get_password() -> str
    """Returns entered main password."""
    
get_backup_password() -> str
    """Returns secondary password (setup only)."""
    
@staticmethod
hash_password(password: str) -> str
    """Hashes password using Argon2."""
    
@staticmethod
verify_password(stored_hash: str, provided_password: str) -> bool
    """Verifies password against hash."""
```

### NumericDelegate (estimate_entry_ui.py)

#### Key Methods

```python
createEditor(parent, option, index) -> QWidget
    """Creates editor with appropriate validator."""
    
setEditorData(editor, index) -> None
    """Populates editor with model data."""
    
setModelData(editor, model, index) -> None
    """Updates model from editor data."""
```

## Signal Reference

### EstimateEntryWidget Signals
- `voucher_edit.editingFinished`: Triggers estimate load
- `item_table.cellChanged`: Triggers calculations
- `silver_rate_spin.valueChanged`: Updates totals

### Dialog Signals
- `LoginDialog.accepted`: Login successful
- `ItemSelectionDialog.accepted`: Item selected
- `SettingsDialog.settings_applied`: Settings changed

### Custom Signals
```python
# ItemImportManager
progress_updated = pyqtSignal(int, int)  # current, total
status_updated = pyqtSignal(str)  # message
import_finished = pyqtSignal(int, int, str)  # success, total, error

# CustomFontDialog
fontSelected = pyqtSignal(QFont)  # Selected font
```

## Constants

### Column Indices
```python
COL_CODE = 0
COL_ITEM_NAME = 1
COL_GROSS = 2
COL_POLY = 3
COL_NET_WT = 4
COL_PURITY = 5
COL_WAGE_RATE = 6
COL_PIECES = 7
COL_WAGE_AMT = 8
COL_FINE_WT = 9
COL_TYPE = 10
```

### Security Constants
```python
SALT_KEY = "security/db_salt"
KDF_ITERATIONS = 100000
```

### UI Settings
```python
DEFAULT_TABLE_FONT_SIZE = 9
DEFAULT_MARGINS = "10,5,10,5"
DEFAULT_PREVIEW_ZOOM = 1.25
```

## Utility Functions

### Formatting
```python
format_indian_rupees(number: float) -> str
    """Formats number in Indian numbering system."""
    # Example: 1234567 → "12,34,567"
    
_get_cell_float(row: int, col: int, default: float = 0.0) -> float
    """Safely extracts float from table cell."""
    
_get_cell_int(row: int, col: int, default: int = 1) -> int
    """Safely extracts integer from table cell."""
    
_parse_float(text: str, default: float = 0.0) -> float
    """Converts locale-aware string to float."""
```

### Navigation
```python
focus_on_code_column(row: int) -> None
    """Sets focus to code column of specified row."""
    
_safe_edit_item(row: int, col: int) -> None
    """Safely starts editing cell at row/col."""
    
_ensure_cell_exists(row: int, col: int, editable: bool = True) -> QTableWidgetItem
    """Ensures cell exists and returns item."""
```

### UI Helpers
```python
_update_row_type_visuals(row: int) -> None
    """Updates visual style for item type."""
    
_get_font_display_text(font: QFont) -> str
    """Generates display text for font settings."""
    
show_status(message: str, timeout: int = 3000) -> None
    """Displays status message in status bar."""
```

## Exception Handling

### Custom Exceptions
```python
class DatabaseError(Exception):
    """Raised for database operation failures."""
    
class EncryptionError(Exception):
    """Raised for encryption/decryption failures."""
    
class ValidationError(Exception):
    """Raised for input validation failures."""
```

### Error Patterns
```python
# Database operations
try:
    self.conn.execute('BEGIN TRANSACTION')
    # Multiple operations
    self.conn.commit()
except sqlite3.Error as e:
    self.conn.rollback()
    raise DatabaseError(f"Operation failed: {e}")

# UI operations
try:
    self.table.blockSignals(True)
    # Batch updates
finally:
    self.table.blockSignals(False)
```

## Configuration

### QSettings Keys
```python
# Font settings
"font/family"          # Print font family
"font/size_float"      # Print font size (float)
"font/bold"           # Print font bold flag

# UI settings
"ui/table_font_size"   # Estimate table font size

# Print settings
"print/margins"        # Page margins (L,T,R,B)
"print/preview_zoom"   # Default preview zoom

# Security settings
"security/password_hash"  # Main password hash
"security/backup_hash"    # Secondary password hash
"security/db_salt"        # Database encryption salt
```

### Default Values
```python
DEFAULT_FONT = QFont("Courier New", 7)
DEFAULT_MARGINS = "10,5,10,5"
DEFAULT_ZOOM = 1.25
DEFAULT_TABLE_SIZE = 9
DEFAULT_PURITY = 0.0
DEFAULT_WAGE_TYPE = "WT"
```

## Database Schema

### SQL Definitions
```sql
-- Items table
CREATE TABLE items (
    code TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    purity REAL DEFAULT 0,
    wage_type TEXT DEFAULT 'P',
    wage_rate REAL DEFAULT 0
);

-- Estimates table
CREATE TABLE estimates (
    voucher_no TEXT PRIMARY KEY,
    date TEXT NOT NULL,
    silver_rate REAL DEFAULT 0,
    total_gross REAL DEFAULT 0,
    total_net REAL DEFAULT 0,
    total_fine REAL DEFAULT 0,
    total_wage REAL DEFAULT 0,
    note TEXT,
    last_balance_silver REAL DEFAULT 0,
    last_balance_amount REAL DEFAULT 0
);

-- Estimate items table
CREATE TABLE estimate_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    voucher_no TEXT,
    item_code TEXT,
    item_name TEXT,
    gross REAL DEFAULT 0,
    poly REAL DEFAULT 0,
    net_wt REAL DEFAULT 0,
    purity REAL DEFAULT 0,
    wage_rate REAL DEFAULT 0,
    pieces INTEGER DEFAULT 1,
    wage REAL DEFAULT 0,
    fine REAL DEFAULT 0,
    is_return INTEGER DEFAULT 0,
    is_silver_bar INTEGER DEFAULT 0,
    FOREIGN KEY (voucher_no) REFERENCES estimates (voucher_no) ON DELETE CASCADE,
    FOREIGN KEY (item_code) REFERENCES items (code) ON DELETE SET NULL
);
```

## Event Handling

### Keyboard Events
```python
def keyPressEvent(event: QKeyEvent) -> None:
    """Handles keyboard navigation."""
    
    Key Mappings:
    - Enter/Tab: Move to next cell
    - Shift+Tab: Move to previous cell
    - Escape: Confirm exit
    - Ctrl+D: Delete row
    - Ctrl+R: Toggle return mode
    - Ctrl+B: Toggle silver bar mode
    - Ctrl+S: Save estimate
    - Ctrl+P: Print preview
    - Ctrl+H: Show history
    - Ctrl+N: New estimate
```

### Cell Events
```python
def handle_cell_changed(row: int, column: int) -> None:
    """Processes cell value changes."""
    
    Column Handlers:
    - COL_CODE: Item lookup
    - COL_GROSS/COL_POLY: Net weight calculation
    - COL_PURITY: Fine weight calculation
    - COL_WAGE_RATE/COL_PIECES: Wage calculation
```

## Import/Export

### ItemImportManager Methods
```python
import_from_file(file_path: str, import_settings: dict) -> None
    """Imports items from file with settings."""
    
    Settings structure:
    {
        'delimiter': str,
        'code_column': int,
        'name_column': int,
        'type_column': int,
        'rate_column': int,
        'purity_column': int,
        'skip_header': bool,
        'use_filter': bool,
        'wage_adjustment_factor': str,
        'duplicate_mode': int
    }
```

### ItemExportManager Methods
```python
export_to_file(file_path: str) -> None
    """Exports all items to file."""
    
    Format: Pipe-delimited with header
    Columns: Code|Name|Purity|Wage Type|Wage Rate
```

## Thread Safety

### UI Updates
```python
# Use QTimer for thread-safe updates
QTimer.singleShot(0, lambda: self.update_ui())

# Block signals during batch updates
self.table.blockSignals(True)
try:
    # Perform updates
finally:
    self.table.blockSignals(False)
```

### Database Operations
```python
# Use transaction for thread safety
with self.db_lock:  # threading.Lock
    self.conn.execute('BEGIN TRANSACTION')
    try:
        # Multiple operations
        self.conn.commit()
    except:
        self.conn.rollback()
        raise
```

## Performance Tips

### Table Operations
- Block signals during batch updates
- Use viewport().update() for forced refresh
- Defer operations with QTimer.singleShot
- Batch row insertion/deletion

### Database Operations
- Use transactions for multi-row operations
- Implement proper indexing
- Regular VACUUM maintenance
- Batch insert/update operations

### Memory Management
- Clean up temporary files immediately
- Release large objects explicitly
- Use context managers
- Monitor long-running operations