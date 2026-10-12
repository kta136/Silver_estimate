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

On screen and on printed slips the wage figures are labelled **Labour**
(`Lbr`, `Lbr Amt`, `Net Labour`, `Labour Type`, `Labour Rate`). The code and
database keep the `wage_*` names.

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

#### Keyboard list workspace
1. Opening management starts a fresh list with weight entry focused and available bars shown automatically. The first successful addition creates its automatic list number; opening an empty workspace writes nothing.
2. Weight input is optional. A blank or whitespace-only field browses all available bars, ordered by weight and bar ID, in pages of 50. Type a weight prefix to filter (e.g. `40` matches `40.00`, `40.25`, and `402.50`) using the shared two-decimal display policy. Arrow keys choose a bar; Down at the last row loads more. Enter adds the selected bar, clears the input, and refreshes the remaining available bars. Clearing a filter restores all available bars. Blank Enter during loading does not queue an unseen addition.
3. Every addition/removal saves atomically. Membership automatically reserves the bar for one active list. There is no separate assignment action. The internal `Assigned` value and existing history remain compatible.
4. Tab dismisses suggestions and moves to the current list; arrow keys select a bar; Delete removes selected rows, releases the bars, and updates totals. Delete in a text input only edits text. Ctrl+F returns to weight entry and refreshes suggestions. Esc dismisses suggestions (including pending reads), then clears any weight without reopening suggestions, then closes the window. New lists and reopened active lists show available bars automatically; issued lists remain read-only.
5. Ctrl+N starts another list. Ctrl+O and Ctrl+H open the same unified history window. F2 edits a note. Ctrl+G creates a separate optimal list. Alt+M opens preview, CSV export, clear/delete list, and help. F1 lists shortcuts.
6. Ctrl+P prints to the configured printer. Successful submission automatically issues the list and opens a fresh workspace with weight entry focused. Ctrl+Shift+P opens preview, PDF export, and printer settings. Cancellation, print failure, closing without printing, and PDF export alone do not issue bars. Printing an issued list only reprints it.
7. Issuing revalidates the printed list snapshot and commits status changes with transfer history together. If issuing fails after printing, Ctrl+P (or Alt+I) retries without reprinting while contents remain unchanged; edits invalidate that retry.
8. History combines all saved lists with All/Active/Issued filters (Ctrl+1) and individual bars with voucher/note, weight, and status filters (Ctrl+2). Ctrl+F searches; Enter opens the selected list. Active lists return to the workspace for editing; issued lists show their contents and full totals within history. Esc returns to results, Ctrl+P reprints, and Ctrl+R reopens for editing after confirmation.
9. Reopening through history clears the issued date and returns the entire list to active membership, preserving bar identities and recording the transition. Existing list and bar records are retained; the separate saved-list picker and issued-list browser are removed.

#### Bar Lifecycle
```
Creation → In Stock → In an active list → Issued
                         ↘ Removed → In Stock
Issued list → Reactivated → In an active list
```

Existing lists, bar IDs, source estimate links, and transfer history are preserved. Active-list writes reject issued lists. Reconciliation safeguards continue to protect bars with lifecycle history.

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

### Delete Vouchers by Range

- Open **Settings → Data & Backups → Danger Zone → Delete Vouchers by Range…**.
  Choose saved estimate dates or numeric voucher numbers. Both endpoints are
  required and inclusive; From cannot exceed To. Date fields initially show today.
- Numeric ranges compare whole, nonnegative decimal numbers, including leading
  zeros and IDs larger than a database integer. For example, 100–200 includes
  both `100` and `00100`. IDs containing letters are excluded from numeric ranges
  but can be selected by date.
- Preview lists every matching voucher, its date, and whether it will be deleted
  or kept. Changing either endpoint or mode requires a fresh preview. Empty ranges
  and ranges containing only protected vouchers cannot be deleted.
- A voucher is protected if any associated silver bar is outside In Stock status,
  belongs to a list, or has transfer history. Skip the entire protected voucher;
  retain all its lines, bars, and history, including bars later returned to stock.
- Final confirmation shows the range, eligible/protected counts, and number of
  associated bars being removed. Cancel is the default. If the active entry is
  affected, confirmation explicitly includes discarding its unsaved edits.
- Delete eligible headers, lines, unprotected inventory, and matching recovery
  drafts in one transaction. Recheck the reviewed snapshot under the write lock;
  changed vouchers or inventory require another preview. Database failures roll
  back the batch. Unrelated and protected drafts/entries remain intact.
- On success, show deleted/skipped counts and keep the voucher results visible.
  Clear an affected active entry only after commit and refresh visible reports.
  Existing delete-all commands and voucher-number generation are unchanged;
  surviving vouchers are not renumbered. Backups remain a separate Settings action.

### Sales Reports

- Open **View → Sales Reports** (Alt+R). Every saved estimate counts as a
  sale; drafts do not appear.
- The date range defaults to Today, can be edited with inclusive From/To dates,
  and uses the estimate's entered date. Day-wise and month-wise grouping are
  available, along with Today, This Month and More Ranges. A date shortcut or
  the Day/Month switch applies at once; typed dates and item codes apply with
  View Report (F5).
- The totals caption names what the figures cover: the date range, or the
  day, month or item that was opened.
- Sale net/fine weights and return net/fine weights appear in four separate
  columns. Return weights are not subtracted from sales. Silver-bar lines and
  carried balances are excluded. Reports are on-screen only.
