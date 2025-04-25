# 🧾 Silver Estimation App — v1.62

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

## ✅ Features (v1.62)

### 🔢 Estimate Entry

- Fast, keyboard-driven input with intuitive navigation.
- Handles gross weight, poly weight, purity %, wage rate, pieces.
- Real-time calculation of Net Weight, Fine Silver, Labour Amount.
- Wage type can be per piece (`PC`) or per weight (`WT`).
- Modes for Return Items and Silver Bars.
- Auto-fill item details via item code (code is automatically converted to uppercase).
- Code not found? Opens filtered `ItemSelectionDialog`.
- Auto-add new rows upon completing entry in the last column.
- Summary sections for Regular, Return, Silver Bar, and Net totals (Silver Bars and Returns are **subtracted** from Regular to calculate Net totals, including a Grand Total = Net Value + Net Wage).
- **Note Field:** Add notes to estimates that are saved with the estimate and displayed in history and silver bar management.
- **Save workflow:** Saving an estimate now automatically opens Print Preview and then clears the form for a new estimate.
- Load and print estimates.
- Status bar for real-time feedback.
- Keyboard shortcuts: Ctrl+S (Save), Ctrl+P (Print Preview), Ctrl+H (History), Ctrl+N (New Estimate), Ctrl+D (Delete Row), Ctrl+R (Toggle Return), Ctrl+B (Toggle Silver Bar).
- **Backspace Navigation:** Pressing Backspace in an empty editable cell navigates to the previous cell.
- **UI Readability:** Improved with better spacing, separators, right-aligned totals, and alternating row colors (off-white/light gray).
- **Delete Option:** Button added to delete the currently loaded estimate (with confirmation).
- **Last Balance:** Add previous balance in silver weight and amount to estimates with the "LB" button.
- **Improved Totals UI:** Redesigned the totals section below the estimate table using a grid layout with clear headers and separators for better readability.

### 📦 Item Master

- Create, edit, delete items with:
  - Code
  - Name
  - Default Purity (no upper limit enforced)
  - Wage Type (`PC`/`WT`)
  - Wage Rate
- Live search and filtering.
- Duplicate code prevention and safe delete checks.
- Update action no longer requires confirmation.

### 🕓 Estimate History

- Browse past estimates by date or voucher number.
- View summary totals (includes **Regular Gross/Net**, **Net Fine**, **Net Wage**, **Grand Total**, **Note**).
- Reload selected estimate for editing.
- Print directly from history (uses selected print font settings).
- **Delete Option:** Button added to delete the selected estimate (with confirmation).

### 🧱 Silver Bar Management (v2.0)

- Completely overhauled system with unique bar IDs and list-based management
- Bars are linked to source estimates via `estimate_voucher_no`
- Create and manage lists of silver bars with notes
- View estimate notes alongside voucher numbers for better identification
- Add/remove bars to/from lists with automatic status tracking
- Filter available bars by weight with real-time search
- View detailed list information including total weight and fine weight
- Print inventory lists with comprehensive details
- Automatic tracking of bar transfers between statuses

### 🖨️ Printing

- Print Preview opens maximized and zoomed to 125% by default.
- Estimate slip uses fixed-width formatting (no `|` separators, relies on spacing) with **S.No.** column (resets per section).
- Printed sections with individual totals (aligned, Labour/Poly rounded) for:
  - Regular Items
  - Silver Bars
  - Return Goods
  - Return Bars
- Final summary displays Net Fine, Silver Cost, Labour, Total (Net calculated as Regular - Bars - Returns; Labour, Cost, Total **rounded to 0 decimals**). S.Cost and Total are omitted if Silver Rate is zero.
- Last Balance section displays previous balance in silver weight and amount when present.
- Silver Bar Inventory printing via HTML table format.
- Reduced blank lines and minimized top/bottom margins on printed estimate slip for tighter layout.
- Section total separators changed from `-` to `=` for clarity.

