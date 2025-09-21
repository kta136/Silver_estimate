# Silver Estimation App - Project Memory Bank

Generated: 2025-09-20
Maintainer: SilverEstimate team (update contact as needed)

## Snapshot
- Current version: 1.72.7 (see silverestimate/infrastructure/app_constants.py)
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
2. Authentication (silverestimate/services/auth_service.py): LoginDialog drives first-time setup, password verification, or data wipe trigger; settings stored via QSettings at SETTINGS_ORG/SETTINGS_APP.
3. Database bootstrap (silverestimate/persistence/database_manager.py): decrypts encrypted DB into a temporary file, runs migrations, wires repositories, schedules flushes, and re-encrypts on close.
4. Main window (main.py MainWindow): loads settings, builds menus and toolbars, registers navigation stack, instantiates EstimateEntryWidget and lazy modules, connects message bar and status handling.
5. Live operations: LiveRateService polls broadcast/API silver rates on a timer; NavigationService and MainCommands coordinate view switches and actions; MessageBar surfaces inline notifications.
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
- Migrations live in silverestimate/persistence/migrations.py; FakeDB fixture in tests/test_repositories.py demonstrates in-memory setup.
- FlushScheduler batches commits, runs WAL checkpoints, and encrypts on idle; hooks in DatabaseManager allow UI to present status messages.
- perform_data_wipe removes encrypted DB, clears security keys, and deletes temp files when triggered.

## Runtime Operations
- LiveRateService (silverestimate/services/live_rate_service.py) schedules QTimer refreshes; threads fetch broadcast rate first, fall back to API scraping, and emit rate_updated signals.
- NavigationService manages stacked widgets and command routing for the main UI.
- MainCommands groups high-level actions (new estimate, open history, import/export, printing) invoked from menus and toolbars.
- Logging configured via silverestimate/infrastructure/logger.py; optional LogCleanupScheduler purges old log files based on config.toml.

## Configuration and Settings
- Global constants defined in silverestimate/infrastructure/app_constants.py (APP_NAME, APP_VERSION, SETTINGS_ORG, SETTINGS_APP, DB_PATH, LOG_DIR).
- User preferences persisted through Qt QSettings, including fonts, window state, live rate intervals, and security metadata.
- config.toml (user profile path) controls logging defaults, retention, and output directories.

## Build, Release, and Deployment
- Local run: activate virtual environment, execute `python main.py`.
- Windows packaging: `pwsh scripts/build_windows.ps1` supports one-file PyInstaller builds; outputs to dist/.
- CI release (GitHub Actions): bump APP_VERSION, tag release, workflow bundles Windows binary zip.
- Logs and database directories are gitignored; clean them before packaging production builds.

## Testing and Quality Status
- Existing automated coverage: tests/test_security.py (encryption primitives) and tests/test_repositories.py (repository integration with migrations).
- Missing coverage: UI flows, service logic (live rates, commands), DatabaseManager error paths, and calculation correctness in estimate_entry_logic.
- Recommended next steps: expand pytest suite with PyQt fixtures, add integration tests for authentication outcomes, create property-based checks for weight/wage calculations, and enforce pytest --cov in CI.

## Known Risks and Open Questions
- Single-user assumption; no concurrency safeguards beyond thread guard on sqlite connection.
- Heavy reliance on QSettings makes environment-specific paths important; verify portability across Windows accounts.
- Live rate fetchers depend on external services; add timeout handling tests and resilience to API changes.
- Evaluate crash recovery for temp decrypted DB files to ensure cleanup_scheduler stops gracefully on exceptions.

- 2025-09-20: Added Hypothesis-backed net/fine/wage strategies and refactored UI tests to use estimate item factories; expanded property coverage for EstimateLogic.



- 2025-09-20: Added navigation silver-bar/history coverage, print workflow command tests, and data-wipe failure handling; roadmap testing items now complete.
- 2025-09-20: Refactored integration repositories/database tests to reuse estimate factories; ensured consistency across service/UI suites.
