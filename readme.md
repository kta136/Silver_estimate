# Silver Estimation App v1.1

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

## ✅ Features (v1.1)

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
This file reflects the state after v1.1 feature additions/fixes.
Key Concepts & Logic Flow:
Estimate Entry: The core logic resides in estimate_entry_logic.py but is executed within the context of the EstimateEntryWidget instance (estimate_entry.py). EstimateUI defines the widgets.
Calculations: calculate_net_weight, calculate_fine, calculate_wage are triggered by handle_cell_changed. calculate_totals aggregates row data based on the "Type" column.
Item Lookup: Entering a code in COL_CODE triggers process_item_code, which uses db_manager.get_item_by_code. If not found, ItemSelectionDialog is shown.
Saving Estimates: save_estimate (in `estimate_entry_logic.py`) collects data, recalculates totals for accuracy, separates items based on flags (`is_return`, `is_silver_bar`), adds relevant silver bars to inventory, and calls `db_manager.save_estimate_with_returns`.
Database: Uses `sqlite3.Row` factory. Foreign keys are enabled. `DatabaseManager` handles all SQL. Schema includes flags (`is_return`, `is_silver_bar`) in `estimate_items`.
Silver Bars (v1.0): Managed independently via `SilverBarDialog`, though bars can be entered on estimates using the toggle mode. Saving an estimate adds "Silver Bar" type items to the `silver_bars` inventory table via `db_manager.add_silver_bar` (using item code as bar number - potential future enhancement needed here for more robust bar tracking independent of item codes).
Printing: `PrintManager` handles formatting. Estimate slips use manual fixed-width formatting within `<pre>` tags in HTML, generated by `_generate_estimate_manual_format`. Inventory/List reports use standard HTML tables. Print preview is handled by `QPrintPreviewDialog`.

#### Recent Debugging & Feature Implementation Summary (April 2025)

1.  **Net Weight Calculation Bug Fix:**
    *   **Symptom:** Net Wt column (`COL_NET_WT`) was not updating when Gross Wt (`COL_GROSS`) or Poly Wt (`COL_POLY`) changed.
    *   **Investigation:**
        *   Checked `estimate_entry_logic.py`. The `calculate_net_weight` function existed and seemed correct (`gross - poly`).
        *   Confirmed `handle_cell_changed` was connected to the `cellChanged` signal and called `calculate_net_weight` for the correct columns.
        *   Added `print()` statements inside `calculate_net_weight`. Output showed the function *was* being called, but `gross` and `poly` values read from the table using `_get_cell_float` were always 0.0.
        *   Examined `_get_cell_float`. It initially used `QLocale.system().toDouble()`. Added more debug prints inside this function.
        *   Output revealed `QLocale.system().toDouble()` was failing because `QLocale` hadn't been imported (`NameError: name 'QLocale' is not defined`).
        *   The function had a fallback using standard `float(text.replace(',', '.'))`, which *was* working, but the missing import was the root cause.
    *   **Fix:**
        *   Added `from PyQt5.QtCore import QLocale` to `estimate_entry_logic.py`.
        *   Refined `_get_cell_float` to handle potential errors during float conversion more robustly.
        *   Removed debug prints.
    *   **Related Files:** `estimate_entry_logic.py`.

2.  **Print Font Settings Feature:**
    *   **Goal:** Allow user selection of font (family, size >= 5pt, bold) via "Tools" menu to control the **printed estimate slip font**, persisting the setting.
    *   **Implementation Steps & Issues:**
        *   Added "Font Settings..." `QAction` to "Tools" menu in `main.py`, initially triggering `QFontDialog`.
        *   Added `load_settings` and `save_settings` methods in `main.py` using `QSettings` to store font properties (`font/family`, `font/size`, `font/bold`).
        *   Applied loaded font on startup and selected font immediately using `apply_font_settings` (initially targeting `estimate_widget.item_table`).
        *   **Issue:** `QFontDialog` doesn't easily support decimal sizes or enforcing a minimum below 8pt.
        *   **Fix:** Created `custom_font_dialog.py` with `QFontComboBox`, `QDoubleSpinBox` (range 5.0-100.0, 1 decimal), `QCheckBox`, and preview label. Modified `main.py` `show_font_dialog` to use this custom dialog.
        *   **Issue:** Requirement changed - font should *only* affect print output, not the UI table.
        *   **Fix:** Removed `apply_font_settings` call from `main.py`. Modified `load_settings` to store the loaded font in `self.print_font`. Modified `show_font_dialog` to update `self.print_font` on acceptance. Modified `PrintManager.__init__` to accept `print_font`. Modified `PrintManager._print_html` to use `self.print_font` (passed during init) when `table_mode` is False. Modified `PrintManager._generate_estimate_manual_format` to use `self.print_font` properties (size, weight) in the generated HTML CSS.
        *   **Issue:** Print preview alignment broke with non-monospace fonts.
        *   **Fix:** Modified `PrintManager._generate_estimate_manual_format` CSS to *force* `font-family: 'Courier New', Courier, monospace;` but still use the `font-size` (float pt) and `font-weight` (bold/normal) from the `self.print_font` setting.
        *   **Issue:** Float font size wasn't persisting correctly (saved as int or string).
        *   **Fix:** Modified `main.py` `save_settings` to explicitly cast size to `float()` and bold to `bool()` before `setValue`. Modified `load_settings` to use `type=float` hint in `settings.value()` for size. Added `settings.sync()` after saving.
        *   **Issue:** Custom font dialog didn't show the *currently active* print font setting when re-opened.
        *   **Fix:** Modified `main.py` `show_font_dialog` to initialize `CustomFontDialog` with `self.print_font` instead of the UI table's font. Ensured `float_size` attribute was present on `self.print_font`.
        *   **Issue:** Printing from "Estimate History" dialog (`estimate_history.py`) did not use the selected font. The `PrintManager` was being created without the font setting.
        *   **Fix Attempts:**
            *   Tried getting font from `self.parent()` in `estimate_history.py` - failed as parent was `EstimateEntryWidget`.
            *   Modified `estimate_history.py` `__init__` to accept explicit `main_window_ref`. Modified `main.py` `show_estimate_history` to pass `self`. Modified `estimate_history.py` `print_estimate` to use `self.main_window.print_font` when creating `PrintManager`.
        *   **Current Status:** This last fix for history printing is **still not working** correctly and remains a TODO item.
    *   **Related Files:** `main.py`, `custom_font_dialog.py`, `print_manager.py`, `estimate_history.py`.

