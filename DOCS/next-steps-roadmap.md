# Next Steps Roadmap

## Purpose

This document captures the recommended implementation order after the recent refactors to:

- estimate totals updates
- print preview/building
- silver-bar management controllers

The goal is to keep momentum while reducing risk: each step should be small enough to validate independently and should leave the codebase in a better state even if the remaining steps are delayed.

## Current State

Completed recently:

- estimate totals hot-path optimization
- async print-preview preparation
- `print_manager` split into renderer, payload-builder, and preview-controller helpers
- `settings_dialog.py` print settings extracted into `settings_print_controller.py`
- focused settings coverage added for:
  - print preference persistence
  - UI preference persistence
  - invalid-value fallback behavior for print and UI settings
- duplicated totals-assembly math extracted into `silverestimate/domain/estimate_totals.py`
- dedicated property/invariant tests added for core totals assembly math
- silver-bar management split into focused controllers for:
  - transfer
  - selection state
  - list lifecycle
  - list print preview
  - table/context-menu behavior
  - optimal-list generation

This means the next work should move away from silver-bar management and into the next large UI and domain cleanup areas.

## Target State

The medium-term target is:

- large dialogs should compose small controllers/helpers instead of owning every workflow directly
- business logic should live in pure domain functions with minimal Qt coupling
- high-risk modules should have focused test coverage
- docs should describe the current implementation, not the previous one

## Recommended Sequence

### Step 1: Refactor `settings_dialog.py`

Status: In progress

Primary target:

- [settings_dialog.py](/mnt/d/Projects/SilverEstimate/silverestimate/ui/settings_dialog.py)

Pain points:

- still a large UI orchestration file
- mixes widget construction, persistence, validation, side effects, and apply callbacks
- harder to test than the newly decomposed modules

Target split:

- print settings controller/helper
- UI preferences controller/helper
- security/storage settings helper where applicable

Checkpoint:

- one responsibility cluster extracted and delegated
- no behavior changes in settings save/apply flows

Progress update:

- completed: print settings persistence/apply/default logic extracted to [settings_print_controller.py](/mnt/d/Projects/SilverEstimate/silverestimate/ui/settings_print_controller.py)
- remaining: extract UI preferences helper and security/storage helper if the dialog remains hard to change

Guardrails:

- add focused tests for persistence and apply behavior before or during extraction

### Step 2: Add Focused Settings Tests

Status: Completed on March 7, 2026

Primary targets:

- [settings_dialog.py](/mnt/d/Projects/SilverEstimate/silverestimate/ui/settings_dialog.py)
- related test files under [tests/ui](/mnt/d/Projects/SilverEstimate/tests/ui)

Focus areas:

- printer preference persistence
- table font size / UI preference persistence
- estimate layout and print margin application
- invalid-value fallback behavior

Checkpoint:

- settings flows are covered by targeted tests instead of only manual verification

Implemented:

- targeted settings dialog tests now cover printer preference persistence
- targeted settings dialog tests now cover table font size, totals font sizes, and totals position persistence
- invalid-value fallback coverage added for both print settings and UI preference settings

### Step 3: Move More Business Logic Into the Domain Layer

Status: Completed for the current slice on March 7, 2026

Primary targets:

- estimate math and validation
- silver-bar optimization inputs/outputs
- pure calculations currently embedded in UI/controller code

Likely destinations:

- [silverestimate/domain](/mnt/d/Projects/SilverEstimate/silverestimate/domain)

Checkpoint:

- extracted functions are pure Python
- no Qt widget or database dependencies in extracted logic

Implemented:

- extracted totals assembly into [estimate_totals.py](/mnt/d/Projects/SilverEstimate/silverestimate/domain/estimate_totals.py)
- rewired [estimate_calculator.py](/mnt/d/Projects/SilverEstimate/silverestimate/services/estimate_calculator.py) and [estimate_entry_totals_controller.py](/mnt/d/Projects/SilverEstimate/silverestimate/ui/estimate_entry_totals_controller.py) to use the shared pure helper

Guardrails:

- add unit tests at the same time as each extraction

### Step 4: Add Property and Invariant Tests

Status: Completed for the current slice on March 7, 2026

Primary targets:

- extracted estimate math
- silver-bar optimization rules

Goals:

- validate totals and weight relationships across a wider input space
- catch edge cases that example-based UI tests will miss

Checkpoint:

- at least one property-based test module added for core calculation logic

Implemented:

- added [test_estimate_totals_properties.py](/mnt/d/Projects/SilverEstimate/tests/unit/test_estimate_totals_properties.py) to exercise totals invariants across a wider input space
- retained example-based tests alongside the property tests for easier debugging

### Step 5: Improve Query/Input Responsiveness

Primary targets:

- search and filter inputs that still trigger work too aggressively

Focus areas:

- debounce remaining search fields
- confirm expensive loads stay off the UI thread

Checkpoint:

- rapid typing no longer causes repeated immediate reloads on targeted screens

### Step 6: Add SQLite Maintenance Hooks

Primary targets:

- startup/shutdown or scheduled maintenance path

Focus:

- `wal_checkpoint(TRUNCATE)`
- `VACUUM`

Checkpoint:

- maintenance path exists and is safe to run without user intervention

Guardrails:

- keep this behind a well-defined maintenance call path
- test with a non-empty database fixture if possible

### Step 7: Raise Coverage in Weak Production Modules

Priority order:

1. settings
2. logging
3. export flows
4. Windows integration

Checkpoint:

- coverage added where failures would be expensive or user-visible

### Step 8: Documentation Alignment

Primary targets:

- [DOCS/security-architecture.md](/mnt/d/Projects/SilverEstimate/DOCS/security-architecture.md)
- [DOCS/project-architecture.md](/mnt/d/Projects/SilverEstimate/DOCS/project-architecture.md)
- operator-facing usage docs

Focus:

- update docs to reflect the current controller split
- document the actual print architecture
- add a user-facing workflow guide

Checkpoint:

- architecture docs reflect the current codebase shape

### Step 9: Packaging and Release Cleanup

Do this after the higher-value refactors above stabilize.

Focus:

- packaging/startup improvements
- support-matrix accuracy
- update/distribution ergonomics

## Suggested Working Rule

For each step:

1. identify the next largest responsibility cluster
2. extract one cluster only
3. add or update focused tests
4. run lint, type-checks, and targeted tests
5. stop once the new seam is stable

This keeps the refactor reversible and avoids another large all-in-one rewrite.

## Immediate Next Action

Start with:

- Step 5: query/input responsiveness

Recommended first cut:

- audit remaining live search fields that still reload immediately
- prioritize [silver_bar_management_ui.py](/mnt/d/Projects/SilverEstimate/silverestimate/ui/silver_bar_management_ui.py) and related load paths for debounce/worker verification

Reason:

- Steps 2-4 are now covered by code and tests
- this is the next user-visible performance path in the sequence
- it should be small enough to validate with targeted UI tests
