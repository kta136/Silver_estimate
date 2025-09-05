# UI/UX Recommendations – Silver Estimation App

This document captures prioritized, actionable UI/UX improvements based on the current codebase.

Audience: developers working on this repo. Each item lists rationale, files to touch, and implementation hints.

Status Key
- Implemented: ✅
- Planned: 🔜
- Recommended: 💡

---

## 1) Primary Navigation
- Status: ✅ Implemented (QStackedWidget) + Lazy-load Item Master
- Files: `main.py`
- Notes:
  - Replaced show/hide with a central `QStackedWidget`. Item Master is created on demand inside `show_item_master()` to reduce startup cost and UI clutter.
  - Because Item Master is used infrequently, a persistent global toolbar was not enabled by default. See section 13 for an optional power-user toolbar toggle.

---

## 1.1) Primary Actions Toolbar (Contextual)
- Status: 💡 (optional, contextual in Estimate view)
- Why: Surface frequent actions (Save, Print, History, New, Silver Bars, Delete) for faster workflows in Estimate Entry without exposing Item Master constantly.
- Files: `estimate_entry.py` (add a small `QToolBar` or button row at top), `main.py` (optional View toggle)
- How:
  - Add a toolbar within Estimate view only, or keep the existing button row but add icons + mnemonics.
  - If desired globally, expose a Settings toggle (see section 13) so users can show/hide it.

---

## 2) Persist Window Geometry + State
- Status: ✅ Implemented
- Why: Restores the user’s last window size/position and (optionally) toolbar/menu states.
- Files: `main.py`
- How:
  - On start (end of `__init__`):
    ```python
    settings = QSettings(SETTINGS_ORG, SETTINGS_APP)
    if (geo := settings.value("ui/main_geometry")):
        self.restoreGeometry(geo)
    if (state := settings.value("ui/main_state")):
        self.restoreState(state)
    ```
  - On close (`closeEvent`):
    ```python
    settings = QSettings(SETTINGS_ORG, SETTINGS_APP)
    settings.setValue("ui/main_geometry", self.saveGeometry())
    settings.setValue("ui/main_state", self.saveState())
    settings.sync()
    ```

---

## 3) HiDPI Support
- Status: ✅ Implemented 
- Why: Sharper UI on high‑resolution displays.
- Files: `main.py`
- How: before creating `QApplication` in `safe_start_app()`:
  ```python
  from PyQt5.QtCore import Qt
  QApplication.setAttribute(Qt.AA_EnableHighDpiScaling)
  QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps)
  ```

---

## 4) Standard Shortcuts + Menus
- Status: ✅ Implemented
- Why: Consistency with platform conventions.
- Files: `main.py`
- Notes:
  - `Quit` uses `QKeySequence.Quit`.
  - `Save`/`Print` wired under File menu using `QKeySequence.Save`/`QKeySequence.Print` and call Estimate view actions.
  - Shortcut reliability: menu actions use `Qt.ApplicationShortcut`; duplicate per‑widget `QShortcut`/`QAction` bindings were removed to avoid “Ambiguous shortcut overload”.

---

## 4.2) Shortcut Reliability (Ctrl+S/Ctrl+P)
- Status: ✅ Implemented
- Why: Ensure hotkeys work while editing fields/table cells without conflicts.
- Files: `main.py`, `estimate_entry.py`
- Notes:
  - Centralize Save/Print to main menu actions with `Qt.ApplicationShortcut`.
  - Avoid attaching additional Ctrl+S/Ctrl+P shortcuts at widget level to prevent ambiguity.

---

## 4.1) View Menu (Stack Switching)
- Status: ✅ Implemented
- Why: Alternative to a global toolbar; lets users switch between views predictably.
- Files: `main.py`
- Notes: Added `&View` menu with two checkable actions; actions are kept in sync with the current stacked view.

---

## 5) Palette‑Aware Styling + Theme Support
- Status: ✅ Groundwork Implemented
- Why: Current inline styles use hardcoded colors; break in dark mode.
- Files: `estimate_entry_ui.py`, `estimate_entry.py`, `item_master.py`
- How:
  - Replaced explicit hex colors for the item table with palette roles (`palette(base)`, `palette(alternate-base)`, `palette(mid)`).
  - Removed hardcoded colors on mode indicators and key labels; use bold font styling instead of color for emphasis.
  - Next: extract to a theme manager and add a Settings toggle for “Dark Mode”.

---

## 6) Safer Destructive Actions
- Status: ✅ Implemented
- Why: Guardrails to prevent accidental data loss.
- Files: `estimate_entry_ui.py`, `estimate_entry_logic.py`, `estimate_entry.py`, `main.py`, `settings_dialog.py`
- How:
  - “Delete This Estimate” is disabled by default and becomes enabled only after loading an existing estimate.
  - “Delete All Data” now has a second explicit confirmation requiring typing `DELETE` after the initial warning.
  - Kept destructive actions grouped under Settings.

---