3.  **Reverted Features (Now TODOs):**
    *   **Hotkeys:** Added Ctrl+S, Ctrl+P, Ctrl+H via `QAction` shortcuts in `main.py`. Required adding trigger methods (`trigger_save_estimate`, `trigger_print_estimate`) to call corresponding methods on `estimate_widget`. *Reverted via `git reset`.*
    *   **UI Spacing:** Added `self.layout.addSpacing(10)` in `estimate_entry_ui.py` after header form and item table, and `addSpacing(15)` after totals section (replacing `QFrame` separator) for readability. *Reverted via `git reset`.*
    *   **Conditional Columns:** Added logic in `estimate_entry_logic.py` (`populate_item_row`, `move_to_next_cell`, `move_to_previous_cell`, `_set_cell_editable`, `_get_row_wage_type`) to disable/enable and skip navigation for `COL_WAGE_RATE` / `COL_PIECES` based on item's `wage_type`. *Reverted via `git reset`.*
    *   **Related Files:** `main.py`, `estimate_entry_ui.py`, `estimate_entry_logic.py`.

### Potential Future Debugging Areas & TODO List

**Known Issues / Bugs:**
- [ ] **Font Settings:** Fix print font application when printing from Estimate History dialog (`estimate_history.py`). The `main_window_ref` passed seems correct, and debugging shows it *is* being passed to `PrintManager`, but the preview doesn't reflect it. Investigate `PrintManager` initialization, `QTextDocument` font setting within `_print_html`, or potential state issues when called from the history dialog context.

**Feature Enhancements / Reverted Tasks:**
- [ ] **Hotkeys:** Re-implement keyboard shortcuts (e.g., Ctrl+S for Save, Ctrl+P for Print, Ctrl+H for History) for common actions in the estimate entry screen (`main.py`, `estimate_entry_logic.py`).
- [ ] **Readability:** Re-apply UI spacing adjustments in the estimate entry screen (`estimate_entry_ui.py`) for better visual separation between elements (e.g., using `addSpacing`).
- [ ] **Conditional Column Logic:** Re-implement logic in `estimate_entry_logic.py` to disable and skip navigation for the "Pieces" column if an item's wage type is "WT" (Weight), and disable/skip the "Wage Rate" column if the type is "PC" (Piece). This involves modifying `populate_item_row`, `move_to_next_cell`, and `move_to_previous_cell`.

**General Areas for Caution/Improvement:**
- **Complex Interactions:** Focus changes, signal blocking (`blockSignals(True/False)`), and `QTimer.singleShot` usage in `estimate_entry_logic.py` manage complex interactions but could be prone to subtle bugs if modified carelessly.
- **Data Conversion/Validation:** Ensure all numeric conversions (`float()`, `int()`, `locale.toDouble()`) handle edge cases (empty strings, invalid formats) robustly, especially when reading from the UI before saving or calculation.
- **Database Schema Migrations:** The current `setup_database` attempts simple `ALTER TABLE` commands which might fail on older SQLite versions or complex changes. A more robust migration system might be needed for production deployment if the schema evolves significantly.
- **Silver Bar Inventory Linking:** The current link between an estimate "Silver Bar" entry and the `silver_bars` inventory relies on matching the `item_code` to the `bar_no`. This could be fragile. A future version might need a more explicit linking mechanism or separate handling.

👤 Author
This project is managed and maintained by Kartikey Agarwal.
