# Project Architecture

## Runtime shape

Silver Estimate is a PySide6 desktop application with a local SQLCipher
database. Windows 10/11 is the supported packaged platform; macOS and Linux are
lint/type development environments.

```text
Qt views and dialogs
  -> narrow widget command/view APIs / explicit controllers / presenter
  -> domain and application services
  -> role-specific repositories
       -> query repositories
       -> command repositories
       -> synchronization repositories
  -> SqlCipherConnectionBroker
       -> owner-thread write connection
       -> keyed, cancellable worker read connections
  -> encrypted database, WAL, and journals
```

## Database startup

After authentication and device-secret retrieval, `StartupController` shows an
indeterminate `MaintenanceProgressDialog`. Its worker runs the normal database
constructor, including journal recovery, key derivation, schema upgrades and all
integrity checks, then checkpoints and closes its writer. No open connection or
cursor crosses back to Qt's GUI thread. A one-use detached manager handoff checks
file freshness and opens a new authenticated writer on the GUI thread. Cache
preload starts only after that attachment; pending first-run credentials are
promoted only after successful initialization. Failed opens roll back uncommitted
work and close the connection on its owner thread.

The modal dialog cannot be dismissed while an upgrade/recovery operation is
running. Authentication and device-secret access still run on the GUI thread,
as does the final writer open. Startup remains synchronous to its caller through
Qt's nested event loop; full scans are not repeated during attachment. Other
`DatabaseManager` constructor callers keep their existing synchronous contract.

## Live database maintenance

Password changes and catalog imports use `run_database_maintenance` with an
exclusive `DatabaseMaintenanceJob`. The GUI reserves the original broker without
waiting. The worker drains existing readers and opens a separate writer before a
queued Qt slot closes the GUI writer. Keeping the worker writer open prevents
that close from performing a last-connection WAL checkpoint on the GUI thread.
The original manager exposes no writer during the operation; its broker blocks
new readers, and the existing draft-recovery maintenance guard pauses writes.

The worker manager has separate connection, cursor, guard and repositories. It
shares the locked item cache, which import refreshes after committing. Password
verification, Argon2 hashing, credential staging/promotion, rekey export,
validation and file switching all run on the worker. Catalog file parsing,
validation, merge/replace and cache rebuilding also run there. The existing
transaction, snapshot-removal protections and replacement confirmation remain.
No database provider or widget is read by the worker; the UI captures those
inputs first.

After the worker closes/checkpoints its session and terminates, the GUI restores
its writer and releases the original broker. Rekey updates that broker's key so
previously captured factories also work. Failed jobs roll back unfinished
transactions. A failed GUI reopen leaves readers blocked and reports that a
restart is needed; the operation may already have committed. Password recovery
hashes are cleared only on success or confirmed rollback, and retained when the
outcome is uncertain. Duplicate page/command submissions are rejected.

## UI and controller boundaries

- `EstimateEntryWidget` is a `QWidget` that explicitly owns workflow, layout, table, and totals controllers. Application commands are explicit and the widget satisfies `EstimateEntryView` without a cast. Entry layout/table/totals/workflow controllers and recovery use a checked `EstimateEntryWidget` host; layout-created controls have concrete Qt types, and the former catch-all `__getattr__` is removed. Cross-controller calls name the target controller. Optional-member checks (`union-attr`) are enabled for this area.
- `SilverBarDialog` owns nine plain controller/builder objects with checked `SilverBarDialog` hosts. `SilverBarManagementFacade` declares their actual types and directly invokes methods with explicit signatures; string dispatch and `HostProxy` are removed. Controls have concrete Qt declarations, the catch-all `__getattr__` is removed, and optional-member checks are enabled across this area. Load runners/page states/shutdown state belong to the load controller; preview lifecycle is delegated to its shared `PreviewBuildController`.
- `LatestRequestRunner[RequestT, ResultT]` owns one persistent worker, a monotonically increasing generation, cooperative cancellation, and at most one pending replacement request. Only the latest generation may deliver a result.
- `PagedLoadState[RowT, CursorT]` owns only mutable page accumulation: replace/append, loaded and total counts, cursor advancement, reset, and has-more state. Item Master, Estimate History, Silver-Bar History, and Silver-Bar Management retain their own queries, cursor types, row conversion, selection, feedback, and telemetry.
- SQLite background work uses a connection owned by its worker thread and a progress handler bound to the cancellation event.
- Estimate printing offers two named formats over the same typed `EstimatePrintDocument`: Classic preserves the former Modern/New fixed-width column layout, while Modern uses the current full-width semantic table with shared column anchors, repeated headers, and kept totals. Both preview, export, and physical print paths use direct `QPainter` rendering and intentionally omit a footer. The selected default is persisted and can be switched inside preview.
- Silver-bar inventory and list printing use typed `SilverBarInventoryPrintDocument` and `SilverBarListPrintDocument` values with the same neutral Modern typography, color, table, elision, and printable-margin primitives as the estimate renderer. Their direct painter repeats report metadata, section titles, and column headings across pages, labels continued sections, avoids split rows, and keeps the total with the final rows. Estimate and silver-bar previews expose the same persistent print-font family, size, and weight control with immediate refresh. Silver-bar reports intentionally have one Modern format and no footer or page numbers.
- `PrintPreviewDialog` is an application-owned `QDialog` containing one explicit toolbar and an embedded `QPrintPreviewWidget`. `PrintPreviewController` is only the composition root: `PrintPreviewSession` owns the current immutable payload, the toolbar/navigation and page-setup collaborators own UI mechanics, `PrintPreviewPreferences` owns persisted state, and `PrintOutputService` returns typed outcomes for atomic PDF export and physical printing. `PrintPreviewOutputController` translates those outcomes into user feedback once. Preview refreshes, export, and physical printing invoke the same typed direct painters.
- `SettingsDialog` is a navigation, dirty-state, validation, apply/defaults, and accept/reject coordinator over independent appearance, live-rate, printing, data-management, logging/diagnostics, and security pages. Pages do not depend on `MainWindow`: typed controllers use narrow callbacks and database protocols, `PasswordChangeService` owns credential staging and SQLCipher rekey orchestration, and maintenance/diagnostics commands return explicit success/cancel/failure outcomes.
- `ApplicationSettings` is the sole production `QSettings` interpreter. `SettingsKey` centralizes the schema, typed readers normalize values and enforce ranges, and ordered forward migrations advance `meta/settings_schema_version`. Production controllers never receive raw keys or Qt-shaped return values.
- Shared display helpers keep user-facing dates in `DD/MM/YYYY` form and currency in Indian-grouped rupees across models and history dialogs.
- History and management tables use shared dense-table styling and explicit empty states; settings surfaces saved/unsaved feedback without controller compatibility aliases.

