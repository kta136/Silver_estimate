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

- **initialize(initial_refresh_delay_ms: int = 500)** – apply settings, set up timers, trigger the first refresh.
- **shutdown()** – stop the service timer during application exit.
- **apply_visibility_settings() -> bool** – toggle rate UI visibility based on QSettings.
- **apply_timer_settings(force_show_ui: Optional[bool] = None)** – restart auto-refresh cadence.
- **refresh_now()** – fire an immediate fetch, falling back to widget-side refresh on failure.

## Service Layer

### Authentication (silverestimate/services/auth_service.py)
- **run_authentication(logger: Optional[logging.Logger] = None) -> Optional[AuthenticationResult]** - drives setup/login; returns `None` on cancel or an `AuthenticationResult` describing the password provided or a wipe request (with silent flag when triggered by the secondary password).
- **perform_data_wipe(db_path: str = DB_PATH, logger: Optional[logging.Logger] = None, *, silent: bool = False) -> bool** - deletes the encrypted DB, removes temporary plaintext, clears credentials, and, when `silent=True`, purges application log files without emitting wipe-related log entries.

### SettingsService (silverestimate/services/settings_service.py)
    SettingsService()

- **load_print_font(default_font: QFont) -> QFont / save_print_font(font: QFont)** – round-trip print font selections.
- **load_table_font_size(default_size: int = 9) -> int / save_table_font_size(size: int)** – persist grid font sizing.
- **restore_geometry(window) -> bool / save_geometry(window)** – handle main window geometry and state.
- **get(key, default=None, type=None)** and **set(key, value)** – thin wrappers around QSettings.
- **raw() -> QSettings** – direct access for advanced scenarios.

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
- **import_items()** – launch the async item import workflow and refresh tables on completion.

### LiveRateService (silverestimate/services/live_rate_service.py)
    LiveRateService(parent: Optional[QObject] = None, logger: Optional[logging.Logger] = None)

- **rate_updated** – Qt signal emitting (broadcast_rate, api_rate, market_open) tuples.
- **start() / stop()** – manage the auto-refresh timer using settings for cadence and enablement.
- **refresh_now()** – fetch the latest rates (broadcast first, API fallback) in a background thread and emit results.

## Persistence Layer

### DatabaseManager (silverestimate/persistence/database_manager.py)
    DatabaseManager(db_path: str, password: str)

Responsibilities:
- Create/delete the decrypted temp database, manage WAL checkpoints, and re-encrypt changes on flush/close.
- Expose repository accessors: items_repo, estimates_repo, silver_bars_repo.
- Coordinate cache controllers, flush scheduling, and recovery helpers.

Key Public Methods:
- **setup_database() -> None** – ensure schema and migrations are applied.
- **generate_voucher_no() -> str** – delegate to EstimatesRepository while keeping legacy compatibility.
- **save_estimate_with_returns(... ) -> bool** – transactional save for headers/items, with bar sync.
- **get_estimate_by_voucher(voucher_no: str) -> Optional[dict]** – retrieve composite estimate payloads.
- **delete_all_estimates() / delete_single_estimate(voucher_no)** – destructive operations used by MainCommands.
- **request_flush(delay_seconds: float = 2.0)** and **flush_to_encrypted()** – trigger immediate or delayed encryption cycles.
- **close()** – commit outstanding work, stop flush scheduler, remove temp files.
- **Static helpers**: check_recovery_candidate, recover_encrypt_plain_to_encrypted, _get_or_create_salt_static.

Note: Legacy item/estimate helper methods remain for backwards compatibility but new code should favour the repositories below.

### ItemsRepository (silverestimate/persistence/items_repository.py)
- **get_item_by_code(code: str)** – fetch item rows with cache support.
- **search_items(search_term: str) / get_all_items()** – list items with filtering.
- **add_item(...) / update_item(...) / delete_item(code: str)** – maintain catalog entries and trigger flushes.

### EstimatesRepository (silverestimate/persistence/estimates_repository.py)
- **generate_voucher_no() -> str** – sequential voucher generator with error fallback.
- **get_estimate_by_voucher(voucher_no: str)** – return header plus line items in a dict payload.
- **get_estimates(...) / get_estimate_headers(...)** – filtered reporting queries.
- **save_estimate_with_returns(voucher_no, date, silver_rate, regular_items, return_items, totals) -> bool** – transactional save/update, including validation for missing item codes.
- **delete_single_estimate(voucher_no: str) -> bool** – cleanup helper used by DatabaseManager.

### SilverBarsRepository (silverestimate/persistence/silver_bars_repository.py)
- **create_list(note: Optional[str] = None) -> Optional[int] / get_lists(include_issued: bool = True)** – manage bar list metadata.
- **assign_bar_to_list(bar_id: int, list_id: int, note: str = ...) -> bool** – move bars into lists with transfer logging.
- **remove_bar_from_list(bar_id: int, note: str = ...) -> bool** – reverse assignments, recording transfer history.
- **get_available_bars(...) / get_bars_in_list(list_id: int)** – query stock by status.
- **delete_list(list_id: int) -> Tuple[bool, str]** – drop lists and safely unassign bars.
- **add_silver_bar(...) / update_silver_bar_values(...)** – maintain silver bar records linked to estimates.

## Supporting Types

- **ItemCacheController (silverestimate/infrastructure/item_cache.py)** – shared cache utilised by ItemsRepository for hot lookups.
- **FlushScheduler (silverestimate/persistence/flush_scheduler.py)** – debounced commit/encrypt worker invoked by DatabaseManager.request_flush.
- **InlineStatusController (silverestimate/ui/inline_status.py)** – helper used across UI widgets to surface status messages without tight UI coupling.

## UI Facades

While the focus of this reference is the controller/service stack, the following UI entry points expose the application logic:
- **EstimateEntryWidget (silverestimate/ui/estimate_entry.py)** – wraps EstimateLogic for calculations and exposes save_estimate(), print_estimate(), safe_load_estimate().
- **ItemMasterWidget (silverestimate/ui/item_master.py)** – allows CRUD via load_items(), add_item(), update_item(), delete_item() (internally using ItemsRepository).
- **SilverBarDialog (silverestimate/ui/silver_bar_management.py)** – provides load_available_bars(), load_bars_in_selected_list(), and list assignment interactions on top of SilverBarsRepository.

Use controllers and services as the primary integration surface; direct UI manipulation should be reserved for Qt widget customisations.
