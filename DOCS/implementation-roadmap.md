# SilverEstimate Implementation Roadmap

_Last updated: 2025-09-19_

## Purpose
This document captures the living implementation plan for the SilverEstimate refactor. It provides a single source of truth across sessions for architectural goals, current state, and immediate next steps. Update this file whenever significant progress is made.

## Guiding Principles
- **Separation of concerns**: isolate UI, services, persistence, security, and infrastructure layers.
- **Testability**: move business logic into plain-Python modules backed by automated tests.
- **Security first**: keep encryption/password flows centralized, audited, and easy to evolve.
- **Incremental refactor**: ship value in slices while maintaining app functionality.

## Recent Updates (2025-09-19)
- Persistence repositories for estimates and silver bars are live; DatabaseManager lazily loads them.
- silverestimate/persistence/database_manager.py now leans on silverestimate/security/encryption.py for all crypto work.

- Added pytest-based repository coverage using in-memory SQLite fixtures (tests/test_repositories.py).

- Authentication flow now lives in silverestimate/services/auth_service.py; UI code delegates to the shared service.

- Main window delegates live-rate, navigation, destructive actions, and item import to shared services; startup now uses a simple main() entry point.

- Migrated print and table font dialogs into silverestimate/ui/font_dialogs.py with SettingsService coordination.
- Consolidated legacy root-level UI/service modules under silverestimate/ui, infrastructure, and persistence to match the target layout.


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

## Current State (2025-09-19)
- [x] Package skeleton created under silverestimate/ with placeholder packages.
- [x] Crypto helpers (silverestimate/security/encryption.py) encapsulate salt creation, PBKDF2 key derivation, and AES-GCM payload handling.
- [x] silverestimate/persistence/database_manager.py delegates encryption work to the new security helpers.
- [x] Schema setup/migration logic lives in silverestimate/persistence/migrations.py, with DatabaseManager.setup_database calling it.
- [x] Items CRUD routes through silverestimate/persistence/items_repository.py via a lazy-loaded repository.
- [ ] Estimate and silver-bar workflows still live inside silverestimate/persistence/database_manager.py alongside UI-driven business logic.

## Near-Term Tasks
1. **Persistence split**
   - [x] Schema/version logic now lives in silverestimate/persistence/migrations.py.
   - [x] Items CRUD extracted into silverestimate/persistence/items_repository.py.
   - [x] Estimate and silver-bar repositories carved under silverestimate/persistence/.
   - [ ] Keep refining DatabaseManager into a thin lifecycle/encryption facade.
2. **Security hardening**
   - [x] Consolidate authentication flow into silverestimate/services/auth_service.py and remove duplicate logic from main.py.
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
