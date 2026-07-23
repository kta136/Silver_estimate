# Changelog

## Unreleased

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