Views cancel work, disconnect delivery, and let workers exit normally during shutdown. `QThread.terminate()` is prohibited.

## Estimate application data

`domain/estimate_entry.py` owns the frozen row, calculation-state, save/load and
save-outcome data classes. Existing presenter and view-model import paths re-export
the same classes for compatibility; application code imports from the domain.
The mutable `EstimateEntryViewModel` remains in the UI layer.

Before save or current-entry preview, the workflow synchronizes the active model
and calls `as_save_snapshot()`. The UI assigns stable line keys, then captures a
tuple of frozen rows and numeric inputs in `EstimateEntrySnapshot`. Subsequent
screen edits cannot change that request. `EstimateEntryPersistenceService` consumes
only this snapshot and the narrow `EstimateSaveExecutor.save_estimate(payload)`
protocol; it imports no UI or presenter modules. It validates rows and totals before
calling the executor once. The existing presenter/repository path still owns its
save outcome and atomic database transaction.

This is an incremental contract improvement. Native entry controllers remain
coupled to their Qt widget, while the application save input is independent of Qt.
Silver-bar controllers likewise use checked native-widget dependencies and explicit
state ownership. Preview-worker reuse is implemented below; database lifecycle orchestration remains open.

## Shared preview preparation

Entry, Estimate History and silver-bar lists use `PreviewBuildController` from
`ui/preview_build_worker.py`. Each screen lazily creates one persistent
`LatestRequestRunner` on its first preview. It runs one captured-data build at a
time, retains at most one replacement and suppresses obsolete results. No preview
worker starts just from opening History. Per-request QThreads and callback routers
are removed.

The shared QObject owns progress and current delivery/error callbacks. Qt slots
deliver on the GUI thread and recheck the request generation, including results
queued before replacement or shutdown. Progress is disposed before opening preview
or an error dialog, so a nested preview cannot accidentally clear newer progress.
Builders receive captured data and must not touch widgets or the main database
writer. Existing estimate/list queries still happen before submission.

Screen close shuts down preview delivery without blocking for document conversion;
direct owner destruction is also handled. The runner has no Qt parent so it cannot
be destroyed by Qt while its Python worker is still completing a pure build. It
finishes that build, suppresses delivery and exits cooperatively. Running builds
are not forcibly interrupted and no claim is made to cancel them mid-conversion.
Existing Save/preview/new-estimate behavior and all output layouts are unchanged.

## Persistence

Fresh schema-v10 creation, the v8 snapshot upgrade or the v9 draft-table upgrade, mandatory indexes, validation,
and the schema-version write run in a single transaction. Versions older than v8
and unversioned schemas fail closed. The silver-bar availability index is:

```sql
(status, list_id, weight, date_added DESC, bar_id DESC)
```

Mandatory indexes are created under savepoints so every failure can be reported before the transaction rolls back. Final validation checks tables, columns, indexes, foreign keys, and schema version.

Keyset pages keep result size bounded:

