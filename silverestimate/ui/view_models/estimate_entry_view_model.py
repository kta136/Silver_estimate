from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Iterable, Iterator, Sequence

from silverestimate.domain.estimate_models import (
    EstimateLine,
    EstimateLineCategory,
    TotalsResult,
)
from silverestimate.presenter.estimate_entry_presenter import EstimateEntryViewState
from silverestimate.services.estimate_calculator import compute_totals


@dataclass(frozen=True)
class EstimateEntryRowState:
    """Represents a single row captured from the estimate entry grid."""

    code: str = ""
    name: str = ""
    gross: float = 0.0
    poly: float = 0.0
    net_weight: float = 0.0
    purity: float = 0.0
    wage_rate: float = 0.0
    pieces: int = 1
    wage_amount: float = 0.0
    fine_weight: float = 0.0
    category: EstimateLineCategory = EstimateLineCategory.REGULAR
    row_index: int = 0

    def is_empty(self) -> bool:
        """Return True when the row does not contain a code."""
        return not self.code.strip()

    def to_estimate_line(self) -> EstimateLine:
        """Convert this row into the lightweight line model used for totals."""
        return EstimateLine(
            code=self.code,
            category=self.category,
            gross=self.gross,
            poly=self.poly,
            net_weight=self.net_weight,
            fine_weight=self.fine_weight,
            wage_amount=self.wage_amount,
        )

    def with_category(self, category: EstimateLineCategory) -> "EstimateEntryRowState":
        """Return a copy with a different category."""
        return replace(self, category=category)


class EstimateEntryViewModel:
    """Pure-Python representation of the estimate entry state."""

    def __init__(self) -> None:
        self._rows: list[EstimateEntryRowState] = []
        self.return_mode: bool = False
        self.silver_bar_mode: bool = False
        self.silver_rate: float = 0.0
        self.last_balance_silver: float = 0.0
        self.last_balance_amount: float = 0.0

    # ------------------------------------------------------------------ #
    # Row management
    # ------------------------------------------------------------------ #
    def set_rows(self, rows: Iterable[EstimateEntryRowState]) -> None:
        """Replace rows with the provided iterable."""
        self._rows = [self._coerce_row(row) for row in rows]
        self._normalize_row_indices()

    def update_row(self, index: int, row: EstimateEntryRowState) -> None:
        """Insert or replace the row at the provided index."""
        coerced = self._coerce_row(row)
        if index < 0:
            raise IndexError("Row index cannot be negative")
        if index >= len(self._rows):
            self._rows.extend(
                EstimateEntryRowState() for _ in range(index - len(self._rows) + 1)
            )
        if coerced.row_index <= 0:
            coerced = replace(coerced, row_index=index + 1)
        self._rows[index] = coerced
        self._normalize_row_indices()

    def clear_rows(self) -> None:
        """Reset the stored rows."""
        self._rows.clear()

    def rows(self) -> Sequence[EstimateEntryRowState]:
        """Return an immutable view of the row data."""
        return tuple(self._rows)

    def active_rows(self) -> Sequence[EstimateEntryRowState]:
        """Return only rows that have an assigned code."""
        return tuple(row for row in self._rows if not row.is_empty())

    def iter_lines(self) -> Iterator[EstimateLine]:
        """Yield `EstimateLine` objects for active rows."""
        for row in self._rows:
            if row.is_empty():
                continue
            yield row.to_estimate_line()

    # ------------------------------------------------------------------ #
    # Totals inputs and mode flags
    # ------------------------------------------------------------------ #
    def set_totals_inputs(
        self,
        *,
        silver_rate: float | None = None,
        last_balance_silver: float | None = None,
        last_balance_amount: float | None = None,
    ) -> None:
        """Update the numeric inputs that influence totals."""
        if silver_rate is not None:
            self.silver_rate = float(silver_rate)
        if last_balance_silver is not None:
            self.last_balance_silver = float(last_balance_silver)
        if last_balance_amount is not None:
            self.last_balance_amount = float(last_balance_amount)

    def set_modes(
        self,
        *,
        return_mode: bool | None = None,
        silver_bar_mode: bool | None = None,
    ) -> None:
        """Update the interaction modes tracked by the widget."""
        if return_mode is not None:
            self.return_mode = bool(return_mode)
        if silver_bar_mode is not None:
            self.silver_bar_mode = bool(silver_bar_mode)

    # ------------------------------------------------------------------ #
    # Derived values
    # ------------------------------------------------------------------ #
    def as_view_state(self) -> EstimateEntryViewState:
        """Return the presenter-facing view state snapshot."""
        return EstimateEntryViewState(
            lines=tuple(self.iter_lines()),
            silver_rate=self.silver_rate,
            last_balance_silver=self.last_balance_silver,
            last_balance_amount=self.last_balance_amount,
        )

    def compute_totals(self) -> TotalsResult:
        """Compute totals using the current snapshot."""
        lines = tuple(self.iter_lines())
        return compute_totals(
            lines,
            silver_rate=self.silver_rate,
            last_balance_silver=self.last_balance_silver,
            last_balance_amount=self.last_balance_amount,
        )

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #
    @staticmethod
    def _coerce_row(row: EstimateEntryRowState) -> EstimateEntryRowState:
        if isinstance(row, EstimateEntryRowState):
            return row
        raise TypeError(f"Unsupported row type: {type(row)!r}")

    def _normalize_row_indices(self) -> None:
        for idx, row in enumerate(self._rows):
            if row.row_index <= 0:
                self._rows[idx] = replace(row, row_index=idx + 1)
