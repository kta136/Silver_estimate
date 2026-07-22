# Security Architecture

## Authentication and key derivation

The main password authenticates and opens the SQLCipher database. The recovery
password triggers the deliberate data-wipe workflow. Password hashes are Argon2
records stored only in the operating-system keyring. First-run hashes are
committed only after the new encrypted database opens, migrates, and validates.
Password rotation uses pending and recovery keyring records so interruption can
be resolved without losing access to the retained old database.

`estimation.kdf.json` contains public, versioned KDF bootstrap data. Version 1 is
accepted only when it exactly specifies Argon2id, a 16-byte salt, time cost 3,
65,536 KiB memory, parallelism 4, and a 32-byte output. Missing, malformed,
unknown, or weakened metadata fails closed. The derived 32-byte value is supplied
to SQLCipher as a raw key and is never persisted.

## Live SQLCipher boundary

Every production connection is created by `SqlCipherConnectionBroker`. It sets
the raw key before schema access, requires SQLCipher 4.17.x, `cipher_status=1`, a
crypto provider, `TEMP_STORE=2`, `THREADSAFE=1`, and codec support, then
authenticates by reading `sqlite_master`. Connections use foreign keys, WAL,
`synchronous=NORMAL`, memory-only temp storage, `mmap_size=0`, and the application
cache policy. Background work receives a keyed connection factory and a
cancellation event; UI objects never receive raw key bytes.

Windows installs resolve the committed CPython 3.14 x64 wheel. CI verifies its
recorded SHA-256 and native inventory plus the installed and frozen runtime;
native recompilation is a manual dependency-update operation, not a per-build
security requirement.

SQLCipher encrypts database-page content and page content written to WAL,
rollback, and statement journals. WAL/journal headers and SHM coordination
metadata can still exist, but must not contain application records. The frozen
artifact smoke test creates and opens an encrypted database and verifies the
native driver identity rather than merely importing it. It also verifies that
the packaged credential-store map contains the main, backup, pending, and
recovery identifiers required by startup and copy-and-switch rekey recovery.

## Migration, backup, restore, and rekey

Storage detection is explicit: missing means first run, `SILVDB01` means legacy
import, a plaintext SQLite header is rejected, and any other existing file must
authenticate through SQLCipher with valid KDF metadata.

The legacy reader is an isolated read-only compatibility importer. It retains a
hashed `estimation.silvdb01.backup`, decrypts only within a marked migration
workspace, exports into a new keyed database, compares typed row digests and
table counts, validates schema/integrity/foreign keys, and atomically publishes
the result. Startup removes interrupted marked workspaces. The application no
longer writes SILVDB01 envelopes or retains plaintext recovery candidates.

The presence of the importer or `estimation.silvdb01.backup` does not mean that
SILVDB01 remains an active storage format. Normal reads, writes, WAL activity,
backup, restore, and password rotation use SQLCipher exclusively. Importer
retirement is allowed only after the sole installed system has migrated,
reopened the SQLCipher database on a later process start, and created a verified
encrypted backup. Retirement does not imply automatic deletion of the retained
legacy envelope.

`.sedbbackup` archives contain an encrypted SQLCipher database, exact KDF
metadata, and a digested non-secret manifest. Restore validates the historical
password and archive before exporting to a current-key staged database. A
pending journal activates it on restart, retains the pre-restore database, and
rolls back on validation failure. Password changes likewise export to a new-key
target, validate, drain connections, retain the old encrypted database and
metadata, switch atomically, reopen, and only then promote keyring hashes.

## Operational controls

- A process-level `QLockFile` is retained from before authentication until
  shutdown. A live owner produces an already-running exit; Qt removes only a
  demonstrably stale lock.
- Maintenance mode blocks new worker connections and cooperatively drains active
  readers before storage mutation.
- Data wipe removes the live database, WAL/SHM/journals, KDF and operation
  journals, staged/retained databases, in-application encrypted backups, legacy
  backup, marked migration workspaces, and related keyring entries.
- Logs must not contain passwords, raw keys, complete database rows, or
  credential values.
- Bandit medium/high findings block pull requests, main, and release workflows.

## Network security

DDA rates use certificate-validated public HTTPS/SSE endpoints. The client sends
no API key or authorization header. It accepts only contract version 1, the exact
configured item ID, `PER_KG`, a finite positive `finalRate`, valid timestamps,
and valid sequences. Unknown fields are ignored for forward compatibility.

## Security limitations

SQLCipher is encryption at rest. It does not protect plaintext already in live
process memory, malware, keyloggers, a compromised logged-in account, malicious
printers, hibernation images, filesystem snapshots, or SSD remanence. The marked
one-time SILVDB01 migration workspace is the sole plaintext database exception.
User-requested `.seitems.json` catalog exports are intentionally plaintext and
are outside the encrypted `.sedbbackup` guarantee. Full-disk encryption and a
trusted device/account remain recommended.
