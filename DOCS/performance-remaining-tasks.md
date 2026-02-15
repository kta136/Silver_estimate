# Remaining Performance Tasks (Original List)

This file captures the unfinished work from the original performance/migration checklist.

## Priority Order (Largest Expected Performance Gain -> Least)

- [ ] Silver bar table migration (`Not Done`)
  - Move from `QTableWidget` to model/view implementation.
  - References:
    - `silverestimate/ui/silver_bar_management.py:36`
    - `silverestimate/ui/silver_bar_management.py:490`
    - `silverestimate/ui/silver_bar_management.py:2216`

- [ ] Totals pipeline (`Not Done`)
  - Replace full recompute path with row-delta incremental updates.
  - References:
    - `silverestimate/ui/estimate_entry.py:1228`
    - `silverestimate/ui/estimate_entry.py:1721`
    - `silverestimate/ui/view_models/estimate_entry_view_model.py:215`

- [x] Voucher sort/indexability fix (`Done`)
  - Remove hot-query `CAST(voucher_no AS INTEGER)` usage.
  - Introduce numeric voucher column and supporting migration/indexes.
  - References:
    - `silverestimate/persistence/estimates_repository.py:32`
    - `silverestimate/persistence/estimates_repository.py:128`
    - `silverestimate/persistence/estimates_repository.py:211`
    - `silverestimate/persistence/migrations.py:57`

- [ ] Packaging startup optimization follow-up (`Deferred`)
  - Keep this out of the current low-risk code pass.
  - Evaluate producing onedir/non-onefile release artifacts by default for faster launch.
  - References:
    - `.github/workflows/release-windows.yml:29`
    - `DOCS/deployment-guide.md:21`

- [ ] Disable content auto-fit while typing (`Partially Done`)
  - Currently reduced via debounce/per-column updates.
  - References:
    - `silverestimate/ui/estimate_entry.py:142`
    - `silverestimate/ui/estimate_entry.py:690`
    - `silverestimate/ui/estimate_entry.py:1798`

- [ ] ItemMaster migration (`Not Done`)
  - Move from `QTableWidget` to `QTableView` + `QSortFilterProxyModel`.
  - References:
    - `silverestimate/ui/item_master.py:16`
    - `silverestimate/ui/item_master.py:161`
    - `silverestimate/ui/item_master.py:221`

- [ ] Estimate table model/view migration cleanup (`Partially Done`)
  - Remove remaining model/view bridge shims that are still wired.
  - References:
    - `silverestimate/ui/estimate_entry_components/estimate_table_view.py:19`
    - `silverestimate/ui/estimate_entry_components/estimate_table_view.py:35`
    - `silverestimate/ui/estimate_entry_components/estimate_table_view.py:217`
    - `silverestimate/ui/estimate_entry.py:579`

- [ ] CI performance regression gates (`Not Done`)
  - Add automated p50/p95 budget checks from perf logs in CI.
  - References:
    - `DOCS/performance-baseline-thresholds.md:1`
    - `.github/workflows/pr-validation.yml:16`

## Additional Findings (Code Review: 2026-02-15)

These are newly identified opportunities from a focused runtime/data-path review.

## Priority Order (Largest Expected Performance Gain -> Least)

- [x] History query still uses non-indexable voucher cast (`Done`)
  - Replace `ORDER BY CAST(voucher_no AS INTEGER)` with `ORDER BY voucher_no_int DESC, voucher_no DESC` in history worker query.
  - Enforced indexed ordering path only (`voucher_no_int DESC, voucher_no DESC`).
  - References:
    - `silverestimate/ui/estimate_history.py:414`
    - `silverestimate/persistence/migrations.py:240`

- [x] Estimate list retrieval does N+1 item queries (`Done`)
  - `get_estimates()` loads headers first, then queries `estimate_items` once per voucher.
  - Replaced with chunked bulk `estimate_items` queries (`IN (...)`) and in-memory grouping by voucher.
  - References:
    - `silverestimate/persistence/estimates_repository.py:111`
    - `silverestimate/persistence/estimates_repository.py:158`
    - `tests/integration/test_repositories.py:279`

- [x] Save path performs expensive existence check by full estimate load (`Done`)
  - `estimate_exists()` calls `load_estimate()` instead of a lightweight `SELECT 1 ... LIMIT 1`.
  - Enforced direct repository existence check path only.
  - References:
    - `silverestimate/persistence/estimates_repository.py:92`
    - `silverestimate/persistence/database_manager.py:674`
    - `silverestimate/services/estimate_repository.py:66`
    - `silverestimate/presenter/estimate_entry_presenter.py:245`

- [x] Silver bar save sync uses per-row commit pattern (`Done`)
  - Presenter loops through bars and repository methods commit each row update/insert.
  - Replaced with transactional bulk sync API for estimate save flows as the only path.
  - References:
    - `silverestimate/presenter/estimate_entry_presenter.py:275`
    - `silverestimate/services/estimate_repository.py:135`
    - `silverestimate/persistence/silver_bars_repository.py:383`
    - `silverestimate/persistence/database_manager.py:754`
    - `tests/integration/test_repositories.py:454`

- [x] Voucher-specific silver bar fetch uses wildcard search (`Done`)
  - `LIKE '%voucher%'` prevents efficient index usage and may over-match.
  - Use exact match (`=`) where voucher identity is known.
  - Service adapter now uses exact estimate fetch API (`get_silver_bars_for_estimate`) directly.
  - References:
    - `silverestimate/services/estimate_repository.py:101`
    - `silverestimate/persistence/silver_bars_repository.py:360`
    - `silverestimate/persistence/database_manager.py:751`
    - `silverestimate/persistence/migrations.py:251`

- [ ] Estimate entry still auto-fits columns during typing (`Partially Done`)
  - Current debounce helps, but `sizeHintForColumn()` remains on edit path and scales with row count.
  - Move auto-fit to explicit actions (font/layout reset/load) instead of per-keystroke updates.
  - References:
    - `silverestimate/ui/estimate_entry.py:741`
    - `silverestimate/ui/estimate_entry.py:2080`
    - `silverestimate/ui/estimate_entry.py:2108`

- [x] Item selection dialog scans/renders all items on each filter pass (`Done`)
  - Dialog loads the full item set and re-ranks/re-renders on every search update.
  - Added DB-backed ranked search with result limiting (`MAX_VISIBLE_RESULTS=500`) as the only execution path.
  - References:
    - `silverestimate/ui/item_selection_dialog.py:39`
    - `silverestimate/ui/item_selection_dialog.py:273`
    - `silverestimate/persistence/items_repository.py:110`
    - `silverestimate/persistence/database_manager.py:658`
    - `tests/ui/test_item_selection_dialog.py:170`
    - `tests/integration/test_repositories.py:184`

- [ ] Item search on `name` lacks dedicated index strategy (`Not Done`)
  - Current query pattern combines `code` and `name` with `OR`; add targeted indexing/search strategy for larger tables.
  - Consider a `name COLLATE NOCASE` index and query-shape review (prefix path + bounded results).
  - References:
    - `silverestimate/persistence/items_repository.py:89`
    - `silverestimate/persistence/items_repository.py:102`
    - `silverestimate/persistence/migrations.py:222`
