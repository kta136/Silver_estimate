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
`synchronous=FULL`, memory-only temp storage, `mmap_size=0`, and the application
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

Startup's background preparation still performs every schema, quick-check,
cipher-integrity and foreign-key validation, including existing journal recovery
and transactional upgrades. It closes its worker-owned connection before
handing back a detached manager. The GUI opens a fresh keyed writer through the
same broker. A one-use file-stat signature checks the database, WAL and recovery
metadata across the closed-connection gap; it detects ordinary external changes,
but is not a cryptographic guarantee against concurrent tampering. Changed files
fail startup and must undergo full validation again. No passwords or raw keys
are added to progress messages or telemetry.

Live password changes reserve the original connection broker and drain its
readers before the GUI writer is released. A distinct worker-owned writer uses
the existing copy/validate/switch rekey protocol. Credential verification,
hashing and staging/promotion use captured values and the system keyring on the
worker, with no widget access. Success and confirmed rollback clear transitional
hashes; uncertain outcomes preserve them. The GUI resumes with a fresh keyed
writer and the original broker's key is updated before readers are admitted.
A GUI reopen failure keeps reader access blocked until restart, even if the
worker's operation already committed. Catalog import uses the same reservation
and worker ownership while retaining atomic upsert/delete and historical-snapshot
checks. Writer connection transfer across threads remains prohibited.

## Backup, restore, and rekey

Storage detection is explicit: a missing file means first run, a plaintext
SQLite header is rejected, and every existing file must authenticate through
SQLCipher with the local device-bound key. Current databases use schema 10; schemas 8 and 9 upgrade transactionally on open.
Older, newer, and unversioned schemas fail closed.

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


## Save durability and backup operation

Writers use WAL with `synchronous=FULL`, requesting a WAL flush for every
committed transaction before reporting success. This strengthens durability
against OS/power failure relative to NORMAL; it still depends on the storage
stack honoring flush requests. It is not a physical power-loss test or a
replacement for backups. See the
[SQLite synchronous contract](https://www.sqlite.org/pragma.html#pragma_synchronous).

The Settings database backup and restore operations run under an application-modal
progress window. A dedicated worker opens and closes its own SQLCipher connections;
the main writer is never passed across threads. The existing broker serializes
maintenance and drains/cancels background readers. Dialogs and password entry can
be cancelled before dispatch; once dispatched, the operation runs to completion
and its progress window cannot be dismissed. Other application actions are blocked
while Qt continues processing paints and timers.

Backups include committed estimates and the latest committed encrypted draft
recovery copy, when present. Keystrokes since that capture are not included.
Backup never implicitly commits an existing writer transaction. A unique temporary
directory on the destination filesystem holds the export and archive; validation and archive flush
precede atomic destination replacement. Failures before replacement preserve the
previous archive and remove temporary files. Restore validates and flushes a
separate candidate before publishing the staged database and ready journal. A
pending restore cannot be replaced by another attempt; it activates on restart.

The data page explains the original-device-secret and historical-main-password
requirements. A separate archive copy cannot recover a lost device secret.
`backup/last_validated_utc` records successful backup creation and validation
through Settings; a failed/cancelled operation does not advance it. This is a
local activity record, not a guarantee that the archive still exists or that
its required credentials remain available. Direct API/CLI callers do not update
this UI setting. No portable recovery key or archive is introduced.

## Unfinished-entry recovery

The schema-v10 recovery slot lives inside the main SQLCipher database; its WAL
and journals inherit encryption and the existing WAL/FULL durability policy.
There is no plaintext recovery file or new credential. An abrupt-process-exit
regression reopens the committed copy and checks that a private canary is absent
from database/sidecar bytes. This does not certify hardware power-loss behavior.
Recovery does not commit an estimate or inventory change. Successful estimate
saving atomically removes the matching recovery slot; explicit estimate-data purge
also removes recovery. Backups include an existing committed draft copy and retain
the same historical-password and original-installation requirements.
