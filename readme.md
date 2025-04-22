# 🧾 Silver Estimation App — v1.1

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

## ✅ Features (v1.1)

### 🔢 Estimate Entry

- Fast, keyboard-driven input with intuitive navigation.
- Handles gross weight, poly weight, purity %, wage rate, pieces.
- Real-time calculation of Net Weight, Fine Silver, Labour Amount.
- Wage type can be per piece (`PC`) or per weight (`WT`).
- Modes for Return Items and Silver Bars.
- Auto-fill item details via item code (code is automatically converted to uppercase).
- Code not found? Opens filtered `ItemSelectionDialog`.
- Auto-add new rows upon completing entry in the last column.
- Summary sections for Regular, Return, Silver Bar, and Net totals (including a Grand Total = Net Value + Net Wage).
- Save, load, and print estimates.
- Status bar for real-time feedback.

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

- Print Preview of estimates with fixed-width formatting.
- Uses `Courier New` font for alignment.
- Printed sections for:
  - Regular
  - Silver Bars
  - Return Goods
  - Return Bars
- Displays Net Fine, Silver Cost, Labour, Total.
- Silver Bar Inventory printing via HTML table format.

### 🔤 Font Settings

- Configure font size (min 5pt), bold option via custom dialog.
- Applies only to **print output**.
- Font settings persist via `QSettings`.
- Known issue: History printout doesn't reflect settings (*see TODO*).

---

## 🛠️ Tech Stack

- **Language:** Python 3.x
- **GUI:** PyQt5
- **Database:** SQLite3

---

## 📁 Project Structure

```
.
├── main.py                   # App entry point & MainWindow
├── estimate_entry.py         # Estimate entry widget & logic entry point
├── estimate_entry_ui.py      # UI layout and table setup
├── estimate_entry_logic.py   # Calculation logic and event handlers
├── item_master.py            # Manage item records
├── estimate_history.py       # History viewer and print interface
├── silver_bar_management.py  # Silver bar management dialog
├── item_selection_dialog.py  # Item selection popup
├── print_manager.py          # Print formatting & preview
├── custom_font_dialog.py     # Font setting dialog
├── database_manager.py       # All SQLite operations
├── database/
│   └── estimation.db         # SQLite DB (auto-created if missing)
└── readme.md
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

- On first run, the `database/estimation.db` will be auto-created along with required tables.

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
...

## 👤 Author

Maintained by **Kartikey Agarwal**.


---

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

- **Known Issue:**  
  - Font settings are not applied when printing from Estimate History.

#### 3. ⏪ Reverted Features

- **Hotkeys (Ctrl+S/P/H)**  
- **UI spacing improvements**  
- **Conditional column behavior** (hide/show Wage/Pieces based on wage type)

---

### 🧪 Known Issues / TODO

- [ ] Fix font settings not applying in Estimate History print
- [ ] Re-add UI spacing, hotkeys, conditional columns
- [ ] Improve signal handling and float parsing for edge cases
- [ ] Replace fragile `item_code == bar_no` logic for bar tracking

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

| Feature               | Reason Reverted | File(s) Involved |
|----------------------|------------------|------------------|
| Keyboard Shortcuts   | Conflicted with other `QActions` | `main.py` |
| UI Spacing Changes   | Overlapped or broke compact layout | `estimate_entry_ui.py` |
| Conditional Columns  | Navigation bugs & blank entries | `estimate_entry_logic.py`, `estimate_entry_ui.py` |

---