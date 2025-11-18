# Estimate Entry Widget - Smoke Test Checklist

**Widget**: `EstimateEntryWidget`
**Purpose**: Manual testing checklist to verify core functionality before and after refactoring
**Last Updated**: 2025-11-01

---

## Prerequisites

- [ ] Application is built and running
- [ ] Database is initialized with test data
- [ ] At least 5 test items exist in the item master
- [ ] At least 2 existing estimates exist in the database
- [ ] Silver rate is configured (e.g., 75,000)

---

## Test Environment Setup

### Test Data Required

**Test Items** (in Item Master):
1. `RING001` - Gold Ring (Purity: 91.6%)
2. `NECK001` - Gold Necklace (Purity: 75%)
3. `BRAC001` - Gold Bracelet (Purity: 91.6%)
4. `ANKL001` - Silver Anklet (Purity: 92.5%)
5. `BAR001` - Silver Bar (Purity: 99.9%)

**Existing Estimates**:
- At least 2 saved estimates with different voucher numbers

---

## Core Workflow Tests

### Test 1: New Estimate Creation

**Objective**: Verify basic estimate entry workflow

1. **Start New Estimate**
   - [ ] Launch application
   - [ ] Verify estimate entry screen loads
   - [ ] Verify new voucher number is auto-generated
   - [ ] Verify format: `EST-YYYY-####` or similar
   - [ ] Verify current date is pre-filled
   - [ ] Verify one empty row exists in table
   - [ ] Verify focus is on Code column (row 0, col 0)
   - [ ] Verify delete button is disabled

2. **Enter First Item**
   - [ ] Type `RING001` in Code column
   - [ ] Press Enter
   - [ ] Verify item name populates automatically
   - [ ] Verify focus moves to Gross Weight column
   - [ ] Enter gross weight: `10.500`
   - [ ] Press Tab
   - [ ] Enter poly weight: `0.300`
   - [ ] Press Tab
   - [ ] Verify Net Weight is auto-calculated (10.500 - 0.300 = 10.200)
   - [ ] Verify Purity auto-fills from item master (91.6)
   - [ ] Press Tab to Wage Rate
   - [ ] Enter wage rate: `250.00`
   - [ ] Press Tab to Pieces
   - [ ] Enter pieces: `2`
   - [ ] Press Tab or Enter
   - [ ] Verify Wage Amount is auto-calculated (10.200 × 250.00 × 2 = expected)
   - [ ] Verify Fine Weight is auto-calculated (10.200 × 0.916 = 9.343)
   - [ ] Verify Type column shows "Regular"

3. **Add Second Item**
   - [ ] Verify new empty row was added automatically
   - [ ] Verify focus moved to Code column of new row
   - [ ] Type `NECK001` in Code column
   - [ ] Press Enter
   - [ ] Complete entry with test values
   - [ ] Verify calculations update correctly

4. **Verify Totals**
   - [ ] Verify totals panel updates automatically
   - [ ] Check Gross Weight total
   - [ ] Check Net Weight total
   - [ ] Check Fine Weight total
   - [ ] Check Wage Amount total
   - [ ] Verify totals match sum of individual rows

5. **Save Estimate**
   - [ ] Add a note in the Note field (e.g., "Test Estimate 1")
   - [ ] Click Save button (or press Ctrl+S from menu)
   - [ ] Verify success message appears
   - [ ] Verify "Unsaved changes" badge disappears
   - [ ] Verify delete button becomes enabled
   - [ ] Verify window modified indicator clears

**Expected Result**: Estimate is saved successfully with all calculations correct

---

### Test 2: Load Existing Estimate

**Objective**: Verify loading saved estimates

1. **Load by Voucher Number**
   - [ ] Clear current form (Ctrl+N or New button)
   - [ ] Confirm discard if prompted
   - [ ] Enter existing voucher number in voucher field
   - [ ] Press Enter or click Load button
   - [ ] Verify estimate loads completely:
     - [ ] Voucher number matches
     - [ ] Date matches
     - [ ] Note matches
     - [ ] All rows populated with correct data
     - [ ] Calculations are correct
     - [ ] Totals match
   - [ ] Verify delete button is enabled
   - [ ] Verify no "unsaved changes" badge

