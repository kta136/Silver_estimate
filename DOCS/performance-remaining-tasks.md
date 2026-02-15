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

- [ ] Voucher sort/indexability fix (`Not Done`)
  - Remove hot-query `CAST(voucher_no AS INTEGER)` usage.
  - Introduce numeric voucher column and supporting migration/indexes.
  - References:
    - `silverestimate/persistence/estimates_repository.py:32`
    - `silverestimate/persistence/estimates_repository.py:98`
    - `silverestimate/persistence/estimates_repository.py:133`
    - `silverestimate/persistence/migrations.py:57`

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
  - Remove compatibility shims that are still wired.
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