- Drill from a period into items, then into contributing vouchers. All items in
  the selected date range can also be viewed together. Search matches item codes.
- Group by the saved item code, combining different purities and names. The
  latest saved name in the selected scope labels an item row. Deleted catalog
  items remain reportable through their saved snapshots.
- Sum recorded line weights using decimal arithmetic and display grams to two
  decimals; do not recalculate historical fine weights or cap purity at 100%.
- Reopening the report or selecting View Report reads current saved data,
  reflecting edited, backdated and deleted estimates. Opening a contributing
  voucher uses the existing unsaved-entry confirmation.

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
- Created and reconciled through atomic estimate saves
- Bar identities and source-line links preserved
- Status tracking mandatory
- Membership exclusive to one list
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

### 6. Window Title Bar
- On Windows the menus sit in the title bar, with Save, Print and New to
  their right on the estimate screen and the window's minimise, maximise and
  close buttons at the end (`silverestimate/ui/title_bar.py`).
- The bar does not show the application's name. The taskbar and Alt+Tab show
  it, with a `*` while the estimate has unsaved changes; the version is in
  Help > About.
- The empty part of the bar drags the window; a double-click there maximises
  or restores it.
- The bar answers Windows' hit test for its menus and buttons itself. Left
  to Qt 6.11, a press in the title bar reaches a widget twice (a question,
  then the click), which opens a menu and closes it again.
- Other systems, and `SILVER_CLASSIC_TITLE_BAR=true`, keep the ordinary title
  bar with the name and version in it and the menus below.

### 7. Estimate Side Panel
- The side panel is always on the right of the estimate table. It holds the
  voucher fields with the live rate, the Regular/Return/Silver Bar switch,
  the totals, the action buttons and a status line (rows, last saved, F1).
- Its place is not a setting. Its width can be dragged, and the order of the
  Regular, Return and Silver Bar rows is changed from the totals' right-click
  menu.

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

### 4. Dialogs and wording
- A confirmation names its action (`Delete Item`, not `Yes`). The action
  button is coloured, red when it deletes; the way out is plain; Enter goes
  to the safer of the two. Confirmations carry their own style, so they look
  the same from every screen (`silverestimate/ui/message_dialogs.py`).
- Unsaved work is offered as Save, Discard or Cancel, with Enter on Cancel.
- Deleting all data or all estimates needs a second step: typing DELETE. The
  button stays off until the word is typed.
- An outcome that needs no decision (saved, deleted, not found, a cell left
  unfinished) appears in a brief toast at the bottom of the window. It clears
  itself, and when the screen changes.
- A mistake in a form is explained beside the field, which is outlined.
- Command buttons and menu commands use Title Case, with `...` when a window
  opens first. Options, filters, captions and messages use sentence case.
- Dates are written dd/mm/yyyy on screen.

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

Estimate printouts never display a date, including repeated page headers, print
previews, PDF exports, and historical reprints. The printed header contains the
voucher number and silver rate. The estimate date remains stored for entry and
history; there is no option to include it in estimate printing.

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

History and catalog displays retain at most 20,000 rows and mark when that display
limit is reached. Filters can narrow results. This cap affects display only, not
stored records or repository query limits. Keyboard bar management searches inventory
in pages of 50 matches and displays saved lists in batches of 1,500 rows. Totals,
export, and printing use the complete saved list snapshot, regardless of displayed rows.


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
its rows, and a toast says so. Active cell edits are committed before
save/preview/transition checks; a cell left with an unfinished value stops the
action and a toast asks for it to be finished first.

Entry preview titles distinguish an unsaved draft from a saved estimate, including
after changing print format or Tunch visibility. This label is preview UI metadata;
the printed estimate layout is unchanged. Print continues to preview current
entry data without requiring a separate save.

Delete Row (Ctrl+D) removes the current row without asking, because the
deletion can be undone. Deleting the only row clears it and leaves a fresh
entry row. Undo Last Row Deletion (Ctrl+Shift+D, also under Tools → Estimate
Actions) restores the most recently deleted row, including
its line identity, historical snapshot fields and recorded precision, without
reverting other row edits. Up to 20 row deletions are retained in memory. A
successful save, New or successful load clears that undo history. This provides
session-only row undo. Encrypted recovery of the unfinished entry is described below.

Saving asks first when an item row has no gross weight, naming the rows, and
offers **Save Anyway** or **Go Back**. Zero-weight rows remain valid.

### Encrypted unfinished-estimate recovery

Entry checks for changes every two seconds and stores one recovery copy inside
its encrypted database. It captures headers, balances, modes, row snapshots and
raw text in an unfinished cell without closing the editor. This is recovery
storage; estimates, inventory and the existing Save/print/clear flow are unchanged.
The status badge's tooltip shows the last successful capture time; the side
panel's footer names the recovery state only when it needs attention.
Unchanged entries do not write.

After restarting, opening Entry offers **Restore & continue**, **Discard recovery
copy** or **Decide Later**, with the copy's time shown in local time.
Restore resumes editing; it does not save or print the estimate. Discard deletes
only the recovery copy. Decide Later keeps it and pauses new captures until it is
resolved through **Tools → Estimate Actions → Recover Unfinished Estimate**. An existing dirty entry
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
Decide Later, then resolve through Tools, and with Discard. Verify ordinary Save
still opens preview and clears for the next entry, reports the saved voucher in
a brief toast without a message box, and makes no recovery offer for the saved
entry on restart.
