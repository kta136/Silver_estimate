# Changelog

## [4.10] - 2026-10-12

### Changed

- Shorter headings in the estimate table, to leave more room for Item Name:
  the weight headings lose "(g)" (Gross, Poly, Net, Fine, and Gross, Net,
  Fine in the side panel's totals), Purity (%) is now "%", Pieces is "Pc",
  and Lbr Amt is "Lbr", the same as the labour rate heading: hover over a
  heading to see which is which. The "%" column is narrower. Printouts,
  reports and other screens keep their headings.

### Fixed

- Fix the estimate screen on a 1280 x 720 screen, such as a remote desktop
  session or a 1600 x 900 screen at 125%. Its side panel scrolled, so the
  bottom of it was cut off, and widening the panel cut off table columns.
  - The line with the row count, last save and F1 hint moved from the
    foot of the side panel to under the table. The panel now fits a
    maximized window there with a few pixels to spare, and the Load button
    is as tall as the voucher field beside it.
  - Item Name and Type now give way when the table is short of room, so
    Gross, Net, Fine and every other number stay whole. Item Name narrows
    first, down to 100 px, then Type, down to 64 px. Type goes back to its
    width as soon as there is room again, and the width it prefers is what
    is saved.
  - The side panel can be widened (up to 440 px) until Item Name and Type
    are both at their minimum, and the divider stops there instead of
    cutting a number or adding a scrollbar. On a narrow window the panel
    narrows, down to what its fields and buttons need (about 296 px), before
    the table scrolls, and goes back to your width when the room returns.
    Before, dragging it below 296 px cut off its fields.
  - The width you give the side panel is remembered.

### Dependencies and tooling

- Replace the self-built SQLCipher wheel with `apsw-sqlite3mc` from PyPI
  (SQLite 3.53.4 with SQLite3 Multiple Ciphers). The database file format
  is unchanged and nothing is converted: this build opens existing
  databases and backups as they are, and a build with the previous engine
  can still open a database or backup that this build has written.
  - The engine no longer contains OpenSSL, whose 3.6 series loses support
    on 1 November 2026. Updating the engine is now a lock-file change. The
    vendored wheel, its build script and workflow, and the two CI steps
    that checked it are removed.
  - `silverestimate/persistence/apsw_dbapi.py` gives the engine the
    `sqlite3` interface the repositories use. A connection that is not
    encrypting in the SQLCipher 4 format is refused.
  - Backup, restore and password change copy the database with SQLite's
    backup interface in place of `sqlcipher_export()`.
  - Database validation no longer runs `PRAGMA cipher_integrity_check`,
    which this engine does not have. A damaged or altered page still
    fails its check when it is read, and the quick check reads every page
    in use.
  - The tests keep a database written by v4.08 and must open it, so an
    engine update that could not read the format fails them.

## [4.09] - 2026-10-11

### Changed

- Redesign the Sign In and Create Passwords windows: a teal strip with the
  logo, name and version beside the form. Create Passwords now sets the
  main and recovery passwords side by side, so it is 840 x 453 instead of
  540 x 728 and fits a 1366 x 768 screen, even with Windows scaled to 125%.
  On 1366 x 768 the old window was too tall, so the note under the main
  password lost its last line and the status line was squeezed.
- New logo: a silver bar with the rupee sign engraved in it, on a teal tile.
  It is the icon of the exe, the taskbar, the windows, About and Sign In.
  Up to 32 px it is a plain bar, so it stays clear in the taskbar and title
  bar. The master is `assets/icons/silverestimate.svg`;
  `python scripts/build_app_icon.py` redraws the icon from it. The Sign In
  strip is now deep teal so the logo stands out, and no longer says
  "Your estimates are encrypted on this PC". The Create Passwords tooltip
  on the main password box no longer says "This password encrypts your
  data" either.
- Shorten the About window to the name, version, what the app does and two
  short licence notices, and remove the link to the source code on GitHub.
- Silver Bars is now a screen in the View menu (Alt+B), beside Estimate
  Entry, Item Master and Sales Reports, instead of a window opened from
  Tools. It is built only when you open it and closed when you leave it, so
  nothing of it loads or runs in the meantime. Leave by choosing another
  screen, pressing Close, or pressing Esc once the weight box is clear; it
  stays open while a list is printing. A list picked in Silver Bar History
  opens in the same screen.
  - File > Print and F1 now act on the open screen: on Silver Bars they print
    the list and show its shortcuts. Retrying an issue moved from Alt+I,
    which opens Item Master, to Ctrl+I.

### Fixed

- Fix several windows that were too tall for a 1366 x 768 screen, which
  cuts the usable height to about 700 px:
  - Estimate History: the Selected Estimate panel needed about 20 px more
    than it got, so it grew two scrollbars and cut off the voucher number,
    date and amounts. It is now more compact and never scrolls sideways.
  - Settings: Printing and Data & Backups scrolled, which left Delete All
    Data and the print sample below the fold. Every page now fits. The
    margins editor is more compact, and the Appearance preview puts the
    sample totals under the table so all its columns show. A page gets a
    scrollbar only when it cannot squeeze into the window.
- Fix gaps on 1600 x 900 screens, and on 1280 x 720 (a 1600 x 900 screen
  with Windows scaled to 125%):
  - Every table heading now sits over its data: figures are right-aligned
    like the numbers below them and labels are left-aligned, instead of
    every heading being centred over left-aligned text.
  - Estimate History opens larger on a big screen (up to 1440 x 800), and
    its Selected Estimate panel fits at 1280 x 720 without a scrollbar
    over the voucher number, date and amounts. The Grand Total row no
    longer pads each label, which had made the row too tall.
  - Item Master: Add, Update and Clear now sit on one row, so the whole
    form, with Delete, fits at 1280 x 720 without scrolling.
  - Settings > Data & Backups fits at 1280 x 720. Its two long paragraphs
    are shorter, and a page's scrollbar now appears whenever the page is
    taller than the window needs, not only at the page's smallest size
    (between the two heights the bottom of a page was cut off with no way
    to reach it).
  - Sales Reports keeps its filters and report to a 1340 px width, centred.
    On a wide screen the five columns had ended up a thousand pixels from
    the dates they belong to.
  - An issued Silver Bars list is a centred 1000 px column for the same
    reason.
  - The button at the foot of Silver Bar History says Close, and Back to
    List only when it was opened from the Silver Bars screen (before, it
    always said Back to List, even when there was no list to go back to).
    The window also opens larger on a big screen.
- Editing a weight of 1000 g or more in the estimate table no longer
  scrolls its first digit out of view (1239.567 read 239.567). The editor
  grows to the left to show everything typed.
- A large total (₹10 crore or more) or a negative one (-₹10 lakh or less)
  no longer drops the Grand Total under its caption, which pushed the side
  panel's buttons out of a short window. The amount shrinks, down to 11 pt,
  to stay beside the caption. Where a value still has to wrap, its card is
  now as tall as it needs, so the Net Fine and Net Labour rows no longer
  overlap, and the panel's height settles again when the numbers get small.
- A background search that finished just as its window was closed could
  leave an error in the log ("Signal source has been deleted"). It is now
  ignored, since nothing is waiting for the result.
- The Silver Bars weight box no longer says "Showing all bars" while the
  list beside it says the bars are hidden.
- Status pills in Silver Bar History keep a clear line above and below them
  and sit in the middle of the row.
- The two columns in the Keyboard Shortcuts window start at the same
  height, and Item Master shows the start of a long name, not its end.
- Clicking File, View, Tools, History or Help with the mouse opens the
  menu again. Since 4.07 put the menus in the title bar, a click made the
  menu appear and close at once: Qt 6.11 delivers a press in the title
  bar twice, first to ask whether the window should be dragged instead,
  then as the click. The bar now tells Windows itself that its menus and
  buttons take the click, so it arrives once. The keyboard, the More
  button and dragging the window by the empty part of the bar were not
  affected and work as before.

## [4.08] - 2026-10-11

### Dependencies and tooling

- Replace the pull-request, main and release workflows with one
  `validation.yml` that runs Ruff, mypy and the tests on Windows for pushes
  and pull requests. CI no longer builds, signs or publishes the executable;
  builds are made locally with `scripts\build_windows_local.cmd`.
- Remove the dependency-policy gate (lock review, licence allowlist, notice
  and provenance checks), the release SBOM step, and the performance and
  startup budget gates, along with their scripts, tests and documents.
  `nox -s audit` lists advisories for the locked runtime packages with
  `pip-audit` and never blocks.
- Reduce `noxfile.py` to `ruff`, `mypy`, `tests`, `smoke_ui` and `audit`;
  plain `nox` runs the first three. The build and artifact sessions, the
  standalone deployment validator, and the `pr`, `ci` and `advisory`
  shortcuts are gone.
- Drop the `diff-cover` and `cyclonedx-bom` development dependencies, the
  `unit`, `integration` and `slow` test markers, the issue and pull-request
  templates, and the pre-commit.ci settings.

- Drop `pre-commit` and its configuration (no hook was installed) and
  `pytest-cov` with the coverage settings nothing ran.
- Remove the packaged-build self-test: the `--artifact-smoke` switch, its
  validator script and the build step that ran it. The local build still
  checks the one-file loader's native dependencies. Start the built
  executable once before copying it to the shop PC.
- Remove `DOCS/modernization-roadmap.md`, `DOCS/api-reference.md` and
  `DOCS/visual-references.md`; cut the readme's version history,
  contributing and support sections; trim `.gitignore` to what this
  project produces.

- Turn off the Ruff complexity rules and delete their exemption lists and
  `noqa` comments; every function they would have flagged was exempt.
- Remove the unused Android and buildozer parts of `pysidedeploy.spec`, and
  the Nuitka report option, which nothing read any more. The rest of the
  generated Nuitka command is unchanged.

### Changed

- **Upgrading:** this build opens only a current database (schema version
  10, single-file, bound to this PC), which is what v4.04 to v4.07 leave
  behind. The one-time conversions for older data are removed: the
  two-file `estimation.kdf.json` format, schema versions 8 and 9, and
  settings saved before v4.0. An install older than v4.04, or a backup
  taken before v4.0, must be opened once with v4.04 to v4.07 first.
- Logging settings store one detail level (errors only, normal, detailed)
  instead of four switches. Existing settings are converted once; a
  hand-edited combination becomes the nearest level.
- The print sample in Settings is painted directly instead of being
  written to a temporary PDF and read back. It looks the same.
- The About dialog uses the application icon file already shipped; the
  separate 789 KB picture is removed.
- Stop writing timing lines to the logs: the `[perf]` debug lines and the
  `[telemetry]` startup metrics are gone.

### Internal

- Estimate saves: the presenter calls the database directly and the save
  input is captured by `EstimateEntrySnapshot.capture()`. The view model
  and the repository adapter are removed.
- Printing has one estimate format, so the format registry, the
  `print/estimate_layout` setting and the switching code are removed.
- Live rates: the controller owns the DDA stream; the relay service is
  removed and the HTTPS and SSE paths share one set of validators.
- Navigation: one `NavigationController` builds the menus and switches
  screens; `NavigationService` is merged into it.
- Silver-bar persistence lives in three modules instead of eight.
- Logging settings: the page keeps its controls with less scaffolding
  around them.
- Replace twelve single-implementation protocols with the class they
  described, and remove a main-window flush-status hook that the database
  never called.
- Printing: the estimate and silver-bar renderers share one report header,
  font rule and page loop. Printed pages are pixel-identical.
- Theme: stylesheets name the colour token instead of repeating its value
  in over 50 places. The generated stylesheets are byte-identical.
- Estimate screen: remove 45 `hasattr`/`getattr` guards around controls
  the screen always creates, and its second, unreachable copy of the
  live-rate refresh; the refresh button asks the live-rate controller.
- The version number is no longer repeated in the readme and docs index.
- Remove code nothing used: 12 settings keys of the old silver-bar window,
  13 icons, stylesheet rules for widgets that no longer exist, the
  available-bars keyset query, and two wrappers only tests called.

### Fixed

- Clear the seven mypy errors that had kept validation on `main` failing.

## [4.07] - 2026-10-10

### Changed

- Set the application and Windows executable version to 4.07.
- Put the menus in the title bar, beside the window's own
  minimise, maximise and close buttons. The bar no longer repeats the
  application's name; the taskbar and Alt+Tab still show it, and the version
  is in Help > About. The empty part of the bar drags the window and a
  double-click maximises it. `SILVER_CLASSIC_TITLE_BAR=true` keeps the
  ordinary title bar.
- Keep the estimate side panel on the right of the table. Settings no longer
  offers `Totals position`; anyone who had chosen Left Side or Bottom gets
  the right-hand panel. The bottom layout's totals strip, header row and
  status line are removed.
- Show estimate-screen failures in the toast instead of a hidden status line:
  a voucher number that does not exist, a save or preview stopped by an
  unfinished cell, and rows left out of a preview.
- Give every confirmation one look from every screen: the action button is
  coloured (red when it deletes), the way out is plain, and Enter goes to the
  safer of the two. The unsaved-estimate, unsaved-item and catalog-restore
  prompts and the About window use it too.
- Replace the plain system input boxes with a styled prompt for the list
  note, the backup password and the typed DELETE step, whose button stays off
  until the word is typed.
- Use Title Case for command buttons and menu commands, and one name for each
  command and column: `Estimate History...`, `Back Up Item Catalog...`,
  `Restore Item Catalog...`, `Purity (%)`, and `voucher · note` for a bar's
  source.
- Show dates as dd/mm/yyyy everywhere on screen, including Last saved and the
  voucher-range confirmation.
- Give Delete Row, Delete Estimate and Delete Item one look, and make buttons
  that cannot be used look switched off.
- Sales Reports: Day/Month applies at once, the totals caption names the
  opened day, month or item, item names take the spare width, the first
  column is headed Date or Month, and the extra ranges sit under More Ranges.
- Estimate History keeps Search in view in a narrow window, groups Today,
  This Month and All Dates, and shows its count as plain text.
- Settings opens at a size that suits its pages, each page needs only its own
  width, Printing is laid out like the other pages, and the default preview
  zoom is entered as a percentage.
- In a narrow print preview, show some buttons as icons instead of pushing
  More and Close out of view.
- Add Alt+R for Sales Reports. The estimate table's right-click menu matches
  the More menu, with Undo, and the totals' right-click menu says what it does.
- Item Master opens sorted A to Z, says what to fix above the buttons and
  outlines the field concerned.
- The optimal-list dialog reports a reversed range under the two weights and
  shows weights to two decimals. Silver Bar History shows Clear Filters only
  while a filter is set.

### Fixed

- Stop the estimate table's header cutting off the tails of letters at the
  default text size.
- Stop the first toast of a session being cut in half, and clear a toast when
  the screen changes.
- Open the History menu with Alt+S; Alt+I already opens the Item Master.
- Keep the fields and buttons of the sign-in and first-run windows in place
  when a message appears, and show that message once.
- Fit the estimate side panel in the smallest window without a scrollbar.
- Fit `Landscape` in the print preview's orientation box and show the Print
  button's icon in white.
- Say `1 silver bar created`, not `1 silver bar(s) created`.
- Keep one copy of each stored credential. Windows holds a roaming and a
  local copy under one name and shows whichever store any program wrote to
  last, so the old layout could check a password against a superseded hash,
  and a wipe could leave a copy that came back later. Each entry is now a
  single local-machine credential under its own name, a delete clears both
  stores, and the first start after updating moves an existing installation
  over, keeping the value written last. Earlier versions of the app can still
  read the entries.
- Accept the live-rate server's `feed-status` events, whose `status` is a
  word such as `stale`. They were being rejected with a warning on every
  connection, so market-open and market-closed updates never arrived.

### Dependencies and tooling

- Store password hashes and the device secret through Windows Credential
  Manager directly, using the standard library. The `keyring` package and the
  eight packages installed with it are gone.
- Fetch live rates with Qt's network stack instead of `urllib` on a worker
  thread. Closing the app or switching live rates off no longer waits for a
  request in flight. The packaged app now ships Qt Network and the Windows TLS
  plugin, and its startup check requires that TLS backend.
- Start a new log file each midnight with the standard
  `TimedRotatingFileHandler` in place of the custom cleanup scheduler. With
  `Delete old logs automatically` on, logs older than the chosen days are
  also cleared at startup, which the scheduler missed when the app was closed
  overnight; with it off, the last 30 daily files are kept. Logs are no longer
  capped by size.
- Replace Bandit with Ruff's security rules (`S`) in lint, pre-commit and CI.

## [4.06] - 2026-10-10

### Changed

- Set the application and Windows executable version to 4.06.
- Reorganise the menus so each destination appears once: File (New, Save,
  Print, Exit), View (screens, with a mark on the open one), Tools, History
  and Help. Estimate Actions shows its shortcuts.
- Replace the plain shortcut list with a grouped Keyboard Shortcuts window (F1)
  shared with Silver Bars.
- Report a saved estimate in a brief toast instead of a message box before the
  print preview. Deleted rows, restored rows and item changes use the same toast,
  so these outcomes are now visible on screen.
- Delete an estimate row without asking; Ctrl+Shift+D undoes it. Deleting the
  only row clears it.
- Ask before saving item rows that have no gross weight.
- Name the action on every destructive confirmation, default to Cancel, and
  require typing DELETE for Delete All Estimates as for Delete All Data.
- Show item, sign-in, first-run and optimal-list mistakes beside the field
  instead of in message boxes; show what is still missing while passwords are
  typed.
- Label wage figures **Labour** throughout the screens (`Net Labour`, `Labour
  Type`, `Labour Rate`), matching `Lbr` on printed slips.
- Rebuild Settings: one log detail level instead of four checkboxes, a Refresh
  Now button for live rates, a clickable print preview, described backup and
  delete actions with the last backup time, and page titles that match the
  sidebar.
- Estimate History opens wide enough for every column, offers Today and This
  month, shows one count, and names the date, total and note of the estimate
  before deleting it.
- Sales Reports can export the table shown to CSV (Ctrl+E), offer more date
  ranges, and draw the fine-weight bar behind the figure.
- Move printer, page and print-font setup into the print preview's More menu.
- Darken input and button outlines and the primary button's hover colour for
  contrast, and keep drop-down and spin arrows inside their fields.
- Set minimum window sizes that keep the estimate table and side panel usable.

### Fixed

- Stop the Return and Silver Bar mode labels being clipped in the side panel.
- Fit the Code and Type columns to their contents when rows are filled in by a
  lookup or a mode change.
- Correct the About box's copyright line and add the licence and source.
- Make counts agree with their nouns (`1 bar`, `1 item`, `1 day`).
- Use the rupee sign for the last-balance amount on printed slips.

## [4.05] - 2026-10-10

### Changed

- Redesign the Silver Bar workspace, history and optimal-list dialog: available
  bars stay visible beside the current list, with a status pill, big totals
  strip, issued-list banner with Reopen (Ctrl+R) and a grouped F1 shortcuts
  dialog. History gains a Lists/Bars switch, filter chips and a side panel for
  the opened list.
- Redesign the Sales reports tab with a one-row filter bar, Day/Month switch,
  Sales and Returns totals cards, a clickable breadcrumb with Backspace to go
  back, and a subtotal row that follows the last table row.
- Give the Estimate table the full window height. With totals beside the table,
  the voucher fields, entry mode (Regular / Return / Silver Bar), live rate and
  actions move into a 320px side panel, and Save, Print, New and the status
  badge dock in the menu bar.
- Set the application and Windows executable version to 4.05.

### Fixed

- Recalculate estimate totals from every row on each change, so draft restores
  and failed-load restores no longer leave stale totals and one error no longer
  freezes the on-screen totals.
- Keep estimate row numbers 1-based and in step with position after rows are
  added, removed or replaced, so save and preview errors name the right row.
- Stop the live-rate refresh recursing until `RecursionError` when the service
  is unavailable.
- Finish a pending restore that was interrupted after the file swap instead of
  refusing to start with "Pending restore target is missing or corrupt".
- Check optimal silver-bar lists against their real fine weight, so a list can
  no longer exceed the requested maximum.
- Free the Settings, Silver Bar, optimal-list and print-font dialogs after they
  close, and stop the Settings live-rate status timer.

### Removed

- Unused silver-bar persistence, UI, print and service code, along with the tests
  that covered only that code.

## [4.04] - 2026-10-06

### Changed

- Show available silver bars automatically in management, including after adding
  a bar and starting a new list. Weight entry is now an optional filter; clearing
  it restores all available bars with the existing keyboard selection and paging.
- Set the application and Windows executable version to 4.04.

## [4.03] - 2026-10-04

### Changed

- Ctrl+P prints the current silver-bar list to the configured printer, issues it
  after successful submission, and starts a fresh list with weight entry focused.
  Ctrl+Shift+P opens preview, PDF export, and printer settings.
- Merge saved lists, issued lists, and silver-bar history into one keyboard-driven
  history window. Filter lists by All/Active/Issued, switch to individual bars,
  and open issued contents in the same window to reprint or reopen for editing.
- Keep lists active after print cancellation or failure. If issuing fails after
  printing, retry an unchanged list without submitting a duplicate print job.
- Set the application and Windows executable version to 4.03.

## [4.02] - 2026-10-04

### Changed

- Rebuild Silver Bar Management around keyboard entry: type a weight, choose a
  match with the arrow keys, and press Enter to add and save immediately.
- Remove the separate list-assignment step; removing a bar with Delete makes it
  available again automatically.
- Place the silver-bar controls in one toolbar and maximize vertical table space.
- Confirm issuing only after a successful print, with a retry for an unchanged
  printed list and no issuing on cancellation or PDF export alone.
- Set the application and Windows executable version to 4.02.

## [4.01] - 2026-09-19

### Changed

- Refresh the estimate-entry workstation layout, spacing, table presentation,
  and responsive final-calculation panel.
- Simplify Modern estimate printouts by removing the date, using a full-width
  final summary, and rounding displayed rupee totals to whole amounts.
- Remove superseded generated GUI-audit and PDF-preview artifacts from source
  control while retaining the maintained golden fixtures.
- Set the application and Windows executable version to 4.01.

### Fixed

- Preserve each estimate row's Regular, Return, or Silver Bar type when its
  item lookup, name, or other editable values change.
- Keep large totals readable by reflowing the final-calculation values instead
  of squeezing or clipping them in narrow layouts.

## [4.0] - 2026-09-08

### Changed

- Apply the approved compact white/gray interface with teal accents across
  estimate entry, item catalog, history, silver bars, settings, and dialogs.
- Add live appearance and print previews, responsive controls, and a one-time
  migration to the approved appearance defaults that preserves later customization.
- Update Modern printing with section subtotals, date and item metadata, and
  rate-aware summaries while retaining Classic printing.
- Set the application and Windows executable version to 4.0.
- Omit item codes from print output and label wage rates as "Lbr" throughout
  the interface and print layouts. Classic labels calculated wages as "Wage Amt".
- Compact the estimate toolbar, status bar, live-rate card, and sidebar actions.
  Replace the totals breakdown with aligned tables and remove redundant headings.
- Fit estimate columns to the available width, show weight/purity/rate units,
  and use the interface font with tabular digits for numeric values.
- Widen the note field, move estimate tools into the menu bar, and add a keyboard
  shortcut reference under Help while shortening the status bar.
- Reflow larger totals into grouped tables without horizontal scrolling.
- Label calculated labour amounts as "Lbr Amt" in the interface and both print layouts.

### Fixed

- Keep menu and table headings at the selected interface size on Windows, and
  refresh styled controls immediately when changing appearance settings.
- Save table and totals font sizes and totals placement through the estimate
  layout controller, fixing the appearance-settings save error.
- Allow for printer font rounding so Classic portrait output fits within the
  printable width when Tunch is shown.
- Apply the totals font size to column headings, row labels, and values together.
- Stack large grand totals below their caption when the sidebar is too narrow
  to keep the amount readable on one line.

## [3.12] - 2026-07-30

### Added

- Added a repository-owned dependency policy that validates the locked
  `pip-audit` report, reviewed exceptions, licenses, notices, and native
  component provenance for release artifacts.
- Added reusable typed paging state and explicit database, settings, password,
  print-preview, and worker-lifecycle contracts.

### Changed

- Split silver-bar persistence into role-specific query, command, and
  synchronization repositories.
- Reworked estimate entry, settings, and print preview as composed,
  independently tested controllers and collaborators with narrow typed
  boundaries.
- Closed the modernization program at its accepted scope. Phase 12 remains
  deferred pending transport-maintenance evidence, and Phase 16 is out of scope
  because the portable EXE/ZIP/checksum/SBOM release path meets the current
  single-system deployment requirements.

### Removed

- Removed the broad `SilverBarsRepository`, forwarding
  `EstimateEntryFacade`, Safety dependency graph, and superseded controller
  ownership paths.

### Security

- Extended the release SBOM and policy gates to cover CPython, Qt, SQLCipher,
  OpenSSL, runtime licenses, native provenance, and rejection of unintended
  SQLite or Qt components.

## [3.11] - 2026-07-26

### Changed

- Replaced Qt's stock print-preview dialog with an application-owned, themed
  `QDialog` containing one responsive toolbar, persistent page navigation, and
  an embedded `QPrintPreviewWidget`, while preserving the existing direct
  painters, report controls, PDF export, page settings, zoom, navigation, and
  quick print. Command controls use accessible icon-only actions in a
  consistent output-to-settings-to-view-to-page order at both wide and compact
  window sizes.
- Replaced silver-bar inventory and individual-list HTML printing with typed
  direct `QPainter` reports that share the Modern estimate's visual primitives,
  repeat metadata and headings across pages, keep totals with final rows, and
  honor the saved print font in preview, export, and physical printing.

### Removed

- Removed the remaining production `QTextDocument`/HTML print payload, renderer,
  templates, callbacks, and escaping path.

### Fixed

- Bypassed Nuitka's unsafe frozen PySide6 application-icon wrapper while
  retaining the embedded executable icon and the application's explicit window
  icon, preventing null Windows icon handles from aborting packaged startup.

### Security

- Bound the SQLCipher key to a random 256-bit secret forced into local-machine
  Windows Credential Manager storage, so the database and new encrypted backups
  cannot be opened on another PC with the password alone.
- Reused SQLCipher's in-file salt to make `estimation.db` the only permanent live
  database file and added atomic migration from the authenticated local two-file
  format.
- Made startup fail closed when an existing database lacks local credentials or
  its device-binding secret, and removed retained rollback files after successful
  password rotation or format migration.

## [3.10] - 2026-07-23

### Changed

- Replaced the application artwork with a simplified silver-and-rupee icon that
  remains legible from the Windows 16 px shell size through the 256 px tile.
- Updated runtime startup, the main window, `pyside6-deploy`, frozen-artifact
  smoke checks, and standalone deployment validation to use the canonical icon.

### Removed

- Removed the superseded application icon artwork and its temporary versioned
  filenames so packaged builds contain only the current icon.

## [3.09] - 2026-07-23

### Removed

- Removed the retired `SILVDB01` importer, AES-GCM envelope reader, plaintext
  migration workspace, importer tests, and direct `cryptography` dependency.
- Removed historical schema v1-v8 upgrade branches; fresh databases are created
  directly at schema v8 and non-current schemas now fail closed.
- Removed password-policy rehash persistence, retired print-layout aliases, the
  compatibility-only re-encryption wrapper, and completed migration tooling.

## [3.08] - 2026-07-23

- Replaced the PyQt6 runtime with PySide6/Shiboken6 6.11.1 and Qt 6.11.1
  without a compatibility layer or SQLCipher data-format change.
- Completed binding-specific signal, enum, context-menu, QObject-lifetime,
  typing, keyboard, visual, print, and performance validation under PySide6.
- Updated maintained documentation, project metadata, notices, and release
  SBOM generation for PySide6, embedded CPython, and the native Qt runtime.
- Replaced PyInstaller packaging with Qt's `pyside6-deploy` wrapper and a
  locked Nuitka 4.1.3/zstandard 0.25.0 toolchain.
- Added curated standalone inventory validation before the one-file build,
  including required Qt plugins, legal files, SQLCipher provenance, and
  rejection of unused Qt/PyQt payloads.
- Added frozen startup validation for the Windows Qt platform, icons, SVG,
  printing, Windows Credential Manager, SQLCipher, and writable runtime paths.
- Updated pull-request, main, release, and local Windows build flows to produce
  and validate the `pyside6-deploy` artifacts directly.
- Replaced Passlib with a UI-independent `argon2-cffi` password service while
  preserving existing Argon2id hashes, keyring entry names, and automatic
  rehash-on-success policy upgrades.
- Replaced the live SILVDB01/plaintext-snapshot lifecycle with direct keyed
  SQLCipher connections so database, WAL, rollback, and statement-journal page
  content remains encrypted during active sessions.
- Added exact atomic Argon2id KDF metadata, strict SQLCipher 4.17.x runtime and
  compile-option checks, keyed worker readers, maintenance draining, and
  QLockFile single-instance ownership.
- Added verified one-time SILVDB01 migration with retained source backup,
  encrypted `.sedbbackup` create/restore, restart activation, and recoverable
  copy-and-switch password rotation.
- Removed the snapshot scheduler, plaintext temp store, lifecycle coordinator,
  legacy envelope writer from production, repository flush requests, and
  plaintext recovery candidates.
- Added the bundled and hash-verified SQLCipher 4.17.0 CPython 3.14 Windows x64
  wheel, provenance/native inventory, strict runtime verification, manual
  candidate-build workflow, encrypted runtime/canary tests, and frozen artifact
  smoke coverage.
- Fixed packaged startup authentication by registering the pending and recovery
  credential kinds used by first-run setup and copy-and-switch password recovery.
- Clarified that SILVDB01 remains only as a one-time read-only importer and a
  retained `estimation.silvdb01.backup`, with an installed-system confirmation
  gate before importer retirement.
- Closed the binding migration after the local Windows source, UI, SQLCipher,
  performance, standalone, and one-file release gates passed.

All notable changes to the Silver Estimation App will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [3.07] - 2026-07-22

### Added
- Added optional Tunch columns to Classic and Modern estimate printing, with preview visibility controls and current item-master values.
- Added item-catalog backup and restore support for nullable free-text Tunch values.

### Changed
- Relicensed the project from proprietary terms to the GNU General Public License v3.0 only (`GPL-3.0-only`) to align distribution terms with PyQt6.
- Changed `items.tunch` from a constrained number to free text through schema version 8 while preserving existing values and estimate-item links.
- Increased Modern estimate spacing to two row heights between goods groups and made table dividers explicit, including PCS to Fine.

### Fixed
- Hid the Modern final Silver Cost and Total metrics when the silver rate is zero.

## [3.06] - 2026-07-19

### Added
- Added persistent Classic and Modern estimate-format selection in Settings and Print Preview.
- Added print-font family, size, and weight controls directly to estimate preview with immediate refresh.
- Added typed estimate print documents, direct `QPainter` rendering, multi-section print fixtures, and visual PDF regression coverage.

### Changed
- Reworked Modern printing into a full-width semantic A4 table with shared Gross, Poly, Net, %, Fine, and Lbr column anchors.
- Preserved the former Modern/New fixed-width layout under the Classic name.
- Simplified estimate headers to keep Voucher and Silver Rate on one row and removed the printed Date.

### Removed
- Removed obsolete estimate HTML generation and the unused legacy estimate formats.
- Removed the estimate footer, `/Doz.` text, weight-unit suffixes from column headings, and the long Labour heading.

## [3.05] - 2026-07-16

### Fixed
- Corrected silver-bar list and inventory printing so SQLite row values for weight, purity, fine weight, and totals no longer render as zero.

### Changed
- Bumped the application/package version to `3.05` for the corrected silver-bar printing build.

## [3.04] - 2026-07-16

### Changed
- Bumped the application/package version to `3.04` after completing the installed-system data migration cycle.
- New databases and recovered plaintext sessions now create their Argon2id salt directly in the authenticated `SILVDB01` envelope instead of QSettings.

### Removed
- Removed the completed working-directory database relocation module and its startup error path.
- Removed the completed legacy-organization QSettings copier and the obsolete organization identifier.
- Removed PBKDF2 key derivation, raw nonce-plus-ciphertext database reads, encrypted migration backups, and their migration-only tests.

## [3.03] - 2026-07-16

### Added
- Added an explicit startup loading message and indeterminate progress indicator while the estimate workspace is being prepared.
- Added UI regression coverage proving that the first code editor accepts typing as soon as it becomes visible.

### Changed
- Bumped the application/package version to `3.03` for the responsive-startup Windows build.
- Prioritized estimate input by activating the first code cell on the first visible event-loop turn and deferring menu and live-rate setup until the input surface is ready.
- Prevented startup focus from stealing an immediate user selection in another estimate cell.

## [3.02] - 2026-07-16

### Added
- Added automatic, verified migration from legacy working-directory database locations to the canonical database beneath the executable directory.
- Added complete one-time QSettings migration from the legacy organization into the canonical settings store, preserving newer conflicting values.
- Added startup performance telemetry and budget checks, plus focused database-path, settings-migration, print-rendering, and runtime regression tests.

### Changed
- Bumped the application/package version to `3.02` and refreshed Windows build and validation metadata.
- Refined estimate-entry layout, totals, table-state handling, main-window interactions, login behavior, print rendering, and silver-bar management controls.
- Replaced icon-font names with explicit semantic Qt-native icon mappings and deterministic theme-aware rendering.

### Removed
- Removed the QtAwesome dependency, PyInstaller hook, bundled resources, hidden imports, compatibility names, and local environment packages.
- Removed relative runtime database selection and the QSettings legacy-store fallback after successful migration.

## [3.01] - 2026-07-15

### Added
- Added atomic schema v6 migration/validation, estimate-header totals backfill, silver-bar availability index, typed keyset pages, Load more controls, and bulk catalog upserts with immutable cache replacement.
- Added `LatestRequestRunner` with persistent workers, generation-based stale-result rejection, thread-local cancellable SQLite connections, and cooperative print/network shutdown.
- Added the versioned `SILVDB01` Argon2id/AES-256-GCM streaming envelope, distinct integrity outcomes, legacy migration verification, generation-aware flushing, marked crash recovery, and flush telemetry.
- Added anonymous DDA current-rates hydration and SSE streaming for item ID `cmomws5tw000004i5k5t6yrnw`, using only customer `finalRate`, with sequence recovery, stale detection, jittered reconnects, 10-second disconnected polling, and verified offline cache.
- Added explicit estimate/silver-bar facades, split silver-bar query/command/synchronization repositories, independent settings ownership, shared print specifications/strategies, and architecture regression tests.
- Added deterministic scale/performance data, complete p95 enforcement, Windows PR smoke/build validation, frozen artifact startup, release tag validation, CycloneDX SBOM, checksums, and optional signing hooks.
- Added shared user-facing Indian rupee/date formatting and reusable empty-table messaging across estimate and silver-bar history screens.

### Changed
- Bumped the application/package version to `3.01` for the upgraded Windows test build.
- Raised global coverage to 75% and pull-request changed-line coverage to 90%.
- Expanded Ruff to Bugbear, Simplify, Performance, McCabe, and selected Pylint complexity rules with a complexity cap of 15.
- Made Bandit medium/high findings blocking and switched PR, main, and release dependency setup to `uv sync --frozen --extra dev`.
- Declared Windows as the supported packaged platform; macOS/Linux remain untested development environments.
- Reduced `.env.example` to the three environment controls consumed by the runtime.
- Refined login, settings, estimate totals, history tables, and print preview for denser layouts, clearer saved/unsaved states, category-aware totals, compact navigation, and consistent display formatting.
- Preserved saved print orientation directly and simplified credential, logging, and print-settings persistence after their one-time migrations completed on the installed system.
- Updated the README, deep-dive documentation, GitHub templates, and repository metadata for the current PyQt6/Windows support model.

### Removed
- Removed DDASilver scraping, hard-coded HTTP/IP/broadcast parsing, invalid-TLS retries, item-name matching, `baseRate` derivation, and all worker `QThread.terminate()` calls.
- Removed completed QSettings credential, logging-key, and print-orientation migration paths.
- Removed the temporary-database compatibility wrapper, dead private helpers/counters/aliases/constants, stale Windows diagnostic text files, and the duplicated v2.8.9 release-note file.

## [3.0] - 2026-06-13

### Changed
- Bumped application/package version to `3.0`.
- Updated project README version header, badge, build-output examples, and version history to `v3.0`.

### Removed
- Removed unused UI helper code: `StatStrip`, `is_numeric_column()`, and `format_estimate_table_number()`.
- Removed stale tracked temporary artifacts: `coverage.tmp.xml` and `pyinstaller-windows.out`.

## [2.9.0] - 2026-06-13

### Added
- Added an opt-in full-startup smoke suite that creates a fresh encrypted test database with fixed smoke passwords and seeded catalog/estimate data.
- Added `nox -s smoke_ui` to run the smoke suite in Qt offscreen mode and capture screenshots into `artifacts/smoke-ui/`.
- Added smoke coverage for login setup, existing-password login, main window, estimate entry, item master, estimate history, settings, custom font, item selection, silver-bar management, silver-bar optimization, silver-bar history, and print preview.

### Changed
- Bumped application/package version to `2.9.0`.
- Updated project README version header, badge, build-output examples, and version history to `v2.9.0`.
- Standardized smoke screenshots around a 1366x768 minimum capture size.
- Improved UI copy and layout on login setup, item selection, item master, estimate history, settings, custom font, silver-bar management, and silver-bar history screens based on smoke screenshot review.

### Fixed
- Fixed offscreen smoke capture sizing so the main-window screenshot reflects the normal table layout instead of a narrow maximized-state artifact.
- Fixed silver-bar CSV export to preserve full timestamps while the UI shows shorter date-only values.
- Fixed print preview to default to fit-width when no saved preview zoom exists.

## [2.8.9] - 2026-05-20

### Added
- Added a Qt6 startup bootstrap that disables Windows dark-mode leakage, keeps pytest-qt on PyQt6, and applies high-DPI rounding policy early.
- Added shared light-theme infrastructure for application-wide QSS/palette coverage, management-screen tokens, and visible-arrow combo/spinbox controls.
- Added `print_page_settings.py` to centralize Qt6 page size, orientation, margin, printer, and custom-page helpers.
- Added an estimate table column-spec registry for headers, editability, precision, widths, editor type, and keyboard navigation order.
- Added regression tests for the Qt6 bootstrap, application light theme, visible-arrow controls, print/PDF hardening, and table column contract.

### Changed
- Bumped application/package version to `2.8.9`
- Updated project README version header and badge to `v2.8.9`
- Upgraded the desktop runtime to PyQt6-only and removed PyQt5 compatibility, stubs, packaging paths, and Qt5 residue.
- Updated the PyInstaller spec and local Windows build script for PyQt6/Qt6 resources and Python 3.14 dependency sync.
- Expanded strict light styling across settings, login, file dialogs, menus, combo popups, message boxes, item views, management screens, and print preview controls.
- Finished the follow-up light UI polish across item selection, item master, silver-bar management/history, estimate history, custom font, calendar popups, input/progress dialogs, and high-DPI secondary-window sizing.
- Refactored printing and PDF export to use Qt6 page layout helpers, stale-printer validation, and temp-file replacement before overwriting a target PDF.
- Refactored estimate table model/delegate/controller paths to consume shared column specs while preserving the existing fast-entry workflow.

### Removed
- Removed the stale `pyinstaller-windows.err` PyQt5 build log from the repository.

### Fixed
- Kept the modern estimate print layout final totals at one decimal place instead of rounding them to whole rupees
- Restored visible up/down arrows and combo dropdown arrows under the app's Qt stylesheet.
- Restored visible date-edit arrows under shared Qt stylesheets.
- Prevented long settings-sidebar labels from creating a horizontal scrollbar.
- Guarded PDF export so an empty failed render does not replace an existing output file.

## [2.8.7] - 2026-03-15

### Changed
- Bumped application/package version to `2.8.7`
- Updated project README version header and badge to `v2.8.7`
- Replaced the legacy item import/export workflow with a native `.seitems.json` catalog backup format and renamed the settings workflow around create/restore backup actions
- Removed dead code and stale compatibility scaffolding left behind by recent UI and settings refactors
- Aligned user-facing and documentation terminology around the recovery-password flow

## [2.8.6] - 2026-03-12

### Changed
- Bumped application/package version to `2.8.6`
- Updated project README version header and badge to `v2.8.6`
- Always emitted item-master performance telemetry in CI so perf-budget validation exercises the expected path consistently
- Refined login dialog startup behavior for a smoother initial authentication flow
- Improved silver bar management and syncing behavior across the latest inventory workflow updates

## [2.8.5] - 2026-03-10

### Changed
- Bumped application/package version to `2.8.5`
- Updated project README version header and badge to `v2.8.5`
- Removed legacy `bcrypt` support from the authentication and packaging flow so password hashing is now Argon2-only
- Rebalanced the estimate-entry table layout so item names and weight columns retain space while wage and piece columns stay compact

### Fixed
- Closed the print-preview dialog immediately after a successful quick print instead of leaving the preview open
- Removed the post-print success popup shown after printing from print preview

## [2.8.4] - 2026-03-10

### Changed
- Bumped application/package version to `2.8.4`
- Updated project README version header and badge to `v2.8.4`
- Persisted print-preview changes for orientation, margins, page size, printer choice, and estimate layout so the next print uses the same defaults
- Reduced CI runtime by collapsing duplicated pytest passes and moving non-build validation jobs to `ubuntu-latest`

### Fixed
- Restored print-preview behavior so user-adjusted preview preferences now become the default for subsequent print sessions

## [2.8.3] - 2026-03-10

### Changed
- Bumped application/package version to `2.8.3`
- Updated project README version header and badge to `v2.8.3`
- Darkened and boldened the estimate summary typography for gross, net, fine, and related totals for better readability
- Updated the perf-validation CI tranche to exercise an existing UI path that emits `[perf]` telemetry, keeping the local/CI perf gate meaningful
- Re-ran and stabilized the local `nox -s ci` pipeline under the project Python 3.13 virtualenv

### Fixed
- Corrected the DDASilver `Silver Agra Local Mohar` live-rate fetch to prefer the homepage-advertised broadcast endpoint
- Resolved pre-existing `ruff` import-order drift and `mypy` typing mismatches that were blocking local CI

## [2.8.1] - 2026-03-08

### Changed
- Bumped application/package version to `2.8.1`
- Updated project README version header and badge to `v2.8.1`
- Applied the CI-required import sorting and small type-safety fixes across the release branch

### Fixed
- Resolved the `Ruff` import-order failures introduced during the `v2.8` UI and print-preview work
- Resolved `mypy` failures in the icon helper, print preview, print manager, settings print controller, secondary action bar, and Windows startup path
- Restored green `main` validation for the post-release branch state

## [2.8] - 2026-03-08

### Changed
- Bumped application/package version to `2.8`
- Updated project README version header and badge to `v2.8`
- Tightened the estimate-entry action layout so the toolbar reads more compactly without costing table space
- Standardized mdi6-based icons across the estimate workflow and supporting dialogs
- Rebuilt the print-preview toolbar into a single consistent action set with clearer grouping for print/export, layout, zoom, and navigation

### Fixed
- Restored visible primary save-button styling on the estimate screen by correcting the scoped stylesheet selector
- Collected `qtawesome` resources in the Windows build spec so packaged icons render reliably
- Removed duplicated built-in preview actions that were leaving mixed icon sets in the print-preview toolbar

## [2.7] - 2026-03-07

### Changed
- Bumped application/package version to `2.7`
- Updated project README version header and badge to `v2.7`
- Added maintainer documentation for the DDASilver live-rate source policy, purity-adjusted fallback, and the current HTTPS limitation

### Fixed
- Restored the DDASilver `Silver Agra Local Mohar` fallback calculation to the required purity-adjusted live rate

## [2.6.10] - 2026-03-07

### Added
- Added `.python-version` pinning and documented `python`-first local setup flows for the project environment
- Added targeted settings, totals, and silver-bar controller test coverage around the ongoing refactor work

### Changed
- Refactored print preview, print settings, and silver-bar management workflows into smaller focused controllers/helpers
- Consolidated estimate totals calculation logic into a shared domain helper used by both full and incremental paths
- Standardized repository scripts and developer docs on `python` and `python -m ...` commands
- Bumped application/package version to `2.6.10`
- Updated project README version header and badge to `v2.6.10`

### Fixed
- Cleared remaining `bandit` advisory failures in the DDASilver fetcher and print-preview cleanup paths
- Revalidated lint, typing, tests, coverage, security checks, and packaging on Python `3.13.12`

## [2.6.9] - 2026-03-07

### Added
- Added numeric-column typography improvements in the estimate table using a dedicated numeric font path for display and edit states

### Fixed
- Removed unreachable legacy exception block in `EstimatesRepository._voucher_to_int`
- Moved estimate-history button re-enable logic into reachable `_loading_done` completion path
- Split estimate-entry numeric `DisplayRole` and `EditRole` values so formatted table cells still edit with raw numeric text
- Applied Indian-style digit grouping across estimate table numeric columns and summary totals
- Aligned estimate-table numeric display, parsing, and validation around a shared locale-aware formatting path

### Changed
- Performed a full dead-code cleanup sweep across `main.py` and `silverestimate/**` (unused imports/locals, stale compatibility scaffolding, wildcard constant exports)
- Bumped application/package version to `2.6.9`
- Updated project README version header and badge to `v2.6.9`

### Removed
- Deleted two dormant UI modules (unused mode-toggle component and legacy table-font dialog)
- Removed obsolete mode-toggle export from `silverestimate/ui/estimate_entry_components/__init__.py`
- Removed legacy-only unit test surface for the deleted mode-toggle component

## [2.6.8] - 2026-02-22

### Changed
- Bumped application/package version to `2.6.8`
- Updated project README version header and badge to `v2.6.8`
- Performed repository hygiene updates (main-only branch model, release-page cleanup, and stale-reference documentation alignment)

## [2.6.7] - 2026-02-18

### Changed
- Bumped application/package version to `2.6.7`
- Updated project README version header and badge to `v2.6.7`
- Documented live-rate source policy to keep DDASilver target item fixed to `Silver Agra Local Mohar` until requirements explicitly change

### Fixed
- Corrected live-rate parsing for DDASilver `Silver Agra Local Mohar` to use the target row commodity value directly (no purity adjustment)

## [2.6.3] - 2026-02-14

### Changed
- Bumped application/package version to `2.6.3`
- Updated project README version header and badge to `v2.6.3`

## [2.6.2] - 2026-02-13

### Changed
- Bumped application/package version to `2.6.2` for the next release build
- Release workflow now explicitly publishes non-prerelease GitHub releases
- Release workflow now explicitly publishes non-draft GitHub releases

## [2.6.1] - 2026-02-13

### Fixed
- Fixed estimate history dialog worker callback binding to prevent `TypeError` on repeated opens
- Hardened history load signal handlers against argument-shape mismatches from queued thread signals

## [2.6] - 2026-02-13

### Changed
- Updated CI so the Windows executable build runs at workflow completion (`if: always()`)
- Added artifact upload for the built `SilverEstimate.exe` in PR validation workflow runs
- Improved summary totals drag/drop so dropping on a card swaps reliably and supports moving `Final Calculation`

## [2.54] - 2026-02-13

### Changed
- Added draggable summary cards with persisted custom ordering in estimate totals
- Enabled reordering of the `Final Calculation` card alongside other summary sections
- Improved summary-card sizing to better adapt to panel width/content changes

### Fixed
- Resolved drag/drop cases that could hide a summary card when dropped over another card
- Normalized drop behavior so dropping on a card swaps positions consistently

## [2.53] - 2026-02-13

### Changed
- Reworked estimate table cursor and row-navigation behavior for manual and keyboard movement
- Enabled arrow-key movement for the in-cell text cursor during estimate entry
- Estimate History now initializes `From` date to the first available estimate date

### Fixed
- Removed row-jump loops that could lock the UI when moving to previous rows
- Prevented not-responding behavior triggered by row clicks during active editing

## [2.5] - 2025-11-18

### Changed
- Decomposed the estimate entry workflow to improve readability and UI information density
- Made action bars and toolbar buttons more compact for smaller displays
- Expanded keyboard shortcut coverage (Ctrl+S/P/N/R/B/D/H) and resolved conflicts

### Fixed
- Prevented segmentation faults when deleting rows with Ctrl+D
- Ensured mode toggle buttons keep row types and display names in sync
- Clarified empty row detection and reduced layout regressions introduced in prior releases

## [2.0.3] - 2025-10-29

### Fixed
- Fixed UI layout issues on small screens where toggle buttons expanded and pushed elements off screen
- Set maximum width (150px) for Return and Silver Bar toggle buttons
- Shortened button text when active to prevent layout expansion
  - Return mode: "↩ RETURN ON" (was "↩ Return Items Mode ACTIVE")
  - Silver Bar mode: "🥈 BAR ON" (was "🥈 Silver Bar Mode ACTIVE")

### Changed
- Improved button labels for better space utilization on smaller resolutions

## [2.0.2] - 2025-10-29

### Fixed
- Fixed segmentation fault on startup by delaying signal connection
- Fixed RuntimeError with deleted QTableWidgetItem in table operations
- Replaced unsafe lambda captures with `_safe_edit_item()` calls in table.py

### Added
- Added guard to prevent auto-loading empty voucher numbers
- Delayed signal connection by 100ms to ensure UI is fully initialized

### Changed
- Improved startup reliability and error handling

## [2.0.1] - 2025-09-16

### Fixed
- Fixed broadcast rate fetch and improved error handling
- Improved network connectivity for live silver rate updates

## [2.0.0] - 2025-09-15

### Changed
- Major version bump for architectural improvements
- Enhanced overall stability and performance
- Code refactoring and optimization

## [1.72.7] - 2025-09-16

### Fixed
- Hardened shutdown process to prevent duplicate DatabaseManager closes
- Eliminated false critical temp-file warnings on application exit

## [1.72.5] - 2025-09-14

### Fixed
- Ensured encryption reads a complete WAL snapshot before sealing
- Eliminated session-only data loss issues
- Serialized encryption with explicit locks
- Postponed shutdown until flush work completes

### Improved
- Item Master persistence messaging
- Flush lifecycle logs

## [1.72.4] - 2025-09-14

### Added
- Refresh button next to Live Silver Rate display
- Async live rate fetch with broadcast/API fallback

### Fixed
- Fixed Estimate History action methods location

### Changed
- Minor layout polish and improved tooltips

## [1.72.3] - 2025-09-13

### Performance
- Faster startup via lazy imports
- Prepared cursors for database operations
- Indexed lookups and batched inserts
- Async flush hygiene on close

### Added
- Inline "Saving." status hint

## [1.72.2] - 2025-09-13

### Performance
- Debounced async encryption flush
- Optimized history aggregations and UI batching
- Debounced totals calculations

### Fixed
- Minor bug fixes and stability improvements

---

## Legend

- **Added**: New features
- **Changed**: Changes in existing functionality
- **Deprecated**: Soon-to-be removed features
- **Removed**: Removed features
- **Fixed**: Bug fixes
- **Security**: Security improvements
- **Performance**: Performance enhancements
