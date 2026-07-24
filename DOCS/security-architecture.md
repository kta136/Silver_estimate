# Security Architecture

## Authentication and key derivation

The main password authenticates and opens the SQLCipher database. The recovery
password triggers the deliberate data-wipe workflow. Password hashes are Argon2
records stored only in the operating-system keyring. First-run hashes are
committed only after the new encrypted database opens, creates its current
schema, and validates.
Password rotation uses pending and recovery keyring records so interruption can
be resolved without losing access to the retained old database.

`PasswordHashService` uses `argon2-cffi` directly with an explicit Argon2id
policy: time cost 3, 65,536 KiB memory, parallelism 4, a 16-byte random salt,
and a 32-byte hash. Stored hashes must match that exact policy; weaker or unknown
parameters fail closed. The service distinguishes an ordinary password mismatch
from malformed or unsupported credential data.

The live database is machine-bound. SQLCipher's first 16 bytes supply the public
per-database salt. Argon2id applies time cost 3, 65,536 KiB memory, parallelism 4,
and a 32-byte output; an HMAC construction then combines that result with a random
256-bit device secret forced into local-machine Windows Credential Manager
storage. The final 32-byte value is supplied to SQLCipher as a raw key and is
never persisted. A password and copied database are therefore insufficient
without the originating PC's secret.

An already-authenticated local `estimation.db` plus `estimation.kdf.json` is
copy-switched once into the machine-bound single-file format. Startup refuses to
adopt any existing database when local password credentials are absent, and a
bound database with a missing device secret fails closed.

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
the packaged credential-store map contains the main, backup, pending, recovery,
and device-binding identifiers required by startup and copy-and-switch recovery.

## Backup, restore, and rekey

Storage detection is explicit: a missing file means first run, a plaintext
SQLite header is rejected, and every existing file must authenticate through
SQLCipher with the local device-bound key. The schema must already be version 8;
older, newer, and unversioned schemas fail closed.

`.sedbbackup` archives contain a machine-bound SQLCipher database and a digested
non-secret manifest carrying the device-binding fingerprint. Restore rejects a
foreign PC before validating the historical password and exporting to a
current-key staged database. A pending journal activates it on restart and rolls
back on validation failure. Password changes likewise export to a new-key target,
validate, drain connections, switch atomically, reopen, and only then promote
keyring hashes; rollback files are removed after successful validation.

## Operational controls

- A process-level `QLockFile` is retained from before authentication until
  shutdown. A live owner produces an already-running exit; Qt removes only a
  demonstrably stale lock.
- Maintenance mode blocks new worker connections and cooperatively drains active
  readers before storage mutation.
- Data wipe removes the live database, WAL/SHM/journals, legacy KDF and operation
  journals, staged/retained databases, in-application encrypted backups, and
  related keyring entries including the device-binding secret.
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
printers, hibernation images, filesystem snapshots, or SSD remanence.
Loss of the originating Windows credential vault, user profile, or PC makes the
machine-bound database and its encrypted backups unrecoverable by design.
User-requested `.seitems.json` catalog exports are intentionally plaintext and
are outside the encrypted `.sedbbackup` guarantee. Full-disk encryption and a
trusted device/account remain recommended.
