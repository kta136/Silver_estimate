# API Reference – Silver Estimation App

This guide documents the primary controller, service, and persistence APIs exposed by the modern SilverEstimate architecture. Namespace paths are relative to the repository root.

## Controller Layer

### StartupController (silverestimate/controllers/startup_controller.py)
    StartupController(logger: Optional[logging.Logger] = None)

- **authenticate_and_prepare() -> StartupResult** - runs the authentication flow, performs optional wipes, and returns a database-connected StartupResult.
- **StartupResult (dataclass)** - fields: status (StartupStatus), db (Optional[DatabaseManager]), and silent_wipe (bool) indicating whether the last wipe suppressed logging.
- **StartupStatus (Enum)** - values: OK, CANCELLED, WIPED, FAILED.

### NavigationController (silverestimate/controllers/navigation_controller.py)
    NavigationController(*, main_window, navigation_service, commands, logger: Optional[logging.Logger] = None)

- **initialize()** – builds menu/toolbar actions and wires them to services.
- **show_estimate() / show_item_master() / show_silver_bars()** – delegate to NavigationService to switch stacked widgets.
- **show_estimate_history() / show_silver_bar_history()** – launch history dialogs with lazy instantiation.
- **refresh_live_rate()** – asks the LiveRateController to perform an immediate refresh.
- **delete_all_data() / delete_all_estimates()** – forward destructive operations to MainCommands.

### LiveRateController (silverestimate/controllers/live_rate_controller.py)
    LiveRateController(*, parent: QObject, widget_getter, status_callback=None, logger=None, service_factory=LiveRateService, settings_provider=get_app_settings)

- **initialize(initial_refresh_delay_ms: int = 500)** - apply settings, set up timers, trigger the first refresh.
- **shutdown()** - stop the service timer during application exit.
- **apply_visibility_settings() -> bool** - toggle rate UI visibility based on QSettings.
- **apply_timer_settings(force_show_ui: Optional[bool] = None)** - restart auto-refresh cadence.
- **refresh_now()** - fire an immediate fetch, falling back to widget-side refresh on failure.

## Presenter Layer

### EstimateEntryPresenter (silverestimate/presenter/estimate_entry_presenter.py)
    EstimateEntryPresenter(view: EstimateEntryView, repository: EstimateRepository)

- **generate_voucher(silent: bool = False) -> str** - request the next voucher number from the repository and push it to the view.
- **refresh_totals() -> TotalsResult** - capture current view state and recompute totals via `services.estimate_calculator` (available for explicit presenter-driven refresh flows).
- **load_estimate(voucher_no: str) -> Optional[LoadedEstimate]** - retrieve persisted estimate payloads and normalise them for the view.
- **open_history() -> None** - open the history dialog, load the chosen voucher, and apply it to the view.
- **handle_item_code(row_index: int, code: str) -> bool** - resolve item code from repository or selection dialog, then populate/focus the row.
- **save_estimate(payload: SavePayload) -> SaveOutcome** - persist header/items, synchronise silver bar metadata (update/add), and surface status messaging.
- **delete_estimate(voucher_no: str) -> bool** - delegate to the repository and clean up related silver bar records.
- **open_silver_bar_management() -> None** - request the view to open silver bar management with UI-safe error reporting.

### Presenter Contracts (silverestimate/presenter/__init__.py)
- **EstimateEntryView** protocol for Qt widgets (`capture_state`, `apply_totals`, `populate_row`, etc.).
- Dataclasses: `EstimateEntryViewState`, `SaveItem`, `SavePayload`, `SaveOutcome`, `LoadedEstimate` encapsulate presenter inputs/outputs.
- Totals ownership note: `EstimateEntryWidget` owns hot-path totals scheduling/recompute for cell edits; presenter totals refresh remains callable for explicit non-edit flows.

## Service Layer

### Authentication (silverestimate/services/auth_service.py)
- **run_authentication(logger: Optional[logging.Logger] = None, *, parent: Optional[QWidget] = None) -> Optional[AuthenticationResult]** - drives setup/login with retry-on-invalid-password behavior; returns `None` only when the dialog is cancelled, otherwise returns an `AuthenticationResult` describing the password provided or a wipe request (with silent flag when triggered by the recovery password).
- **hash_password(password: str, *, logger=None) -> Optional[str] / verify_password(stored_hash: str, provided_password: str, *, logger=None) -> bool** - UI-facing authentication helpers that delegate to the password security service without placing cryptography in Qt widgets.
- **perform_data_wipe(db_path: str = DB_PATH, logger: Optional[logging.Logger] = None, *, silent: bool = False) -> bool** - deletes the encrypted DB, removes temporary plaintext, clears credentials, and, when `silent=True`, purges application log files without emitting wipe-related log entries.

