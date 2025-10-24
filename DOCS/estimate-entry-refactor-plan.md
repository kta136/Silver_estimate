# Estimate Entry Refactor Plan

Last updated: 2025-10-17

## Progress Tracker
- [x] Phase 0 - Recon Map (2025-10-17)
- [x] Phase 1 - ViewModel Scaffold (2025-10-17)
- [ ] Phase 2 - Persistence Extraction
- [ ] Phase 3 - UI Layer Slimming
- [ ] Phase 4 - Presenter & Contract Updates
- [ ] Phase 5 - Documentation & Cleanup

## Overview

`EstimateEntryWidget` currently mixes Qt UI responsibilities with persistence, state management, and calculation logic. Supporting modules (notably `estimate_entry_logic/table.py` and `estimate_entry_logic/persistence.py`) are large and difficult to reason about or unit test. This plan outlines a phased refactor to introduce a view-model layer, slim the widget, and improve testability without regressing behaviour.

## Objectives

1. Separate UI rendering from business/state logic.
2. Introduce a testable view-model/controller layer with clear contracts.
3. Reduce widget size and clarify presenter interactions.
4. Maintain existing behaviour with incremental migrations and test coverage.

## Phase 0 - Recon Map

- Inventory the public API of `EstimateEntryWidget`, including attributes and slots used outside the class.
- Categorize methods into:
  - View-only (Qt updates, focus handling).
  - State transforms (row manipulation, totals).
  - Persistence operations (save/load, voucher generation).
- Document signal/slot entry points and how the presenter interacts with the widget today.

Deliverables: annotated API map, list of external dependencies, initial test impact assessment.

### Phase 0 Findings (2025-10-17)

- **Public API inventory**
  - UI/view helpers: `show_status`, `show_inline_status`, `request_totals_recalc`, `force_focus_to_first_cell`, `focus_on_empty_row`, `keyPressEvent`, `resizeEvent`, `closeEvent`, `reconnect_load_estimate`, `safe_load_estimate`.
  - State + table operations: `populate_row`, `populate_item_row`, `add_empty_row`, `cell_clicked`, `selection_changed`, `current_cell_changed`, `handle_cell_changed`, `move_to_next_cell`, `move_to_previous_cell`, `focus_on_code_column`, `toggle_return_mode`, `toggle_silver_bar_mode`, `delete_current_row`, `calculate_net_weight`, `calculate_fine`, `calculate_wage`, `clear_all_rows`.
  - Persistence/presenter glue: `set_voucher_number`, `connect_signals`, `refresh_silver_rate`, `clear_form`, `confirm_exit`, `capture_state`, `apply_loaded_estimate`, `apply_totals`, `calculate_totals`, `generate_voucher`, `load_estimate`, `save_estimate`, `print_estimate`, `delete_current_estimate`.
  - Dialog and lookup hooks: `prompt_item_selection`, `focus_after_item_lookup`, `open_history_dialog`, `show_history`, `show_last_balance_dialog`, `show_silver_bars`, `show_silver_bar_management`.
  - Exposed attributes relied on externally: `db_manager`, `presenter`, `main_window`, `item_table`, `voucher_edit`, `return_toggle_button`, `silver_bar_toggle_button`, `save_button`, `print_button`, `delete_estimate_button`, `silver_rate_spin`, `note_edit`, `date_edit`, status labels and total labels provided by `EstimateUI`.
- **Signal/slot map**
  - `voucher_edit.editingFinished` -> `safe_load_estimate` (or `load_estimate` when unsafe path is used).
  - `silver_rate_spin.valueChanged` -> totals recalculation and unsaved state marking.
  - `note_edit.textEdited`, `date_edit.dateChanged`, and table mutation signals update unsaved state indicators.
  - Item table events (`cellClicked`, `currentCellChanged`, `cellChanged`, selection changes) funnel into table mixin handlers for navigation and calculations.
  - Command buttons forward to persistence (`save_estimate`, `print_estimate`, `delete_current_estimate`), form maintenance (`clear_form`), or mode toggles; auxiliary buttons invoke dialog helpers.
