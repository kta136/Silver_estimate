"""Totals and row-calculation controller for estimate entry."""

from __future__ import annotations

import time
from dataclasses import replace
from typing import TYPE_CHECKING, Iterable

from shiboken6 import isValid

from silverestimate.domain.estimate_entry import EstimateEntryRowState
from silverestimate.domain.estimate_models import EstimateLineCategory, TotalsResult
from silverestimate.services.estimate_calculator import (
    compute_fine_weight,
    compute_net_weight,
    compute_totals,
    compute_wage_amount,
)

from .estimate_entry_logic.constants import (
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
    from .estimate_entry import EstimateEntryWidget


class EstimateEntryTotalsController:
    """Own row recalculation and estimate totals."""

    def __init__(self, host: EstimateEntryWidget) -> None:
        self.host = host

    def calculate_net_weight(self):
        self._recompute_row_derived_values(self.host.current_row)

    def _row_wage_type(self, row: int) -> str:
        table = getattr(self.host, "item_table", None)
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
        except AttributeError, TypeError, RuntimeError, ValueError:
            pass
        return "WT"

    def _recompute_row_derived_values(self, row: int, *, schedule_totals: bool = True):
        started_at = time.perf_counter()
        if row is None or row < 0:
            return
        if row >= self.host.item_table.rowCount():
            return
        try:
            gross = self.host.table_controller._get_cell_float(row, COL_GROSS)
            poly = self.host.table_controller._get_cell_float(row, COL_POLY)
            net = compute_net_weight(gross, poly)
            purity = self.host.table_controller._get_cell_float(row, COL_PURITY)
            fine = compute_fine_weight(net, purity)
            wage_rate = self.host.table_controller._get_cell_float(row, COL_WAGE_RATE)
            pieces = self.host.table_controller._get_cell_int(row, COL_PIECES)
            wage_basis = self._row_wage_type(row)
            wage = compute_wage_amount(
                wage_basis,
                net_weight=net,
                wage_rate=wage_rate,
                pieces=pieces,
            )

            self.host.item_table.set_cell_value(row, COL_NET_WT, net)
            self.host.item_table.set_cell_value(row, COL_FINE_WT, fine)
            self.host.item_table.set_cell_value(row, COL_WAGE_AMT, wage)

            if schedule_totals:
                self.calculate_totals(start=started_at)
        except (AttributeError, TypeError, ValueError) as exc:
            self.host.logger.warning(
                "Failed to recompute row %s derived values: %s", row, exc, exc_info=True
            )

    def _schedule_totals_recalc(self, delay_ms: int | None = None) -> None:
        timer = getattr(self.host, "_totals_timer", None)
        if timer is None or not isValid(timer):
            self.calculate_totals()
            return
        if delay_ms is None:
            delay_ms = int(timer.interval())
        try:
            timer.setInterval(max(0, int(delay_ms)))
            timer.start()
        except (AttributeError, RuntimeError, TypeError, ValueError) as exc:
            self.host.logger.debug("Failed to schedule totals recalculation: %s", exc)
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
            self.host.logger.debug("[perf] %s=%.2fms %s", name, elapsed_ms, details)
        else:
            self.host.logger.debug("[perf] %s=%.2fms", name, elapsed_ms)

    @staticmethod
    def _row_category(row_state: EstimateEntryRowState) -> EstimateLineCategory:
        category = row_state.category
        if isinstance(category, EstimateLineCategory):
            return category
        return EstimateLineCategory.from_label(str(category))

    @classmethod
    def build_totals(
        cls,
        rows: Iterable[EstimateEntryRowState],
        *,
        silver_rate: float,
        last_balance_silver: float = 0.0,
        last_balance_amount: float = 0.0,
    ) -> TotalsResult:
        """Compute estimate totals from the current row states."""
        lines = [
            replace(row.to_estimate_line(), category=cls._row_category(row))
            for row in rows
            if row is not None and not row.is_empty()
        ]
        return compute_totals(
            lines,
            silver_rate=silver_rate,
            last_balance_silver=last_balance_silver,
            last_balance_amount=last_balance_amount,
        )

    def calculate_totals(self, *, start: float | None = None) -> None:
        """Recompute totals from every row and show them."""
        started_at = time.perf_counter() if start is None else start
        if not self.host.table_controller._is_table_valid():
            return
        try:
            totals = self.build_totals(
                self.host.item_table.get_all_rows(),
                silver_rate=float(self.host.silver_rate_spin.value()),
                last_balance_silver=float(self.host.last_balance_silver),
                last_balance_amount=float(self.host.last_balance_amount),
            )
            self.host.apply_totals(totals)
        except (AttributeError, RuntimeError, TypeError, ValueError) as exc:
            self.host.logger.warning(
                "Failed to recalculate estimate totals: %s", exc, exc_info=True
            )
            return
        self._log_perf_metric(
            "estimate_entry.totals_apply",
            started_at,
            threshold_ms=15.0,
        )
