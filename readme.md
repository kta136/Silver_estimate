# Silver Estimation App v1.0

A desktop application built using **PyQt5** and **SQLite** for managing silver sales estimates, including item-wise entries, silver bar inventory, returns, and print-ready formatted outputs.

---

## 💡 Purpose
Designed for silver shops to:
- Generate detailed silver item estimates.
- Track gross/net/fine silver.
- Manage silver bar inventory.
- Handle return goods and silver bar entries.
- Print estimate slips in a specific, structured format.
- Print silver bar inventory reports.

---

## ✅ Features (v1.0)

### Estimate Entry
- Fast, keyboard-friendly item entry grid.
- Supports gross weight, poly weight, purity %, wage rate, pieces.
- Calculates Net Wt, Fine Wt, Labour Amt based on Item Master settings (Wage Type PC/WT).
- Toggle modes for entering **Return Items** or **Silver Bars** (affects calculations and identification).
- Uses `NumericDelegate` for proactive numeric input validation in the table.
- Auto-fills item name, purity, wage rate based on entered item code.
- Provides `ItemSelectionDialog` with filtering if an entered code is not found.
- Auto-row generation upon completing the 'Pieces' column in the last row.
- Navigation using `Enter`/`Tab` and `Shift+Tab`.
- Calculates and displays detailed totals for Regular, Return, Silver Bar, and Net categories.
- Save, Load, and Print Preview estimates.
- Status bar feedback for operations.

### Item Master
- Add/edit/delete items with code, name, default purity, wage type (`PC`=Per Piece, `WT`=Per Weight), and rate.
- Uses validated `QLineEdit` widgets for numeric inputs (Purity, Wage Rate).
- Live search filtering by code or name.
- Prevents editing the `code` of existing items.
- Prevents adding items with duplicate codes.
- Warns on deleting items potentially used in estimates.

### Estimate History
- Browse past estimates.
- Filter by date range or voucher number search.
- View summary totals in the list.
- Open selected estimate back into the main entry screen.
- Print selected estimate directly from history.

### Silver Bar Management (v1.0 - Basic)
- Add silver bars with Bar Number, Weight, Purity.
- View inventory, filterable by Status (All, In Stock, Transferred, Sold, Melted).
- Transfer selected bar(s) to a new status with optional notes.
- Print inventory list based on current filter.
- *Note: Advanced list management (grouping bars under a named list) planned for v1.1.*

### Printing
- Print Preview for estimates using a fixed-width format. Font size and style (bold) are configurable via "Tools" -> "Font Settings...". Font family is fixed to monospace (`Courier New`) to maintain alignment.
- Separate sections on estimate printout for Regular, Silver Bar, Return Goods, Return Silver Bar items.
- Calculates and prints Net Fine, Silver Cost, Labour, and Total amounts.
- Print Preview for Silver Bar Inventory using a standard HTML table format.

### Font Settings (via Tools Menu)
- Allows selection of font family, style (bold), and size (decimal, min 5.0pt) using a custom dialog (`custom_font_dialog.py`).
- Selected font size and style are applied **only** to the printed estimate slip (`print_manager.py`). The font family is ignored for estimate printing to maintain fixed-width alignment.
- Settings are saved and loaded between sessions using `QSettings` (`main.py`).
- *Known Issue:* Printing from "Estimate History" currently does not apply the selected font settings (See TODO).

---

## 🛠 Tech Stack
- **Language:** Python 3.x
- **GUI:** PyQt5
- **Database:** SQLite 3

---

## 🔁 Project Structure
Use code with caution.
Markdown
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
---

## 🚀 Getting Started

### Prerequisites
- Python 3 (recommended 3.8+)
- `pip` (Python package installer)

### Installation
1.  **Clone or download** the project files.
2.  **Navigate** to the project directory in your terminal.
3.  **(Recommended)** Create and activate a virtual environment:
    ```bash
    python -m venv .venv
    # Windows:
    .\.venv\Scripts\activate
    # macOS/Linux:
    source .venv/bin/activate
    ```
4.  **Install dependencies:**
    ```bash
    pip install PyQt5
    ```

