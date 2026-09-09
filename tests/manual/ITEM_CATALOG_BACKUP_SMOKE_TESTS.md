# Windows item-catalog backup release check

Use a dedicated Windows test profile and disposable database. Include a WT item,
a PC item, optional Tunch text, an unused item and one item referenced by a saved
estimate. Automated tests cover file validation and transactional safeguards;
these checks verify native dialogs and the visible restore workflow.

## Backup file chooser

- In Item Master, select `Save Item Backup...` and cancel. The catalog must remain
  unchanged and no success notification should appear.
- Save to a directory containing spaces. Verify the native `.seitems.json` suffix,
  the selected location and a readable completion message.
- Save again to the same file and check the native overwrite confirmation.

## Merge restore

- Change an existing item's name, add a local-only item and remove an unused item
  that is present in the backup.
- Select `Restore Item Backup...`, choose the saved file and leave full replacement
  disabled. Confirm the action.
- Check the reported inserted/updated counts and the restored values, including
  WT/PC wage type and optional Tunch. The local-only item must remain present.
- Cancel the chooser and the confirmation in separate attempts. Neither should
  modify the catalog.

## Full replacement and saved-estimate references

- Choose full replacement using a backup that retains every referenced item code.
  Verify unused local-only codes are removed and counts match the visible result.
- Prepare a backup that omits a code referenced by a saved estimate. Apply full
  replacement and verify the catalog code is removed while the estimate retains
  its original code, name, purity, wages and Tunch in History and Modern printing.
- Reopen that estimate, change only its note, save, and verify every line remains.
- Repeat with single-item deletion and with a later catalog item reusing the code.
  Existing lines must keep their saved Tunch; new lines use the new catalog value.

## Invalid files and filesystem failures

- Try malformed JSON and unsupported format/version values. Confirm rejection is
  readable, the dialog remains usable and no catalog data changes.
- Try an unwritable destination and a destination whose existing backup is locked.
  Verify the failure is shown and the previous valid backup remains intact.
- Finish with a valid backup and restore to confirm the workflow recovers after
  errors. Record the build, Windows version and exact steps for any failure.
