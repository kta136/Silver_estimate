# Performance Gates

`scripts/run_performance_gate.py` creates a fresh deterministic dataset for every run:

- 10,000 catalog items;
- 50,000 silver bars;
- 10,000 estimate headers and 50,000 estimate lines;
- 500 estimate-entry view-model rows;
- one 10 MiB SQLCipher payload database for encrypted export measurement.

The fast paging fixture uses standard `sqlite3` and a simplified schema. The
encrypted export metric times export only; it does not time the full application
backup archive operation. Use the separate SQLCipher profile below for those
production workflows.

No network request is included in the DDA parse timings.

## Required p95 budgets

| Metric | Samples | p95 budget |
|---|---:|---:|
| `estimate_history.page` | 20 | 250 ms |
| `silver_bar_history.page` | 20 | 250 ms |
| `estimate_totals.recompute` | 20 | 60 ms |
| `view_model.synchronize` | 20 | 120 ms |
| `encrypted_backup_export` | 5 | 350 ms |
| `dda_current.parse` | 20 | 20 ms |
| `dda_sse.parse_apply` | 20 | 20 ms |
| Frozen executable startup (`--artifact-smoke`) | 5 | 3,000 ms |

`scripts/check_perf_budgets.py` fails when any configured metric is absent, has too few samples, contains malformed/non-finite/negative telemetry, or exceeds its p95 budget.

The default `local` profile owns the budgets above. GitHub-hosted Windows
workflows select the `github-windows` profile. It preserves every threshold
except `encrypted_backup_export`, which is 800 ms for the shared runner while
remaining 350 ms locally. Main-validation run `30001409060` measured its five
10 MiB SQLCipher exports at 537-646 ms (635 ms p95); the runner-specific
ceiling prevents host disk/CPU variance from weakening the representative
workstation gate.

`scripts/check_startup_budgets.py` measures the complete one-file executable process externally, including bootloader extraction and imports, and fails the Windows release build when its p95 exceeds the configured budget.

## Local run

```powershell
uv sync --frozen --extra dev
uv run python scripts/run_performance_gate.py --output perf-metrics.log
uv run python scripts/check_perf_budgets.py --log-file perf-metrics.log
uv run python scripts/check_perf_budgets.py --log-file perf-metrics.log --profile github-windows
uv run python scripts/check_startup_budgets.py --artifact dist\SilverEstimate.exe --samples 5 --p95-budget-ms 3000
```

The harness uses the production history query helpers, silver-bar read repository,
totals calculator, estimate-entry view model, SQLCipher export function and DDA
HTTP/SSE parsers. It is a repeatable regression gate; interactive rendering and
representative customer hardware need separate measurements.

## Production SQLCipher baseline

Run the opt-in profile independently of builds and other benchmarks:

```powershell
uv run nox -s perf_sqlcipher -- --profile small --output artifacts/performance/sqlcipher-small.json
uv run nox -s perf_sqlcipher -- --profile large --output artifacts/performance/sqlcipher-large.json
```

The equivalent command is `uv run python -m scripts.benchmark_sqlcipher`. The
`small` profile uses 10,000 estimates, 50,000 lines, 50,000 bars and 10,000 items.
The `large` profile uses 100,000 estimates, 500,000 lines, 500,000 bars and 50,000
items. Both create a temporary encrypted database through `DatabaseManager`,
retain production schema/index/WAL settings, and use synthetic credentials.
They do not open the live database or apply experimental indexes.

The profile measures first/deep/filtered pages, full validation, a complete
validated backup archive, and opening/closing the database. Every query opens
its own production read connection. Deep cursors are approximately 90% through
the ordering. Backup includes export, validation, hashing and archive placement;
open/close includes authentication, schema/integrity checks and closing/checkpoint.
Neither metric is complete visible application startup.

JSON records the environment, driver identity, dataset counts/size, fixture
version, result fingerprints and individual samples. Each operation warms once;
queries default to 11 samples and lifecycle operations to three. `--samples` and
`--lifecycle-samples` control these counts. p95 uses nearest rank (the maximum
for the default small sample counts). These are warm-cache local comparisons,
not cold-storage or production service guarantees. A changed result between
identical requests fails the run.

This profile records a baseline without imposing uncalibrated machine-specific
CI thresholds. The existing blocking budgets remain in place. Later tuning
should add regression limits based on representative runs and also measure
write throughput, index storage, GUI append work and dialog-worker lifetime.

### Pre-tuning reference, 5 September 2026

The audit used Windows 11, Python 3.14.7 and the production SQLCipher schema.
Values below are local medians from the audit's matching synthetic dataset;
compare new changes against a fresh run on the same machine and fixture version.