## 7) Labels and Tab Order (No Renames/Mnemonics)
- Status: ✅ Implemented (header + table focus)
- Why: Improve keyboard flow without renaming labels or adding mnemonics.
- Files: `estimate_entry_ui.py`, `item_master.py`
- How:
  - Kept existing button texts as-is (e.g., “LB”), no new mnemonics.
  - Added `QLabel.setBuddy(...)` for Voucher/Date/Silver Rate/Note.
  - Defined tab order: Voucher → Load → Date → Silver Rate → Note → Item Table.

---

## 8) Autocomplete and Pickers
- Status: 💡
- Why: Reduce typing; prevent invalid codes.
- Files: `estimate_entry.py`, `item_selection_dialog.py`
- How:
  - Add `QCompleter` to voucher number and code fields with database‑backed models.
  - Keep `ItemSelectionDialog` for discovery; invoke when code not found or ambiguous.

---

## 9) Locale & Currency Formatting
- Status: ✅ Implemented
- Why: Consistent display of currency and numbers.
- Files: `estimate_entry_logic.py`, `print_manager.py`
- How:
  - Centralized currency formatting via `QLocale.system().toCurrencyString(...)` with safe fallbacks.
  - Totals (Net Wage, Net Value, Grand Total) and printing (Last Balance, S.Cost, Total) now use localized currency strings.

---

## 10) Progress & Responsiveness
- Status: 🔜 In Progress (async import done)
- Why: Keep UI responsive during long ops (import/export/printing).
- Files: `settings_dialog.py`, `item_import_dialog.py`, `item_import_manager.py`, `print_manager.py`
- How:
  - Import now runs on a dedicated `QThread` (non‑blocking UI) with progress signals.
  - Print action disables the initiating button while preparing preview.
  - Next: add `QProgressDialog` or overlay for long print/exports and disable initiating buttons consistently.

---

## 11) Unify QSettings Usage
- Status: ✅ Implemented
- Why: Avoid fragmented preference keys.
- Files: `estimate_entry.py`, `settings_dialog.py`, `app_constants.py`
- Notes: All app QSettings now use `SETTINGS_ORG/SETTINGS_APP` constants (e.g., in `estimate_entry.py`, `settings_dialog.py`, `main.py`).

---

## 12) Totals Section Cleanup
- Status: ✅ Implemented
- Why: Improve theme compatibility and accessibility.
- Files: `estimate_entry_ui.py`
- How:
  - Replaced inline HTML with styled `QLabel` (bold/underline via font), keeping numeric labels right‑aligned.
  - Palette‑friendly styling for the totals area, avoiding hard‑coded colors.

---

## 13) Optional Power‑User Toolbar (Toggle)
- Status: 💡 (unchanged)
- Why: Some users prefer 1‑click access.
- Files: `main.py`, `settings_dialog.py`
- How:
  - Add a Settings toggle (View → Toolbar) to show/hide a minimal toolbar bound to the stack switching.
  - Default: off, given Item Master’s rare use.
  - If enabled, include actions: Save, Print, History, New, Silver Bars, Delete (icons + standard shortcuts).

---

## 14) Accessibility & Feedback
- Status: 💡 (partial improvements)
- Why: Improve clarity and trust.
- Files: app‑wide
- How:
  - Pending: caps‑lock indicator and show/hide toggles on login fields.
  - Current: status bar messaging and defensive disabling of destructive actions when not applicable.

---

## 14.1) Login & Security UX
- Status: 💡
- Why: Keep login focused; clarify destructive paths.
- Files: `login_dialog.py`, `settings_dialog.py`
- How:
  - Add show/hide password toggles, caps‑lock detection, and a basic strength meter in setup mode.
  - Prefer relocating wipe/reset to Settings > Data with clear copy and multi‑step confirmation; if keeping on the login screen, visually separate the destructive action.

---

## 15) Future: Model‑View for Scalability
- Status: 💡
- Why: Smooth performance with large tables.
- Files: `estimate_entry_ui.py`, `estimate_entry_logic.py`
- How:
  - Consider migrating `QTableWidget` → `QTableView` + custom model when row counts grow. Keep current approach for now if performance is fine.

---

## Suggested Implementation Order (Quick Wins First)
1) Safer destructive actions (6) – ✅
2) Tab order + buddies only (7) – ✅
3) Currency/locale formatting for totals (9) – ✅
4) Palette‑aware styling groundwork (5) – ✅ groundwork
5) Progress + async wrappers (10) – 🔜 (import async done)
6) Autocomplete/pickers (8)

---

## Implementation Summary (Current Sprint)
- Delete safeguards: Disabled Delete until an estimate is loaded; typed DELETE required for “Delete All Data”. Files: `estimate_entry_ui.py`, `estimate_entry_logic.py`, `estimate_entry.py`, `main.py`.
- Keyboard flow: Added label buddies and tab order in header; table focus kept. File: `estimate_entry_ui.py`.
- Currency formatting: Localized currency strings in UI totals and printing. Files: `estimate_entry_logic.py`, `print_manager.py`.
- Palette-friendly UI: Replaced hardcoded colors with palette roles and font emphasis. Files: `estimate_entry_ui.py`, `estimate_entry.py`.
- Responsiveness: Item import runs on a worker `QThread`; print button is disabled during preview generation. Files: `main.py`, `estimate_entry_logic.py`.
