# Project Learnings (Silver Estimate)

This file documents key learnings, decisions, and important information about the Silver Estimate project.
## Currency Formatting (April 24, 2025)

- **File:** `print_manager.py`
- **Change:** Corrected the `format_indian_rupees` function to properly implement comma separation according to the Indian numbering system (lakhs, crores). The previous implementation incorrectly used thousand separators.
- **Location:** The function is used to format the final Silver Cost and Total Cost on the printed estimate slip.
## Silver Bar Management Overhaul (vNext - April 24, 2025)

**Objective:** Rewrite the silver bar tracking and management system to use unique IDs, link bars to source estimates, and implement a list-based grouping/assignment system.

**Implementation Steps:**

1.  **Database Schema (`database_manager.py`):**
    *   **`silver_bars` Table:**
        *   Add `bar_id` (INTEGER PRIMARY KEY AUTOINCREMENT).
        *   Add `estimate_voucher_no` (TEXT/INTEGER, Foreign Key to `estimates.voucher_no`).
        *   Add `list_id` (INTEGER, Foreign Key to `silver_bar_lists.list_id`, nullable).
        *   Modify `status` field options (e.g., 'In Stock', 'Assigned', 'Sold', 'Melted').
        *   (Optional: Keep `bar_no` for user reference if needed, otherwise remove).
    *   **`silver_bar_lists` Table (New):**
        *   `list_id` (INTEGER PRIMARY KEY AUTOINCREMENT).
        *   `list_identifier` (TEXT, unique, e.g., "List-YYYYMMDD-HHMMSS").
        *   `list_note` (TEXT, nullable).
        *   `creation_date` (TEXT/TIMESTAMP).

2.  **Database Manager (`database_manager.py`):**
    *   Update `_create_tables` with the new schema.
    *   Modify `add_silver_bar` to accept `estimate_voucher_no` and insert new fields.
    *   Modify `get_silver_bars` for searching/filtering (weight, status, estimate_voucher_no) and return new fields.
    *   Modify `update_silver_bar_status` to handle list assignment/removal (setting `list_id`, updating `status`).
    *   Add `delete_silver_bars_for_estimate(voucher_no)` function.
    *   Add functions for list management:
        *   `create_silver_bar_list(identifier, note)`
        *   `get_silver_bar_lists()`
        *   `get_silver_bar_list_details(list_id)`
        *   `update_silver_bar_list_note(list_id, note)`
        *   `delete_silver_bar_list(list_id)` (consider unassigning bars first).
        *   `assign_bar_to_list(bar_id, list_id)`
        *   `remove_bar_from_list(bar_id)`
        *   `get_bars_in_list(list_id)`
        *   `get_available_bars()` (status='In Stock', list_id IS NULL).

3.  **Estimate Entry Logic (`estimate_entry_logic.py`):**
    *   Modify `save_estimate`:
        *   If updating an existing estimate (`voucher_no` exists), call `db_manager.delete_silver_bars_for_estimate(voucher_no)` first.
        *   After saving header/items, iterate through current silver bar line items and call `db_manager.add_silver_bar` for each, passing `voucher_no`.

4.  **Silver Bar Management GUI (`silver_bar_management.py`):**
    *   **Rewrite UI:**
        *   **Main View:** Table for available bars (inc. `bar_id`, `estimate_voucher_no`), weight search, "Create List" button, list selector.
        *   **List View:** Display selected list details (ID, Note), table for assigned bars, "Add Bars", "Remove Bars", "Print List", "Delete List" buttons.
        *   **Add Bars Dialog:** Show available bars, allow multi-selection, "Add Selected" button.
    *   **Implement Logic:** Connect UI to new `db_manager` functions, handle UI state changes, filtering, list operations.

5.  **Print Manager (`print_manager.py`):**
    *   Update `print_silver_bar_list_details` (or create new method) to use `list_id` and fetch/display data based on the new schema.
## Silver Bar Management Overhaul Implementation (April 24, 2025)

- **Objective:** Implemented the planned overhaul for silver bar management.
- **Files Modified:**
    - `database_manager.py`: Updated schema (`silver_bars`, `silver_bar_lists`, `bar_transfers`) and related methods (add, get, delete, list management, assign/remove).
    - `estimate_entry_logic.py`: Modified `save_estimate` to delete old bars and add new bars linked to the estimate voucher.
    - `silver_bar_management.py`: Rewrote the GUI with separate views for available and listed bars, implemented actions (create list, add/remove bars, edit note, delete list).
    - `print_manager.py`: Updated `_generate_list_details_html` to use the new data structure for list printing.
