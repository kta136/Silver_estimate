from __future__ import annotations

from dataclasses import replace
from typing import Iterable, Sequence
from uuid import uuid4

from silverestimate.domain.estimate_entry import (
    EstimateEntryRowState as EstimateEntryRowState,
)
from silverestimate.domain.estimate_entry import (
    EstimateEntrySnapshot,
)


class EstimateEntryViewModel:
    """Pure-Python representation of the estimate entry state."""

    def __init__(self) -> None:
        self._rows: list[EstimateEntryRowState] = []
        self.return_mode: bool = False
        self.silver_bar_mode: bool = False
        self.silver_rate: float = 0.0
        self.last_balance_silver: float = 0.0
        self.last_balance_amount: float = 0.0

        # Voucher metadata
        self.voucher_number: str = ""
        self.voucher_date: str = ""  # ISO format date string
        self.voucher_note: str = ""

    # ------------------------------------------------------------------ #
    # Row management
    # ------------------------------------------------------------------ #
    def set_rows(self, rows: Iterable[EstimateEntryRowState]) -> None:
        """Replace rows with the provided iterable."""
        self._rows = [self._coerce_row(row) for row in rows]
        self._normalize_row_indices()

    def rows(self) -> Sequence[EstimateEntryRowState]:
        """Return an immutable view of the row data."""
        return tuple(self._rows)

    def ensure_line_keys(self) -> None:
        """Assign stable line keys for active rows that do not yet have one."""
        for idx, row in enumerate(self._rows):
            if row.is_empty() or str(row.line_key or "").strip():
                continue
            self._rows[idx] = replace(row, line_key=uuid4().hex)

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
    # Voucher metadata management
    # ------------------------------------------------------------------ #
    def set_voucher_metadata(
        self,
        *,
        voucher_number: str | None = None,
        voucher_date: str | None = None,
        voucher_note: str | None = None,
    ) -> None:
        """Update voucher metadata fields.

        Args:
            voucher_number: The voucher number
            voucher_date: The voucher date (ISO format string)
            voucher_note: The voucher note
        """
        if voucher_number is not None:
            self.voucher_number = str(voucher_number)
        if voucher_date is not None:
            self.voucher_date = str(voucher_date)
        if voucher_note is not None:
            self.voucher_note = str(voucher_note)

    def get_voucher_metadata(self) -> dict[str, str]:
        """Get all voucher metadata as a dictionary.

        Returns:
            A dictionary with voucher_number, voucher_date, and voucher_note
        """
        return {
            "voucher_number": self.voucher_number,
            "voucher_date": self.voucher_date,
            "voucher_note": self.voucher_note,
        }

    # ------------------------------------------------------------------ #
    # Derived values
    # ------------------------------------------------------------------ #
    def as_save_snapshot(self) -> EstimateEntrySnapshot:
        """Assign line identities in the UI, then detach the application save input."""
        self.ensure_line_keys()
        return EstimateEntrySnapshot(
            rows=tuple(self._rows),
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
