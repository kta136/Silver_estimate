# 🧾 Silver Estimation App — v1.12

A desktop application built using **PyQt5** and **SQLite** for managing silver sales estimates, including item-wise entries, silver bar inventory, returns, and print-ready formatted outputs.

---

## 💡 Purpose

This app is designed for silver shops to:

- Generate itemized silver estimates.
- Track gross, net, and fine silver.
- Manage silver bar inventory and return entries.
- Print formatted estimate slips.
- View and print silver bar inventory reports.

---

## ✅ Features (v1.12)

### 🔢 Estimate Entry

- Fast, keyboard-driven input with intuitive navigation.
- Handles gross weight, poly weight, purity %, wage rate, pieces.
- Real-time calculation of Net Weight, Fine Silver, Labour Amount.
- Wage type can be per piece (`PC`) or per weight (`WT`).
- Modes for Return Items and Silver Bars.
- Auto-fill item details via item code (code is automatically converted to uppercase).
- Code not found? Opens filtered `ItemSelectionDialog`.
- Auto-add new rows upon completing entry in the last column.
- Summary sections for Regular, Return, Silver Bar, and Net totals (Silver Bars and Returns are subtracted from Regular to calculate Net totals, including a Grand Total = Net Value + Net Wage).
- Save workflow: Saving an estimate now automatically opens Print Preview and then clears the form for a new estimate.
- Load and print estimates.
- Status bar for real-time feedback.
- Keyboard shortcuts: Ctrl+S (Save), Ctrl+P (Print Preview), Ctrl+H (History), Ctrl+N (New Estimate), Ctrl+D (Delete Row), Ctrl+R (Toggle Return), Ctrl+B (Toggle Silver Bar).
- Backspace in an empty editable cell navigates to the previous cell.
- Improved readability with better spacing, separators, and right-aligned totals.
- Table background uses alternating light colors (off-white/light gray).

### 📦 Item Master

- Create, edit, delete items with:
  - Code
  - Name
  - Default Purity
  - Wage Type (`PC`/`WT`)
  - Wage Rate
- Live search and filtering.
- Duplicate code prevention and safe delete checks.
- Update action no longer requires confirmation.

### 🕓 Estimate History

- Browse past estimates by date or voucher number.
- View summary totals.
- Reload selected estimate for editing.
- Print directly from history.

### 🧱 Silver Bar Management (Basic v1.0)

- Add bars with Bar No, Weight, and Purity.
- Filter inventory by status: In Stock, Transferred, Sold, Melted.
- Transfer bars with notes.
- Print inventory list.
- *(Advanced grouping planned for v1.1)*

### 🖨️ Printing

- Print Preview opens maximized and zoomed to 125% by default.
- Estimate slip uses fixed-width formatting (no `|` separators, relies on spacing).
- Printed sections with individual totals for:
  - Regular Items
  - Silver Bars
  - Return Goods
  - Return Bars
- Final summary displays Net Fine, Silver Cost, Labour, Total (Net calculated as Regular - Bars - Returns).
- Silver Bar Inventory printing via HTML table format.

### 🔤 Font Settings

- Configure **Print Font** (family, size min 5pt, bold) via "Tools -> Print Font Settings...". Applies only to estimate slip print output. Persists via `QSettings`.
- Configure **Table Font Size** (7-16pt) via "Tools -> Table Font Size...". Applies to the estimate entry table UI. Persists via `QSettings`.

---

## 🛠️ Tech Stack

- **Language:** Python 3.x
- **GUI:** PyQt5
- **Database:** SQLite3

---

## 🔁 Project Structure
```
.
├── main.py # App entry point, MainWindow, Menu Bar
├── estimate_entry.py # Estimate screen main widget (combines UI/Logic)
├── estimate_entry_ui.py # Estimate screen UI layout class, NumericDelegate
├── estimate_entry_logic.py # Estimate screen calculation logic, event handlers
├── item_master.py # Item management screen UI and logic
├── estimate_history.py # Estimate history browser dialog UI and logic
├── silver_bar_management.py # Silver bar inventory dialog UI and logic (v1.0)
├── item_selection_dialog.py # Dialog to select items when code not found
├── print_manager.py # Handles print formatting and preview dialogs
├── database_manager.py # All SQLite database operations and schema setup
├── readme.md # This file
└── database/
    └── estimation.db # SQLite database file (auto-created)
```
---

## 🚀 Getting Started

### 🔧 Prerequisites

- Python 3.8+
- `pip` (Python package installer)

### ⚙️ Installation

