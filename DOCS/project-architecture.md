# Project Architecture

## Runtime shape

Silver Estimate is a PySide6 desktop application with a local SQLCipher
database. Windows 10/11 is the supported packaged platform; macOS and Linux are
lint/type development environments.

```text
Qt views and dialogs
  -> explicit widget facades / controllers / presenter
  -> domain and application services
  -> repository facades
       -> query repositories
       -> command repositories
       -> synchronization repositories
  -> SqlCipherConnectionBroker
       -> owner-thread write connection
       -> keyed, cancellable worker read connections
  -> encrypted database, WAL, and journals
```

## UI and controller boundaries

- `EstimateEntryWidget` inherits `EstimateEntryFacade`. Every routed workflow, layout, table, and totals method is declared explicitly; controller methods are no longer installed with runtime `setattr`.
- `SilverBarDialog` follows the same pattern through `SilverBarManagementFacade`.
- `LatestRequestRunner[RequestT, ResultT]` owns one persistent worker, a monotonically increasing generation, cooperative cancellation, and at most one pending replacement request. Only the latest generation may deliver a result.
- SQLite background work uses a connection owned by its worker thread and a progress handler bound to the cancellation event.
- Estimate printing offers two named formats over the same typed `EstimatePrintDocument`: Classic preserves the former Modern/New fixed-width column layout, while Modern uses the current full-width semantic table with shared column anchors, repeated headers, and kept totals. Both preview, export, and physical print paths use direct `QPainter` rendering and intentionally omit a footer. The selected default is persisted and can be switched inside preview; the estimate preview also exposes persistent print-font family, size, and weight settings with immediate refresh. Silver-bar inventory and list reports remain available through their existing HTML renderer.
- Settings contains independently owned pages/controllers, including the DDA live-rate page and print-settings controller. Pages expose state/signals instead of reaching into transport code.
- Shared display helpers keep user-facing dates in `DD/MM/YYYY` form and currency in Indian-grouped rupees across models and history dialogs.
- History and management tables use shared dense-table styling and explicit empty states; settings surfaces saved/unsaved feedback without controller compatibility aliases.

Views cancel work, disconnect delivery, and let workers exit normally during shutdown. `QThread.terminate()` is prohibited.

## Persistence

Schema setup is a single transaction. Migrations, backfills, mandatory indexes, validation, and the schema-version write either commit together or roll back together. Version 6 recomputes stored estimate headers and adds the silver-bar availability index:

```sql
(status, list_id, weight, date_added DESC, bar_id DESC)
```

Mandatory indexes are created under savepoints so every failure can be reported before the migration rolls back. Final validation checks tables, columns, indexes, foreign keys, and schema version.

Keyset pages keep result size bounded:

- Items: 1,000 by normalized code and code.
- Available/listed bars: 1,500 by `(date_added, bar_id)` or `bar_id`.
- Estimate history: 500 headers by `(voucher_no_int, voucher_no)`.
- Silver-bar history: 1,000 by `(date_added, bar_id)`.

History reads stored header totals. Estimate line items are loaded only when a record is opened or printed. Catalog imports use bulk upserts and replace the immutable item-cache mapping once after the transaction.

Silver-bar persistence is separated into `SilverBarQueryRepository`, `SilverBarCommandRepository`, and `SilverBarSynchronizationRepository` behind the compatibility `SilverBarsRepository` facade. New synchronization calls return `SilverBarSyncResult`, preserving success/failure information.

## Encrypted database lifecycle

The active format is SQLCipher. `DatabaseManager` derives a raw 32-byte key from
the exact version-1 Argon2id metadata in `estimation.kdf.json` and passes it to
`SqlCipherConnectionBroker`. Every connection is keyed before reading
`sqlite_master`, verifies the controlled driver, authenticates the database,
and then applies foreign keys, WAL, `synchronous=NORMAL`, memory-only temporary
storage, the application cache size, and `mmap_size=0`.

Worker APIs carry a connection factory, never a database path or raw key.
Maintenance mode blocks new readers and cancels/drains current readers before
migration, backup, restore, rekey, or wipe. `QLockFile` ownership is acquired
before authentication or storage mutation.

Password verification is separate from Qt widgets and database-key derivation.
`PasswordHashService` owns the direct `argon2-cffi` Argon2id policy and
compatibility with existing PHC hashes. `AuthService` owns login-time
verification, opportunistic rehash persistence, and the distinction between
credential mismatch and malformed credential data. `CredentialStore` remains
the only keyring boundary.

`SILVDB01` is read only by the one-time importer. It decrypts inside a marked
application-owned workspace, exports to a keyed target with
`sqlcipher_export()`, compares counts and deterministic typed digests, validates
the target, retains the original envelope, and removes plaintext and sidecars on
all exits. It cannot write a new live envelope.

This importer is a temporary upgrade boundary, not a second database backend.
After the installed system has completed migration, restarted successfully from
`estimation.db`, and produced a verified encrypted backup, a compatibility
retirement release may remove the importer and its envelope-reading dependency.
That retirement must not automatically delete `estimation.silvdb01.backup`.

Encrypted `.sedbbackup` archives contain a SQLCipher database, its KDF metadata,
and a digested non-secret manifest. Restore and password change use staged
copy-and-switch activation with journals and retained encrypted rollback files.

## DDA live-rate path

`DdaCurrentRatesClient` hydrates anonymously from `https://ddajewels.com/api/v1/rates/current`. `DdaRateStreamWorker` then consumes `https://ddajewels.com/sse/rates`.

Only item ID `cmomws5tw000004i5k5t6yrnw` is accepted. The customer-facing `finalRate` and `PER_KG` unit are mandatory; `baseRate` and item names are ignored. The worker validates schema version 1, timestamps, sequence order, values, and event shapes.

SSE is primary. A disconnected stream polls current-rates every 10 seconds, sequence gaps trigger one reconciliation, and no activity for 45 seconds marks the socket stale. Reconnect delays are jittered around 1, 2, 4, 8, and 10 seconds. A verified cached snapshot supplies the offline/stale state.

## Quality boundaries

- Ruff enables Bugbear, Simplify, Performance, McCabe complexity, and the selected Pylint complexity rules. Complexity is capped at 15; explicit file-level exceptions document legacy hotspots.
- Mypy fully checks all modules and applies strict-definition/generic/call rules to domain pagination, async runners, encryption, DDA transports, new repository roles, facades, settings pages, and print specifications.
- The Windows CI gate enforces 75% global coverage, 90% changed-line coverage,
  deterministic p95 budgets, offscreen Qt smoke, curated `pyside6-deploy`
  standalone/one-file builds, and frozen-artifact startup.

## Extension rules

- Add a typed domain type before adding another dictionary-shaped cross-layer contract.
- Add repository reads, writes, and reconciliation to the corresponding role rather than the compatibility backend.
- Use keyset cursors for user-visible collections.
- Use `LatestRequestRunner` for replaceable UI work and cooperative stop events for long-running I/O.
- Keep Classic and Modern estimate preview, PDF export, and physical printing on the shared typed document and direct painters. Preserve the former Modern/New fixed-width layout as Classic; add new structured print changes to Modern's semantic column/section model.
- Keep DDA selection pinned to the stable item ID and `finalRate`.