- **Key Changes:**
    - Bars now have unique `bar_id`.
    - Bars are linked to `estimate_voucher_no`.
    - List management system implemented using `silver_bar_lists` table and `list_id` foreign key.
    - GUI redesigned for the new workflow.

## Bug Fix: Silver Bar GUI Table Population (April 24, 2025)

- **File:** `silver_bar_management.py`
- **Function:** `_populate_table`
- **Issue:** An `AttributeError: 'sqlite3.Row' object has no attribute 'get'` occurred because the code incorrectly used the `.get()` method to access data from `sqlite3.Row` objects returned by the database manager.
- **Fix:** Modified the `_populate_table` function to use dictionary-style key access (e.g., `bar_row['column_name']`) which is the correct way to access data from `sqlite3.Row` objects. Added checks (`if 'column_name' in bar_row.keys() else default_value`) for robustness.
## Critical Fix: Schema Versioning to Prevent Data Loss (April 24, 2025)

- **Issue:** Silver bars were being deleted when the program was restarted because the `setup_database` method was unconditionally dropping and recreating the silver bar tables on every application startup.
- **File:** `database_manager.py`
- **Function:** `setup_database`
- **Fix:** 
  - Implemented a schema versioning system with a new `schema_version` table to track database migrations.
  - Added `_check_schema_version` and `_update_schema_version` helper methods.
  - Modified `setup_database` to only perform the schema migration (dropping and recreating tables) when the schema version is 0 (initial setup).
  - For subsequent startups (version >= 1), the method only ensures tables exist without dropping them.
  - This ensures that silver bar data persists across application restarts.
## Fix: Column Name Consistency in Print Manager (April 24, 2025)

- **Issue:** The `_generate_silver_bars_html_table` method in `print_manager.py` was using the old column name `bar_no` instead of the new `bar_id` from the updated schema, which would cause errors when printing the silver bar inventory.
- **File:** `print_manager.py`
- **Function:** `_generate_silver_bars_html_table`
- **Fix:** 
  - Updated the method to use the correct column names from the new schema (`bar_id` instead of `bar_no`).
  - Added the `estimate_voucher_no` column to the printed table to show the source estimate for each bar.
  - Added proper checks using `in bar.keys()` for safer access to sqlite3.Row objects.
  - Fixed indentation issues that were causing syntax errors.
## Fix: SQLite3.Row Access in List Details Printing (April 24, 2025)

- **Issue:** The `_generate_list_details_html` method in `print_manager.py` was using `.get()` method on `sqlite3.Row` objects, which was causing "sqlite3.row has no attribute get" errors when printing silver bar lists.
- **File:** `print_manager.py`
- **Function:** `_generate_list_details_html`
- **Fix:** 
  - Changed all instances of `.get()` to use dictionary-style access with `[]` notation.
  - Added proper checks using `in bar.keys()` for safer access to sqlite3.Row objects.
  - This ensures compatibility with both dictionary and sqlite3.Row objects when printing list details.
## Fix: Additional SQLite3.Row Access in Print Preview Title (April 24, 2025)

- **Issue:** Another instance of using `.get()` on a `sqlite3.Row` object was found in the `print_silver_bar_list_details` method when setting the preview window title, causing "sqlite3.row has no attribute get" errors.
- **File:** `print_manager.py`
- **Function:** `print_silver_bar_list_details`
- **Line:** 131
- **Fix:** 
  - Changed `.get('list_identifier', 'N/A')` to use dictionary-style access with proper checks:
  - `list_info['list_identifier'] if 'list_identifier' in list_info.keys() and list_info['list_identifier'] is not None else 'N/A'`
  - This ensures compatibility with sqlite3.Row objects when setting the print preview window title.
## UI Improvements to Silver Bar Management Dialog (April 24, 2025)

- **File:** `silver_bar_management.py`
- **Improvements:**
  1. **Removed Timestamps:** 
     - Removed time portion from date display in list selection dropdown
     - Shows only the date part (YYYY-MM-DD) for cleaner presentation
  2. **Added Totals Display:**
     - Added summary labels showing totals for both available bars and list bars
     - Each summary shows: bar count, total weight, and total fine weight
     - Updates dynamically when tables are populated
  3. **Enhanced List Selection:**
     - Added list notes to the dropdown items for easier identification
     - Format: "List-ID (Date) - Note" when a note exists
  4. **Improved Note Handling:**
     - Updated the combo box text update logic when editing notes
     - Ensures consistent display format across the UI