```bash
# Clone or download the project
cd SilverEstimationApp/

# (Recommended) Create and activate a virtual environment
python -m venv .venv

# Windows:
.venv\Scripts\activate

# macOS/Linux:
source .venv/bin/activate

# Install dependencies
pip install PyQt5
```

### ▶️ Run the Application

```bash
python main.py
```

On the first run, a database folder and the estimation.db SQLite file will be created automatically if they don't exist. The necessary tables will also be created.

---

## 🧠 Developer Notes & Architecture Overview

### 🔄 Logic Flow Summary

- **Estimate Entry:**
  - Core logic in `estimate_entry_logic.py`
  - UI defined in `estimate_entry_ui.py`
  - Live calculations via `handle_cell_changed`
- **Item Lookup:**
  - Code triggers `process_item_code`
  - Uses `db_manager.get_item_by_code`
- **Saving Estimates:**
  - Saves line items, calculates categories (Return/Silver Bar)
  - Uses `db_manager.save_estimate_with_returns`
- **Silver Bars:**
  - Entries saved in `silver_bars` table
  - Linked by item code (future: decouple item code and bar tracking)
- **Printing:**
  - Uses `PrintManager`
  - Manual format with `<pre>` tags
  - Font size/bold via user settings

---

## 🐞 Key Fixes & Enhancements (April 2025)

### 1. ✅ **Net Weight Calculation Bug Fix**

## 📝 Development & Debugging Notes for AI

This file reflects the state after v1.1 feature additions/fixes.

### 🔧 Key Concepts & Logic Flow:

- **Estimate Entry:**  
  The core logic resides in `estimate_entry_logic.py` but is executed within the `EstimateEntryWidget` (from `estimate_entry.py`). The UI layout is defined in `EstimateEntryUI`.

- **Calculations:**  
  - `calculate_net_weight`, `calculate_fine`, `calculate_wage` are triggered by `handle_cell_changed`.  
  - `calculate_totals` aggregates row data based on the "Type" column.

- **Item Lookup:**  
  Entering a code in `COL_CODE` triggers `process_item_code`, which uses `db_manager.get_item_by_code`.  
  If the code is not found, it opens `ItemSelectionDialog`.

- **Saving Estimates:**  
  `save_estimate()` in `estimate_entry_logic.py`:
  - Collects and validates data
  - Calculates category-wise totals
  - Adds Silver Bars if present
  - Uses `db_manager.save_estimate_with_returns()`

- **Database:**  
  - Uses `sqlite3.Row` factory  
  - Foreign keys enabled  
  - Schema includes `is_return` and `is_silver_bar` flags in `estimate_items`

- **Silver Bars (v1.0):**  
  Managed independently in `SilverBarDialog`, but can also be entered via toggle mode in estimates.  
  Added to inventory via `db_manager.add_silver_bar`.

- **Printing:**  
  - `PrintManager` handles all formats  
  - Estimate slips: `<pre>` manual layout  
  - Inventory: standard HTML tables  
  - Preview via `QPrintPreviewDialog`

---

### 🐞 Recent Fixes & Features (April 2025)

#### 1. 🧮 Net Weight Not Updating

- **Symptom:**  
  Net Wt column not reflecting updated Gross/Poly inputs.

- **Issue:**  
  `QLocale.system().toDouble()` failed silently due to missing import.

- **Fix:**  
  - Added `from PyQt5.QtCore import QLocale`  
  - Improved `_get_cell_float()` with fallback and error handling.

#### 2. 🖨️ Font Settings for Print

- Added custom font dialog using `QFontComboBox`, `QDoubleSpinBox`, `QCheckBox`
- Saved settings via `QSettings`
- Font applied only to estimate print via `PrintManager`


- **Symptom:** Custom font settings (family, size, bold) selected via "Tools -> Font Settings..." were not applied when printing an estimate initiated from the "Estimate History" dialog (either via the main menu or the button on the estimate screen). Printing directly from the estimate screen worked correctly.
- **Debugging:**
    - Initial checks confirmed `PrintManager` was intended to use the stored font setting (`self.print_font`) from the `MainWindow` instance.
    - Attempts to modify CSS within `PrintManager._generate_estimate_manual_format` to force font application failed, suggesting the issue was earlier in the process.
    - Debug `print()` statements were added to `estimate_entry_logic.py` and `estimate_history.py` where `PrintManager` was instantiated.
    - Output revealed that when the history dialog was launched from the *estimate screen button* (`estimate_entry_logic.show_history`), the `main_window_ref` passed to `EstimateHistoryDialog` was incorrectly referencing the `EstimateEntryWidget` instance (`self`) instead of the actual `MainWindow` instance (`self.main_window`).
    - This caused an `AttributeError` in `EstimateHistoryDialog.print_estimate` when trying to access `self.main_window.print_font`, resulting in `print_font_setting` being `None` and `PrintManager` using its default font.
