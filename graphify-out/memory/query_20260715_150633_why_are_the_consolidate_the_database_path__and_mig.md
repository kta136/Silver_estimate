---
type: "query"
date: "2026-07-15T15:06:33.444308+00:00"
question: "Why are the Consolidate the database path. and Migrate QSettings. are not automatically?"
contributor: "graphify"
outcome: "useful"
source_nodes: ["DatabaseManager", "get_app_settings", "SettingsDialog", "EncryptedDatabaseStore"]
---

# Q: Why are the Consolidate the database path. and Migrate QSettings. are not automatically?

## Answer

Expanded from graph vocabulary: automatic, database, paths, settings, legacy, fallback, migration, copy, current, primary, choose, move. They are not automatic because the code implements compatibility fallbacks, not one-time migrations. DB_PATH is relative, so two valid databases can exist and the program has no authority rule for choosing or overwriting one. get_app_settings returns the primary store only when critical keys exist; otherwise it returns the legacy YourCompany store without copying, conflict resolution, verification, or rollback. Automatic migration is appropriate here but should first choose a canonical database location, compare candidates, back up and verify the selected database, copy all QSettings keys only under explicit conflict rules, sync/verify, then retire the legacy sources after a successful restart.

## Outcome

- Signal: useful

## Source Nodes

- DatabaseManager
- get_app_settings
- SettingsDialog
- EncryptedDatabaseStore