### 🔤 Font Settings

- Configure **Print Font** (family, size min 5pt, bold) via "Tools -> Print Font Settings...". Applies only to estimate slip print output. Persists via `QSettings`.
- Configure **Table Font Size** (7-16pt) via "Tools -> Table Font Size...". Applies to the estimate entry table UI. Persists via `QSettings`.

### 🛠️ Settings & Data Management (Tools Menu)

- **Settings Dialog:** Centralized configuration options under "Tools -> Settings...". Includes:
    - Print Font configuration.
    - Estimate Table Font Size configuration.
    - Data Deletion options (Delete All Estimates, DELETE ALL DATA).
    - Security options (Password Change).
    - Import/Export options (Item List Import/Export).
- **Silver Bar Management:** Remains directly accessible under "Tools -> Silver Bar Management".

### 🔄 Import/Export (v1.62)

-   **Item List Import:**
-   Accessed via "Tools -> Settings... -> Import/Export" tab.
-   Supports importing from delimited text files (e.g., `.txt`, `.csv`).
-   **Configurable Parser:** Allows setting the delimiter, column indices (0-based) for Code, Name, Purity, Wage Type, Wage Rate.
-   **Options:** Skip header row, apply specific line filtering (for TBOOK.TXT format).
-   **Wage Rate Adjustment:** Apply multiplication or division (e.g., `*1.1`, `/1000`) to parsed wage rates.
-   **Q-Type Conversion:** Automatically converts 'Q' type wage rates from per kg to per gram (before applying adjustment factor).
-   **Duplicate Handling:** Options to "Skip" or "Update" existing items based on item code.
-   **Preview:** Shows the first 10 rows of data as parsed with current settings.
-   Provides progress and status feedback during import.
-   **Item List Export:**
-   Accessed via "Tools -> Settings... -> Import/Export" tab.
-   Prompts for a save file location.
-   Exports all items from the database to a pipe-delimited (`|`) text file with a header row (`Code|Name|Purity|Wage Type|Wage Rate`).
-   This format is directly compatible with the default settings of the Item Importer.

### 🔒 Security Features (v1.61+)

-   **Password Authentication:** The application requires password authentication upon startup.
    -   **First Run:** Users are prompted to create a main password (for login) and a secondary password. Both passwords must be different.
    -   **Subsequent Runs:** Users must enter their main password to access the application.
-   **Password Hashing:** Passwords are not stored directly. Secure hashes (using the Argon2 algorithm via `passlib`) are generated and stored using the platform's standard settings mechanism (`QSettings`).
-   **Database Encryption:** The main database file (`database/estimation.db`) is encrypted at rest using AES-GCM encryption (`cryptography` library).
    -   The encryption key is derived from the user's main password and a unique, randomly generated salt (also stored securely via `QSettings`).
    -   The database is decrypted into a temporary file only when the application is running and the correct main password has been provided. The temporary file is deleted upon closing the application.
-   **Password Change:** Users can change both their main and secondary passwords via the "Security" tab in the "Settings" dialog. This requires entering the current main password for verification.
    -   *Note:* Changing the main password requires an application restart for the new password to be used for database decryption.
-   **Data Reset:** An explicit "Reset / Wipe All Data" button is available on the login screen.
    -   This action requires confirmation due to its irreversible nature.
    -   If confirmed, it permanently deletes the encrypted database file and all stored security settings (password hashes, encryption salt), effectively resetting the application to its first-run state.

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
├── silver_bar_management.py # Silver bar inventory dialog UI and logic (v2.0)
├── item_selection_dialog.py # Dialog to select items when code not found
├── print_manager.py # Handles print formatting and preview dialogs
├── database_manager.py # All SQLite database operations and schema setup
├── table_font_size_dialog.py # Dialog for setting table font size
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

### 📦 Building Executable (using PyInstaller)

