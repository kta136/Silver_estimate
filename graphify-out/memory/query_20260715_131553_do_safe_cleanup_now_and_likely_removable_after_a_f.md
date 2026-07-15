---
type: "cleanup"
date: "2026-07-15T13:15:53.503556+00:00"
question: "Do Safe cleanup now and Likely removable after a focused change"
contributor: "graphify"
outcome: "useful"
source_nodes: ["DatabaseManager", "TempDatabaseStore", "CredentialStore", "run_authentication", "load_orientation", "get_log_config", "SilverBarLoadController"]
---

# Q: Do Safe cleanup now and Likely removable after a focused change

## Answer

Removed confirmed dead helpers, aliases, constants, stale diagnostics, and the obsolete v2.8.9 release note. Retired completed QSettings credential, logging-key, and print-orientation migrations; replaced the temporary database compatibility wrapper with TempDatabaseStore; updated tests and docs. Ruff, mypy, 63 focused tests, and the full 609-test collection passed (608 passed, 1 opt-in smoke skipped).

## Outcome

- Signal: useful

## Source Nodes

- DatabaseManager
- TempDatabaseStore
- CredentialStore
- run_authentication
- load_orientation
- get_log_config
- SilverBarLoadController