"""Totals and row-calculation controller for estimate entry."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Optional

from PyQt5 import sip
from PyQt5.QtWidgets import QDoubleSpinBox

from silverestimate.domain.estimate_models import (
    CategoryTotals,
    EstimateLineCategory,
    TotalsResult,
)
from silverestimate.services.estimate_calculator import (
    compute_fine_weight,
    compute_net_weight,
    compute_wage_amount,
)
from silverestimate.ui.view_models import EstimateEntryRowState

from ._host_proxy import HostProxy
from .estimate_entry_ui import (
    COL_FINE_WT,
    COL_GROSS,
    COL_NET_WT,
    COL_PIECES,
    COL_POLY,
    COL_PURITY,
    COL_WAGE_AMT,
    COL_WAGE_RATE,
)

if TYPE_CHECKING:
    from .estimate_entry import _RowContribution, _RunningCategoryTotals
    from .estimate_entry_components import EstimateTableView


class EstimateEntryTotalsController(HostProxy):
    """Own totals recompute and incremental aggregation behavior."""

    if TYPE_CHECKING:
        item_table: EstimateTableView
        silver_rate_spin: QDoubleSpinBox
        _agg_overall_gross: float
        _agg_overall_poly: float
        _agg_regular: _RunningCategoryTotals
        _agg_returns: _RunningCategoryTotals
        _agg_silver_bars: _RunningCategoryTotals
        _incremental_totals_enabled: bool
        _incremental_totals_failed: bool
        _row_contrib_cache: dict[int, _RowContribution]

    def calculate_net_weight(self):
        self._recompute_row_derived_values(self.current_row)

    def calculate_fine(self):
        self._recompute_row_derived_values(self.current_row)

    def calculate_wage(self):
        self._recompute_row_derived_values(self.current_row)

    def _row_wage_type(self, row: int) -> str:
        table = getattr(self, "item_table", None)
        if table is None:
            return "WT"
        model = table.get_model() if hasattr(table, "get_model") else table.model()
        if model is None:
            return "WT"
        try:
            get_row = getattr(model, "get_row", None)
            if callable(get_row):
                row_state = get_row(row)
                if row_state is not None:
                    wage_type = getattr(row_state, "wage_type", "WT")
                    return (
                        "PC" if str(wage_type or "").strip().upper() == "PC" else "WT"
                    )
        except (AttributeError, TypeError, RuntimeError, ValueError):
            pass
        return "WT"

    def _recompute_row_derived_values(self, row: int, *, schedule_totals: bool = True):
        if row is None or row < 0:
            return
        if row >= self.item_table.rowCount():
            return
        try:
            gross = self._get_cell_float(row, COL_GROSS)
            poly = self._get_cell_float(row, COL_POLY)
            net = compute_net_weight(gross, poly)
            purity = self._get_cell_float(row, COL_PURITY)
            fine = compute_fine_weight(net, purity)
            wage_rate = self._get_cell_float(row, COL_WAGE_RATE)
            pieces = self._get_cell_int(row, COL_PIECES)
            wage_basis = self._row_wage_type(row)
            wage = compute_wage_amount(
                wage_basis,
                net_weight=net,
                wage_rate=wage_rate,
                pieces=pieces,
            )

            self.item_table.set_cell_text(row, COL_NET_WT, f"{net:.2f}")
            self.item_table.set_cell_text(row, COL_FINE_WT, f"{fine:.2f}")
            self.item_table.set_cell_text(row, COL_WAGE_AMT, f"{wage:.0f}")
            self._update_incremental_for_row(row)

            if schedule_totals:
                self._schedule_totals_recalc()
        except (AttributeError, TypeError, ValueError) as exc:
            self.logger.warning(
                "Failed to recompute row %s derived values: %s", row, exc, exc_info=True
            )

    def _schedule_totals_recalc(self, delay_ms: int | None = None) -> None:
        timer = getattr(self, "_totals_timer", None)
        if timer is None or sip.isdeleted(timer):
            self.calculate_totals()
            return
        if delay_ms is None:
            delay_ms = int(timer.interval())
        try:
            timer.setInterval(max(0, int(delay_ms)))
            timer.start()
        except (AttributeError, RuntimeError, TypeError, ValueError) as exc:
            self.logger.debug("Failed to schedule totals recalculation: %s", exc)
            self.calculate_totals()

    def _log_perf_metric(
        self,
        name: str,
        start_time: float,
        *,
        threshold_ms: float = 0.0,
        **metadata,
    ) -> None:
        elapsed_ms = (time.perf_counter() - start_time) * 1000.0
        if elapsed_ms < max(0.0, float(threshold_ms)):
            return
        details = " ".join(f"{key}={value}" for key, value in metadata.items())
        if details:
            self.logger.debug("[perf] %s=%.2fms %s", name, elapsed_ms, details)
        else:
            self.logger.debug("[perf] %s=%.2fms", name, elapsed_ms)

    @staticmethod
    def _inactive_row_contribution() -> "_RowContribution":
        from .estimate_entry import _RowContribution

        return _RowContribution()

    def _totals_incremental_is_active(self) -> bool:
        return bool(
            self._incremental_totals_enabled and not self._incremental_totals_failed
        )

    @staticmethod
    def _category_bucket_for(
        category: EstimateLineCategory,
        *,
        regular,
        returns,
        silver_bars,
    ):
        if category is EstimateLineCategory.RETURN:
            return returns
        if category is EstimateLineCategory.SILVER_BAR:
            return silver_bars
        return regular

    def _row_contribution_from_row_state(
        self, row_state: Optional[EstimateEntryRowState]
    ):
        from .estimate_entry import _RowContribution

        if row_state is None:
            return self._inactive_row_contribution()

        code = str(getattr(row_state, "code", "") or "").strip()
        if not code:
            return self._inactive_row_contribution()

        category = getattr(row_state, "category", EstimateLineCategory.REGULAR)
        if not isinstance(category, EstimateLineCategory):
            category = EstimateLineCategory.from_label(str(category))

        return _RowContribution(
            category=category,
            gross=float(getattr(row_state, "gross", 0.0) or 0.0),
            poly=float(getattr(row_state, "poly", 0.0) or 0.0),
            net=float(getattr(row_state, "net_weight", 0.0) or 0.0),
            fine=float(getattr(row_state, "fine_weight", 0.0) or 0.0),
            wage=float(getattr(row_state, "wage_amount", 0.0) or 0.0),
            is_active=True,
        )

    @staticmethod
    def _apply_signed_contribution(bucket, contrib, *, sign: int) -> None:
        bucket.gross += sign * contrib.gross
        bucket.net += sign * contrib.net
        bucket.fine += sign * contrib.fine
        bucket.wage += sign * contrib.wage

    def _apply_contribution_delta(self, old_contrib, new_contrib) -> None:
        if old_contrib.is_active:
            old_bucket = self._category_bucket_for(
                old_contrib.category,
                regular=self._agg_regular,
                returns=self._agg_returns,
                silver_bars=self._agg_silver_bars,
            )
            self._apply_signed_contribution(old_bucket, old_contrib, sign=-1)
            self._agg_overall_gross -= old_contrib.gross
            self._agg_overall_poly -= old_contrib.poly

        if new_contrib.is_active:
            new_bucket = self._category_bucket_for(
                new_contrib.category,
                regular=self._agg_regular,
                returns=self._agg_returns,
                silver_bars=self._agg_silver_bars,
            )
            self._apply_signed_contribution(new_bucket, new_contrib, sign=1)
            self._agg_overall_gross += new_contrib.gross
            self._agg_overall_poly += new_contrib.poly

    def _reset_incremental_aggregates(self) -> None:
        from .estimate_entry import _RunningCategoryTotals

        self._row_contrib_cache.clear()
        self._agg_regular = _RunningCategoryTotals()
        self._agg_returns = _RunningCategoryTotals()
        self._agg_silver_bars = _RunningCategoryTotals()
        self._agg_overall_gross = 0.0
        self._agg_overall_poly = 0.0

    def _rebuild_incremental_totals_from_table(self) -> None:
        self._reset_incremental_aggregates()
        if not self._is_table_valid():
            return

        rows = list(self.item_table.get_all_rows())
        for row_idx, row_state in enumerate(rows):
            contrib = self._row_contribution_from_row_state(row_state)
            self._apply_contribution_delta(self._inactive_row_contribution(), contrib)
            self._row_contrib_cache[row_idx] = contrib

    def _update_incremental_for_row(self, row: int) -> None:
        if not self._totals_incremental_is_active():
            return
        if row is None or row < 0:
            return
        if not self._is_table_valid():
            return
        if row >= self.item_table.rowCount():
            return

        try:
            row_state = self.item_table.get_row_state(row)
            old_contrib = self._row_contrib_cache.get(
                row, self._inactive_row_contribution()
            )
            new_contrib = self._row_contribution_from_row_state(row_state)
            self._apply_contribution_delta(old_contrib, new_contrib)
            self._row_contrib_cache[row] = new_contrib
        except (AttributeError, RuntimeError, TypeError, ValueError) as exc:
            self._disable_incremental_totals_and_fallback(exc)

    def _remove_incremental_row(self, row: int) -> None:
        if not self._totals_incremental_is_active():
            return
        if row is None or row < 0:
            return

        old_contrib = self._row_contrib_cache.pop(
            row, self._inactive_row_contribution()
        )
        self._apply_contribution_delta(old_contrib, self._inactive_row_contribution())
        if not self._row_contrib_cache:
            return

        shifted: dict[int, _RowContribution] = {}
        for index in sorted(self._row_contrib_cache):
            contrib = self._row_contrib_cache[index]
            shifted[index - 1 if index > row else index] = contrib
        self._row_contrib_cache = shifted

    @staticmethod
    def _frozen_category_totals(bucket) -> CategoryTotals:
        return CategoryTotals(
            gross=float(bucket.gross),
            net=float(bucket.net),
            fine=float(bucket.fine),
            wage=float(bucket.wage),
        )

    def _build_totals_result_from_aggregates(self) -> TotalsResult:
        regular_totals = self._frozen_category_totals(self._agg_regular)
        return_totals = self._frozen_category_totals(self._agg_returns)
        bar_totals = self._frozen_category_totals(self._agg_silver_bars)

        silver_rate = float(self.silver_rate_spin.value())
        last_balance_silver = float(self.last_balance_silver)
        last_balance_amount = float(self.last_balance_amount)

        net_fine_core = regular_totals.fine - bar_totals.fine - return_totals.fine
        net_wage_core = regular_totals.wage - bar_totals.wage - return_totals.wage
        net_value_core = net_fine_core * silver_rate if silver_rate > 0 else 0.0
        net_fine = net_fine_core + last_balance_silver
        net_wage = net_wage_core + last_balance_amount
        net_value = net_fine * silver_rate if silver_rate > 0 else 0.0
        grand_total = net_value + net_wage if silver_rate > 0 else net_wage

        return TotalsResult(
            overall_gross=float(self._agg_overall_gross),
            overall_poly=float(self._agg_overall_poly),
            regular=regular_totals,
            returns=return_totals,
            silver_bars=bar_totals,
            net_fine_core=net_fine_core,
            net_wage_core=net_wage_core,
            net_value_core=net_value_core,
            net_fine=net_fine,
            net_wage=net_wage,
            net_value=net_value,
            grand_total=grand_total,
            silver_rate=silver_rate,
            last_balance_silver=last_balance_silver,
            last_balance_amount=last_balance_amount,
        )

    def _calculate_totals_full_legacy(self, *, start: float | None = None) -> None:
        started_at = time.perf_counter() if start is None else start
        self._update_view_model_snapshot()
        totals = self.view_model.compute_totals()
        self.apply_totals(totals)
        self._log_perf_metric(
            "estimate_entry.totals_recompute", started_at, threshold_ms=15.0
        )

    def _disable_incremental_totals_and_fallback(self, exc: Exception) -> None:
        if not self._incremental_totals_failed:
            self.logger.warning(
                "Incremental totals failed; legacy fallback is disabled: %s",
                exc,
                exc_info=True,
            )
        self._incremental_totals_failed = True

    def calculate_totals(self):
        start = time.perf_counter()
        if not self._incremental_totals_enabled:
            self._calculate_totals_full_legacy(start=start)
            return
        if self._incremental_totals_failed:
            return

        try:
            if len(self._row_contrib_cache) != self.item_table.rowCount():
                self._rebuild_incremental_totals_from_table()
            totals = self._build_totals_result_from_aggregates()
            self.apply_totals(totals)
            self._log_perf_metric(
                "estimate_entry.totals_incremental_apply",
                start,
                threshold_ms=15.0,
            )
        except (AttributeError, RuntimeError, TypeError, ValueError) as exc:
            self._disable_incremental_totals_and_fallback(exc)