To create a single-file executable (`.exe` on Windows) that includes all dependencies and doesn't open a console window:

1.  **Install PyInstaller:**
    ```bash
    pip install pyinstaller
    ```
2.  **Install Required Backend:** Ensure the Argon2 backend for `passlib` is installed:
    ```bash
    pip install argon2_cffi
    ```
3.  **Run PyInstaller:** Navigate to the project root directory in your terminal (where `main.py` is located) and run the following command:

    ```bash
    pyinstaller --onefile --windowed --name v1.62 --hidden-import=passlib.handlers.argon2 --hidden-import=passlib.handlers.bcrypt main.py
    ```

    -   `--onefile`: Creates a single executable file.
    -   `--windowed`: Prevents the console window from appearing when the application runs.
    -   `--name v1.62`: Sets the name of the output executable (e.g., `v1.62.exe`).
    -   `--hidden-import=passlib.handlers.argon2`: Explicitly includes the Argon2 handler needed by `passlib`.
    -   `--hidden-import=passlib.handlers.bcrypt`: Explicitly includes the bcrypt handler needed by `passlib` (as it's listed as a fallback scheme).
    -   `main.py`: The main script of the application.

4.  The executable will be created in the `dist` subfolder within your project directory.
---

## 🧠 Developer Notes & Architecture Overview

### 🔄 Logic Flow Summary

- **Estimate Entry:** Core logic in `estimate_entry_logic.py`, UI in `estimate_entry_ui.py`, combined in `EstimateEntryWidget`.
- **Item Lookup:** `process_item_code` -> `db_manager.get_item_by_code` -> `ItemSelectionDialog` if needed.
- **Saving Estimates:** `save_estimate` -> `db_manager.save_estimate_with_returns`. Stores net totals (Reg-Bar-Ret) in header.
- **Silver Bars:** Entries saved in `silver_bars` table. Linked by item code (future: decouple).
- **Printing:** `PrintManager` handles formats. Estimate slip uses `<pre>` and fixed-width spacing. Preview via `QPrintPreviewDialog`.

---

## 🐞 Key Fixes & Enhancements (v1.60 - April 2025)

### 1. ⚙️ Centralized Settings Dialog
- Refactored the "Tools" menu.
- Created a new `SettingsDialog` accessible via "Tools -> Settings...".
- Moved Print Font, Table Font Size, Delete All Estimates, and DELETE ALL DATA actions into this dialog.
- Removed the previous "Advanced Tools" dialog implementation.
- Kept "Silver Bar Management" directly in the "Tools" menu.

## 🐞 Key Fixes & Enhancements (v1.59 - April 2025)

### 1. ✨ Totals Section UI Redesign
- Replaced the previous totals layout with a structured `QGridLayout`.
- Added clear row headers (Gross Wt, Net Wt, etc.) and column headers (Regular, Return, Bar, Net).
- Included vertical separators between sections and a horizontal separator before the Grand Total.
- Improved alignment and bolded Net totals for better readability.

## 🐞 Key Fixes & Enhancements (v1.58 - April 2025)

### 1. 🖨️ Section Total Separator Change
- Changed the separator line printed *after* each section's totals (Regular, Bars, Returns) from dashes (`-`) to equals signs (`=`) for better visual distinction.

## 🐞 Key Fixes & Enhancements (v1.57 - April 2025)

### 1. 📄 Print Layout Adjustments
- Removed most blank lines between sections on the printed estimate slip for a more compact view.
- Reduced top and bottom page margins to 2mm for less wasted space.

## 🐞 Key Fixes & Enhancements (v1.56 - April 2025)

### 1. 🖨️ Conditional Print Summary
- Modified the final summary line on the printed estimate slip.
- If the Silver Rate is zero, the "S.Cost" and "Total" fields are now omitted, showing only Net Fine and Net Wage.

## 🐞 Key Fixes & Enhancements (v1.55 - April 2025)

### 1. 🚀 Startup & Window Behavior Fixes
- Fixed `AttributeError` related to `reconnect_load_estimate` by ensuring method is correctly defined within the class.
- Prevented premature "Estimate not found" error on startup by delaying signal connection for voucher field.
- Ensured main window starts maximized correctly using `setWindowState`.

## 🐞 Key Fixes & Enhancements (v1.54 - April 2025)

### 1. 💰 Last Balance Feature
- **Added "LB" button** to the estimate entry screen
- When clicked, prompts for last balance in silver weight and amount
- Last balance is added to the totals in calculations
- Displayed in a separate section in the printed estimate
- Stored in the database with automatic schema migration

## 🐞 Key Fixes & Enhancements (v1.52 - April 2025)

### 1. 📝 Estimate Notes Feature

- **Added note field** beside silver rate in the estimate entry screen
- Notes are saved with estimates and displayed in:
  - Estimate history columns
  - Silver bar management alongside voucher numbers
- Helps with better identification and tracking of estimates and silver bars
- **Database Compatibility:** Automatically adds the note column to existing databases
- **UI Improvements:**
  - Note column placed next to Date column in Estimate History for better visibility
  - Larger Estimate History window (1000x600) for better readability
  - Notes appear on the same line as "ESTIMATE SLIP ONLY" title while keeping the title centered

## 🐞 Key Fixes & Enhancements (v1.51 - April 2025)

### 1. 🧱 Silver Bar Management Overhaul (v2.0)

- **Objective:** Completely rewrote the silver bar tracking and management system
- **Implementation:**
  - New database schema with `silver_bars`, `silver_bar_lists`, and `bar_transfers` tables
  - Bars now have unique `bar_id` and are linked to source estimates
  - List-based grouping/assignment system for organizing bars
  - Comprehensive UI redesign with separate views for available and listed bars
  - Enhanced printing capabilities for lists and inventory

### 2. 💰 Currency Formatting Fix

- **File:** `print_manager.py`
- **Change:** Corrected the `format_indian_rupees` function to properly implement comma separation according to the Indian numbering system (lakhs, crores)
- **Impact:** Correctly formatted Silver Cost and Total Cost on printed estimate slips

### 3. 🐛 Critical Database Schema Versioning

- **Issue:** Silver bars were being deleted when the program was restarted
- **Fix:** Implemented a schema versioning system with a new `schema_version` table
- **Impact:** Prevents data loss by only performing schema migrations when necessary

### 4. 🔄 Silver Bar Lifecycle Management

- **Issue:** Multiple issues with silver bars being deleted or duplicated
- **Fix:** Completely redesigned the silver bar lifecycle:
  - Silver bars are created only once when an estimate is first saved
  - They are preserved when an estimate is edited or saved again
  - They are deleted only when their parent estimate is deleted
  - Lists that become empty due to bar deletion are also removed
- **Technical Details:**
  - Fixed cascade deletion issue caused by `ON DELETE CASCADE` constraint
  - Rewrote `save_estimate_with_returns` to use UPDATE instead of INSERT OR REPLACE
  - Added checks to prevent duplicate bars when saving estimates multiple times
  - Enhanced estimate deletion to properly clean up related data

### 5. 🔧 SQLite3.Row Access Fixes

- **Issue:** Multiple instances of using `.get()` on `sqlite3.Row` objects causing errors
- **Fix:** Changed all instances to use dictionary-style access with proper key existence checks
- **Impact:** Ensures compatibility with both dictionary and sqlite3.Row objects throughout the application

### 6. 💅 UI Improvements to Silver Bar Management

- **Removed Timestamps:** Cleaner presentation with date-only format
- **Added Totals Display:** Summary labels showing bar count, total weight, and fine weight
- **Enhanced List Selection:** Added list notes to dropdown items for easier identification
- **Improved Note Handling:** Consistent display format across the UI

## 🐞 Key Fixes & Enhancements (v1.14 - April 2025)

#### 1. 🧮 Net Weight Calculation Bug Fix (Pre-v1.12)

- **Symptom:** Net Wt column not reflecting updated Gross/Poly inputs.
- **Issue:** `QLocale.system().toDouble()` failed silently due to missing import.
- **Fix:** Added `from PyQt5.QtCore import QLocale`; Improved `_get_cell_float()` with fallback.

#### 2. 🖨️ Print Font Settings (Pre-v1.12)

- Added custom font dialog ("Tools -> Print Font Settings...").
- Saved settings via `QSettings`.
- Font applied only to estimate print via `PrintManager`.

#### 3. 🛠️ History Print Font Fix (v1.12)

- **Symptom:** Custom print font settings were not applied when printing from the Estimate History dialog.
- **Fix:** Corrected `main_window_ref` passed to `EstimateHistoryDialog` from `estimate_entry_logic.show_history()` to ensure the correct `MainWindow` instance (holding `print_font`) was referenced.

#### 4. 📉 Silver Bar Calculation Correction (v1.14)

- **Symptom:** Silver bars entered in the estimate were being added to totals instead of subtracted.
- **Fix:** Modified `calculate_totals` (screen display) and `save_estimate` (DB storage) in `estimate_entry_logic.py`, and print summary calculation in `print_manager.py` to subtract Bar values along with Return values from Regular values for Net Fine/Wage.

#### 5. 💅 Print Format Update (v1.14)

- **Change:** Added Serial Number (S.No) column (resets per section). Removed all vertical pipe (`|`) separators. Added individual total lines under each section (Regular, Bars, Returns). Removed decimals from Poly column. Rounded Labour in section totals. Rounded Labour, S.Cost, Total in final summary. Ensured section totals align under headers.
- **Implementation:** Modified `format_line`, `format_totals_line`, `header_line`, and `final_line` construction in `print_manager._generate_estimate_manual_format`. Added `sno_counter` reset logic.

#### 6. ✨ UI/UX Improvements (v1.14)

- **Print Preview:** Opens maximized and zoomed to 125%.
- **Save Workflow:** Save button now triggers print preview and then clears the form.
- **Estimate Screen Readability:** Added spacing, separators, right-aligned totals, and alternating background colors to the table.
- **Table Font Size:** Added option in "Tools -> Table Font Size..." menu (persists via `QSettings`).
- **Backspace Navigation:** Backspace in empty editable table cell moves to previous cell (handled in `NumericDelegate`).
- **Item Master:** Removed confirmation dialog on item update. Purity % validation limit removed.
- **Estimate History:** Columns updated to show Regular Gross/Net, Net Fine, Net Wage, Grand Total. Calculation logic updated to fetch line items for Regular Gross/Net.

#### 7. 🗑️ Data Deletion Features (v1.14)

- **Change:** Added ability to delete all estimates or a single estimate.
- **Implementation:**
    - Added `delete_all_estimates` and `delete_single_estimate` methods to `DatabaseManager`.
    - Renamed "Reset Database Tables" menu action to "DELETE ALL DATA" and connected to `delete_all_data` handler in `MainWindow` (which calls `db.drop_tables`).
    - Added "Delete All Estimates..." menu action connected to `delete_all_estimates` handler in `MainWindow`.
    - Added "Delete This Estimate" button and logic to `EstimateEntryWidget`/`EstimateLogic`.
    - Added "Delete Selected" button and logic to `EstimateHistoryDialog`.
    - All deletion actions include confirmation dialogs.

#### 8. ⏪ Reverted Features (Status as of v1.14)

- **Hotkeys (Ctrl+S/P/H)** (Note: Ctrl+S/P/H/N/D/R/B were re-added in v1.12 via `QShortcut` in `EstimateEntryWidget`)
- **UI spacing improvements** (Note: Some manual spacing added in v1.14, but original dynamic/reverted spacing not restored)
- **Conditional column behavior** (hide/show Wage/Pieces based on wage type)

---

## 📝 Development & Debugging Notes for AI

This file reflects the state after v1.62 feature additions/fixes.

### 🔧 Key Concepts & Logic Flow:

- **Estimate Entry:** Core logic in `estimate_entry_logic.py`, UI in `estimate_entry_ui.py`, combined in `EstimateEntryWidget`.
- **Calculations:** `handle_cell_changed` triggers row calculations; `calculate_totals` aggregates for screen display; `save_estimate` recalculates net totals before DB save.
- **Item Lookup:** `process_item_code` -> `db_manager.get_item_by_code` -> `ItemSelectionDialog` if needed.
- **Saving Estimates:** `save_estimate` -> `db_manager.save_estimate_with_returns`. Stores net totals (Reg-Bar-Ret) in header.
- **Database:** `sqlite3.Row` factory, FKs enabled, `is_return`/`is_silver_bar` flags used.
- **Printing:** `PrintManager` handles formats. Estimate slip uses `<pre>` and fixed-width spacing. Preview via `QPrintPreviewDialog`.
- **Import/Export:** Moved to Settings dialog. `ItemImportDialog` collects settings, `ItemImportManager` handles parsing/DB interaction, `ItemExportManager` handles DB query/file writing.
- **Window Maximizing:** Setting `self.setWindowState(Qt.WindowMaximized)` at the end of `MainWindow.__init__` seems more reliable than calling `showMaximized()` after `show()`.

---

### 🧪 Known Issues / TODO (Post v1.62)

- [x] ~~Print: Add Serial number column & Round off printed amounts.~~ (Completed in v1.14)
- [x] ~~Tools Menu: Rename "Reset Database Tables" action.~~ (Completed in v1.14)
- [x] ~~Estimate History: Update columns.~~ (Completed in v1.14)
- [x] ~~Tools Menu: Add "Delete All Estimates" option.~~ (Completed in v1.14)
- [x] ~~Delete Single Estimate: Add option/button.~~ (Completed in v1.14)
- [x] ~~Silver Bar Management: Implement list-based grouping system.~~ (Completed in v1.51)
- [x] ~~Silver Bar Lifecycle: Fix issues with deletion and duplication.~~ (Completed in v1.51)
- [x] ~~Database Schema: Implement versioning to prevent data loss.~~ (Completed in v1.51)
- [ ] Estimate Screen: Allow table column widths to be resized by the user and persist the sizes between sessions (using `QSettings`).
- [x] ~~Estimate Notes: Add feature (UI, DB, Logic, History).~~ (Completed in v1.52)
- [x] ~~Encryption/Password: Implement password protection & reset.~~ (Completed v1.61)
- [x] ~~Import/Export: Add Item List Import/Export.~~ (Completed v1.62)
- [ ] Re-add UI spacing improvements (original dynamic spacing was reverted).
- [ ] Re-add conditional column navigation/visibility based on Wage Type.
- [ ] Improve signal handling and float parsing for edge cases.
- [ ] Replace fragile `item_code == bar_no` logic for bar tracking.

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
- For major DB schema changes, consider dumping data and recreating `estimation.db` with updated schema, or implement a proper migration system (see suggestions below).
- **Backspace Navigation:** Pressing Backspace in an empty, editable cell in the estimate table moves focus to the previous cell. This is handled within the `NumericDelegate.eventFilter` in `estimate_entry_ui.py`.
- **Passing Window References:** When needing access to main window properties (like settings) from dialogs or child widgets, ensure the actual `MainWindow` instance is passed during instantiation, not just `self` from the calling widget (as seen in the history print font fix).
- **Print Formatting:** The estimate slip format relies on fixed-width spacing and `<pre>` tags. Alignment depends heavily on the calculated widths (`W_SNO`, `W_FINE`, etc.) in `print_manager.py` and the use of a monospace or near-monospace font for the print output. The `format_totals_line` function explicitly calculates padding based on column widths to align totals. Labour/Poly totals and final summary amounts are rounded to 0 decimals.
- **Database Transactions:** Deletion operations (single estimate, all estimates, all data via drop tables) are wrapped in `BEGIN TRANSACTION`/`COMMIT`/`ROLLBACK` blocks in `DatabaseManager` for safety.
- **Net Total Calculation:** Net Fine/Wage values stored in the `estimates` table header represent `Regular - Bars - Returns`. This calculation happens in `estimate_entry_logic.save_estimate` before saving. Ensure consistency if `calculate_totals` logic changes.
- **Estimate History Totals:** The history dialog calculates Regular Gross/Net by summing line items but displays Net Fine/Wage/Grand Total based on the values stored in the estimate header (which are already net values).

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
| UI Spacing Changes   | Reverted        | `estimate_entry_ui.py` | Overlapped or broke compact layout. (Some manual spacing added v1.14). |
| Conditional Columns  | Reverted        | `estimate_entry_logic.py`, `estimate_entry_ui.py` | Navigation bugs & blank entries. |

---

## 📋 Additional Code Analysis and Enhancement Suggestions (April 2025)

### Core Architecture Understanding

#### Column Constants System
The application uses a consistent column index constants system defined in `estimate_entry_ui.py`.

#### Signal Flow and Event Handling
UI Events -> `estimate_entry_logic.py` methods -> Update UI/Calculations -> `calculate_totals()` refreshes summary.

### Identified Issues and Enhancement Opportunities

#### 1. Font Settings in History Dialog Printing
**Status:** Fixed in v1.12.

#### 2. Refactoring Opportunity: Table Navigation Logic
**Problem:** Navigation logic doesn't handle conditional columns (reverted feature).
**Suggestion:** Extract logic to dedicated methods aware of Wage Type.

#### 3. Input Validation Enhancement
**Problem:** Limited visual feedback on invalid input.
**Suggestion:** Use CSS in `NumericDelegate` to style invalid input fields.

#### 4. Database Schema Migration Framework
**Problem:** Manual schema changes are fragile.
**Suggestion:** Implement version-based migration system.

#### 5. Silver Bar Inventory Integration
**Problem:** Link between estimate bars and inventory is fragile.
**Suggestion:** Generate unique bar numbers in `save_estimate`.

#### 6. Error Handling Improvements
**Problem:** Generic exception handlers can mask issues.
**Suggestion:** Use more specific `try...except` blocks.

#### 7. UI Spacing and Layout Improvements
**Problem:** UI could use better visual separation.
**Suggestion:** Add strategic `addSpacing()` calls (partially done manually in v1.14).

#### 8. Performance Optimization for Large Datasets
**Problem:** Table operations might slow with many rows.
**Suggestion:** Batch operations, block signals during multi-row updates.

### Implementation Priority Suggestions (Post v1.52)

In order of importance, consider addressing:

1.  **Navigation Logic**: Implement conditional column handling based on wage type.
2.  ~~**Database Migrations**: Add proper versioning before schema changes become more complex.~~ (Completed in v1.51)
3.  ~~**Silver Bar Integration**: Strengthen the inventory linking system.~~ (Completed in v1.51)
4.  **Input Validation**: Improve error handling and visual feedback.
5.  **UI Spacing**: Re-evaluate and potentially restore dynamic spacing.
6.  ~~**Estimate Notes**: Implement the notes feature.~~ (Completed in v1.52)
7.  ~~**Encryption/Password**: Implement security features.~~ (Completed v1.61)
8.  **Performance/Refactoring**: Address signal handling, float parsing, large dataset optimizations.

These targeted improvements will enhance the application's robustness while maintaining its core functionality and user experience.