2. **Load via History Dialog**
   - [ ] Click History button (or press Ctrl+H)
   - [ ] Verify history dialog opens
   - [ ] Verify list shows all saved estimates
   - [ ] Select an estimate from the list
   - [ ] Click OK or double-click
   - [ ] Verify estimate loads correctly
   - [ ] Verify all fields populated

**Expected Result**: Estimates load completely and accurately

---

### Test 3: Edit Existing Estimate

**Objective**: Verify modification and re-saving

1. **Load and Modify**
   - [ ] Load an existing estimate
   - [ ] Modify gross weight of first item
   - [ ] Press Tab to trigger calculation
   - [ ] Verify Net Weight recalculates
   - [ ] Verify Fine Weight recalculates
   - [ ] Verify Wage Amount recalculates
   - [ ] Verify totals update
   - [ ] Verify "Unsaved changes" badge appears

2. **Save Changes**
   - [ ] Click Save button
   - [ ] Verify success message
   - [ ] Verify "Unsaved changes" badge disappears

3. **Reload and Verify**
   - [ ] Note the voucher number
   - [ ] Clear form (Ctrl+N)
   - [ ] Reload the same voucher
   - [ ] Verify changes were persisted correctly

**Expected Result**: Modifications are saved and persisted

---

### Test 4: Delete Estimate

**Objective**: Verify estimate deletion

1. **Delete Loaded Estimate**
   - [ ] Load an existing estimate
   - [ ] Verify delete button is enabled
   - [ ] Click Delete button
   - [ ] Verify confirmation dialog appears
   - [ ] Click Yes/OK to confirm
   - [ ] Verify success message appears
   - [ ] Verify form clears
   - [ ] Verify new voucher number is generated

2. **Verify Deletion**
   - [ ] Open History dialog (Ctrl+H)
   - [ ] Verify deleted estimate is NOT in the list
   - [ ] Try to load deleted voucher manually
   - [ ] Verify appropriate error message

**Expected Result**: Estimate is deleted and cannot be reloaded

---

### Test 5: Return Mode

**Objective**: Verify return item entry mode

1. **Enable Return Mode**
   - [ ] Start with new estimate or clear form
   - [ ] Press Ctrl+R or click Return Mode toggle
   - [ ] Verify mode indicator shows "Return Items"
   - [ ] Verify UI reflects return mode (if visual changes exist)

2. **Enter Return Item**
   - [ ] Enter item code (e.g., `RING001`)
   - [ ] Complete item entry with values
   - [ ] Verify Type column shows "Return" (not "Regular")
   - [ ] Verify calculations work correctly
   - [ ] Verify negative values if applicable

3. **Toggle Back to Regular**
   - [ ] Press Ctrl+R again
   - [ ] Verify mode indicator shows regular mode
   - [ ] Add another row
   - [ ] Verify Type column shows "Regular"

4. **Save Mixed Estimate**
   - [ ] Ensure estimate has both Regular and Return items
   - [ ] Save estimate
   - [ ] Reload estimate
   - [ ] Verify Return rows still marked as "Return"

**Expected Result**: Return mode correctly marks items and calculations work

---

### Test 6: Silver Bar Mode

**Objective**: Verify silver bar entry mode

1. **Enable Silver Bar Mode**
   - [ ] Clear form or start new estimate
   - [ ] Press Ctrl+B (or Ctrl+Shift+S if changed)
   - [ ] Verify mode indicator shows "Silver Bars"

2. **Enter Silver Bar Item**
   - [ ] Enter silver bar code (e.g., `BAR001`)
   - [ ] Complete entry
   - [ ] Verify Type column shows "Silver Bar"
   - [ ] Verify calculations work correctly

3. **Save and Reload**
   - [ ] Save estimate with silver bar items
   - [ ] Reload estimate
   - [ ] Verify silver bar rows marked correctly

**Expected Result**: Silver bar mode works correctly

---

### Test 7: Item Code Lookup

**Objective**: Verify item lookup functionality

