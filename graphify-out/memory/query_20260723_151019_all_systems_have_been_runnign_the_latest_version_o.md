---
type: "query"
date: "2026-07-23T15:10:19.787984+00:00"
question: "All systems have been runnign the latest version of the software find and remove any legacy code, any code which is used to migrate etc"
contributor: "graphify"
outcome: "useful"
source_nodes: ["DatabaseManager", "PasswordHashService", "schema.py"]
---

# Q: All systems have been runnign the latest version of the software find and remove any legacy code, any code which is used to migrate etc

## Answer

Expanded from graph vocabulary via [legacy, migration, compatibility, settings, database, encrypted, credential, startup, fallback, temporary, upgraded]. Removed the SILVDB01 importer and AES envelope stack, historical schema upgrade branches, password-policy rehash persistence and acceptance of noncurrent Argon2 parameters, retired print aliases, a compatibility-only re-encryption wrapper, completed migration tooling, stale configuration, tests, and the obsolete modernization roadmap. Fresh databases now create schema v8 directly; existing databases must already be schema v8. Verification: Ruff passed, mypy passed, uv lock is current, and 622 tests passed with 1 skipped.

## Outcome

- Signal: useful

## Source Nodes

- DatabaseManager
- PasswordHashService
- schema.py