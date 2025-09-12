# SilverEstimate Project Recommendations

This document captures a focused, actionable set of recommendations after reviewing the current repository. Items are sorted by difficulty (easiest → hardest) to help plan implementation order.

## Quick Wins

- main.py: Remove duplicate directory creation call when setting up the DB path.
- Replace hardcoded `QSettings("YourCompany", "SilverEstimateApp")` with `QSettings(SETTINGS_ORG, SETTINGS_APP)` and import constants from `app_constants.py`.
- Add WAL mode on connect for SQLite.
- Update CI workflow to use `silverestimate.spec` and package `dist/SilverEstimate/` as a versioned zip.
- Persist table layouts and splitter sizes for Item Master, Estimate History, Silver Bar Management.
- Add 250–300ms debounce to text-based searches (Item Master, Estimate History).
- Enable batch actions (multi-select print/export/delete) in Estimate History with clear confirmations.

## Docs

- Keep README and code in sync: Remove or implement `SILVER_APP_ENCRYPTION_KEY` in code.
- Data locations: Add a section documenting where DB/logs/backups live on each OS (using `QStandardPaths`).
- Build matrix: Clarify supported platforms for builds (Windows CI present; macOS/Linux builds listed as future/optional in README).

## Code Quality

- Type hints: Add type annotations for public APIs in `database_manager.py`, import/export managers, and critical UI methods. Improves static analysis and maintainability.
- Linters/formatters: Add `ruff` and `black` via pre-commit. Start by enforcing only on changed files to avoid massive diffs.
- Remove unused imports and small nits:
  - `database_manager.py`: `hashlib` appears unused.
  - `main.py`: redundant `from PyQt5.QtGui import QKeySequence` near menu setup.
- Replace hardcoded QSettings IDs with imports from `app_constants.py` for consistency.

## UX

- High DPI support: Before creating `QApplication`, set attributes `Qt.AA_EnableHighDpiScaling` and `Qt.AA_UseHighDpiPixmaps` for sharper rendering on high-DPI displays.
- Centralized error reporter: Wrap repetitive `QMessageBox.critical` patterns with a helper that logs full tracebacks and shows user-friendly messages consistently.
- Persist last active view: You already persist window geometry/state; also persist the last active page (Estimate/Item Master/Silver Bars) for a smoother resume.

### UI/UX (Window Reviews)

Item Master (item_master.py)
- Persist table layout: save/restore column widths, sort order, and visibility via `QHeaderView.saveState()`/`restoreState()` and `QSettings`.
- Debounced search: add 250–300ms debounce on `textChanged` to avoid DB chatter while typing.
- Filter chips: quick filters for Wage Type (PC/WT) and non-zero wage, plus purity ranges.
- Empty states: when no items match, show a helpful message and a “Clear Filter” action.
- Inline validation: style invalid fields (empty/duplicate code, empty name); disable Add/Update until valid.
- Context menu: right-click row → Open in estimate, Duplicate, Delete, Export selected.
- Keyboard: Enter to Add/Update, Esc to clear selection, Ctrl+F to focus search.
- Bulk actions: allow multi-select rows for Delete and Export CSV.
- Discoverability: surface Import/Export buttons (reuse existing managers).

Estimate History (estimate_history.py)
- Two-pane layout: optional details pane shows line items for the selected estimate for quick preview.
- Persist filters/state: remember date range, voucher search, dialog size/position, and sort per column.
- Debounced voucher search: 250ms debounce for snappier UX.
- Batch actions: multi-select → Print, Export CSV/PDF, or Delete with counts and progress feedback.
- Column UX: ellipsis for long Note with full tooltip; enable header sorting and persist it.
- Safety: clearer delete prompts with exact count; consider soft-delete (undo) with later purge.
- Shortcuts: Enter=Open, Ctrl+P=Print, Del=Delete, Esc=Close.