1. **Direct Code Entry**
   - [ ] Type existing item code (e.g., `RING001`)
   - [ ] Press Enter
   - [ ] Verify item loads automatically
   - [ ] Verify name, purity, and wage type populate

2. **Code Not Found - Selection Dialog**
   - [ ] Type non-existent code (e.g., `XXXXX`)
   - [ ] Press Enter
   - [ ] Verify item selection dialog opens
   - [ ] Verify dialog shows filtered results (if partial match)
   - [ ] Select an item from the dialog
   - [ ] Verify item populates in the row
   - [ ] Verify code is updated to selected item code

3. **Cancel Selection Dialog**
   - [ ] Type non-existent code
   - [ ] Press Enter
   - [ ] Click Cancel in selection dialog
   - [ ] Verify row remains empty
   - [ ] Verify focus stays on Code column

**Expected Result**: Item lookup and fallback dialog work correctly

---

### Test 8: Row Management

**Objective**: Verify adding and deleting rows

1. **Auto-Add Empty Row**
   - [ ] Start with one row
   - [ ] Complete first row entry
   - [ ] Press Enter/Tab past last column
   - [ ] Verify new empty row is added automatically
   - [ ] Verify focus moves to new row's Code column

2. **Delete Row (Keyboard)**
   - [ ] Have at least 3 rows
   - [ ] Click on row 2 to select it
   - [ ] Press Ctrl+D
   - [ ] Verify row 2 is deleted
   - [ ] Verify remaining rows shift up
   - [ ] Verify totals recalculate

3. **Delete Last Row**
   - [ ] Delete all rows except one
   - [ ] Verify at least one empty row always remains

4. **Clear All Rows**
   - [ ] Click "New" button (or Ctrl+N)
   - [ ] Confirm discard if prompted
   - [ ] Verify all rows cleared
   - [ ] Verify one empty row exists
   - [ ] Verify new voucher number generated

**Expected Result**: Row management works correctly

---

### Test 9: Keyboard Navigation

**Objective**: Verify keyboard shortcuts and navigation

1. **Tab Navigation**
   - [ ] Enter Code
   - [ ] Press Tab to move to Item Name (if editable) or Gross
   - [ ] Continue pressing Tab through all columns
   - [ ] Verify focus moves correctly through editable columns
   - [ ] Verify skips calculated/read-only columns

2. **Shift+Tab (Reverse)**
   - [ ] Navigate to middle of row
   - [ ] Press Shift+Tab
   - [ ] Verify focus moves backward correctly

3. **Enter Key**
   - [ ] In Code column: Press Enter
   - [ ] Verify item lookup triggered
   - [ ] In other columns: Press Enter
   - [ ] Verify moves to next cell (similar to Tab)

4. **Backspace in Code Column**
   - [ ] Navigate to Code column (not first cell)
   - [ ] Ensure column is empty
   - [ ] Press Backspace
   - [ ] Verify focus moves to previous row's last editable column

5. **Keyboard Shortcuts**
   - [ ] Test Ctrl+R (Toggle Return Mode)
   - [ ] Test Ctrl+B (Toggle Silver Bar Mode)
   - [ ] Test Ctrl+D (Delete Current Row)
   - [ ] Test Ctrl+H (Open History Dialog)
   - [ ] Test Ctrl+N (New Estimate/Clear Form)

**Expected Result**: All keyboard navigation and shortcuts work

---

### Test 10: Calculations

**Objective**: Verify all automatic calculations

1. **Net Weight Calculation**
   - [ ] Enter Gross: 50.000
   - [ ] Enter Poly: 1.500
   - [ ] Verify Net = 48.500

2. **Fine Weight Calculation**
   - [ ] With Net: 48.500
   - [ ] With Purity: 91.6
   - [ ] Verify Fine ≈ 44.426 (48.5 × 0.916)

3. **Wage Amount Calculation**
   - [ ] With Net: 48.500
   - [ ] With Wage Rate: 300.00
   - [ ] With Pieces: 1
   - [ ] Verify Wage = 14,550.00 (48.5 × 300 × 1)
   - [ ] Change Pieces to 2
   - [ ] Verify Wage = 29,100.00

