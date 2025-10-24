from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List

from silverestimate.domain.estimate_models import EstimateLineCategory
from silverestimate.presenter import SaveItem, SaveOutcome, SavePayload
from silverestimate.services.estimate_calculator import compute_totals
from silverestimate.ui.view_models import (
    EstimateEntryRowState,
    EstimateEntryViewModel,
)


@dataclass(frozen=True)
class SavePreparation:
    """Container for save payload and any row-level validation issues."""

    payload: SavePayload
    skipped_rows: List[int]
    row_errors: Dict[int, str]


class EstimateEntryPersistenceService:
    """Translate between the view-model state and presenter persistence calls."""

    def __init__(self, view_model: EstimateEntryViewModel) -> None:
        self._view_model = view_model

    # ------------------------------------------------------------------ #
    # Save helpers
    # ------------------------------------------------------------------ #
    def prepare_save_payload(
        self,
        *,
        voucher_no: str,
        date: str,
        note: str,
    ) -> SavePreparation:
        """Create a SavePayload from the current view-model rows."""
        rows = self._view_model.rows()
        save_items: List[SaveItem] = []
        skipped_rows: List[int] = []
        row_errors: Dict[int, str] = {}

        for idx, row in enumerate(rows):
            if row.is_empty():
                continue
            row_number = row.row_index if row.row_index > 0 else idx + 1
            try:
                save_item = self._row_to_save_item(row, row_number)
            except ValueError as exc:
                skipped_rows.append(row_number)
                row_errors[row_number] = str(exc)
                continue
            save_items.append(save_item)

        if not save_items:
            raise ValueError("No valid items found to save.")

        totals = compute_totals(
            [self._row_to_estimate_line(row) for row in rows if not row.is_empty()],
            silver_rate=self._view_model.silver_rate,
            last_balance_silver=self._view_model.last_balance_silver,
            last_balance_amount=self._view_model.last_balance_amount,
        )

        regular_items = tuple(
            item for item in save_items if not item.is_return and not item.is_silver_bar
        )
        return_items = tuple(
            item for item in save_items if item.is_return or item.is_silver_bar
        )

        payload = SavePayload(
            voucher_no=voucher_no,
            date=date,
            silver_rate=self._view_model.silver_rate,
            note=note,
            last_balance_silver=self._view_model.last_balance_silver,
            last_balance_amount=self._view_model.last_balance_amount,
            items=tuple(save_items),
            regular_items=regular_items,
            return_items=return_items,
            totals={
                "total_gross": sum(item.gross for item in save_items),
                "total_net": sum(item.net_wt for item in save_items),
                "net_fine": totals.net_fine_core,
                "net_wage": totals.net_wage_core,
                "note": note,
                "last_balance_silver": self._view_model.last_balance_silver,
                "last_balance_amount": self._view_model.last_balance_amount,
            },
        )

        return SavePreparation(
            payload=payload,
            skipped_rows=skipped_rows,
            row_errors=row_errors,
        )

    def execute_save(
        self,
        *,
        voucher_no: str,
        date: str,
        note: str,
        presenter,
    ) -> tuple[SaveOutcome, SavePreparation]:
        """Run save using the presenter and return the outcome plus preparation info."""
        preparation = self.prepare_save_payload(
            voucher_no=voucher_no,
            date=date,
            note=note,
        )
        outcome = presenter.save_estimate(preparation.payload)
        return outcome, preparation

    # ------------------------------------------------------------------ #
    # Load helpers
    # ------------------------------------------------------------------ #
    @staticmethod
    def build_row_states_from_items(
        items: Iterable[SaveItem],
    ) -> List[EstimateEntryRowState]:
        """Convert persisted SaveItem entries into view-model row states."""
        rows: List[EstimateEntryRowState] = []
        for idx, item in enumerate(items):
            if not item.code:
                continue
            category = (
                EstimateLineCategory.RETURN
                if item.is_return
                else EstimateLineCategory.SILVER_BAR
                if item.is_silver_bar
                else EstimateLineCategory.REGULAR
            )
            rows.append(
                EstimateEntryRowState(
                    code=item.code,
                    name=item.name,
                    gross=item.gross,
                    poly=item.poly,
                    net_weight=item.net_wt,
                    purity=item.purity,
                    wage_rate=item.wage_rate,
                    pieces=item.pieces,
                    wage_amount=item.wage,
                    fine_weight=item.fine,
                    category=category,
                    row_index=item.row_number if item.row_number else idx + 1,
                )
            )
        return rows

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #
    @staticmethod
    def _row_to_estimate_line(row: EstimateEntryRowState):
        return row.to_estimate_line()

    @staticmethod
    def _row_to_save_item(row: EstimateEntryRowState, row_number: int) -> SaveItem:
        if row.net_weight < 0 or row.fine_weight < 0 or row.wage_amount < 0:
            raise ValueError("Calculated values cannot be negative.")

        is_return = row.category.is_return()
        is_silver_bar = row.category.is_silver_bar()

        return SaveItem(
            code=row.code,
            row_number=row_number,
            name=row.name,
            gross=row.gross,
            poly=row.poly,
            net_wt=row.net_weight,
            purity=row.purity,
            wage_rate=row.wage_rate,
            pieces=row.pieces,
            wage=row.wage_amount,
            fine=row.fine_weight,
            is_return=is_return,
            is_silver_bar=is_silver_bar,
        )
