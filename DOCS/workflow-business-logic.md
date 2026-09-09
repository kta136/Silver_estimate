# Workflow & Business Logic - Silver Estimation App

## Core Business Processes

### 1. Estimate Creation Workflow

#### Process Flow
1. Generate/Enter voucher number
2. Set silver rate and date
3. Add line items (Regular/Return/Silver Bar)
4. System calculates totals automatically
5. Save estimate → Creates silver bars if applicable
6. Open print preview automatically
7. Clear form for new estimate

#### Calculation Logic
```
Net Weight = Gross Weight - Poly Weight
Fine Weight = Net Weight × (Purity% / 100)
Wage Amount = PC: Pieces × Rate | WT: Net Weight × Rate
Net Fine = Regular Fine - Return Fine - Silver Bar Fine
Net Wage = Regular Wage - Return Wage - Silver Bar Wage (usually 0)
Grand Total = (Net Fine × Silver Rate) + Net Wage + Last Balance Amount
```

### 2. Item Management Workflow

#### Item Creation
1. Validate unique code (uppercase)
2. Set name, purity, wage type/rate
3. Prevent duplicates
4. Set defaults for empty fields

#### Item Usage
1. Code entry → Lookup or selection dialog
2. Auto-populate item details
3. Override purity/wage if needed
4. Navigate to next editable field

### 3. Silver Bar Management

#### Bar Creation
1. Created automatically from estimate silver bar items
2. One bar per line item
3. Linked to source estimate
4. Default status: 'In Stock'

#### List Management
1. Create lists with unique identifiers
2. Assign bars to lists
3. Track status changes
4. Generate transfer records
5. Mark lists as issued when dispatched (sets `issued_date` and moves them to history view)
6. Reactivate issued lists to return bars to active status (clears `issued_date`, resets bar statuses)

#### Bar Lifecycle
```
Creation → In Stock → Assigned to List → Issued
                       ↘ Unassigned → In Stock
                       ↘ Sold
Issued list → Reactivated → Assigned
```

### 4. Authentication and Security

#### Login Flow
1. Check the operating-system credential store for existing password hashes
2. First run: Dual password setup
3. Subsequent runs: Verify main password
4. Secondary password triggers data wipe

#### Data Protection
1. Direct SQLCipher page encryption for the live database, WAL, and journals
2. Authenticated canonical metadata and ordered 1 MiB chunks
3. Argon2id key derivation once per normal startup
4. Argon2id parameters and salt stored in the authenticated envelope header
5. Marked, permission-restricted temporary decrypted files during the session

### 5. Catalog Backup Processes

#### Item Import
1. Read native `.seitems.json` catalog backup
2. Validate the file signature and schema version
3. Validate every item record before applying any changes
4. Update existing item codes and insert missing ones atomically

#### Item Export
1. Generate native `.seitems.json` catalog backup
2. Include format/version metadata
3. Export all items in catalog
4. Preserve round-trip import fidelity

## Business Rules

### 1. Estimate Rules
- Voucher numbers must be unique
- Return items reduce totals
- Silver bars create inventory records
- Last balance adds to final calculation
- Notes persist with estimates

### 2. Item Master Rules
- Codes must be unique and uppercase
- Numeric Purity/Tunch must be finite and non-negative; values above 100% are valid.
- Wage types: PC (per piece) or WT (per weight)
- Catalog deletion preserves saved estimate details; incomplete snapshots block removal

### 3. Silver Bar Rules
- Created only on first estimate save
- Permanent once created
- Status tracking mandatory
- List assignment exclusive
- Transfer history maintained

### 4. Calculation Rules
- All weights in grams
- Purity as percentage
- Wage rates in rupees
- Rounding: 2 decimals for weights and money
- Indian number formatting for display

Calculation precision policy:
- Numeric Purity/Tunch is a commercial calculation multiplier, not a physical
  purity constraint. Do not cap, clamp, reject, or rescale it at 100% in item entry,
  catalog backup/import, estimate entry/save/reload, inventory, or printing.
  For example, net weight `10.00 g` at `125.50%` produces fine weight `12.55 g`.
  Fine weight may therefore exceed net weight. Reject negative values, NaN, and
  infinity; retain the entered finite percentage and the existing `/ 100` formula.