4. **Totals Calculation**
   - [ ] Enter 3 rows with different values
   - [ ] Manually verify:
     - [ ] Total Gross = sum of all gross weights
     - [ ] Total Net = sum of all net weights
     - [ ] Total Fine = sum of all fine weights
     - [ ] Total Wage = sum of all wage amounts
   - [ ] Verify totals update in real-time as values change

5. **Decimal Precision**
   - [ ] Enter value with many decimals (e.g., 12.3456789)
   - [ ] Verify proper rounding in calculations
   - [ ] Verify display precision matches expectations

**Expected Result**: All calculations are accurate

---

### Test 11: Column Management

**Objective**: Verify column width persistence and reset

1. **Resize Columns**
   - [ ] Resize Item Name column wider
   - [ ] Resize Gross Weight column narrower
   - [ ] Close and reopen application
   - [ ] Verify column widths are restored

2. **Reset Column Layout**
   - [ ] Resize several columns
   - [ ] Right-click on table header
   - [ ] Select "Reset Column Layout"
   - [ ] Verify columns return to default widths

3. **Window Resize**
   - [ ] Resize main window to smaller size
   - [ ] Verify Item Name column adjusts (if stretch enabled)
   - [ ] Resize main window to larger size
   - [ ] Verify layout adapts correctly

**Expected Result**: Column management works and persists

---

### Test 12: Font Size Customization

**Objective**: Verify font size changes persist

1. **Table Font Size**
   - [ ] Open Settings dialog
   - [ ] Go to font settings
   - [ ] Change table font size to 12
   - [ ] Apply changes
   - [ ] Verify table text size increases
   - [ ] Restart application
   - [ ] Verify font size is restored

2. **Breakdown Font Size**
   - [ ] Change breakdown panel font size
   - [ ] Verify change applies
   - [ ] Verify persists across restarts

3. **Final Calculation Font Size**
   - [ ] Change final calc font size
   - [ ] Verify change applies
   - [ ] Verify persists across restarts

**Expected Result**: Font sizes are customizable and persistent

---

### Test 13: Print Functionality

**Objective**: Verify print preview and printing

1. **Print Current Estimate**
   - [ ] Load or create an estimate with data
   - [ ] Click Print button (or Ctrl+P from menu)
   - [ ] Verify print preview dialog opens
   - [ ] Verify estimate details are formatted correctly
   - [ ] Verify all rows visible
   - [ ] Verify totals visible
   - [ ] Click Print or Cancel
   - [ ] Verify no errors occur

2. **Print Empty Estimate**
   - [ ] Clear form
   - [ ] Try to print
   - [ ] Verify appropriate warning or empty print preview

**Expected Result**: Print functionality works correctly

---

### Test 14: Unsaved Changes Tracking

**Objective**: Verify unsaved changes detection

1. **Track Changes**
   - [ ] Load an estimate
   - [ ] Verify no "unsaved changes" badge
   - [ ] Modify any value
   - [ ] Verify "unsaved changes" badge appears
   - [ ] Verify window modified indicator (asterisk in title)

2. **Discard Changes Warning**
   - [ ] With unsaved changes present
   - [ ] Try to load another estimate
   - [ ] Verify warning dialog appears
   - [ ] Click No/Cancel
   - [ ] Verify current estimate remains
   - [ ] Try to load again
   - [ ] Click Yes/OK
   - [ ] Verify new estimate loads

3. **Clear Changes Flag on Save**
   - [ ] Make changes
   - [ ] Verify badge appears
   - [ ] Save estimate
   - [ ] Verify badge disappears
   - [ ] Verify window modified indicator clears

**Expected Result**: Unsaved changes tracking works correctly

---

### Test 15: Silver Bar Management Integration

**Objective**: Verify silver bar management dialog access

1. **Open Silver Bar Management**
   - [ ] Click button/menu to open silver bar management
   - [ ] Verify dialog opens
   - [ ] Verify separate interface for silver bars
   - [ ] Close dialog
   - [ ] Verify returns to estimate entry

**Expected Result**: Silver bar management is accessible

---

### Test 16: Status Messages

