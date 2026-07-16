# Security Architecture

## Authentication

The main password authenticates and decrypts the database. The recovery password triggers the established data-wipe workflow. Password hashes use Argon2 and are stored only in the operating-system keyring. QSettings contains non-sensitive preferences and marked crash-recovery metadata, not credential hashes or encryption salts. Passwords and derived encryption keys are never persisted as plaintext.

## SILVDB01 encrypted envelope

Databases use this binary layout:

```text
"SILVDB01"
4-byte big-endian canonical-JSON header length
canonical JSON header
repeated chunk records:
  8-byte chunk index
  4-byte plaintext chunk length
  12-byte nonce
  AES-256-GCM ciphertext and 16-byte tag
```

The header records format version, AES-256-GCM, Argon2id parameters and salt, plaintext size, 1 MiB chunk size, chunk count, key check, and a metadata checksum. The complete envelope prefix plus each chunk index/length is authenticated as AES-GCM additional authenticated data.

Normal startup derives the Argon2id encryption key once (time cost 3, 64 MiB memory, parallelism 4). The salt and KDF parameters live in the authenticated envelope header. Readers accept only `SILVDB01`; obsolete raw encrypted payloads and unknown envelope versions fail closed as unsupported.

The reader returns distinct outcomes for:

- wrong password;
- unsupported magic/version/KDF/cipher;
- corrupt authenticated metadata or ciphertext;
- truncated data;
- reordered chunks;
- duplicate chunks;
- trailing data.

Plaintext and ciphertext are streamed; the implementation does not keep complete duplicate buffers in memory.

## Flush integrity

SQLite is committed and checkpointed before a consistent backup snapshot is encrypted. The encrypted replacement is written to a sibling temporary file, verified, and atomically replaced. Flush telemetry includes duration and byte size.

Dirty and flushed generations prevent redundant rewrites. A save during an active flush sets a pending flag and guarantees a subsequent pass.

## Crash recovery and temporary plaintext

Each temporary database directory is permission-restricted and includes `.silverestimate-temp.json` with:

- owner identifier;
- process ID;
- creation time;
- plaintext database filename;
- SHA-256 identity of the encrypted database path.

Startup considers only a marked directory belonging to the current encrypted file. A newer valid SQLite database can be offered for recovery. Declined, invalid, or older-than-24-hours abandoned candidates are removed together with WAL/SHM and snapshot files. Unmarked directories are never cleaned.

Temporary database overwrite and deletion is best-effort. SSD wear levelling, filesystem snapshots, cloud synchronization, and copy-on-write storage may retain physical copies. Full-disk encryption and trusted-device controls are required when that residual risk matters.

## Network security

DDA rates use certificate-validated public HTTPS/SSE endpoints. The client sends no API key or authorization header. It accepts only contract version 1, the exact configured item ID, `PER_KG`, a finite positive `finalRate`, valid timestamps, and valid sequences. Unknown fields are ignored for forward compatibility. `baseRate`, product names, and previous-rate percentage calculations are not trusted inputs.

## Operational controls

- Startup fails closed when no trusted operating-system keyring backend is available.
- Logs must not contain passwords, keys, complete database rows, or credential values.
- Bandit medium/high findings block pull requests, main, and release workflows. False positives use narrow, test-specific `# nosec Bxxx` annotations.
- Dependency advisory scanning remains non-blocking until its upstream database and remediation workflow are made deterministic.
- Windows code-signing hooks are present but non-blocking until certificate secrets are supplied.

## Security limitations

Encryption at rest does not defend against malware, keyloggers, a compromised logged-in account, live process memory inspection, malicious printers, or a user who has already authenticated. The application is single-user and does not provide role-based access control.
