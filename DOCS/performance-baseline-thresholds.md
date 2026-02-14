# Performance Baseline Thresholds

This file tracks the baseline thresholds for the current optimization pass.
Instrumentation emits `[perf]` entries in debug logs for the primary hotspots.

## Thresholds

- `estimate_entry.cell_edit` p95:
  - <= 25 ms at ~100 active rows
  - <= 60 ms at ~500 active rows
- `estimate_entry.apply_loaded_estimate`:
  - <= 800 ms for ~500 estimate lines
- `item_master.load_items`:
  - <= 150 ms for ~10,000 catalog rows (after debounce)
- `silver_bars.load_available` / `silver_bars.load_list`:
  - <= 500 ms UI-blocking work for ~1,500 rendered rows

## Instrumented Metrics

- `estimate_entry.cell_edit`
- `estimate_entry.totals_recompute`
- `estimate_entry.sync_view_model`
- `estimate_entry.apply_loaded_estimate`
- `item_master.load_items`
- `silver_bars.load_available`
- `silver_bars.load_list`
- `silver_bars.populate_table`

## Collection Notes

1. Enable debug logging.
2. Run the app with representative datasets:
   - estimates: 100 and 500 rows
   - item catalog: 2,000 and 10,000 rows
   - silver bars: 5,000 rows
3. Extract `[perf]` lines from logs and compute p95 values per metric.
