# Silver Estimation App - Project Memory Bank

Generated: 2025-09-20
Maintainer: SilverEstimate team (update contact as needed)

## Snapshot
- Current version: 1.72.7 (see silverestimate/infrastructure/app_constants.py)
- Refactor milestone: controllers/services/persistence split in place; DatabaseManager now acts as lifecycle/encryption facade.
- Application type: offline PyQt5 desktop app with encrypted SQLite persistence
- Primary entry: main.py -> main() bootstraps logging, authentication, and MainWindow
- Core mission: manage silver sales estimates, silver bar inventory, returns, and print-ready output

## How To Use This Document
- Treat this file as the shared memory bank between sessions; update it whenever notable work happens.
- Add dated notes under "Session Journal" so future contributors understand context and decisions.
- Cross link to source files or existing DOCS entries instead of duplicating deep explanations.
- Keep entries concise and ASCII-only to preserve compatibility with automation.

## Application Flow Overview
1. Startup (main.py): configure logging, install Qt message handler, instantiate QApplication, run authentication, open MainWindow.
2. Controller layer (silverestimate/controllers/*): StartupController authenticates/wires DatabaseManager; NavigationController builds menus and routes actions; LiveRateController manages periodic rate refresh.
3. Authentication (silverestimate/services/auth_service.py): LoginDialog drives first-time setup, password verification, or data wipe trigger; settings stored via QSettings at SETTINGS_ORG/SETTINGS_APP.
4. Database bootstrap (silverestimate/persistence/database_manager.py): decrypts encrypted DB into a temporary file, runs migrations, wires repositories, schedules flushes, and re-encrypts on close.
5. Main window (main.py MainWindow): loads settings, builds menus and toolbars, registers navigation stack, instantiates EstimateEntryWidget and lazy modules, connects message bar and status handling.
6. Live operations: LiveRateService polls broadcast/API silver rates on a timer; controllers/services coordinate view switches and actions; MessageBar surfaces inline notifications.
6. Shutdown: flush scheduler commits outstanding work, encrypts database, stops cleanup threads, and closes connections.

## Package Map
- main.py: application shell, logging/bootstrap, dependency wiring, menu command registration, shutdown handling.
- silverestimate/ui: Qt widgets for estimates, item master, silver bar management, dialogs (font, login, message bar) and navigation scaffolding.
- silverestimate/services: functional services such as authentication, live rate fetching, command handlers, settings, navigation, and print helpers.
- silverestimate/persistence: DatabaseManager, migrations, repositories (items, estimates, silver bars), flush scheduler, and cache controller.
- silverestimate/infrastructure: logging configuration, constants, threading guards, utility helpers.
- silverestimate/security: encryption utilities (salt management, key derivation, AES-GCM payload helpers).

## Data, Persistence, and Security
- Encrypted database stored at database/estimation.db; decrypted temp path recorded in QSettings under security/last_temp_db_path to recover after crashes.
- crypto_utils wraps AES-256-GCM encryption; salts persisted via QSettings (security/db_salt); key derivation uses PBKDF2 with DEFAULT_KDF_ITERATIONS.
- Migrations live in silverestimate/persistence/migrations.py; fixtures in tests/integration/test_repositories.py demonstrate in-memory setup.
- FlushScheduler batches commits, runs WAL checkpoints, and encrypts on idle; hooks in DatabaseManager allow UI/controllers to present status messages.
- perform_data_wipe removes encrypted DB, clears security keys, and deletes temp files when triggered.

## Runtime Operations
- LiveRateService (silverestimate/services/live_rate_service.py) schedules QTimer refreshes; threads fetch broadcast rate first, fall back to API scraping, and emit rate_updated signals.
- NavigationService manages stacked widgets and command routing for the main UI.
- MainCommands groups high-level actions (new estimate, open history, import/export, printing) invoked from menus and toolbars.
- Logging configured via silverestimate/infrastructure/logger.py; optional LogCleanupScheduler purges old log files according to QSettings values under `logging/*`.

## Configuration and Settings
- Global constants defined in silverestimate/infrastructure/app_constants.py (APP_NAME, APP_VERSION, SETTINGS_ORG, SETTINGS_APP, DB_PATH, LOG_DIR).
- User preferences persisted through Qt QSettings, including fonts, window state, live rate intervals, and security metadata.
- Logging defaults, retention, and output directories are stored in QSettings (`logging/debug_mode`, `logging/cleanup_days`, etc.).

## Build, Release, and Deployment
- Local run: activate virtual environment, execute `python main.py`.
- Windows packaging: `pwsh scripts/build_windows.ps1` builds `dist/SilverEstimate/` and zips it as `dist/SilverEstimate-v<version>-win64.zip`; pass `-OneFile` for a self-extracting exe.
- CI release (GitHub Actions): bump APP_VERSION, tag release, workflow bundles Windows binary zip.
- Logs and database directories are gitignored; clean them before packaging production builds.

- Existing automated coverage: tests/test_security.py (encryption primitives); tests/integration/test_repositories.py and tests/integration/test_database_manager.py (repository + lifecycle integration); tests/services/* (auth, navigation, main commands, live rate); tests/ui/* (smoke coverage for estimate entry flows).
- Gaps: complex UI edge cases (table navigation, save/print confirmations), DatabaseManager fault injection, bar list lifecycle regressions, controller-service failure simulations, and full calculation property checks in estimate_entry_logic.
- Recommended next steps: grow end-to-end GUI coverage (pytest-qt), add controller/service failure tests, and enforce `pytest --cov` in CI once coverage stabilises.

## Known Risks and Open Questions
- Single-user assumption; no concurrency safeguards beyond thread guard on sqlite connection.
- Heavy reliance on QSettings makes environment-specific paths important; verify portability across Windows accounts.
- Live rate fetchers depend on external services; add timeout handling tests and resilience to API changes.
- Evaluate crash recovery for temp decrypted DB files to ensure cleanup_scheduler stops gracefully on exceptions.

## Session Journal
- 2025-09-21: Completed controller/service refactor; Startup/Navigation/Live-rate controllers now front services and repositories; updated documentation and API reference.
- 2025-09-20: Added Hypothesis-backed net/fine/wage strategies and refactored UI tests to use estimate item factories; expanded property coverage for EstimateLogic.
- 2025-09-20: Added navigation silver-bar/history coverage, print workflow command tests, and data-wipe failure handling; roadmap testing items now complete.
- 2025-09-20: Refactored integration repositories/database tests to reuse estimate factories; ensured consistency across service/UI suites.