- The separate optional `tunch` catalog field is free text (for example
  `125.50% + loss`), retained in saved print snapshots. It has no percentage cap
  and does not drive calculations; the numeric `purity` field does.
- Gross/poly inputs and computed net/fine weights use 2 decimal places in grams.
  Purity percentages and monetary rates use 2 decimal places; pieces are integers.
- New line calculations use decimal arithmetic. Net weight is gross minus poly,
  clamped at zero and rounded to 2 decimals. Fine weight is net weight times purity
  divided by 100, rounded to 2 decimals. WT wages use net weight times wage rate;
  PC wages use pieces times wage rate. Both wage results round to 2 decimals.
- Halfway values round away from zero (`ROUND_HALF_UP`): `1.235 g` becomes
  `1.24 g`, `₹10.125` becomes `₹10.13`, and `-₹10.125` becomes `-₹10.13`.
  Rounded zero is displayed without a negative sign.
- Totals add the recorded line values. Carried silver and cash can be positive or
  negative. Silver cost rounds to 2 decimals after applying the carried silver and
  rate; the final monetary total rounds to 2 decimals after wages and carried cash.
  A zero/non-positive silver rate contributes no silver cost.
- Entry, History and print summaries display weights and monetary values to 2
  decimals. Within each estimate print section, Modern omits `.00`
  from a numeric column only if all its rows and its subtotal round to whole
  numbers at 2 decimals. Otherwise every populated cell uses 2 decimals, including
  across page breaks. Blank cells stay blank.
  Formatters do not overwrite stored row values. Inventory created or
  updated by an estimate uses that line's recorded fine weight.
- Loading, printing or changing only a note does not recalculate historical line
  amounts. Editing a line's calculation inputs applies the current policy to that
  line. Existing amounts previously rounded away cannot be recovered automatically.

### 5. Navigation Rules
- Tab/Enter moves to next logical field
- Backspace in empty field moves back
- Auto-add row on last column completion
- Code field triggers lookup on exit

## Error Handling

### 1. Input Validation
- Numeric fields use validators
- Code format enforced
- Numeric Purity/Tunch checked for finite, non-negative values, with no 100% cap
- Required fields validated

### 2. Database Operations
- Transaction control for multi-step operations
- Cascade deletion protection
- Foreign key enforcement
- Schema version checking

### 3. File Operations
- UTF-8 parsing with format/signature/schema validation for native catalog backups
- Graceful handling of malformed data
- Temporary file cleanup
- Encryption failure recovery

## User Interface Logic

### 1. Mode Management
- Regular/Return/Silver Bar toggles
- Visual indicators for modes
- Mutually exclusive activation
- Mode-specific calculations

### 2. Table Navigation
- Cell-based focus control
- Keyboard-driven workflow
- Skip calculated fields
- Conditional column access

### 3. Form Management
- Clear with confirmation
- Load with validation
- Save with recalculation
- Print with formatting

## Performance Considerations

### 1. Database Access
- Batch operations where possible
- Index optimization
- Transaction grouping
- Row factory for result sets

### 2. UI Responsiveness
- Signal blocking during updates
- Deferred operations with QTimer
- Progress indication for long tasks
- Efficient table updates

### 3. Memory Management
- Temporary file cleanup
- Resource disposal
- Event loop consideration
- Widget recycling


### Historical estimates and reprints

Saved line names, codes, purity, wage rates/mode, piece counts, calculated weights
and wages remain independent of later catalog changes. New saves snapshot Tunch
from the catalog in the save transaction. Updating an existing line with the same
code and line key retains its original Tunch, including an empty Tunch. Changing
the item code or adding a new line captures the current catalog Tunch.

History reprints and loaded draft previews use these saved details. Unsaved new
lines preview the current catalog Tunch until saved. The chosen print format,
font, and Show Tunch setting still apply; this is preservation of transaction
content, not an archived PDF or a guarantee of identical future page layout.

