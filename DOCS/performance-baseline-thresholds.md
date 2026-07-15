# Performance Gates

`scripts/run_performance_gate.py` creates a fresh deterministic dataset for every run:

- 10,000 catalog items;
- 50,000 silver bars;
- 10,000 estimate headers and 50,000 estimate lines;
- 500 estimate-entry view-model rows;
- one 10 MiB plaintext snapshot for encrypted flush measurement.

No network request is included in the DDA parse timings.

## Required p95 budgets

| Metric | Samples | p95 budget |
|---|---:|---:|
| `estimate_history.page` | 20 | 250 ms |
| `silver_bar_history.page` | 20 | 250 ms |
| `estimate_totals.recompute` | 20 | 60 ms |
| `view_model.synchronize` | 20 | 120 ms |
| `encrypted_flush` | 5 | 150 ms |
| `dda_current.parse` | 20 | 20 ms |
| `dda_sse.parse_apply` | 20 | 20 ms |

`scripts/check_perf_budgets.py` fails when any configured metric is absent, has too few samples, contains malformed/non-finite/negative telemetry, or exceeds its p95 budget.

## Local run

```powershell
uv sync --frozen --extra dev
uv run python scripts/run_performance_gate.py --output perf-metrics.log
uv run python scripts/check_perf_budgets.py --log-file perf-metrics.log
```

The harness uses the production history query helpers, silver-bar snapshot repository, totals calculator, estimate-entry view model, encrypted-envelope writer, and DDA HTTP/SSE parsers. It is a repeatable regression gate, not a substitute for profiling interactive rendering on representative customer hardware.

## Runtime telemetry

The application also logs existing `[perf]` startup and UI timings plus encrypted-flush duration/size. Keep metric names stable so results remain comparable across releases.