### Password Hashing (silverestimate/security/password_service.py)
- **PasswordHashService.hash_password(password: str) -> str** - creates an Argon2id PHC hash using the explicit application policy.
- **PasswordHashService.verify_password(stored_hash: str, provided_password: str) -> PasswordVerification** - distinguishes mismatch from malformed storage.

### Credential Store (silverestimate/security/credential_store.py)
- **get_backend_status() -> CredentialBackendStatus** - reports whether the active operating-system keyring backend is trusted and usable.
- **get_password_hash(kind: str) -> Optional[str] / set_password_hash(kind, value, *, logger=None) / delete_password_hash(kind, *, logger=None)** - read, write, or remove the `main` and `backup` Argon2 hashes in the OS keyring. Credential hashes are not read from or written to QSettings.

### SettingsService (silverestimate/services/settings_service.py)
    SettingsService()

- **load_print_font(default_font: QFont) -> QFont / save_print_font(font: QFont)** – round-trip print font selections.
- **load_table_font_size(default_size: int = 9) -> int / save_table_font_size(size: int)** – persist grid font sizing.
- **restore_geometry(window) -> bool / save_geometry(window)** – handle main window geometry and state.
- **get(key, default=None, type=None)** and **set(key, value)** – thin wrappers around QSettings.
- **raw() -> QSettings** – direct access for advanced scenarios.

### Print Page Settings (silverestimate/ui/print_page_settings.py)
- **PrintPageSettings** - normalized margins, printer, page-size dimensions, and orientation used by settings, preview, quick print, and PDF export.
- **load_print_page_settings(settings) / save_print_page_settings(settings, state)** - round-trip the current print preferences without one-time orientation migration markers.
- **apply_print_page_settings_to_printer(...) / save_printer_page_settings(...)** - apply or capture a Qt6 `QPrinter` page layout.
- **validate_quick_print_printer(printer) -> tuple[bool, str]** - reject missing, stale, or unconfigured printer targets with user-facing guidance.

### NavigationService (silverestimate/services/navigation_service.py)
    NavigationService(main_window, stack_widget, logger: Optional[logging.Logger] = None)

- **update_db(db_manager)** – swap the active DatabaseManager after re-authentication.
- **show_estimate() / show_item_master() / show_silver_bars()** – ensure widgets exist (lazy creation) and set the stacked widget.
- **show_estimate_history() / show_silver_bar_history()** – open modal dialogs and coordinate selection hand-off.

### MainCommands (silverestimate/services/main_commands.py)
    MainCommands(main_window, db_manager, logger: Optional[logging.Logger] = None)

- **update_db(db_manager)** – synchronise command targets after DB reconnects.
- **save_estimate() / print_estimate()** – forward actions to EstimateEntryWidget.
- **delete_all_data() / delete_all_estimates()** – handle confirmation flows, drop/reseed tables, and refresh views.
- **create_item_catalog_backup()** – create a native `.seitems.json` item catalog backup via an asynchronous worker.
- **restore_item_catalog()** – restore a native `.seitems.json` item catalog backup and refresh visible item tables after completion.

### LiveRateService (silverestimate/services/live_rate_service.py)
    LiveRateService(parent: Optional[QObject] = None, logger: Optional[logging.Logger] = None)

- Source policy: public DDA HTTPS/SSE, exact item ID `cmomws5tw000004i5k5t6yrnw`, `PER_KG`, and `finalRate` only. No API key is sent.
- **DdaCurrentRatesClient.fetch_current() -> DdaRateSnapshot** – hydrate/reconcile from `/api/v1/rates/current`.
- **DdaRateStreamWorker** – class-level PySide6 `Signal` delivery for rate, feed status, connection state, and errors; consumes `/sse/rates`, sequence-checks events, and polls current-rates every 10 seconds only while disconnected.
- **start() / stop()** – start the stream thread or cooperatively close the active response and exit.
- **refresh_now()** – request an anonymous current-rates reconciliation.

## Persistence Layer

### DatabaseManager (silverestimate/persistence/database_manager.py)
    DatabaseManager(db_path: str, password: str)

Responsibilities:
- Open the live SQLCipher database directly through the keyed broker and expose repository compatibility cursors.
- Expose repository accessors: items_repo, estimates_repo, silver_bars_repo.
- Detect/create current storage, validate the controlled driver and schema, and serialize maintenance operations.