- **Fix:**
    - Modified `estimate_entry_logic.py` -> `show_history()` method.
    - Changed the instantiation of `EstimateHistoryDialog` from `EstimateHistoryDialog(self.db_manager, self)` to `EstimateHistoryDialog(self.db_manager, main_window_ref=self.main_window, parent=self)`.
    - This ensures the correct `MainWindow` instance (which holds the `print_font` attribute) is passed to the dialog, allowing the `PrintManager` to receive the correct font settings.
- **Learning:** When passing references between widgets/dialogs, especially for accessing shared state like settings stored in the main window, ensure the correct object instance is being passed. Using `self` isn't always correct if the method is called from a child widget that needs a reference to the top-level window.

#### 4. 📉 Silver Bar Calculation Correction

- **Symptom:** Silver bars entered in the estimate were being added to the regular item totals instead of being subtracted.
- **Fix:** Modified `calculate_totals` in `estimate_entry_logic.py` and the final summary calculation in `print_manager.py` to subtract `bar_fine` and `bar_wage` along with return values from the regular item totals when calculating `net_fine_calc` and `net_wage_calc`.

#### 5. 💅 Print Format Update

- **Change:** Removed all vertical pipe (`|`) separators from the estimate slip printout. Added individual total lines under each section (Regular, Bars, Returns).
- **Implementation:** Modified `format_line`, `format_totals_line`, `header_line`, and `final_line` construction in `print_manager._generate_estimate_manual_format` to use f-string padding and spacing instead of joining with `|`. Added calls to `format_totals_line` after each section loop. Removed the old combined total line.
- **Note:** Alignment now relies purely on fixed-width spacing and the chosen print font. Non-monospace fonts might cause minor misalignments.

#### 6. ⏪ Reverted Features (Previously Numbered 3)

- **Hotkeys (Ctrl+S/P/H)**  
- **UI spacing improvements**  
- **Conditional column behavior** (hide/show Wage/Pieces based on wage type)

---

### 🧪 Known Issues / TODO

- [x] ~~Fix font settings not applying in Estimate History print~~ (Fixed in v1.12: Corrected `main_window_ref` passed from `estimate_entry_logic.py`)
- [ ] Re-add UI spacing improvements (partially addressed via manual spacing in v1.12, but original dynamic spacing was reverted).
- [ ] Re-add conditional column navigation/visibility based on Wage Type.
- [ ] Improve signal handling and float parsing for edge cases.
- [ ] Replace fragile `item_code == bar_no` logic for bar tracking.

---


---

## 🔄 Additional Notes & Developer Tips

### 📦 Additional Dependencies

In some environments, especially on Windows, you may need additional packages:

```bash
pip install PyQt5 PyQt5-sip
```

If your PyQt5 install fails or fonts do not render correctly in print previews, try reinstalling with:

```bash
pip install --upgrade --force-reinstall PyQt5
```

---

### 💡 Tips for New Developers

- Always test changes in a separate branch or clone.
- Use the console (`print()` or logging) to trace issues in `estimate_entry_logic.py`.
- UI bugs are often related to signal connections or blocked updates.
- When working with table cell updates, use `blockSignals(True/False)` with care.
- Check `QSettings` output for font storage under Windows Registry (`regedit`) if settings don't persist.
- For major DB schema changes, consider dumping data and recreating `estimation.db` with updated schema.
- **Backspace Navigation:** Pressing Backspace in an empty, editable cell in the estimate table moves focus to the previous cell. This is handled within the `NumericDelegate.eventFilter` in `estimate_entry_ui.py`, which is more reliable for intercepting events within the cell editor than using the parent widget's `keyPressEvent`.
- **Passing Window References:** When needing access to main window properties (like settings) from dialogs or child widgets, ensure the actual `MainWindow` instance is passed during instantiation, not just `self` from the calling widget (as seen in the history print font fix).
- **Print Formatting:** The estimate slip format relies on fixed-width spacing and `<pre>` tags. While the selected print font (family, size, bold) is now applied via `setDefaultFont`, non-monospace fonts might cause minor alignment issues in the printout compared to the previous hardcoded 'Courier New'.

---

## 🧩 Additional Clarification on Logic Flow

### `handle_cell_changed`

Triggered on every change in table cells. Determines which column changed and triggers:
- `calculate_net_weight`
- `calculate_fine`
- `calculate_wage`
- `calculate_totals` (indirectly at save or row completion)

### `populate_item_row`