- **Presenter interaction surfaces**
  - `EstimateEntryPresenter` (see `silverestimate/presenter/estimate_entry_presenter.py`) depends on view methods: `capture_state`, `apply_totals`, `set_voucher_number`, `populate_row`, `focus_after_item_lookup`, `prompt_item_selection`, `open_history_dialog`, `show_silver_bar_management`, `apply_loaded_estimate`, and `show_status`.
  - Presenter invokes repository-facing operations (`generate_voucher`, `load_estimate`, `save_estimate`, `delete_estimate`) via widget methods, and expects immediate UI feedback through status helpers.
- **External dependencies**
  - Persistence and calculations: `silverestimate.presenter.EstimateEntryPresenter`, `silverestimate.services.estimate_repository.EstimateRepository`, `silverestimate.services.estimate_calculator.compute_totals`, `silverestimate.domain.estimate_models` (for `EstimateLine`, `TotalsResult`, `SaveItem`, etc.).
  - Infrastructure: `silverestimate.infrastructure.settings.get_app_settings`, `silverestimate.ui.inline_status.InlineStatusController`, `silverestimate.ui.print_manager.PrintManager`, `DatabaseManager` implementations supplied via `db_manager`.
  - Qt dependencies include `QTableWidgetItem`, `QMessageBox`, `QShortcut`, `QTimer`, `QKeySequence`, and numerous widgets instantiated by `EstimateUI`.
  - Threaded live-rate refresh touches external rate provider through `db_manager.rate_service` (when present) and updates UI asynchronously.
- **Initial test impact assessment**
  - `tests/ui/test_estimate_entry_widget.py` exercises a broad surface: direct calls to `toggle_return_mode`, `add_empty_row`, `populate_row`, `calculate_totals`, `save_estimate`, and verification of table cell mutations. Introducing a view-model will require shims or updated fixtures so these tests can either bind to the view-model directly or operate through the widget with preserved method signatures.
  - Existing pytest-qt fixtures assume synchronous presenter interactions; asynchronous refactors must keep deterministic hooks for `save_estimate`, `load_estimate`, and table operations to avoid flakiness.
  - No dedicated unit tests currently cover `EstimateEntryPresenter`. Phase 1 should add new tests around the forthcoming `EstimateEntryViewModel` to backfill logic now embedded in widget mixins.

## Phase 1 - ViewModel Scaffold

- Introduce a pure-Python `EstimateEntryViewModel` that maintains the core state:
  - Active rows/items (using `EstimateLine` domain models).
  - Mode flags (regular/return/silver bar).
  - Totals inputs (silver rate, balances).
- Provide an interface mirroring the widget's current behaviour while delegating actual state logic to the view-model.
- Update the widget to instantiate the view-model and pass through relevant calls without altering UI code yet.

Testing: new unit tests for the view-model (no Qt); ensure existing widget tests still pass.

### Phase 1 Progress (2025-10-17)

- Added `EstimateEntryViewModel` (`silverestimate/ui/view_models/estimate_entry_view_model.py`) with row snapshots, mode flags, totals inputs, and helpers to emit `EstimateEntryViewState` plus computed totals.
- `EstimateEntryWidget` now constructs the view-model and keeps it in sync for mode toggles; `_EstimatePersistenceMixin` captures table state via `_update_view_model_snapshot()` so presenter interactions read from the shared model.
- Clearing the form and loading estimates refresh the view-model to avoid stale state; mixins call `_update_view_model_modes()` when toggles change.
- Introduced pure unit coverage in `tests/unit/test_estimate_entry_view_model.py` validating row filtering, totals math, and mode setters.
- Next: adapt persistence/save flows to consume the view-model data structures directly, then start trimming table mixin responsibilities (Phase 2).

## Phase 2 - Persistence Extraction

- Move save/load logic from `_EstimatePersistenceMixin` into a dedicated service (e.g., `EstimateEntryPersistenceService`) that consumes the view-model and repositories.
- Adjust presenter interactions to target the new service/view-model where possible.
- Keep the widget responsible only for initiating persistence actions and applying results to the UI.

Testing: unit tests for the persistence service, covering success/failure paths and integration with repositories.

### Phase 2 Progress (2025-10-17)