Key Public Methods:
- **setup_database() -> None** – create a fresh schema v8 or validate an existing schema v8.
- **generate_voucher_no() -> str** – delegate to `EstimatesRepository` through the repository facade.
- **save_estimate_with_returns(... ) -> bool** – transactional save for headers/items, with bar sync.
- **get_estimate_by_voucher(voucher_no: str) -> Optional[dict]** – retrieve composite estimate payloads.
- **delete_all_estimates() / delete_single_estimate(voucher_no)** – destructive operations used by MainCommands.
- **open_read_connection(cancel_event=None)** – return a keyed read-only worker connection owned by the caller.
- **create_encrypted_backup(destination=None) -> MaintenanceOutcome** – export and validate a `.sedbbackup` archive.
- **stage_encrypted_restore(path, archive_password) -> MaintenanceOutcome** – validate and stage restore activation for the next open.
- **change_passwords(new_password) -> MaintenanceOutcome** – copy, validate, switch, and retain rollback material.
- **close()** – commit, checkpoint when possible, and close the live encrypted connection.

New integrations should favour the role-specific repositories below instead of adding more forwarding methods to `DatabaseManager`.

### ItemsRepository (silverestimate/persistence/items_repository.py)
- **get_item_by_code(code: str)** – fetch item rows with cache support.
- **get_items_page(...) -> Page[dict, ItemCursor]** – keyset page of up to 1,000 filtered items.
- **search_items(search_term: str) / get_all_items()** – list-oriented query helpers.
- **add_item(...) / update_item(...) / delete_item(code: str)** – maintain catalog entries in direct SQLCipher transactions.

### EstimatesRepository (silverestimate/persistence/estimates_repository.py)
- **generate_voucher_no() -> str** – sequential voucher generator with error fallback.
- **get_estimate_by_voucher(voucher_no: str)** – return header plus line items in a dict payload.
- **get_estimate_history_page(...) -> Page[dict, EstimateHistoryCursor]** – up to 500 stored header summaries; line items load only on open/print.
- **save_estimate_with_returns(voucher_no, date, silver_rate, regular_items, return_items, totals) -> bool** – transactional save/update, including validation for missing item codes.
- **delete_single_estimate(voucher_no: str) -> bool** – cleanup helper used by DatabaseManager.

### SilverBarsRepository (silverestimate/persistence/silver_bars_repository.py)
- Public facade over `SilverBarQueryRepository`, `SilverBarCommandRepository`, and `SilverBarSynchronizationRepository`.
- **create_list(note: Optional[str] = None) -> Optional[int] / get_lists(include_issued: bool = True)** – manage bar list metadata.
- **assign_bar_to_list(bar_id: int, list_id: int, note: str = ...) -> bool** – move bars into lists with transfer logging.
- **remove_bar_from_list(bar_id: int, note: str = ...) -> bool** – reverse assignments, recording transfer history.
- **get_available_bars_keyset_page(...) / get_bars_in_list_keyset_page(...)** – up to 1,500 rows with typed cursors.
- **search_history_bars_page(...)** – up to 1,000 rows by `(date_added, bar_id)`.
- **get_silver_bars(..., unassigned_only: bool = False)** – query inventory with optional `list_id IS NULL` filtering for available-only screens.
- **delete_list(list_id: int) -> Tuple[bool, str]** – drop lists and safely unassign bars.
- **add_silver_bar(...) / update_silver_bar_values(...)** – maintain silver bar records linked to estimates.

## Supporting Types

- **ItemCacheController (silverestimate/infrastructure/item_cache.py)** - shared cache utilised by ItemsRepository for hot lookups.
- **SqlCipherConnectionBroker (silverestimate/persistence/database_driver.py)** - owns the raw database key, verifies the controlled SQLCipher runtime, configures direct live and worker connections, and serializes maintenance operations.
- **KdfMetadata and maintenance journals (silverestimate/persistence/storage_metadata.py)** - strict versioned KDF plus backup, rekey, and restore records with canonical JSON and atomic publication.
- **InlineStatusController (silverestimate/ui/inline_status.py)** - helper used across UI widgets to surface status messages without tight UI coupling.
- **CredentialStore (silverestimate/security/credential_store.py)** - OS keyring abstraction for hashed credentials.
- **Display formatting (silverestimate/ui/display_formatting.py)** - `format_display_date()` and `format_rupees()` provide consistent user-facing dates and Indian-number currency grouping.

## UI Facades

While the focus of this reference is the controller/service stack, the following UI entry points expose the application logic:
- **EstimateEntryWidget (silverestimate/ui/estimate_entry.py)** - integrates `EstimateEntryPresenter` with a model-first `EstimateTableView` data path; exposes `save_estimate()`, `print_estimate()`, `safe_load_estimate()`.
- **ItemMasterWidget (silverestimate/ui/item_master.py)** - allows CRUD via load_items(), add_item(), update_item(), delete_item() (internally using ItemsRepository).
- **SilverBarDialog (silverestimate/ui/silver_bar_management.py)** - provides load_available_bars(), load_bars_in_selected_list(), and list assignment interactions on top of SilverBarsRepository.

Use controllers and services as the primary integration surface; direct UI manipulation should be reserved for Qt widget customisations.
