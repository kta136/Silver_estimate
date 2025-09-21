# Changelog (Silver Estimate)

This file tracks notable changes, fixes, and decisions for the Silver Estimate project.

## Release v1.72.7 (2025-09-16)

- Database: Prevent false critical temp-file warnings when shutdown triggers multiple DatabaseManager closes; only flag when encryption genuinely fails.

## Release v1.72.5 (2025-09-14)

- Persistence: Fixed session-only data issue by ensuring encryption reads a complete DB image.
  - Added WAL checkpoint before encrypting and a snapshot via SQLite backup API.
  - Commit now runs only on the connection's owner thread to avoid cross-thread errors.
  - Serialized encryption with a lock and extended shutdown wait for background flush.
- Item Master: Items reliably persist across restarts; continued UI polish for status messages.
- Logs: More precise messages around flush/encrypt lifecycle to aid troubleshooting.

## Release v1.72.4 (2025-09-14)

- UI: Added a refresh icon button for Silver Rate and placed it next to the Live Silver Rate field for quick manual updates.
- Logic: Implemented `refresh_silver_rate()` to fetch live rates (broadcast-first with API fallback) without blocking the UI.
- History: Fixed AttributeError in Estimate History by ensuring print/delete helpers live on the dialog class, not the worker.
- UX: Minor layout polish and tooltips for the new refresh control.

## Release v1.72.3 (2025-09-13)

- Startup: Lazy-import rarely used windows (Item Master, Settings, Silver Bar History) to reduce initial load time.
- History: Background-threaded history load with headers-only query + single aggregate for regular-only totals.
- Database: Case-insensitive indexed item lookup (NOCASE) and added `idx_estimates_date` for faster date filters.
- Database: Prepared cursors for hot statements and batch `executemany` insert of `estimate_items` on save.
- Items: Warm up in-memory item cache at startup for faster code validations.
- Close hygiene: Cancel pending flush and briefly wait on in-progress encryption worker during shutdown.
- UI: Inline "Saving…" hint during debounced async flush (cleared on completion).

## Release v1.72.2 (2025-09-13)

- Performance: Debounced, async database encryption flush to avoid UI stalls.
- Performance: Optimized history view by aggregating regular gross/net via a single SQL query.
- Performance: Batching applied to selection dialog table updates to cut repaints/signals.
- DB: Added index `idx_estimate_items_code` and PRAGMA verification logs on connect.
- UI: Debounced totals recalculation for smoother editing.
- Fix: Resolved indentation error in `silverestimate/ui/estimate_entry.py` for `show_inline_status`.
- Docs: Updated `PERFORMANCE_OBSERVATIONS.md` to reflect completed optimizations.

## Release v1.70 (2025-09-06)

- UI/UX: Enhanced tooltips system with comprehensive help and format guidance throughout the application
- UI/UX: Mode button visual enhancement with distinct color schemes (blue for Return Items, orange for Silver Bar modes)
- UI/UX: Mode buttons now include icons (↩ Return, 🥈 Silver Bar) and "ACTIVE" text for clear visual feedback
- UI/UX: Mode indicator label styling coordinated with button colors for consistent visual language
- UI/UX: Header field spacing improvement with logical grouping using subtle "|" separators
- UI/UX: Enhanced professional layout with proper spacing (15px between groups) while maintaining single-row efficiency
- Tooltips: All input fields now have detailed format explanations, ranges, and examples
- Tooltips: Button tooltips include keyboard shortcuts (Ctrl+S, Ctrl+P, etc.) for better discoverability
- Tooltips: Context-aware help for setup vs login modes in authentication dialog
- Build: Version bumped to v1.70; prepared for Windows executable rebuild
- Touched files: `silverestimate/ui/estimate_entry_ui.py`, `silverestimate/ui/estimate_entry.py`, `silverestimate/ui/settings_dialog.py`, `silverestimate/ui/login_dialog.py`, `silverestimate/ui/item_selection_dialog.py`, `silverestimate/infrastructure/app_constants.py`, `DOCS/UI_UX_RECOMMENDATIONS.md`

## Release v1.69 (2025-09-05)

- UI: Status messages now display inline next to the Mode label in the header to prevent window reflows and flicker.
- Startup: Initial "Ready" and "Database connected securely" messages route to the inline label.
- Cleanup: Top `MessageBar` instance retained for fallback but removed from the layout to avoid resizing.
- Build: Rebuilt Windows executable as `SilverEstimate-v1.69.exe`; created Git tag `v1.69` and GitHub release.
- Touched files: `main.py`, `silverestimate/ui/estimate_entry.py`, `silverestimate/ui/estimate_entry_ui.py`, `silverestimate/ui/message_bar.py`, `silverestimate/infrastructure/app_constants.py`, `requirements.txt`, `README.md`.

