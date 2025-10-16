# Estimate Entry Refactor Plan

## Purpose & Scope
- Carve the monolithic estimate entry UI logic into smaller, testable units without breaking existing workflows.
- Cover the estimate-entry UI logic package (now `silverestimate/ui/estimate_entry_logic/`) and the widgets/services it drives, with an emphasis on introducing presenter/service seams that can be unit tested.
- Provide a concrete sequence of steps, owned code locations, and test expectations to guide the refactor.

> **Status update (2025-10-16):** The legacy `estimate_entry_logic.py` module has been split into a package composed of `_EstimateBaseMixin`, `_EstimateTableMixin`, `_EstimatePersistenceMixin`, and `_EstimateDialogsMixin`, re-exported via `silverestimate/ui/estimate_entry_logic/__init__.py`. References below are kept for historical context; ongoing work should target the new package modules.

## Current State Summary
- `EstimateLogic` mixes UI wiring, domain calculations, persistence, and async workflows inside a single mixin used by `EstimateEntryWidget` (see `silverestimate/ui/estimate_entry_logic/base.py` and `silverestimate/ui/estimate_entry.py`).
- UI signal wiring and widget state management live alongside data operations (`silverestimate/ui/estimate_entry_logic/base.py`, `silverestimate/ui/estimate_entry_logic/table.py`).
- Row/total calculations are intertwined with widget manipulation instead of pure functions (`silverestimate/ui/estimate_entry_logic/table.py`).
- Data access uses `db_manager` directly from the UI layer, including inline SQL for specialised flows (`silverestimate/ui/estimate_entry_logic/persistence.py`).
- External concerns such as printing and live-rate fetching are triggered synchronously from the widget (`silverestimate/ui/estimate_entry_logic/persistence.py`, `silverestimate/ui/estimate_entry_logic/base.py`), making isolation and failure handling hard to test.
- `EstimateEntryWidget` still holds keyboard routing, mode toggles, and persistence helpers (`silverestimate/ui/estimate_entry.py:220`, `silverestimate/ui/estimate_entry.py:300`, `silverestimate/ui/estimate_entry.py:420`), reinforcing the tight coupling.

## Pain Points
- **Single monolith**: Any change risks regressions across unrelated functionality because control flow and state flags are shared through mutable widget fields.
- **UI coupling**: Logic functions depend on PyQt widgets, making unit tests impractical without full GUI scaffolding.
- **Hidden dependencies**: `db_manager`, `PrintManager`, dialogs, and QTimers are accessed ad hoc, complicating dependency reasoning and mocking.
- **Asynchronous gaps**: Long-running work (silver rate refresh, vouchers) runs inline with UI thread orchestration, and there is no clear seam for timeouts, retries, or error injection tests.
- **Duplication of domain concepts**: Estimate row structure, totals, and silver bar rules are scattered, preventing reuse across other flows (e.g., history dialogs, exports).

## Target End-State Architecture
### Layer Overview
| Layer | Responsibility | Notes |
| --- | --- | --- |
| View (`EstimateEntryWidget`) | Pure Qt widget operations; delegates logic through interfaces. | Keeps signals/slots but forwards to presenter/service. |
| Presenter (`EstimateEntryPresenter`) | Orchestrates workflows, maintains form state, coordinates with services. | New module under `silverestimate/presenter/`. |
| Domain Models | Immutable dataclasses for header, line items, totals, silver bars. | `silverestimate/domain/estimate_models.py`. |
| Services | Deterministic, testable units for calculations, persistence, live data. | `silverestimate/services/estimate_calculator.py`, `estimate_repository.py`, etc. |

### Proposed Components
1. **Domain models**
   - `EstimateHeader`, `EstimateLineItem`, `EstimateTotals`, `SilverBarAssignment`.
   - Capture validation rules and derived properties that do not require Qt.
2. **Calculation service**
   - Move `calculate_net_weight`, `calculate_fine`, `calculate_wage`, `calculate_totals` logic into pure functions (currently in `_EstimateTableMixin` within `silverestimate/ui/estimate_entry_logic/table.py`).
   - Presenter invokes these functions and only pushes formatted results into the view.
3. **Repository abstraction**
   - Define `EstimateRepository` protocol wrapping existing `db_manager` methods used by the UI (`generate_voucher_no`, `get_item_by_code`, `save_estimate_with_returns`, etc.).
   - Provide an adapter `DbManagerEstimateRepository` for the current implementation and allow simple fakes in tests.
4. **Presenter**
   - `EstimateEntryPresenter` owns the mutable form state, exposes methods invoked by UI events (e.g., `on_code_entered`, `on_save_clicked`, `on_rate_changed`).
   - Presenter communicates with view through an interface (e.g., `EstimateEntryViewContract`) implemented by `EstimateEntryWidget`.
   - Asynchronous operations (`refresh_silver_rate`, print+clear after save) are handled via injected services/callbacks so they can be stubbed.
5. **View adapter**
   - Minimal mixin or helper inside `EstimateEntryWidget` to translate presenter requests to actual Qt updates (editing items, showing dialogs).
   - Consolidate keyboard shortcuts and focus manipulation behind presenter notifications where feasible.
