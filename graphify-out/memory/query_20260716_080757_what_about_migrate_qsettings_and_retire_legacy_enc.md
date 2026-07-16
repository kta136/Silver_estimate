---
type: "query"
date: "2026-07-16T08:07:57.803227+00:00"
question: "What about Migrate QSettings and retire legacy encrypted-database support after confirming migration?"
contributor: "graphify"
outcome: "useful"
source_nodes: ["SettingsStore", "DatabaseManager", "EncryptedDatabaseStore", "Argon2Metadata"]
---

# Q: What about Migrate QSettings and retire legacy encrypted-database support after confirming migration?

## Answer

Expanded from graph vocabulary: [settings, legacy, canonical, database, encrypted, encryption, decrypt, decryption, migrate, migration, pbkdf, salt]. Live QSettings verification found YourCompany=0 keys and SilverEstimate=60 keys, so the earlier 60/0 observation was stale and the migration had already completed. Verified the EXE-root database has a valid SILVDB01 header with a 16-byte Argon2id salt, then removed the obsolete canonical security/db_salt value; final stores are SilverEstimate=59, YourCompany=0. Source has no legacy QSettings copier, PBKDF2/raw-payload reader, legacy decryption outcome/helper, migration test, or current documentation requirement.

## Outcome

- Signal: useful

## Source Nodes

- SettingsStore
- DatabaseManager
- EncryptedDatabaseStore
- Argon2Metadata