- Items: 1,000 by normalized code and code.
- Available/listed bars: 1,500 by `(date_added, bar_id)` or `bar_id`.
- Estimate history: 500 headers by `(voucher_no_int, voucher_no)`.
- Silver-bar history: 1,000 by `(date_added, bar_id)`.

History reads stored header totals. Estimate line items are loaded only when a record is opened or printed. Catalog imports use bulk upserts and replace the immutable item-cache mapping once after the transaction.

Silver-bar persistence is owned directly by `SilverBarQueryRepository`, `SilverBarCommandRepository`, and `SilverBarSynchronizationRepository`. `DatabaseManager` lazily exposes each role and adapts synchronization results only at its established application API; the former private backend and broad `SilverBarsRepository` facade are removed. Synchronization returns `SilverBarSyncResult`, preserving success/failure information.

Database consumers declare structural contracts from `database_protocols.py`.
Concrete repositories receive `RepositoryDatabase`; item-catalog transfer,
main-window commands, estimate adapters, and startup lifecycle code each receive
their narrower protocol. The composition root alone uses the combined
`ApplicationDatabase` contract. Repositories use their transaction connection
directly and do not depend on private prepared cursors owned by
`DatabaseManager`.

## Encrypted database lifecycle

The active format is machine-bound SQLCipher. `DatabaseManager` reads SQLCipher's
16-byte in-file salt, derives an Argon2id password key, combines it with a random
256-bit device secret from local-machine Windows Credential Manager, and passes the final raw 32-byte key to
`SqlCipherConnectionBroker`. Every connection is keyed before reading
`sqlite_master`, verifies the controlled driver, authenticates the database,
and then applies foreign keys, WAL, `synchronous=FULL`, memory-only temporary
storage, the application cache size, and `mmap_size=0`.

Worker APIs carry a connection factory, never a database path or raw key.
Maintenance mode blocks new readers and cancels/drains current readers before
backup, restore, rekey, or wipe. `QLockFile` ownership is acquired
before authentication or storage mutation.

Password verification is separate from Qt widgets and database-key derivation.
`PasswordHashService` owns and strictly enforces the direct `argon2-cffi`
Argon2id policy.
`AuthService` owns login-time verification and the distinction between
credential mismatch and malformed credential data. `CredentialStore` remains
the only keyring boundary.

The `SILVDB01` importer and its AES-GCM dependency have been retired. An
authenticated local two-file SQLCipher database is migrated once to the
machine-bound single-file format. Existing files without the local device secret,
plaintext files, unversioned files, and schemas older than v8 fail closed.

Encrypted `.sedbbackup` archives contain a machine-bound SQLCipher database and a
digested non-secret manifest. Restore and password change use staged
copy-and-switch activation with journals; encrypted rollback files are removed
after successful validation.

## DDA live-rate path

`DdaCurrentRatesClient` hydrates anonymously from `https://ddajewels.com/api/v1/rates/current`. `DdaRateStreamWorker` then consumes `https://ddajewels.com/sse/rates`.

Only item ID `cmomws5tw000004i5k5t6yrnw` is accepted. The customer-facing `finalRate` and `PER_KG` unit are mandatory; `baseRate` and item names are ignored. The worker validates schema version 1, timestamps, sequence order, values, and event shapes.

SSE is primary. A disconnected stream polls current-rates every 10 seconds, sequence gaps trigger one reconciliation, and no activity for 45 seconds marks the socket stale. Reconnect delays are jittered around 1, 2, 4, 8, and 10 seconds. A verified cached snapshot supplies the offline/stale state.

## Quality boundaries

- Ruff enables Bugbear, Simplify, Performance, McCabe complexity, and the selected Pylint complexity rules. Complexity is capped at 15; explicit file-level exceptions document complex hotspots.
- Mypy fully checks all modules and applies strict-definition/generic/call rules to domain pagination, async runners, encryption, DDA transports, new repository roles, facades, settings pages, and print specifications.
- The Windows CI gate enforces 75% global coverage, 90% changed-line coverage,
  deterministic p95 budgets, offscreen Qt smoke, curated `pyside6-deploy`
  standalone/one-file builds, and frozen-artifact startup.

## Extension rules

- Add a typed domain type before adding another dictionary-shaped cross-layer contract.
- Add repository reads, writes, and reconciliation to the corresponding role rather than the public facade.
- Use keyset cursors for user-visible collections.
- Use `PagedLoadState` for UI page accumulation and `LatestRequestRunner` for replaceable UI work. Every runner must have one owner that calls cooperative `shutdown()`; never submit new work after shutdown.
- Keep every report preview, PDF export, and physical print path on typed documents and direct painters. Preserve the former Modern/New fixed-width estimate layout as Classic; add new structured estimate changes to Modern's semantic column/section model, and reuse the neutral Modern primitives for the Modern-only silver-bar reports.
- Keep preview chrome in the application-owned `PrintPreviewDialog`; do not depend on the stock dialog's internal widget hierarchy or action set.
- Keep DDA selection pinned to the stable item ID and `finalRate`.
