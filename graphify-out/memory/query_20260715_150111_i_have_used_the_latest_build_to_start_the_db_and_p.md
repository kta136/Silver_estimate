---
type: "query"
date: "2026-07-15T15:01:11.481625+00:00"
question: "I have used the latest build to start the db and program, what legacy paths, legacy code etc we can remove?"
contributor: "graphify"
outcome: "useful"
source_nodes: ["DatabaseManager", "EncryptedDatabaseStore", "TempDatabaseStore", "DatabaseRepositoryFacadeMixin", "SettingsDialog"]
---

# Q: I have used the latest build to start the db and program, what legacy paths, legacy code etc we can remove?

## Answer

Expanded from graph vocabulary: startup, runtime, database, paths, legacy, compatibility, fallback, migration, old, temporary, remove, build. Verified on this machine: dist/database/estimation.db is current SILVDB01 with Argon2id metadata; source database/estimation.db is still legacy; all 60 application settings keys remain under YourCompany. Consolidate the database path/copy and migrate settings first, then remove PBKDF2/legacy envelope migration branches, their tests, and related current docs. Also remove the obsolete PyInstaller hook path, normalize five mdi6 icon names, drop the stale Python crypt warning filter, and clear generated caches/build artifacts. Keep TempDatabaseStore, DatabaseRepositoryFacadeMixin, schema and legacy-row fallbacks until data/backups are explicitly normalized, and the horizontal totals layout because it is actively selected by the UI. Ruff passed; 41 focused tests passed.

## Outcome

- Signal: useful

## Source Nodes

- DatabaseManager
- EncryptedDatabaseStore
- TempDatabaseStore
- DatabaseRepositoryFacadeMixin
- SettingsDialog