### Running the Application
```bash
python main.py


On the first run, a database folder and the estimation.db SQLite file will be created automatically if they don't exist. The necessary tables will also be created.
📝 Development & Debugging Notes for AI
This file serves as a stable checkpoint (v1.0).
Key Concepts & Logic Flow:
Estimate Entry: The core logic resides in estimate_entry_logic.py but is executed within the context of the EstimateEntryWidget instance (estimate_entry.py). EstimateUI defines the widgets.
Calculations: calculate_net_weight, calculate_fine, calculate_wage are triggered by handle_cell_changed. calculate_totals aggregates row data based on the "Type" column.
Item Lookup: Entering a code in COL_CODE triggers process_item_code, which uses db_manager.get_item_by_code. If not found, ItemSelectionDialog is shown.
Saving Estimates: save_estimate (in estimate_entry_logic.py) collects data, recalculates totals for accuracy, separates items based on flags (is_return, is_silver_bar), adds relevant silver bars to inventory, and calls db_manager.save_estimate_with_returns.
Database: Uses sqlite3.Row factory. Foreign keys are enabled. DatabaseManager handles all SQL. Schema includes flags (is_return, is_silver_bar) in estimate_items.
Silver Bars (v1.0): Managed independently via SilverBarDialog, though bars can be entered on estimates using the toggle mode. Saving an estimate adds "Silver Bar" type items to the silver_bars inventory table via db_manager.add_silver_bar (using item code as bar number - potential future enhancement needed here for more robust bar tracking independent of item codes).
Common Issues & Fixes Applied:
Net Wt Calculation: Fixed by ensuring calculate_net_weight is called from handle_cell_changed for both COL_GROSS and COL_POLY, and ensuring Poly field defaults to "0.000" if left blank before moving focus (keyPressEvent modifications were tested but final logic relies on handle_cell_changed).
Double Clicks/Executions: Fixed by ensuring signal connections (.clicked.connect) are made only once, typically in the dedicated connect_signals method, not in the UI setup methods.
Shortcut Conflicts: Fixed by removing redundant QShortcut objects when the same shortcut was also defined on a QAction in the menu bar. Rely on QAction.setShortcut for menu items.
AttributeError: ... no attribute 'get': Fixed by replacing .get() calls on sqlite3.Row objects with direct dictionary-style access row['column_name'] and checking for None.
AttributeError: 'MainWindow' object has no attribute 'estimate_widget': Fixed by ensuring setup_menu_bar() is called after self.estimate_widget is initialized in MainWindow.__init__.
Import Errors: Fixed by importing classes (QLocale, QValidators) from the correct Qt module (QtCore, QtGui).
Column Indices: Replaced magic numbers with named constants (e.g., COL_CODE) for clarity and maintainability.
Net Wt Calculation (Locale Issue): If Net Wt stops calculating, check `_get_cell_float` in `estimate_entry_logic.py`. A previous issue was caused by a missing `from PyQt5.QtCore import QLocale` import, preventing locale-based number parsing. The fix involved adding the import and ensuring the fallback `float()` conversion handles potential errors.

Font Settings Implementation & Debugging (April 2025):
- **Goal:** Add configurable font (family, size >= 5pt, bold) via Tools menu for printing.
- **Initial Steps:** Added "Font Settings..." QAction in `main.py`. Used standard `QFontDialog`. Applied selected font directly to `estimate_widget.item_table`. Saved settings using `QSettings`.
- **Issue 1:** `QFontDialog` limitations (min size 8pt, no decimals).
- **Fix 1:** Created `custom_font_dialog.py` with `QFontComboBox`, `QDoubleSpinBox` (min 5.0, decimals), `QCheckBox`. Updated `main.py` to use this dialog.
- **Issue 2:** Font was changing UI table, requirement was to change *print* font only.
- **Fix 2:** Modified `main.py` to store selection in `self.print_font` instead of applying to UI. Modified `print_manager.py` `__init__` to accept `print_font` and `_print_html` / `_generate_estimate_manual_format` to use it for estimate CSS/font setting.
- **Issue 3:** Print preview format broke (alignment lost) when using non-monospace families.
- **Fix 3:** Modified `print_manager.py` (`_generate_estimate_manual_format`) to *force* `font-family: 'Courier New', Courier, monospace;` in CSS, but still use the selected `font-size` (float pt) and `font-weight` (bold/normal) from settings.
- **Issue 4:** Settings persistence failed for float size (reverted to integer on reload).
- **Fix 4:** Modified `main.py` `load_settings` and `save_settings` to explicitly use `type=float` when reading and `float()` / `bool()` when writing to `QSettings`. Added `settings.sync()`.
- **Issue 5:** Printing from Estimate History dialog didn't use the selected font.
- **Fix 5 (Attempt 1):** Modified `estimate_history.py` `print_estimate` to get font from `self.parent()`. Failed because `self.parent()` was `EstimateEntryWidget`, not `MainWindow`.
- **Fix 5 (Attempt 2):** Modified `estimate_history.py` `__init__` to accept explicit `main_window_ref`. Modified `main.py` `show_estimate_history` call to pass `self` as `main_window_ref`. Modified `estimate_history.py` `print_estimate` to use `self.main_window.print_font`.
- **Current Status:** Font settings persist and apply correctly to print preview from main estimate screen. Custom dialog shows current setting. **However, printing from Estimate History still doesn't apply the font.**

Potential Future Debugging Areas & TODO:
- **TODO:** Fix print font application when printing from Estimate History dialog (`estimate_history.py`). The `main_window_ref` passed seems correct, but the `PrintManager` initialized from there isn't using the font. Investigate `PrintManager` initialization or font object state when called from the history dialog context.
- Complex Interactions: Focus changes, signal blocking (blockSignals(True/False)), and QTimer.singleShot usage in estimate_entry_logic.py manage complex interactions but could be prone to subtle bugs if modified carelessly.
- Data Conversion/Validation: Ensure all numeric conversions (float(), int(), locale.toDouble()) handle edge cases (empty strings, invalid formats) robustly, especially when reading from the UI before saving or calculation.
- Database Schema Migrations: The current setup_database attempts simple ALTER TABLE commands which might fail on older SQLite versions or complex changes. A more robust migration system might be needed for production deployment if the schema evolves significantly.
- Silver Bar Inventory Linking: The current link between an estimate "Silver Bar" entry and the silver_bars inventory relies on matching the item_code to the bar_no. This could be fragile. A future version might need a more explicit linking mechanism or separate handling.

👤 Author
This project is managed and maintained by Kartikey Agarwal.