| Operation | Small (24.8 MiB) | Large (265.0 MiB) |
|---|---:|---:|
| Estimate first page | 11.3 ms | 96.6 ms |
| Silver-bar history first page | 86.1 ms | 943.0 ms |
| Available bars first page | 40.8 ms | 401.3 ms |
| Complete validation | 158.3 ms | 2,280.7 ms |
| Database open and close | 248.1 ms | 2,954.2 ms |
| Complete validated backup | 496.3 ms | 4,466.6 ms |

The original measurements used one warm-up plus 11 query samples and three
lifecycle samples. They are observations, not pass/fail thresholds. Preserve
filter semantics and page identities when comparing fingerprints. Candidate
indexes must also pass migration and write-cost checks before adoption.

## History lifecycle regression checks

`tests/ui/test_history_safeguards.py` runs through the normal `tests_full` session
using an encrypted database. It checks 50 History cycles for each completion
path: accept, reject, window close and `done()`, plus 50 closes during an active
database query. Finished dialogs must leave no owned History dialogs or named
History/preview workers, and canceled queries must release broker readers.
Preview workers start only when requested; queued previews must not open after
their History dialog closes. These are lifecycle invariants, not RSS or latency
benchmarks. GUI append cost and large-query tuning remain separate work.

## Runtime telemetry

The atomic estimate save regression tests in
`tests/integration/test_atomic_estimate_inventory.py` verify one writer transaction
and commit for the header, lines and inventory. Transfer-history protection uses
`idx_bar_transfers_bar` on `bar_transfers(silver_bar_id)`; the test checks the actual
reconciliation query plan for an indexed lookup. Normal schema setup installs
this index for existing version-8 databases without changing records. These checks
establish transaction/query behavior; they do not measure large-dataset save
latency or the one-time index-build cost. Those timings belong in paired encrypted
benchmarks during the broader performance phase.

The application also logs existing `[perf]` startup and UI timings plus encrypted-flush duration/size. Keep metric names stable so results remain comparable across releases.


## Query and page-loading improvements (6 September 2026)

Run `python -m scripts.benchmark_sqlcipher --profile large --samples 5
--lifecycle-samples 1 --output artifacts/performance/sqlcipher-large.json` for the
production encrypted fixture: 100,000 estimates, 500,000 bars and 50,000 catalog
items. This is a manual large-data comparison; the seven existing CI budgets
remain smaller-fixture regression checks. The benchmark now also measures append
pages with `include_total=False`.

The paired review run retained matching fingerprints for all 14 original queries.
Warm median milliseconds before / after:

| Query | Before | After |
|---|---:|---:|
| Estimate History, first page | 102.62 | 9.35 |
| Estimate History, deep page | 40.77 | 9.63 |
| Bar History, first page | 939.65 | 20.18 |
| Bar History, deep page | 399.62 | 20.84 |
| Bar History, In Stock | 1070.25 | 92.93 |
| Bar History, substring | 575.69 | 284.71 |
| Available bars, first page | 405.27 | 91.89 |
| Available bars, deep page | 225.40 | 91.81 |
| Available bars, weight filter | 32.88 | 30.63 |

Deep append pages without exact counts measured 2.25 ms for estimates, 4.39 ms for
bar History and 6.08 ms for availability. New count SQL avoids display joins;
note searches build matching voucher IDs once. Unrestricted substring searches
use a table scan to avoid random reads through the date-order index; explicit
weight/status filters remain available to the query planner.

Four expression indexes match nullable voucher/date ordering. A leading cursor
bound permits indexed seeks before checking ties. Setup installs these indexes
transactionally on existing v8/v9 databases as well as fresh databases, retaining
schema version 9 and stored records. Existing indexes used by other query paths
remain in place.

Costs on the same large fixture: index installation plus schema validation took
2.51 s and added 57.22 MiB of allocated database pages. A complete estimate/bar
save-and-delete cycle changed from 0.88 to 1.05 ms median (1.45 to 2.07 ms p95,
31 samples). Independently seeded full-file sizes were 266.31 / 381.49 MiB; this
includes B-tree insertion layout and free space, and is not the compact index
size. Full validation also increased from 2.36 to 4.03 s in the single lifecycle
samples. Maintenance responsiveness remains separate work.

GUI measurement with 19,000 existing History rows and 500 new rows: rebuilding
all rows took 203.87 ms median; incremental insertion took 10.02 ms. Sorting by
fine weight gave 218.98 / 9.40 ms. These timings exclude subsequent paint and
physical display latency. New rows preserve model selection/persistent indexes;
bar totals update from new rows rather than resumming retained rows.

The regression suite covers mixed numeric/text vouchers, NULL/empty/duplicate
dates, filter combinations, indexed ordering, skipped count queries, unchanged
records during index setup, and selection-preserving insertion. Timing results
are evidence from one Windows machine, not universal latency guarantees.