6. **Service integration**
   - Wrap live rate fetching (`silverestimate/services/ddar_rate_fetcher`) behind an injected `LiveRateService`.
   - Surface printing via an injected `EstimatePrintService` that can be mocked.

## Incremental Migration Plan
### Phase 0 – Baseline & Guard Rails
- Capture existing behaviour with smoke tests against `EstimateLogic` where practical (e.g., totals for canned table data) and record manual regression checklist for UI flows.
- Enable logging assertions around `save_estimate` to compare post-refactor status messages.

### Phase 1 – Pure Calculations & State
- [x] Introduced domain models in `silverestimate/domain/estimate_models.py`, including enum-backed line categories and totals structures.
- [x] Added pure calculator helpers in `silverestimate/services/estimate_calculator.py` and migrated `EstimateLogic` net/fine/wage/totals logic to delegate to them.
- [ ] Add unit tests for calculator functions using the fixtures from the UI tests.

### Phase 2 - Repository & Service Seams
- [x] Defined `EstimateRepository` protocol and a `DatabaseEstimateRepository` adapter to wrap the existing `db_manager` calls (`silverestimate/services/estimate_repository.py`).
- [x] Updated `EstimateLogic` to resolve all persistence operations through the repository (item lookup, voucher generation, load/save, silver bar sync, deletion) while keeping dialog helpers on the legacy manager (`silverestimate/ui/estimate_entry_logic/persistence.py`).
- [ ] Extract silver bar persistence heuristics from `save_estimate` into dedicated service helpers and cover the adapter with unit tests.

### Phase 3 - Presenter Introduction
- [x] Created presenter-facing view contract and presenter module (`silverestimate/presenter/estimate_entry_presenter.py`), defining `EstimateEntryViewState`, `EstimateEntryView`, and `EstimateEntryPresenter`.
- [x] Instantiated the presenter inside `EstimateEntryWidget` and routed voucher generation plus totals recomputation through it (`silverestimate/ui/estimate_entry.py`, `silverestimate/ui/estimate_entry_logic/__init__.py`).
- [x] Routed item lookup and save workflows through the presenter, centralising persistence and silver-bar synchronisation (`silverestimate/ui/estimate_entry_logic/persistence.py`, `silverestimate/presenter/estimate_entry_presenter.py`).
- [x] Migrated estimate loading to the presenter with a dedicated `LoadedEstimate` data flow, keeping UI updates in a single helper (`silverestimate/ui/estimate_entry_logic/persistence.py`, `silverestimate/presenter/estimate_entry_presenter.py`).
- [x] Delegated estimate deletion to the presenter to consolidate repository usage and simplify UI error handling (`silverestimate/ui/estimate_entry_logic/persistence.py`, `silverestimate/presenter/estimate_entry_presenter.py`).
- [x] Migrate modal dialog flows (history, silver bar management) onto the presenter-enabled view contract.
- [x] Provide presenter-focused unit tests using a fake view capturing method calls (`tests/unit/test_estimate_entry_presenter.py`).

### Phase 4 – Widget Simplification
- Update `EstimateEntryWidget` to instantiate presenter and forward Qt signals (e.g., `item_table.cellChanged`, `save_button.clicked`) to presenter methods.
- Remove direct business logic from widget (e.g., `toggle_return_mode`, `generate_voucher_silent`) once presenter covers them.
- Retire redundant mixin functions and shrink `EstimateLogic` to a thin compatibility layer or remove entirely once coverage is complete.

### Phase 5 – Clean-up & Regression Hardening
- Replace ad hoc dialog instantiations with view contract methods so presenter controls flow.
- Expand automated tests: presenter happy-path, failure-handling, repository error propagation.
- Verify manual regression checklist and adjust documentation (including user guide updates if behaviour changes).

## Unit Testing Strategy
- **Calculator tests**: Deterministic inputs/outputs across wage, fine, totals (no Qt, pure Python).
- **Presenter tests**: Fake view collects commands; repository and live-rate services mocked to force success/failure paths.
- **Repository tests**: Use in-memory SQLite (mirroring existing `db_manager`) to validate SQL and transaction handling.
- **Integration shims**: Lightweight Qt test (or smoke script) to ensure signals still connect post-migration before full GUI QA.

## Risks & Open Questions
- **Threading/async**: `refresh_silver_rate` currently mixes threading and UI updates (`silverestimate/ui/estimate_entry_logic/base.py`). Decide whether to keep QTimer-based callbacks or move to a dedicated worker abstraction.
- **Dialog ownership**: Presenter will need a strategy for modal dialogs (`ItemSelectionDialog`, `EstimateHistoryDialog`); ensure view contract exposes hooks to avoid presenter importing Qt modules.
- **State synchronisation**: Presenter must keep widget selection/focus consistent; confirm we can represent selection state inside domain models or view contract without regressing keyboard navigation.
- **Incremental delivery**: Each phase should ship as separate PRs to keep reviewable; consider feature flags to guard partially migrated behaviour.