## Table of Contents
- [Comprehensive Logging System Design & Integration (2025-05)](#comprehensive-logging-system-design--integration-may-2025)
- [Estimate Loading Architecture Stabilization (2025-05)](#estimate-loading-architecture-stabilization-may-2025)
- [Security Architecture Summary (2025-05)](#security-architecture-summary-may-2025)
- [Data Model, Integrity, and Migrations (2025-05)](#data-model-integrity-and-migrations-may-2025)
- [Silver Bar Lifecycle: Permanent Bars With Controlled Deletion (Apr-May 2025)](#silver-bar-lifecycle-permanent-bars-with-controlled-deletion-apr-may-2025)
- [Core Business Logic and UI Patterns (May 2025)](#core-business-logic-and-ui-patterns-may-2025)
- [Performance Optimization Playbook (May 2025)](#performance-optimization-playbook-may-2025)
- [Testing Implementation Playbook (May 2025)](#testing-implementation-playbook-may-2025)
- [Deployment and Packaging Notes (May 2025)](#deployment-and-packaging-notes-may-2025)
- [Project Overview & Roadmap Highlights (May 2025)](#project-overview--roadmap-highlights-may-2025)

## Comprehensive Logging System Design & Integration (May 2025)

- Summary: Introduced a robust, configurable logging architecture replacing print statements, with selective log levels, rotation, cleanup, Qt integration, and Settings UI control.
- Files: `silverestimate/infrastructure/logger.py`, `main.py`, `silverestimate/ui/settings_dialog.py`, `DOCS/logging-system-technical-guide.md`, `DOCS/logging_features.md`
- Capabilities:
  - Three file streams: `silver_app.log` (INFO+), `silver_app_error.log` (ERROR/CRITICAL), `silver_app_debug.log` (all when debug enabled)
  - Size-based rotation (5–10MB) with archived backups
  - Selective enabling/disabling: info, error, debug logs independently
  - Qt message redirection via `qt_message_handler`
  - Status bar integration via `LoggingStatusBar`
  - Automatic daily cleanup with configurable retention (1–365 days) using `LogCleanupScheduler`
  - Environment overrides: `SILVER_APP_DEBUG`, `SILVER_APP_LOG_DIR`
- Key APIs:
  - `setup_logging(app_name="silver_app", log_dir="logs", debug_mode=False, enable_info=True, enable_error=True, enable_debug=True) -> logging.Logger`
  - `get_log_config() -> dict` reads QSettings + env for: `debug_mode`, `log_dir`, `enable_info`, `enable_error`, `enable_debug`, `auto_cleanup`, `cleanup_days`
  - `cleanup_old_logs(log_dir, max_age_days) -> int` removes old rotated logs
  - `class LogCleanupScheduler` schedules daily cleanup at midnight
- Settings UI:
  - New Logging tab (in `silverestimate/ui/settings_dialog.py`): toggle each log stream, enable Debug Mode, configure auto-cleanup and retention, and run manual cleanup
- Best practices:
  - Avoid logging secrets; use sanitization utilities
  - Use WARN for potential issues and INFO for business events; reserve CRITICAL for abort conditions
  - Prefer lazy evaluation for expensive DEBUG messages

## Estimate Loading Architecture Stabilization (May 2025)

- Summary: Resolved startup crashes by making loading explicit and guarding initialization.
- Files: `silverestimate/ui/estimate_entry.py`, `silverestimate/ui/estimate_entry_logic.py`, `silverestimate/ui/estimate_entry_ui.py`, `DOCS/estimate_loading_architecture.md`, `DOCS/estimate_loading_fix.md`
- Changes:
  - Added `initializing` flag to prevent premature loads during widget setup
  - Replaced implicit load on `editingFinished` with explicit "Load" button
  - Implemented `safe_load_estimate()` wrapper with exception handling and signal disconnect/reconnect to avoid recursion
  - Added `generate_voucher_silent()` to set voucher without emitting signals
- Lessons:
  - Avoid connecting heavy slots before UI is fully constructed
  - Prefer explicit user actions for destructive/heavy operations
  - Wrap DB/UI interactions with safe guards and user-facing error messages

## Security Architecture Summary (May 2025)

- Summary: Multi-layered security protecting data at rest with AES-256-GCM, Argon2 password hashing, and per-installation salts.
- Files: `silverestimate/ui/login_dialog.py`, `silverestimate/persistence/database_manager.py`, `DOCS/security-architecture.md`
- Key elements:
  - Dual-password system: Primary (access) and Secondary (data wipe trigger)
  - Argon2 hashing via passlib; salts stored in `QSettings`
  - Key derivation using PBKDF2-HMAC-SHA256 (configurable iterations) to 256-bit keys
  - Encrypted DB format: `nonce(12b) + ciphertext(+tag)`; temp plaintext file used only during sessions; secure cleanup on exit
  - Data wipe clears encrypted DB, password hashes, and salt
- Limitations/Future:
  - Single-user, local-only access model; consider 2FA, RBAC, audit logging later

## Data Model, Integrity, and Migrations (May 2025)

- Summary: Normalized schema with strict FK rules and versioned migrations enabling safe evolution.
- Files: `silverestimate/persistence/database_manager.py`, `DOCS/data-model-relationships.md`
- Core tables: `items`, `estimates`, `estimate_items`, `silver_bars`, `silver_bar_lists`, `bar_transfers`, `schema_version`
- Relationships and cascades:
  - `estimates` 1–M `estimate_items` (DELETE CASCADE)
  - `estimates` 1–M `silver_bars` (DELETE CASCADE)
  - `silver_bar_lists` 1–M `silver_bars` (ON DELETE SET NULL)
  - `silver_bars` 1–M `bar_transfers` (DELETE CASCADE)
- Integrity rules:
  - Codes uppercase unique; sequential voucher numbers
  - Fine/net/wage calculations normalized to stored columns
  - Status set: In Stock, Assigned, Sold, Melted
- Migrations:
  - `schema_version` table; forward-only numbered migrations; automatic ALTERs for new columns (e.g., `estimates.note`)

## Silver Bar Lifecycle: Permanent Bars With Controlled Deletion (Apr–May 2025)

- Summary: Prevented accidental loss of silver bar records by eliminating unsafe REPLACE patterns and clarifying lifecycle.
- Files: `silverestimate/persistence/database_manager.py`, `silverestimate/ui/estimate_entry_logic.py`, `silverestimate/ui/silver_bar_management.py`, `silverestimate/ui/print_manager.py`
- Root causes addressed:
  - `INSERT OR REPLACE` on `estimates` triggered implicit DELETE and FK CASCADE on `silver_bars`
  - Re-saves created duplicate bars
- Fixes:
  - Use UPSERT logic: INSERT for new, UPDATE for existing estimates (no REPLACE)
  - Create bars only on first save; skip if bars already exist for voucher
  - Bar management (assignment/status/listing) handled solely in Silver Bar UI
  - Comprehensive delete path: deleting an estimate deletes its bars; empties lists pruned

## Core Business Logic and UI Patterns (May 2025)

- Summary: Strong separation of UI and calculations with signal-safe updates and validators.
- Files: `silverestimate/ui/estimate_entry.py`, `silverestimate/ui/estimate_entry_ui.py`, `silverestimate/ui/estimate_entry_logic.py`, `DOCS/workflow-business-logic.md`
- Calculations:
  - Net = Gross − Poly; Fine = Net × (Purity/100)
  - Wage: PC = Pieces × Rate; WT = Net × Rate
  - Net Fine = Regular − Return − Silver Bar; Grand Total = (Net Fine × Silver Rate) + Net Wage + Last Balance Amount
- UI/UX:
  - Numeric delegates for validation; keyboard-first navigation; skip calculated cells
  - Mode toggles for Regular/Return/Silver Bar with clear indicators
  - Print preview integrates Indian number formatting and compact templates

## Performance Optimization Playbook (May 2025)

- Summary: Patterns to keep UI responsive and DB access fast.
- Files: `DOCS/performance-optimization.md`
- UI:
  - Batch updates with signals blocked + `viewport().update()`
  - Defer recalcs via `QTimer.singleShot`; throttle frequent signals
  - Lazy-load heavy widgets; virtual scrolling models for large datasets
- DB:
  - Proper indexes on hot columns; batch inserts with transactions
  - Prepared statements and simple connection pooling patterns
  - Caching for expensive queries with TTL and size limits
- Monitoring:
  - `PerformanceProfiler` and `PerformanceMonitor` helpers; memory leak detector via `weakref` + GC

## Testing Implementation Playbook (May 2025)

- Summary: Multi-level pytest suite with focus on calculations, persistence, and UI behavior.
- Files: `DOCS/testing-implementation-playbook.md`
- Levels: Unit (logic), Integration (DB+UI), System (E2E flows), UAT
- Security tests: hash verification, decrypt/encrypt cycles, wipe flow
- Performance tests: large-table operations and memory profiling
- CI example: GitHub Actions workflow sets up PyQt, crypto deps, and runs pytest with coverage

## Deployment and Packaging Notes (May 2025)

- Summary: PyInstaller builds for Windows/macOS/Linux with platform packaging.
- Files: `DOCS/deployment-guide.md`
- Windows: onefile `--windowed`, Inno Setup installer, versioned metadata
- macOS: `.app` bundle with `Info.plist`, codesigning, DMG creation
- Linux: AppImage with AppDir layout and desktop entry
- Dependency pins in `requirements.txt` and dev tooling in `requirements-dev.txt`

## Project Overview & Roadmap Highlights (May 2025)

- Summary: Current strengths and areas for growth.
- Files: `DOCS/project-summary.md`, `DOCS/project-architecture.md`, `DOCS/component-analysis.md`
- Strengths:
  - Encrypted local data, modular UI, robust calculations, silver bar inventory with list-based organization
  - Clear component boundaries and signal/slot patterns scale well
- Limitations:
  - Single-user, local-only; Windows-first
  - Memory footprint ~200MB typical; cross-platform rendering variance
- Opportunities:
  - Multi-user roles, cloud sync, advanced reporting, barcode/QR integration
  - Async DB ops, broader test coverage, backup/restore UX