**Objective**: Verify status message display

1. **Inline Status Messages**
   - [ ] Perform actions that trigger status messages:
     - [ ] Save estimate (success message)
     - [ ] Load estimate (success message)
     - [ ] Delete estimate (success message)
     - [ ] Enter invalid item code (error message)
   - [ ] Verify messages appear in status label
   - [ ] Verify messages disappear after timeout (~3 seconds)

2. **Error Messages**
   - [ ] Trigger error conditions (e.g., load non-existent voucher)
   - [ ] Verify error messages display
   - [ ] Verify error level styling (if applicable)

**Expected Result**: Status messages display correctly

---

### Test 17: Edge Cases and Error Handling

**Objective**: Test boundary conditions and error scenarios

1. **Empty Fields**
   - [ ] Leave Gross Weight empty
   - [ ] Try to calculate
   - [ ] Verify graceful handling (0 or validation message)

2. **Invalid Values**
   - [ ] Enter negative gross weight
   - [ ] Verify validation prevents or handles
   - [ ] Enter letters in numeric fields
   - [ ] Verify validation prevents

3. **Large Values**
   - [ ] Enter very large numbers (e.g., 999999.999)
   - [ ] Verify calculations don't overflow
   - [ ] Verify display doesn't break layout

4. **Many Rows**
   - [ ] Add 50+ rows
   - [ ] Verify scrolling works
   - [ ] Verify calculations remain accurate
   - [ ] Verify save/load works with many rows

5. **Database Errors**
   - [ ] (If possible) Simulate database unavailable
   - [ ] Verify graceful error messages
   - [ ] Verify application doesn't crash

**Expected Result**: Edge cases handled gracefully

---

## Performance Tests

### Test 18: Responsiveness

**Objective**: Verify UI remains responsive

1. **Large Estimate**
   - [ ] Create estimate with 100+ rows
   - [ ] Modify values
   - [ ] Verify totals update without lag
   - [ ] Verify scrolling is smooth

2. **Rapid Input**
   - [ ] Rapidly change values in multiple cells
   - [ ] Verify calculations update correctly
   - [ ] Verify no data loss or corruption

**Expected Result**: UI remains responsive under load

---

## Regression Test Summary

After refactoring, re-run all tests above and check:

- [ ] All functional tests pass
- [ ] No performance degradation
- [ ] No visual regressions (layout, fonts, spacing)
- [ ] All keyboard shortcuts work
- [ ] All calculations remain accurate
- [ ] Settings persistence works
- [ ] Error handling unchanged

---

## Test Result Template

| Test # | Test Name | Status | Notes | Tester | Date |
|--------|-----------|--------|-------|--------|------|
| 1 | New Estimate Creation | ⬜ | | | |
| 2 | Load Existing Estimate | ⬜ | | | |
| 3 | Edit Existing Estimate | ⬜ | | | |
| 4 | Delete Estimate | ⬜ | | | |
| 5 | Return Mode | ⬜ | | | |
| 6 | Silver Bar Mode | ⬜ | | | |
| 7 | Item Code Lookup | ⬜ | | | |
| 8 | Row Management | ⬜ | | | |
| 9 | Keyboard Navigation | ⬜ | | | |
| 10 | Calculations | ⬜ | | | |
| 11 | Column Management | ⬜ | | | |
| 12 | Font Size Customization | ⬜ | | | |
| 13 | Print Functionality | ⬜ | | | |
| 14 | Unsaved Changes Tracking | ⬜ | | | |
| 15 | Silver Bar Management | ⬜ | | | |
| 16 | Status Messages | ⬜ | | | |
| 17 | Edge Cases | ⬜ | | | |
| 18 | Responsiveness | ⬜ | | | |

**Legend**: ⬜ Not Tested | ✅ Pass | ❌ Fail | ⚠️ Partial

---

## Issues Found

| Issue # | Test # | Description | Severity | Status |
|---------|--------|-------------|----------|--------|
| | | | | |

**Severity Levels**: Critical | High | Medium | Low

---

**Document Version**: 1.0
**Created**: 2025-11-01
**Phase**: 1.2 - Snapshot & Guardrails