Schema 9 upgrades schema 8 transactionally. It copies the surviving item code and
Tunch available at upgrade, fills missing wage modes once from the available
catalog, and assigns missing line keys. It does not recalculate stored numeric
values. Earlier codes or Tunch values already lost cannot be reconstructed.
Lines with a lost code remain visible as `[Code unavailable]` and participate in
totals, preview and subsequent saves. Blank codes are accepted by the repository
only for the same persisted line in the same voucher; new lines require a catalog
item. Removing a catalog code does not remove its estimate lines.


### Paged lists and sorting

Estimate History, bar History, the item catalog and bar-management tables sort
**loaded rows** when a column header is clicked. Search and filters query the full
database. Loading more continues the repository's stable voucher/date/ID order,
then inserts the new rows into the selected display sort without changing the
selected records. Sorting a partial list does not request a global database sort.

The first page includes an exact count for that request. Subsequent asynchronous
pages omit the count and display loaded-row counts; they do not reuse an old
exact total after possible writes. Refresh/filter changes start a new page sequence.
Each page is a current read; the whole sequence is not a frozen database snapshot.

Each paged display retains at most 20,000 rows and marks when that display limit
is reached. History/catalog/availability filters can narrow results; a selected
bar-list pane also has this display cap. This cap affects display only, not stored
records or repository query limits. The selected-list pane does not currently
offer additional filters beyond choosing the list.


### Entry commands and draft safeguards

The existing single **Save** action is retained by product choice: save the
estimate and inventory, show the success message, prepare print preview, then
clear the form for the next estimate. There are no separate Save & Print or
Save & New actions. Failure leaves the entry available for correction/retry.
Internal save-before-navigation uses the existing `continue_editing=True` path
so that navigation does not trigger printing or clear the draft prematurely.

New, voucher loading, History selection and exit offer Save/Discard/Cancel when
there are unsaved changes. A failed save cancels the requested transition.
Voucher loading saves the current entry under its active voucher identity;
missing targets and failed loads retain the current entry rather than relabelling
its rows. Active cell edits are committed before save/preview/transition checks.

Entry preview titles distinguish an unsaved draft from a saved estimate, including
after changing print format or Tunch visibility. This label is preview UI metadata;
the printed estimate layout is unchanged. Print continues to preview current
entry data without requiring a separate save.

Tools → Undo Last Row Deletion restores the most recently deleted row, including
its line identity, historical snapshot fields and recorded precision, without
reverting other row edits. Up to 20 row deletions are retained in memory. A
successful save, New or successful load clears that undo history. This provides
session-only row undo. Encrypted recovery of the unfinished entry is described below.

### Encrypted unfinished-estimate recovery

Entry checks for changes every two seconds and stores one recovery copy inside
its encrypted database. It captures headers, balances, modes, row snapshots and
raw text in an unfinished cell without closing the editor. This is recovery
storage; estimates, inventory and the existing Save/print/clear flow are unchanged.
The footer shows the last successful capture time. Unchanged entries do not write.

After restarting, opening Entry offers **Restore**, **Discard** or **Cancel**.
Restore resumes editing; it does not save or print the estimate. Discard deletes
only the recovery copy. Cancel keeps it and pauses new captures until it is
resolved through **Tools → Recover Unfinished Estimate**. An existing dirty entry
must pass the usual Save/Discard/Cancel guard before restoration replaces it.

A successful estimate save removes its matching recovery copy in the same
transaction. Explicitly discarding the current entry removes its owned copy;
failed removal blocks that transition. Failed saves/captures retain the last good
copy. Deliberately clearing estimate data also clears applicable recovery data.
Backups include the latest captured draft; rekey and staged restoration preserve
it under the database's existing password and installation-binding requirements.

The most recent two seconds can be lost on a crash; modal dialogs, database
maintenance, contention or write failures can extend that interval. Recovery is
limited to 20,000 rows and an 8 MiB encoded snapshot. The footer reports waiting
or failure rather than claiming a new capture. The row-deletion undo stack is
session-only and is not included in recovery.

Manual verification on a disposable installation: enter regular/return/bar rows,
balances and a note; leave a weight editor containing `12.`; wait for Captured in
the footer, terminate the process and restart. Restore should retain the unfinished
text and totals without creating an estimate or changing inventory. Repeat with
Cancel, then resolve through Tools, and with Discard. Verify ordinary Save still
shows success, opens preview and clears for the next entry, with no recovery offer
for the saved entry on restart.