Populates a row based on selected/entered item code. Pulls data from DB, fills columns like:
- Name
- Purity
- Wage Rate
- Wage Type (used for skipping columns)

### `move_to_next_cell` / `move_to_previous_cell`

Custom logic for keyboard-only navigation.
- Skips non-editable columns like `Net Wt`
- Adjusts focus flow based on Wage Type (`PC` vs `WT`)

---

## 📎 Appendix: Reverted Features Recap (for AI / future devs)

| Feature               | Status          | File(s) Involved | Notes |
|----------------------|-----------------|------------------|-------|
| Keyboard Shortcuts   | Partially Re-added | `estimate_entry.py` | Ctrl+S/P/H/N/D/R/B added via `QShortcut` in `EstimateEntryWidget`. Original `main.py` shortcuts remain reverted due to potential conflicts. |
| UI Spacing Changes   | Reverted        | `estimate_entry_ui.py` | Overlapped or broke compact layout. |
| Conditional Columns  | Reverted        | `estimate_entry_logic.py`, `estimate_entry_ui.py` | Navigation bugs & blank entries. |

---

## 📋 Additional Code Analysis and Enhancement Suggestions (April 2025)

### Core Architecture Understanding

#### Column Constants System
The application uses a consistent column index constants system defined in `estimate_entry_ui.py`:
```python
COL_CODE = 0
COL_ITEM_NAME = 1
COL_GROSS = 2
COL_POLY = 3
COL_NET_WT = 4
# ... more constants
```
These constants are used throughout the codebase for table operations, making the code more maintainable. When adding new columns, update these constants and all references.

#### Signal Flow and Event Handling
The application follows a consistent pattern for event handling:
1. UI Events (keypress, cell edit) trigger methods in `estimate_entry_logic.py`
2. These methods update calculated values and UI elements
3. `calculate_totals()` is called to refresh all summary values

Understanding this signal flow is crucial when debugging UI responsiveness issues.

### Identified Issues and Enhancement Opportunities

#### 1. Font Settings in History Dialog Printing
**Problem:** Font settings don't apply when printing from Estimate History.

**Root Cause Analysis:**
The print font isn't correctly transferred from `main_window` to `PrintManager` when accessed from the history dialog context.

**Suggested Fix:**
```python
# In estimate_history.py, ensure print_font access is working
def print_estimate(self):
    # Debug verification
    if hasattr(self.main_window, 'print_font'):
        print(f"Using font: {self.main_window.print_font.family()}, "
              f"size: {getattr(self.main_window.print_font, 'float_size', 0)}")
    else:
        print("main_window.print_font not available!")
        
    # Use getattr with fallback to safely access print_font
    print_font = getattr(self.main_window, 'print_font', None)
    print_manager = PrintManager(self.db_manager, print_font=print_font)
    # Continue with existing code...
```

#### 2. Refactoring Opportunity: Table Navigation Logic
**Problem:** Navigation logic for table cells is complex and doesn't handle conditional columns.

**Suggestion:** Extract navigation logic to dedicated methods with wage-type awareness:
```python
def _find_next_cell(self, current_row, current_col):
    """Determine the next logical cell based on current position and row data."""
    wage_type = self._get_row_wage_type(current_row)
    
    # Custom navigation logic based on column and wage type
    if current_col == COL_PURITY:
        # For PC wage type, go to wage rate
        if wage_type == "PC":
            return current_row, COL_WAGE_RATE
        # For WT wage type, potentially skip to pieces
        else:
            return current_row, COL_PIECES
    
    # Handle other column transitions
    # ...
    
    return next_row, next_col
```

#### 3. Input Validation Enhancement
**Problem:** `NumericDelegate` provides validation but limited visual feedback.

**Suggestion:** Add visual cues for validation status:
```python
# In NumericDelegate.createEditor
def createEditor(self, parent, option, index):
    editor = QLineEdit(parent)
    
    # Add visual styling for validation feedback
    editor.setStyleSheet("""
        QLineEdit { background-color: white; }
        QLineEdit:focus:invalid { background-color: #FFDDDD; }
    """)
    
    # Continue with existing validation logic...
```

#### 4. Database Schema Migration Framework
**Problem:** The current database migration approach is fragile for complex changes.