- Introduced `EstimateEntryPersistenceService` (`silverestimate/services/estimate_entry_persistence.py`) which builds `SavePayload` objects from `EstimateEntryViewModel` rows, tracks skipped row metadata, and supports presenter execution.
- `EstimateEntryWidget.save_estimate` now syncs the view-model snapshot and delegates payload construction + presenter invocation to the service, reducing direct table parsing.
- Load/apply path now hydrates the view-model via `build_row_states_from_items` before re-rendering the table, keeping UI state aligned with persisted items.
- Added unit coverage for the service (`tests/unit/test_estimate_entry_persistence_service.py`) validating payload assembly, error handling, presenter wiring, and round-tripping from `SaveItem`.
- `EstimateEntryRowState` now records `row_index`, allowing consistent row-number propagation between the view-model, service, and presenter.
- Next: document presenter/view contract assumptions and plan table adapter extraction for Phase 3.

#### Presenter Contract Notes (2025-10-17)
- Presenter invokes only the protocol methods (`capture_state`, `apply_totals`, `set_voucher_number`, `show_status`, `populate_row`, `prompt_item_selection`, `focus_after_item_lookup`, `open_history_dialog`, `show_silver_bar_management`, `apply_loaded_estimate`) — no hidden widget access detected.
- Mixins still reference the presenter for repository-backed lookups (e.g., `calculate_wage` pulls wage basis via `presenter.repository.fetch_item`), highlighting future adapter responsibilities.
- Table logic owns item selection flows and navigational focus; these should migrate toward a dedicated adapter in Phase 3 while presenter contracts remain stable.

## Phase 3 - UI Layer Slimming

- Extract table manipulation helpers into a focused adapter class (e.g., `EstimateTableAdapter`) responsible for syncing the view-model with `QTableWidget`.
- Compress `_EstimateTableMixin` to rely on the adapter for row-level operations.
- Ensure inline status messaging and shortcuts continue to work via dependency injection or callback hooks.

Testing: targeted Qt integration tests validating row rendering and mode toggles; existing ui tests should remain green.

### Phase 3 Preparation (2025-10-17)

- Existing `_EstimateTableMixin` exposes table behavior via module functions that assume `self.item_table`, `self.view_model`, `_status`, and `_mark_unsaved`; presenters are only consulted for item lookups through `presenter.handle_item_code` and repository wage lookups.
- `process_item_code` delegates item loading to the presenter, but topping up rows (`populate_row`, `add_empty_row`, `_update_row_type_visuals*`) operates directly on the Qt table; the adapter will need references to the table widget, a status callback, and mode flags from the view-model to take over these responsibilities.
- Mode toggling for return/silver bar relies on both the view-model (`return_mode`, `silver_bar_mode`) and UI updates via `_refresh_empty_row_type`—future adapter should accept mode state and update row visuals without widget mixin duplication.
- Adapter should expose primitives such as `populate_row`, `ensure_empty_row`, `apply_row_type`, `delete_row`, and `navigate_to_code` that consume pure row state data, while the mixin becomes a thin proxy that forwards to the adapter.

## Phase 4 - Presenter & Contract Updates

- Revisit `EstimateEntryPresenter` to ensure it operates against the view-model abstraction rather than the full widget when computing totals or reacting to events.
- Update protocols/data classes if needed to reflect the new layering.

Testing: presenter unit tests and UI integration tests verifying totals, saving, and load flows.

## Phase 5 - Documentation & Cleanup

- Update:
  - `DOCS/project-architecture.md` with the new view-model/service layer.
  - `DOCS/security-architecture.md` or related docs if persistence flows change.
  - README sections referencing estimate-entry internals.
- Remove dead code from the old mixins and ensure all modules pass linting.

## Stretch Goals / Future Work

- Expose the view-model through observable patterns (signals/callbacks) to further decouple UI updates.
- Add granular unit tests for totals calculation triggers.
- Consider splitting `EstimateEntryWidget` into smaller widgets (toolbar, summary, table) once the view-model layer is stable.

## Testing Strategy

- Maintain existing `pytest-qt` widget tests for regression coverage.
- Expand pure unit tests for the new view-model and persistence service.
- Add targeted integration tests for new abstractions where necessary.
- Run the full suite (`pytest`) after each phase; update CI configuration if new test directories are introduced.

## Notes

- Prioritize incremental PRs per phase to ease code review and reduce merge risk.
- Coordinate with any concurrent feature branches touching estimate-entry logic to avoid conflicts.
- Track technical debt items encountered during the refactor (e.g., presenter contract changes) for follow-up.
