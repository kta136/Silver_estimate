# Silver Estimation App - Project Architecture

## Overview

A PyQt5 desktop application for silver shops that combines encrypted persistence, rich desktop UI, and operational tooling for estimates, inventory, and silver bar management.

## Core Architecture

### 1. Application Shell
- `silverestimate/infrastructure/application.py` contains the `ApplicationBuilder`, which configures logging, installs the Qt message handler, performs authentication, and owns the QApplication lifecycle before handing off to the main window.
- `main.py` is a thin entry point that constructs the builder, retains the `MainWindow` definition, and delegates startup/shutdown.
- Controllers, presenter, and services are still wired inside `MainWindow`, while the builder guarantees graceful shutdown (flush scheduler drain, encryption re-seal, controller teardown).

### 2. Controller Layer
- **StartupController (`silverestimate/controllers/startup_controller.py`)**: runs authentication, optional data wipe, and DatabaseManager initialisation before the UI shows.
- **NavigationController (`silverestimate/controllers/navigation_controller.py`)**: wires actions/menus/toolbars to navigation + command services, maintains stacked widget routing.
- **LiveRateController (`silverestimate/controllers/live_rate_controller.py`)**: orchestrates background rate polling, refresh timers, and UI updates using `live_rate_service`.

### 3. Presenter Layer
- **EstimateEntryPresenter (`silverestimate/presenter/estimate_entry_presenter.py`)**: mediates between the Qt widget and repositories, normalises item payloads, coordinates voucher generation, totals, saves, deletes, and silver bar synchronisation.
- **Contracts (`silverestimate/presenter/__init__.py`)**: protocols and dataclasses (`EstimateEntryView`, `SavePayload`, `SaveOutcome`, etc.) keep presenter logic UI-agnostic and test-friendly.

### 4. Service Layer
- **AuthService (`services/auth_service.py`)**: password setup/verification, secondary wipe flow, secure credential storage via `security/credential_store.py` (OS keyring with legacy migration support).
- **SettingsService (`services/settings_service.py`)**: applies persisted preferences (fonts, printers, logging toggles) and reconfigures logging/live-rate behaviour.
- **NavigationService (`services/navigation_service.py`)**: central navigation registry and helpers consumed by controllers and MainWindow.
- **MainCommands (`services/main_commands.py`)**: high-level verbs (new estimate, import/export, printing, history) invoked from controllers/UI.
- **LiveRateService (`services/live_rate_service.py` + `services/dda_rate_fetcher.py`)**: broadcast/API polling, fallback logic, signal emission for UI refresh.
- **Repository adapters (`services/estimate_repository.py`)**: protocol + concrete adapter that wrap `DatabaseManager` repository calls for presenter use.

### 5. UI Layer
- **`silverestimate/ui/estimate_entry.py`**: composite widget that wires UI helpers, presenter callbacks, and logic mixins.
- **`silverestimate/ui/estimate_entry_logic/`**: calculation helpers, persistence mixins, table utilities, and inline status plumbing consumed by the widget.
- **`silverestimate/ui/item_master.py`**: CRUD console with validation, search, and bulk operations.
- **`silverestimate/ui/silver_bar_management.py`**: list-based bar inventory manager with print/export and issuance workflows.
- **`silverestimate/ui/estimate_history.py` / `silverestimate/ui/silver_bar_history.py`**: history browsers with filtering, reactivation, and batch actions.
- Dialogs (settings, login, printing, font) share helpers such as `InlineStatusController` and rely on services/controllers for orchestration.

### 6. Persistence Layer
- **DatabaseManager (`persistence/database_manager.py`)**: connection lifecycle, encryption/decryption, repo composition, flush checkpoints.
- **Repositories**: `items_repository`, `estimates_repository`, `silver_bars_repository` expose focused CRUD/query APIs and enforce the repository pattern.
- **`migrations.py`**: schema creation/versioning; invoked during startup via DatabaseManager.
- **`flush_scheduler.py`**: debounced commit/encrypt loop triggered by DatabaseManager when idle.

### 7. Infrastructure & Security
- **Encryption (`security/encryption.py`)**: AES-256-GCM payload helpers, salt management, PBKDF2 key derivation.
- **Credential store (`security/credential_store.py`)**: OS keyring abstraction with migration helpers for legacy QSettings storage.
- **FlushScheduler (`persistence/flush_scheduler.py`)**: queued commits + WAL checkpoints to keep encrypted snapshots current.
- **ItemCache (`infrastructure/item_cache.py`)**: hot cache for frequently accessed items, reducing database round-trips.
- **Logger (`infrastructure/logger.py`)**: logging setup, Qt bridge, cleanup scheduler; reconfigured via SettingsService.
- **Settings (`infrastructure/settings.py` / `app_constants.py`)**: central QSettings identifiers, app metadata, filesystem paths.

## Data Flow

```
User Input
   |
Qt Widgets (UI Layer)
   | signals/events
EstimateEntryPresenter (Presenter Layer)
   | service calls
Services (Auth, Settings, Commands, Navigation, Live Rate)
   | repository calls
Repositories → DatabaseManager → Encrypted SQLite
                    ^
                    |
            Infrastructure (FlushScheduler, Encryption, ItemCache, Credential Store)
```

## Component Relationships

```
MainWindow
├── Controllers
│   ├── StartupController → AuthService / DatabaseManager
│   ├── NavigationController → NavigationService / MainCommands
│   └── LiveRateController → LiveRateService / SettingsService
├── EstimateEntryPresenter ⇆ EstimateEntryWidget (UI + logic mixins)
├── ItemMasterDialog / SilverBarManagementDialog / History Dialogs
└── Services & Repositories
    ├── Auth / Settings / Commands / LiveRate / Navigation
    └── Items / Estimates / SilverBars repositories → DatabaseManager
```

## Technical Stack
- Python 3.11+
- PyQt5 5.15+
- SQLite 3 with WAL mode for concurrency-friendly access
- `cryptography` for AES-GCM payload encryption
- `passlib[argon2]` and `argon2_cffi` for password hashing
- PyInstaller 6.x for packaging
- Optional dev tooling: `pytest`, `pytest-qt`, `pytest-mock`, `hypothesis`

## Architectural Notes
- UI and presenter separation keeps heavy logic outside Qt widgets and simplifies unit testing.
- Repositories shield the UI from raw SQL and centralise integrity checks.
- QSettings stores user preferences, salts, and crash recovery hints (temporary DB path).
- Automatic log cleanup (timer-driven) prevents unbounded growth when retention is enabled.
- Silver bar management treats bars as permanent records; estimate resaves synchronise edits instead of recreating rows.
- Credential storage uses the OS keyring; legacy QSettings entries are migrated automatically.

## Extension Points
- Additional presenters (e.g., for future dialogs) can follow the `EstimateEntryPresenter` pattern with protocol-defined views.
- New services (reporting, remote sync) should follow the existing service pattern with explicit wiring from `main.py`.
- Packaging changes belong in `SilverEstimate.spec` and `scripts/build_windows.ps1` so CI and local builds stay aligned.
- Domain models can expand under `silverestimate/domain/` to keep persistence and presenter layers strongly typed.
