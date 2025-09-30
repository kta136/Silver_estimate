# SilverEstimate Implementation Roadmap

_Last updated: 2025-09-21_

## Purpose
This document captures the living implementation plan for the SilverEstimate refactor. It provides a single source of truth across sessions for architectural goals, current state, and immediate next steps. Update this file whenever significant progress is made.

## Guiding Principles
- **Separation of concerns**: isolate UI, services, persistence, security, and infrastructure layers.
- **Testability**: move business logic into plain-Python modules backed by automated tests.
- **Security first**: keep encryption/password flows centralized, audited, and easy to evolve.
- **Incremental refactor**: ship value in slices while maintaining app functionality.

## Recent Updates (2025-09-21)
- Repository split complete: items, estimates, and silver bar repositories back DatabaseManager, which now acts as a lifecycle/encryption facade.
- Authentication service fully extracted (`silverestimate/services/auth_service.py`) and referenced by the StartupController.
- Navigation and command orchestration handled by controllers/services (`NavigationController`, `MainCommands`, `NavigationService`).
- Font dialogs unified in `silverestimate/ui/font_dialogs.py` with SettingsService hooks.
- Controller layer (startup, navigation, live rate) created under `silverestimate/controllers/`, coordinating UI with services.
- Added pytest coverage for navigation, commands, and auth services; repository tests now use shared fixtures in `tests/integration/`.


## Target Package Layout
`
silverestimate/
    __init__.py
    domain/                # Dataclasses / DTOs shared across layers
    infrastructure/        # Logging, async helpers, configuration primitives
    persistence/           # Database manager, migrations, repositories
    security/              # Auth + encryption utilities
    services/              # Business logic (calculations, rate orchestration, workflows)
    ui/                    # Qt widgets/controllers; thin wrappers around services
`
Existing top-level scripts (main.py, dialogs, etc.) will gradually import from this package.

## Current State (2025-09-21)
- [x] Layered packages in place (controllers, services, persistence, infrastructure, security, UI).
- [x] Controller layer manages startup authentication, navigation, and live-rate refresh loops.
- [x] DatabaseManager focuses on connection lifecycle, encryption, and repository composition.
- [x] Items, estimates, and silver bar repositories supply CRUD/query logic behind the controllers/services.
- [x] Services (auth, navigation, live rate, settings, main commands) expose business workflows that controllers invoke.
- [ ] Further break down remaining UI-side calculation helpers into service/domain modules.

## Near-Term Tasks
1. **Persistence split**
   - [x] Schema/version logic now lives in silverestimate/persistence/migrations.py.
   - [x] Items CRUD extracted into silverestimate/persistence/items_repository.py.
   - [x] Estimate and silver-bar repositories carved under silverestimate/persistence/.
   - [x] DatabaseManager reduced to lifecycle/encryption + repository wiring; further tuning tracked under long-term goals.
2. **Security hardening**
   - [x] Consolidated authentication flow into silverestimate/services/auth_service.py (controller-integrated).
   - [ ] Introduce salt rotation on password change; evaluate upgrading to Argon2id KDF (passlib already bundled).
   - [ ] Revisit handling of security/last_temp_db_path to minimise plaintext leakage.
3. **Testing groundwork**
   - [x] Add a pytest harness covering migrations and repositories using in-memory SQLite fixtures.
   - [ ] Expand coverage to encryption helpers and failure scenarios.
4. **Main window cleanup**

   - [x] Delegate live-rate orchestration, navigation wiring, destructive operations, and item import to service modules; main.py now acts as a thin UI shell.

   - [x] Continue moving remaining widget wiring (fonts/dialog helpers) into silverestimate/services/ + silverestimate/ui/ packages.


## Longer-Term Goals
- Replace ad-hoc background threads with managed executors/Qt workers.
- Provide CLI tooling for DB migrations and recovery operations.
- Document deployment/build flow alongside code changes to keep the PyInstaller spec in sync.

## Update Checklist
When completing a unit of work:
- [ ] Document updates here (summary of change, new TODOs).
- [ ] Note any new modules or configuration requirements.
- [ ] Record testing performed and outstanding gaps.

Keeping this checklist current ensures continuity between sessions.
