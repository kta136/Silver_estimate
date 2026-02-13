# Project Audit Suggestions (2026-02-13)

## Scope

This document tracks the remaining suggestions from the 2026-02-13 audit pass.
Completed items have been removed.

## Executive Summary

The critical workflow fixes (import cancellation, auth retry, wipe confirmation,
settings apply reliability, print escaping, and core docs drift) have been
implemented.

P1 reliability/scaling follow-up is now complete:

- Silver bar screens now enforce configurable row limits for large datasets.
- Import workflow now emits inserted/updated/skipped/error summary buckets and
  uses a dedicated parser service.
- High-traffic UI flows were hardened with more explicit/logged exception paths.

Remaining work is now concentrated in maintainability and longer-horizon cleanup:

- Large UI modules still need decomposition.
- Additional broad exception cleanup is still needed outside critical paths.

## Remaining Findings by Priority

## P1 (Medium Priority)

No open P1 findings remain.

## P2 (Low Priority)

1. Continue reducing "god files".
High-impact targets:
- `silverestimate/ui/silver_bar_management.py`
- `silverestimate/ui/print_manager.py`
- `silverestimate/ui/estimate_entry.py`
- `silverestimate/ui/settings_dialog.py`

2. Remove dead/legacy scaffolding where no longer used.
Candidates:
- Stale compatibility code paths and unused helpers.

3. Improve status messaging consistency.
Current issue:
- Inline and modal messaging severity boundaries are not fully consistent.

Recommendation:
- Standardize inline status for routine outcomes and modal dialogs for blocking
  failures only.

## Window-by-Window Remaining Plan

## Main Window (`main.py`)

Suggestions:
- Continue reducing direct UI wiring in `MainWindow`.
- Prefer controller/service composition for new features.

## Estimate Entry (`silverestimate/ui/estimate_entry.py`)

Suggestions:
- Split save behavior into explicit options (`Save`, `Save & Print`, `Save & New`).
- Continue replacing broad exception handlers with targeted handling.

## Item Selection Dialog (`silverestimate/ui/item_selection_dialog.py`)

Suggestions:
- Add scaling strategy for very large catalogs.
- Improve keyboard-first default-row behavior after filtering.

## Silver Bar Management (`silverestimate/ui/silver_bar_management.py`)

Suggestions:
- Split into smaller subcomponents/services (filters, actions, table presenter).
- Consider background/non-blocking loading for very large result sets.

## Silver Bar History (`silverestimate/ui/silver_bar_history.py`)

Suggestions:
- Continue reducing direct SQL in UI class.
- Keep export/copy feedback and status messaging consistent.

## Settings Dialog (`silverestimate/ui/settings_dialog.py`)

Suggestions:
- Consolidate one source of truth for defaults/ranges.
- Expand inline validation for apply errors where possible.

## Print Manager (`silverestimate/ui/print_manager.py`)

Suggestions:
- Extract large HTML builders into reusable template/helper modules.

## Testing Suggestions (Remaining)

1. Add UI tests for:
- `silver_bar_management`
- `silver_bar_history`

2. Add performance/regression checks for:
- Silver bar search/filter latency with larger fixtures.

## Documentation Suggestions (Remaining)

1. Keep architecture docs aligned as `MainWindow` composition continues to evolve.
2. Keep API docs synchronized as presenter/service interfaces change.

## Updated Execution Roadmap

## Phase 1 (Performance and Reliability)

Completed:
1. Silver bar row limits for large result sets.
2. Import summary reporting + parser extraction.
3. Targeted exception hardening in critical UI paths.

## Phase 2 (Maintainability)

1. Continue broad exception cleanup outside critical paths.
2. Start decomposition of largest UI modules.
3. Remove dead compatibility scaffolding.

## Phase 3 (Coverage and Regression Safety)

1. Add missing UI tests for silver bar windows.
2. Add performance regression checks for large fixture datasets.
