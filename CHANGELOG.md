# Changelog

All notable changes to the Silver Estimation App will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