**Suggestion:** Implement proper version-based migration system:
```python
def _apply_migrations(self):
    """Apply database migrations based on current schema version."""
    # Create version tracking table if needed
    self.cursor.execute("""
        CREATE TABLE IF NOT EXISTS db_version (
            version INTEGER PRIMARY KEY,
            applied_date TEXT
        )
    """)
    
    # Get current version
    self.cursor.execute("SELECT MAX(version) as current_version FROM db_version")
    result = self.cursor.fetchone()
    current_version = result['current_version'] if result and result['current_version'] else 0
    
    # Define migrations to apply
    migrations = [
        # Migration 1: Initial schema (already in setup_database)
        None,
        # Migration 2: Add list_id to bar_transfers
        """ALTER TABLE bar_transfers 
           ADD COLUMN list_id INTEGER REFERENCES silver_bar_lists(list_id)""",
        # Migration 3: Future migration
        # Add more migrations here
    ]
    
    # Apply needed migrations
    for version, sql in enumerate(migrations[1:], start=1):
        if version > current_version and sql:
            try:
                self.cursor.execute("BEGIN TRANSACTION")
                self.cursor.execute(sql)
                applied_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                self.cursor.execute(
                    "INSERT INTO db_version (version, applied_date) VALUES (?, ?)",
                    (version, applied_date)
                )
                self.cursor.execute("COMMIT")
                print(f"Applied migration {version}")
            except sqlite3.Error as e:
                self.cursor.execute("ROLLBACK")
                print(f"Migration {version} failed: {e}")
                break
```

#### 5. Silver Bar Inventory Integration
**Problem:** The link between estimate-entered silver bars and inventory is fragile.

**Suggestion:** Create robust bar number generation when adding from estimates:
```python
# In save_estimate when adding silver bars to inventory
if is_silver_bar and not is_return:
    # Generate a unique bar number if code is empty
    bar_no = item_dict['code'].strip()
    if not bar_no:
        # Format: SB-YYYYMMDD-NNNNN
        timestamp = datetime.now().strftime('%Y%m%d')
        sequence = self._get_next_bar_sequence()
        bar_no = f"SB-{timestamp}-{sequence:05d}"
        # Update the item code for display in the UI
        self.item_table.blockSignals(True)
        try:
            self.item_table.item(row, COL_CODE).setText(bar_no)
        finally:
            self.item_table.blockSignals(False)
    
    # Add to inventory with the properly formatted bar_no
    silver_bars_for_inventory.append({**item_dict, 'bar_no': bar_no})
```

#### 6. Error Handling Improvements
**Problem:** Generic exception handlers can mask specific issues.

**Suggestion:** Add more granular exception handling:
```python
try:
    # Existing calculation code
except ValueError as e:
    # Specific handling for value errors (e.g., format issues)
    self._status(f"Invalid value format: {e}", 3000)
    return default_value
except ZeroDivisionError:
    # Specific handling for division by zero
    self._status("Cannot divide by zero", 3000)
    return 0.0
except Exception as e:
    # Log unexpected errors with traceback
    print(f"Unexpected error in calculation: {e}")
    print(traceback.format_exc())
    self._status(f"Calculation error: {e}", 5000)
    return default_value
```

#### 7. UI Spacing and Layout Improvements
**Problem:** The UI could use better visual separation between sections.

**Suggestion:** Add strategic spacing in the UI:
```python
# In estimate_entry_ui.py, _setup_ui method
def setup_ui(self, widget):
    # After header section
    self.layout.addSpacing(10)
    
    # After header form
    self._setup_header_form(widget)
    self.layout.addSpacing(8)
    
    # After table
    self._setup_item_table(widget)
    self.layout.addWidget(self.item_table)
    self.layout.addSpacing(12)
    
    # After totals
    self._setup_totals()
    self.layout.addSpacing(15)
```

#### 8. Performance Optimization for Large Datasets
**Problem:** Table operations might slow down with many rows.

**Suggestion:** Batch operations for multi-row updates:
```python
# When loading many rows or calculating totals
def update_multiple_rows(self, start_row, end_row):
    """Update calculations for a range of rows efficiently."""
    self.item_table.blockSignals(True)
    try:
        # Process all rows first
        for row in range(start_row, end_row + 1):
            self.calculate_net_weight_for_row(row)
            self.calculate_fine_for_row(row)
            self.calculate_wage_for_row(row)
        
        # Calculate totals once after all rows are updated
        self.calculate_totals()
    finally:
        self.item_table.blockSignals(False)
```

### Implementation Priority Suggestions

In order of importance, consider addressing:

1. **Font Settings Bug**: Fix the history dialog print font issue
2. **Navigation Logic**: Implement conditional column handling based on wage type
3. **Database Migrations**: Add proper versioning before schema changes become more complex
4. **Input Validation**: Improve error handling and visual feedback
5. **UI Spacing**: Enhance visual experience with better layout
6. **Silver Bar Integration**: Strengthen the inventory linking system

These targeted improvements will enhance the application's robustness while maintaining its core functionality and user experience.