Silver Bar Management (silver_bar_management.py)
- Persist UI state: splitter sizes; table layouts and sort states for Available vs List tables (unique QSettings keys).
- Dynamic affordances: enable/disable transfer buttons based on selections; include counts in button labels (e.g., “→ Add (3)”).
- Feedback style: prefer non-blocking toasts for success/info; reserve modals for confirmations/errors.
- Issued lists: read-only view or filter for issued lists; add clear badges; prevent edits.
- Performance: consider `QAbstractTableModel` instead of `QTableWidget` for large datasets.
- Keyboard: Enter to add selected; Backspace/Delete to remove; Ctrl+A select all; F5 refresh.
- CSV import/export: export exists; optionally add admin import with validation and preview.

Settings Dialog (settings_dialog.py)
- Search within settings: filter sidebar/page labels and highlight matching controls.
- Per-section reset: “Restore defaults” for a section, in addition to global reset.
- Live previews: add table font live sample and a simple margins preview graphic.
- Danger Zone: move wipe/reset actions to a clearly separate section with multi-step confirmation and time delay.
- Logging controls: expose debug/info/error toggles, auto-cleanup days, and a “Clean Now” button (hooks into `logger.reconfigure_logging()`/`cleanup_old_logs`).
- Settings export/import: export QSettings to JSON and restore with conflict prompts.
- Printer UX: show current default; warn when the chosen default printer is unavailable.
- Apply feedback: subtle “Settings applied” toast on successful apply.

Login Dialog (login_dialog.py)
- Show-password toggle (eye icon), caps-lock warning, and strength indicator during setup.
- Clarify secondary password purpose with a concise note and “Learn more” link.
- Improve error text for incorrect password; keep reset/wipe clearly separated.
- Keyboard polish: Enter submits, Esc cancels; audit tab order.

Item Selection Dialog (item_selection_dialog.py)
- Fuzzy search with ranked results and match highlighting.
- Recents/favorites management; pin favorites at top.
- Keyboard-first flow: Up/Down to navigate, Enter to select, Esc to close, Ctrl+F to focus search.
- Persist window size and the last-used filter.

## Logging

- Path location: Move default log directory to the user-data location (see Data & Storage) and keep it configurable via `QSettings` and `SILVER_APP_LOG_DIR` env var.
- Console handler: Make console logging optional via a `logging/enable_console` setting (default off for production).
- Retention: You already have scheduled cleanup. Consider also enforcing a total size cap for the log directory.

## Architecture

- Centralize QSettings IDs: Use the constants from `app_constants.py` everywhere (`SETTINGS_ORG`, `SETTINGS_APP`) so all components share the same settings store.
  - Update usages like `QSettings("YourCompany", "SilverEstimateApp")` in:
    - `logger.py`
    - `database_manager.py`
    - Any other occurrences
- Set application identity once: In your bootstrap (before any `QSettings`), call `QCoreApplication.setOrganizationName(SETTINGS_ORG)` and `QCoreApplication.setApplicationName(SETTINGS_APP)`. Then prefer `QSettings()` without explicit IDs.
- Split responsibilities in `main.py`: Extract the authentication/bootstrap routines (safe_start_app/run_authentication) to `app.py` (or `bootstrap.py`). Keep `MainWindow` focused on UI.

## Database

- Indexes: Add indexes for frequent access patterns to improve UI responsiveness:
  - `CREATE INDEX IF NOT EXISTS idx_estimate_items_voucher ON estimate_items(voucher_no);`
  - `CREATE INDEX IF NOT EXISTS idx_estimates_date ON estimates(date);`
- Pragmas on connect: For single-user desktop apps, `PRAGMA journal_mode=WAL; PRAGMA synchronous=NORMAL;` generally improves UX with minimal risk.
- Voucher number generation: Current logic casts voucher numbers to integer which is good; ensure a UNIQUE constraint or check prevents duplicates during concurrent sessions (low risk on desktop, but easy safeguard).
- Migrations: You maintain a `schema_version` table and conditional DDL. Consider a simple migration runner using sequential `.sql` files (V1.sql, V2.sql…), applied in order, to simplify branching and reviews.

## Packaging & Release