## Critical Fix: Preserve Silver Bars in Lists When Saving Estimates (April 24, 2025)

- **Issue:** When saving an estimate again, all silver bars associated with that estimate were being deleted from the database, even if they were assigned to a list in the silver bar management dialog. This caused bars to disappear from lists unexpectedly.
- **File:** `database_manager.py`
- **Function:** `delete_silver_bars_for_estimate`
- **Fix:** 
  - Modified the function to only delete silver bars that are not assigned to a list (`list_id IS NULL`)
  - Added a check to count and report how many bars are in lists and will be preserved
  - Updated the function's documentation to clarify its behavior
  - This ensures that silver bars remain in their assigned lists even when the source estimate is modified and saved again
## Enhanced Fix: Preserve Silver Bars in Lists When Editing Estimates (April 24, 2025)

- **Issue:** Even after fixing the `delete_silver_bars_for_estimate` method, there was still an issue with the estimate saving process. When editing an estimate that had silver bars assigned to lists, those bars would be preserved in the database but would not be reflected in the saved estimate data.
- **File:** `estimate_entry_logic.py`
- **Function:** `save_estimate`
- **Fix:** 
  - Enhanced the save process to be aware of silver bars that are in lists
  - Added code to check and report the number of bars in lists before saving
  - Modified the silver bar creation logic to account for existing bars in lists
  - Added more detailed logging to help track what's happening with silver bars during the save process
  - This ensures that when an estimate is edited and saved again, it properly maintains the relationship with any silver bars that were previously assigned to lists
## Major Change: Silver Bars Are Now Permanent (April 24, 2025)

- **Issue:** Despite previous fixes, silver bars were still being affected when editing estimates. The fundamental problem was the approach of deleting and recreating silver bars during the estimate save process.
- **Solution:** Completely changed the silver bar lifecycle model:
  - Silver bars are now **permanent** once created
  - They are never automatically deleted when editing or saving estimates
  - They can only be managed through the Silver Bar Management interface
  - This is a fundamental architectural change to ensure data integrity

- **Files Modified:**
  1. **database_manager.py**:
     - Converted `delete_silver_bars_for_estimate` to a no-op function that only reports information
     - The function now returns success without deleting anything
     - Added detailed comments explaining the new approach

  2. **estimate_entry_logic.py**:
     - Removed all code that attempted to delete silver bars before saving
     - Simplified the save process to only add new silver bars
     - Maintained compatibility with the existing API

- **Benefits:**
  - Silver bars will never be unexpectedly removed from lists
  - Data integrity is preserved across estimate edits
  - The separation of concerns is clearer: estimates create bars, the bar management interface manages them
## Critical Fix: Prevent Cascade Deletion of Silver Bars (April 24, 2025)

- **Root Cause Identified:** We found the fundamental issue causing silver bars to be deleted when saving estimates. The problem was in the database schema and the save method:
  1. The `silver_bars` table has a foreign key constraint with `ON DELETE CASCADE` to the `estimates` table
  2. The `save_estimate_with_returns` method was using `INSERT OR REPLACE` to update estimates
  3. SQLite internally performs a DELETE followed by an INSERT when using `INSERT OR REPLACE`
  4. This DELETE operation was triggering the CASCADE constraint, causing all silver bars to be deleted automatically by the database engine

- **File:** `database_manager.py`
- **Function:** `save_estimate_with_returns`
- **Fix:** 
  - Completely rewrote the save method to avoid triggering the CASCADE constraint
  - Added a check to determine if the estimate exists
  - For existing estimates, use explicit UPDATE instead of INSERT OR REPLACE
  - For new estimates, use regular INSERT
  - This prevents the database engine from automatically deleting silver bars through the CASCADE constraint
  - Added detailed logging to track the save process

- **Benefits:**
  - Silver bars are now truly permanent and will never be deleted when saving estimates
  - The fix addresses the issue at its root cause in the database layer
  - No changes to the database schema were required, making this a non-invasive fix
## Fix: Prevent Duplicate Silver Bars When Saving Estimates (April 24, 2025)

