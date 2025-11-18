# Changelog

All notable changes to the Silver Estimation App will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
