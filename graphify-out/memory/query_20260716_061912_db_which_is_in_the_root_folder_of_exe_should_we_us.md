---
type: "query"
date: "2026-07-16T06:19:12.443044+00:00"
question: "db WHICH IS IN THE ROOT FOLDER OF EXE SHOULD WE USED, also on the next run of the project move all the compatiblity legacy data to new"
contributor: "graphify"
outcome: "useful"
source_nodes: ["get_database_path", "migrate_legacy_database", "get_app_settings", "StartupController"]
---

# Q: db WHICH IS IN THE ROOT FOLDER OF EXE SHOULD WE USED, also on the next run of the project move all the compatiblity legacy data to new

## Answer

Expanded from original query via graph vocabulary: [database, path, legacy, compatibility, migrate, migration, settings, startup, root, data, copy, move]. Implemented an absolute canonical database path at <EXE folder>\database\estimation.db for frozen builds and repository\database\estimation.db for source runs. Startup now performs a verified one-time legacy database move before authentication, never overwrites an existing canonical database, and stops safely if migration fails. get_app_settings now copies every legacy QSettings key into the canonical organization, preserves newer conflicting values, verifies the write, removes migrated legacy keys, and always returns the canonical store. Version 3.02 build and tests verified the flow.

## Outcome

- Signal: useful

## Source Nodes

- get_database_path
- migrate_legacy_database
- get_app_settings
- StartupController