- **Issue:** After fixing the cascade deletion problem, we encountered another issue: when saving an estimate multiple times, new silver bars were being created each time, resulting in duplicate bars for the same estimate.
- **File:** `estimate_entry_logic.py`
- **Function:** `save_estimate`
- **Fix:** 
  - Added a check to see if silver bars already exist for the estimate before creating new ones
  - Only create new silver bars if none exist for the estimate
  - Added informative messages to notify the user when silver bars are not being created because they already exist
  - This ensures that each estimate has a consistent set of silver bars, regardless of how many times it's saved

- **Complete Silver Bar Lifecycle:**
  1. Silver bars are created only once when an estimate is first saved
  2. They are never automatically deleted when the estimate is edited or saved again
  3. They can only be managed through the Silver Bar Management interface
  4. This provides a clean, predictable lifecycle that preserves data integrity
## Change in Approach: Comprehensive Deletion of Estimates and Related Data (April 24, 2025)

- **Requirement Change:** After implementing the "permanent silver bars" approach, the requirement changed to ensure that when an estimate is deleted, all associated data (including silver bars and potentially empty lists) should also be deleted.
- **File:** `database_manager.py`
- **Function:** `delete_single_estimate`
- **Implementation:** 
  - Completely rewrote the `delete_single_estimate` method to handle comprehensive deletion
  - The new method now:
    1. Identifies all silver bars associated with the estimate
    2. Tracks which lists contain these bars
    3. Deletes all the silver bars (which also deletes related transfers due to CASCADE)
    4. Deletes the estimate items and header
    5. Checks each affected list to see if it's now empty
    6. Deletes any lists that no longer contain any bars
  - Added detailed logging to track the deletion process

- **New Data Lifecycle:**
  - Silver bars are created when an estimate is saved (only once)
  - They are preserved when an estimate is edited or saved again
  - They are deleted when their parent estimate is deleted
  - Lists that become empty due to bar deletion are also removed
  - This provides a clean, consistent approach to data management
## Fix: Add Note Column to Existing Databases (April 24, 2025)

- **Issue:** After adding the note feature, users with existing databases encountered an error: "DB error saving estimate: no such column: note"
- **Root Cause:** The note column was added to the CREATE TABLE statement for new databases, but not to existing databases
- **File:** `database_manager.py`
- **Function:** `setup_database`
- **Fix:** 
  - Added code to check if the note column exists in the estimates table
  - If it doesn't exist, execute an ALTER TABLE statement to add it
  - This ensures that both new and existing databases will have the note column
  - The fix is applied automatically when the application starts
## UI Improvements for Estimate Notes (April 24, 2025)

- **Issue:** The note feature needed UI improvements for better visibility and usability
- **Files Modified:**
  - `estimate_history.py`:
    - Increased window size to 1000x600 for better readability
    - Moved note column next to date column for better visibility
  - `print_manager.py`:
    - Added note display on the same line as "ESTIMATE SLIP ONLY" title
    - Keeps the title centered while adding the note after it
    - Implemented intelligent truncation for long notes
    - Only displays notes when they exist
    - No "Note:" prefix for cleaner appearance
- **Benefits:**
  - Better visibility of notes in the estimate history
  - Improved print layout with notes prominently displayed
  - More user-friendly interface with larger history window
  - Cleaner print layout with note integrated into the header
## Last Balance Feature Implementation (April 24, 2025)

- **Feature:** Added ability to include previous balance in estimates
- **Files Modified:**
  - `database_manager.py`: 
    - Added last_balance_silver and last_balance_amount columns to estimates table
    - Implemented automatic schema migration for existing databases
    - Updated save_estimate_with_returns to handle last balance values
  - `estimate_entry_ui.py`:
    - Added "LB" button to the estimate entry screen
  - `estimate_entry_logic.py`:
    - Added show_last_balance_dialog method to prompt for last balance values
    - Connected LB button to the dialog
    - Updated calculate_totals to include last balance in calculations
    - Updated save_estimate to store last balance values
    - Updated load_estimate to load last balance values
  - `print_manager.py`:
    - Added last balance section to printed estimate (displayed before final section)
    - Combined silver weight and amount on a single line for cleaner presentation
    - Properly included last balance in all final calculations
    - Fixed calculation: last balance silver is added to fine silver, last balance amount is added to wage
  - `readme.md`:
    - Updated documentation to reflect new feature
    - Incremented version number to 1.54
- **Benefits:**
  - Allows tracking of previous balances in estimates
  - Provides clear visibility of last balance in printed output
  - Automatically includes last balance in total calculations