- Align CI with your spec: `.github/workflows/release-windows.yml` uses an ad-hoc, one-file build named `SilverEstimate.exe`. Switch to building with `silverestimate.spec` so CI outputs match your local script (`scripts/build_windows.ps1`) and include hidden imports/UPX settings consistently.
  - Zip the `dist/SilverEstimate/` folder as `SilverEstimate-vX.YY-win64.zip`, using the app version from `app_constants.py`.
- Icon and version resource: Add the icon and version metadata to the spec (README’s alternative build references them; keep the spec as the single source of truth).
- UPX toggle: Keep UPX on by default, but allow disabling via an environment flag in CI to avoid antivirus false positives.
- Code signing (optional): Integrate certificate-based signing for Windows if available; otherwise document manual signing in `DOCS/deployment-guide.md`.

## Testing

- Add an initial, minimal test suite to cover critical flows:
  - DB encryption round-trip: derive key → encrypt temp sqlite → decrypt and validate.
  - Voucher number generation with non-numeric vouchers present.
  - Item import: parsing, duplicate handling, validation feedback.
  - Silver bar lists: create, assign, transfer/issue flows using an in-memory DB.
- Headless Qt smoke test: Use the offscreen platform plugin to validate Login/DB setup without a display server.
- CI gate: Add a test job to CI before the build job runs.

## Data & Storage

- Use platform user-data locations for DB and logs instead of the repo’s `database/` and `logs/` directories. On Windows, writing under `Program Files` will fail.
  - Compute paths via `QStandardPaths.writableLocation(QStandardPaths.AppDataLocation)` and `AppLocalDataLocation`.
  - Create subfolders (`database/`, `logs/`, `backups/`) and ensure they exist at startup.
  - Provide a migration step if an existing DB is found at the old path.
- Add periodic, verifiable backups for SQLite:
  - Daily copy to `backups/` with retention (e.g., 7–30 days).
  - Before encrypting, run `PRAGMA quick_check` on the temp DB; only persist a backup if it passes.
- Remove duplicate directory creation call in `main.py` (there are two `os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)` in a row).

## Security

- KDF for DB encryption: Consider moving from PBKDF2HMAC to Argon2id (consistent with password hashing via passlib). If staying with PBKDF2, increase iterations (e.g., 300k–600k on modern hardware) and make it configurable with sane defaults.
- Salt storage: Keeping the salt in `QSettings` is acceptable; document this in `DOCS/security-architecture.md`. Optionally, store a small metadata file next to the encrypted DB with restricted ACLs.
- Crash recovery hygiene: You already store a plaintext temp DB path for recovery. On successful close, it’s cleared. Add a startup sweep to prune orphaned temp DB files older than N hours in the OS temp directory.
- README mentions `SILVER_APP_ENCRYPTION_KEY`, but `DatabaseManager` does not implement an override. Either implement a carefully documented override (and disable for production builds), or remove it from README to prevent confusion.

## Suggested Next Steps

1) Paths and Settings (high impact, low risk)
- Introduce a `paths.py` that resolves `DB_PATH`, `LOG_DIR`, and `BACKUP_DIR` via `QStandardPaths` with fallbacks.
- Replace direct paths in `app_constants.py` with calls into `paths.py` (or compute at startup and pass around).

2) QSettings Consistency (low risk)
- Add `QCoreApplication.setOrganizationName` and `setApplicationName` in the bootstrap function and switch remaining explicit QSettings calls to use constants.

3) CI Alignment (medium impact)
- Modify `.github/workflows/release-windows.yml` to build with `silverestimate.spec` and zip the versioned output folder. Optionally add a test job running `pytest` first.

4) Migrations and Indexes (medium impact)
- Add the two indexes listed above and a minimal migration framework (or keep in-code migrations but isolate them cleanly).

5) Security Hardening (medium impact)
- Increase PBKDF2 iterations (or migrate to Argon2id for DB encryption), add an optional setting to configure the KDF cost, and document the salt location.

---

If you want, I can implement any or all of the Quick Wins and wire up `QStandardPaths`-based locations, then adjust the CI workflow to use the spec-based build and versioned artifacts.

