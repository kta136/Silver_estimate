---
type: "query"
date: "2026-07-16T08:01:32.963316+00:00"
question: "Now all the older db/setttings etc have been migrated, remove the older legacy code"
contributor: "graphify"
outcome: "useful"
source_nodes: ["DatabaseManager", "EncryptedDatabaseStore", "StartupController", "SettingsStore"]
---

# Q: Now all the older db/setttings etc have been migrated, remove the older legacy code

## Answer

Expanded from original query via graph vocab: [legacy, migration, migrations, database, settings, canonical, paths, compatibility, fallback, store, runtime, older]. Removed the completed working-directory database relocation module and startup branch, the legacy-organization QSettings copier and constant, PBKDF2 and raw nonce-plus-ciphertext database support, settings-owned database salts, encrypted migration backups, and obsolete migration tests. Kept current schema migrations, marked crash recovery, active repository facades, and live-rate fallbacks. Verified the EXE-root database magic is SILVDB01 and no old root-level database candidate remains.

## Outcome

- Signal: useful

## Source Nodes

- DatabaseManager
- EncryptedDatabaseStore
- StartupController
- SettingsStore