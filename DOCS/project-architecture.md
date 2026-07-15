# Project Architecture

## Runtime shape

Silver Estimate is a PyQt6 desktop application with a local encrypted SQLite database. Windows 10/11 is the supported packaged platform; macOS and Linux are untested development environments.

```text
Qt views and dialogs
  -> explicit widget facades / controllers / presenter
  -> domain and application services
  -> repository facades
       -> query repositories
       -> command repositories
       -> synchronization repositories
  -> thread-local SQLite connections
  -> streamed SILVDB01 encrypted snapshot
```

## UI and controller boundaries

- `EstimateEntryWidget` inherits `EstimateEntryFacade`. Every routed workflow, layout, table, and totals method is declared explicitly; controller methods are no longer installed with runtime `setattr`.
- `SilverBarDialog` follows the same pattern through `SilverBarManagementFacade`.
- `LatestRequestRunner[RequestT, ResultT]` owns one persistent worker, a monotonically increasing generation, cooperative cancellation, and at most one pending replacement request. Only the latest generation may deliver a result.
- SQLite background work uses a connection owned by its worker thread and a progress handler bound to the cancellation event.
- Printing uses shared `PrintFormatSpec` values and renderer strategies. Existing Classic, Modern, Thermal, inventory, and list output remains compatible.
- Settings contains independently owned pages/controllers, including the DDA live-rate page and print-settings controller. Pages expose state/signals instead of reaching into transport code.

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

The active format is the versioned `SILVDB01` envelope described in the security guide. A session works on a permission-restricted temporary SQLite database. Flushes snapshot SQLite, stream the snapshot through authenticated 1 MiB AES-GCM chunks, verify the new envelope, and replace the encrypted file atomically.

`FlushScheduler` tracks dirty and flushed generations. A request received during encryption sets a pending flag; a second flush begins after the active one. Unchanged generations do not rewrite the encrypted file.

Every plaintext temporary directory contains an ownership marker with owner, PID, creation time, database filename, and encrypted-database identity. Recovery and cleanup operate only on matching marked directories.

## DDA live-rate path

`DdaCurrentRatesClient` hydrates anonymously from `https://ddajewels.com/api/v1/rates/current`. `DdaRateStreamWorker` then consumes `https://ddajewels.com/sse/rates`.

Only item ID `cmomws5tw000004i5k5t6yrnw` is accepted. The customer-facing `finalRate` and `PER_KG` unit are mandatory; `baseRate` and item names are ignored. The worker validates schema version 1, timestamps, sequence order, values, and event shapes.

SSE is primary. A disconnected stream polls current-rates every 10 seconds, sequence gaps trigger one reconciliation, and no activity for 45 seconds marks the socket stale. Reconnect delays are jittered around 1, 2, 4, 8, and 10 seconds. A verified cached snapshot supplies the offline/stale state.

## Quality boundaries

- Ruff enables Bugbear, Simplify, Performance, McCabe complexity, and the selected Pylint complexity rules. Complexity is capped at 15; explicit file-level exceptions document legacy hotspots.
- Mypy fully checks all modules and applies strict-definition/generic/call rules to domain pagination, async runners, encryption, DDA transports, new repository roles, facades, settings pages, and print specifications.
- The Windows CI gate enforces 75% global coverage, 90% changed-line coverage, deterministic p95 budgets, offscreen Qt smoke, PyInstaller build, and frozen-artifact startup.

## Extension rules

- Add a typed domain type before adding another dictionary-shaped cross-layer contract.
- Add repository reads, writes, and reconciliation to the corresponding role rather than the compatibility backend.
- Use keyset cursors for user-visible collections.
- Use `LatestRequestRunner` for replaceable UI work and cooperative stop events for long-running I/O.
- Add print formats through a shared specification and renderer strategy.
- Keep DDA selection pinned to the stable item ID and `finalRate`.
