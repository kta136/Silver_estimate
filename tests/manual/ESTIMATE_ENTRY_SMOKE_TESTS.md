# Windows estimate-entry release check

Use a dedicated Windows test profile, a disposable database and synthetic records.
Record the build version, Windows version, display scaling and printer used.
Automated tests cover calculation cases, persistence, navigation and PDF pagination;
this checklist concentrates on the real desktop experience.

## Startup and window behavior

- Launch the packaged application from a folder containing spaces.
- Complete first-run password setup, close it, and reopen the same test database.
- Confirm the existing-password dialog receives keyboard focus and the main window
  opens in front after authentication.
- Check the estimate screen at 100%, 125%, 150% and 200% Windows display scaling.
  Inspect text, table editors, menus, totals, tooltips and dialog buttons for clipping.
- Resize the window and switch totals positions. Confirm all totals remain visible
  and the table has usable space; reopen to check saved layout preferences.

## Keyboard entry and displayed values

Create one WT item and one PC item with purity 91.6 and wage rate 250.

- Enter the WT item using the keyboard: gross 10.500 and poly 0.300. Net weight
  should be 10.200, fine weight should represent 9.3432 rounded for display, and
  wages should be 2,550. WT items have no editable piece count.
- Enter the PC item with two pieces. Wages should be 500, independently of weight.
- Exercise Enter, Tab, Backspace and arrow navigation inside a cell editor. Check
  selection, numeric grouping, focus and the new empty row at the end of entry.
- Use both the buttons and Ctrl+R/Ctrl+B to enter return and silver-bar items.
  Check the visible mode and row type, and verify the two toggles are exclusive.
- Click a different row while an edit is committing. The cursor should stay with
  the user's selection and existing values should remain intact.
- Try an invalid row, then Save. Check that the draft is retained, the error is
  readable and focus moves to the problem row.

## Save, history and dialogs

- Save a mixed estimate with a note, reopen it through Ctrl+H and through the
  History menu from Item Master, and check the visible rows, note and totals.
- Modify a saved estimate, save, then reopen it to confirm the change.
- With a dirty draft, select an estimate from History and exercise Save, Discard
  and Cancel. Save should preserve the draft in the database before opening the
  selected estimate, without launching print preview. Cancel and a failed save
  must retain the draft. Canceling History without a selection should not prompt.
- Save estimates with positive and negative carried silver/cash balances. History
  grand totals should match Estimate Entry, including when the silver rate is zero.
- Select voucher 2 among vouchers 1, 2 and 10, then sort in both directions. Open,
  Print and Delete must continue targeting voucher 2. Repeat selection and sorting
  in Item Master and the silver-bar tables using disposable records.
- Repeatedly open History, accept or cancel it, and close it while data is loading.
  Confirm no hidden dialog or late preview appears afterward.
- Try closing with unsaved changes. Cancel must keep the draft; confirming discard
  must close cleanly without a background window or a second prompt.
- Open item selection, settings and the font chooser. Check tab order, focus,
  password visibility controls, dropdown arrows and native dialog positioning.

## Estimate and inventory consistency

- Enter two regular rows with gross/net `10.125 g`, purity `92.50%`, and a WT wage
  rate of `₹1.00`. Each fine weight must be `9.366 g` and each wage `₹10.13`; totals
  must add these rounded rows. Save, reopen, and compare Entry, History and both
  print formats. Check that silver rates retain two decimals in the classic header.
- Enter carried balances of `-0.005 g` and `-₹1.25`. Reopen the balance dialog and
  accept it unchanged; both values must be preserved and included in print totals.
- Reopen a disposable historical estimate with stored amounts beyond the current
  precision. Printing or changing only its note must preserve the recorded row
  amounts. Editing a calculation input should recalculate that row with the current
  precision policy.

- Save an estimate containing regular items, returns and two silver bars. Inventory
  should contain exactly those two bars. Reorder the lines and save again: bar IDs,
  date added and assignments must stay with the same lines, with no duplicate bars.
- Change the weight/purity of an unused stock bar, remove another unused bar, and
  save. Reopen entry and inventory to confirm both reflect the changes. Removing
  the last bar line must remove its unused inventory row.
- Assign a bar to a list, issue it, then reactivate the list and return the bar to
  stock. At each stage, changing its weight/purity, removing its line, converting
  its line to a return/regular item, or deleting its estimate must be blocked.
  The message should identify the bar or lifecycle restriction. Notes and regular
  item edits remain allowed when the protected bar line stays unchanged.
- With a disposable legacy estimate whose bars have no line links, first save the
  original bar weights/purities. A unique match should retain the existing bar ID
  and transfer history. Ambiguous matches or changed unmatched bars must produce
  an error and preserve the saved estimate and inventory.
- A storage error during save must preserve the entire previous estimate and
  inventory, keep the current draft visible and dirty, and avoid printing/clearing.
  Repeat through History's Save choice; the chosen voucher must not open on error.
  After resolving the error, retry and verify entry and inventory together.

## Print and export

- Preview classic and modern estimates with multiple pages and long item names.
  Inspect headers, totals, page breaks, optional Tunch and landscape/portrait layout.
- Change print font and page size, then reopen the preview to verify preferences.
- Export a PDF through the native file chooser, cancel a second export, then try
  replacing an existing PDF. Open the result in an external PDF viewer.
- Print to the intended Windows printer. Check the selected device, paper size,
  orientation, margins and readability on actual paper.
- Close all preview/dialog windows and the application. Confirm the process exits.

Record failures with the exact steps, expected result and a screenshot or printed
sample. Use synthetic data in any shared screenshot.


## History and catalog pagination

- Use enough disposable records to span pages. Select a non-first row, sort a
  column, then Load more. The selected voucher/item/bar must remain the same.
- Confirm new rows follow the chosen sort among loaded records and header help
  explains that filters search the full database while sorting affects loaded rows.
- Change the filter and verify the page sequence restarts. First-page totals may
  be exact; after Load more the display reports loaded rows.
- Check dates across month/year boundaries and vouchers such as 2, 02, 10 and A1.
- With more than 20,000 matches, confirm the display stops at the stated cap and
  reports the limit. Narrow History/catalog/availability filters to inspect other
  records; verify no stored data is changed by paging or sorting.


### Encrypted backup and restore responsiveness

Use a disposable installation and synthetic database for restore checks.

1. Open Settings → Data Management. Confirm recovery requirements and the last
   successful backup/validation time are visible.
2. Cancel the backup file picker; the recorded time must not change.
3. Create a backup of a large database. The progress indicator must animate;
   Settings/entry actions, Escape and window close must not interrupt the job.
4. On success, confirm the time advances. Simulate an unavailable destination;
   confirm an error is shown and the previous time/archive are retained.
5. Stage a backup with its historical main password. The indicator must animate
   through validation, and success must instruct a restart.
6. Try staging another backup before restarting. It must be rejected without
   disturbing the existing staged restore. Restart and verify the expected data.
7. A backup from another PC or an incorrect password must fail without replacing
   live data. Backups do not include an unsaved estimate draft.
