# Item Catalog Backup Smoke Tests

Use this checklist after changes to the item catalog backup/restore workflow.

## Preconditions

- Launch the app with a test database.
- Open `Item Master`.
- Ensure at least two item codes exist before creating a backup.

## Scenario 1: Create Backup

- [ ] Open `Settings` > `Data Management`
- [ ] In `Item Master Backup`, click `Create Item Backup...`
- [ ] Save the file as `item_catalog_backup.seitems.json`
- [ ] Verify the success dialog shows the expected record count
- [ ] Open the saved file in a text editor
- [ ] Verify it is JSON with top-level keys `format`, `version`, `exported_at`, and `items`
- [ ] Verify `format` is `silverestimate.item_catalog`

## Scenario 2: Restore Into Empty Catalog

- [ ] Start with a fresh test database or clear the `items` table only
- [ ] Open `Settings` > `Data Management`
- [ ] In `Item Master Backup`, click `Restore Item Backup...`
- [ ] Choose the previously exported `.seitems.json` file
- [ ] Confirm the restore
- [ ] Verify the completion dialog shows inserted records and zero unexpected errors
- [ ] Open `Item Master`
- [ ] Verify all exported item codes are present with correct name, purity, wage type, and wage rate

## Scenario 3: Restore Into Populated Catalog

- [ ] In `Item Master`, edit one existing exported item so its values differ from the backup
- [ ] Add one extra item code that does not exist in the backup file
- [ ] Run `Restore Item Backup...` again using the same file
- [ ] Verify the completion dialog reports both inserted and updated counts as expected
- [ ] Verify the edited existing item is restored to the values from the backup file
- [ ] Verify item codes from the backup that were missing locally are inserted
- [ ] Verify the extra local-only item code is still present and unchanged

## Scenario 4: Full Replace Toggle

- [ ] In `Item Master`, keep one extra local-only item code that is not present in the backup file
- [ ] Run `Restore Item Backup...` again using the same file
- [ ] Enable `Replace the entire current item master with this backup`
- [ ] Confirm the restore
- [ ] Verify the completion dialog reports a non-zero `Deleted` count
- [ ] Verify the extra local-only item code has been removed from `Item Master`
- [ ] Verify item codes that exist in the backup are still present with the backup values
- [ ] Verify the warning text explains that removing old codes can break item-code links on older estimates

## Scenario 5: Invalid File Handling

- [ ] Copy the backup file and change `format` or `version` to an invalid value
- [ ] Run `Restore Item Backup...` with the modified file
- [ ] Verify the restore is rejected with a clear error dialog
- [ ] Verify `Item Master` data remains unchanged after the failed restore
