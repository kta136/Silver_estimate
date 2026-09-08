from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Dict, Iterable, List, Protocol

from silverestimate.domain.estimate_entry import (
    EstimateEntryRowState,
    EstimateEntrySnapshot,
    SaveItem,
    SaveOutcome,
    SavePayload,
)
from silverestimate.domain.estimate_models import EstimateLine, EstimateLineCategory
from silverestimate.domain.estimate_validation import (
    validate_estimate_item,
    validate_estimate_totals,
)
from silverestimate.services.estimate_calculator import compute_totals


@dataclass(frozen=True)
class SavePreparation:
    """Container for save payload and any row-level validation issues."""

    payload: SavePayload
    skipped_rows: List[int]
    row_errors: Dict[int, str]


class SaveValidationError(ValueError):
    """Validation failure retaining row locations for the entry screen."""

    def __init__(self, row_errors: Dict[int, str]) -> None:
        self.row_errors = row_errors
        detail = "\n".join(f"Row {row}: {error}" for row, error in row_errors.items())
        super().__init__(f"Correct the invalid rows before saving.\n{detail}")


class EstimateSaveExecutor(Protocol):
    """Only the save command is required by the application save workflow."""

    def save_estimate(self, payload: SavePayload) -> SaveOutcome: ...


class EstimateEntryPersistenceService:
    """Validate a detached entry snapshot and execute one save command."""

    def __init__(self, snapshot: EstimateEntrySnapshot) -> None:
        self._snapshot = snapshot

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
        """Create a SavePayload from the detached input rows."""
        rows = self._snapshot.rows
        save_items: List[SaveItem] = []
        accepted_rows: List[EstimateEntryRowState] = []
        skipped_rows: List[int] = []
        row_errors: Dict[int, str] = {}

        for idx, row in enumerate(rows):
            if row.is_empty() and not self._has_row_data(row):
                continue
            row_number = row.row_index if row.row_index > 0 else idx + 1
            try:
                save_item = self._row_to_save_item(row, row_number)
            except ValueError as exc:
                skipped_rows.append(row_number)
                row_errors[row_number] = str(exc)
                continue
            save_items.append(save_item)
            accepted_rows.append(row)

        if not save_items:
            if row_errors:
                raise SaveValidationError(row_errors)
            raise ValueError("No valid items found to save.")

        if not voucher_no.strip():
            raise ValueError("Voucher number is required.")
        validate_estimate_totals(
            self._snapshot.silver_rate,
            {
                "last_balance_silver": self._snapshot.last_balance_silver,
                "last_balance_amount": self._snapshot.last_balance_amount,
            },
        )
        totals = compute_totals(
            [self._row_to_estimate_line(row) for row in accepted_rows],
            silver_rate=self._snapshot.silver_rate,
            last_balance_silver=self._snapshot.last_balance_silver,
            last_balance_amount=self._snapshot.last_balance_amount,
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
            silver_rate=self._snapshot.silver_rate,
            note=note,
            last_balance_silver=self._snapshot.last_balance_silver,
            last_balance_amount=self._snapshot.last_balance_amount,
            items=tuple(save_items),
            regular_items=regular_items,
            return_items=return_items,
            totals={
                "total_gross": sum(item.gross for item in save_items),
                "total_net": sum(item.net_wt for item in save_items),
                "net_fine": totals.net_fine_core,
                "net_wage": totals.net_wage_core,
                "note": note,
                "last_balance_silver": self._snapshot.last_balance_silver,
                "last_balance_amount": self._snapshot.last_balance_amount,
            },
        )
        validate_estimate_totals(payload.silver_rate, payload.totals)

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
        presenter: EstimateSaveExecutor,
    ) -> tuple[SaveOutcome, SavePreparation]:
        """Run save using the presenter and return the outcome plus preparation info."""
        preparation = self.prepare_save_payload(
            voucher_no=voucher_no,
            date=date,
            note=note,
        )
        if preparation.row_errors:
            return SaveOutcome(
                success=False,
                message="Estimate was not saved. Correct the invalid rows and try again.",
                error_detail="\n".join(
                    f"Row {row}: {error}"
                    for row, error in preparation.row_errors.items()
                ),
            ), preparation
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
            category = (
                EstimateLineCategory.RETURN
                if item.is_return
                else (
                    EstimateLineCategory.SILVER_BAR
                    if item.is_silver_bar
                    else EstimateLineCategory.REGULAR
                )
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
                    wage_type=item.wage_type,
                    wage_amount=item.wage,
                    fine_weight=item.fine,
                    category=category,
                    row_index=item.row_number if item.row_number else idx + 1,
                    line_key=str(item.line_key or ""),
                    tunch=item.tunch,
                    snapshot_version=item.snapshot_version,
                )
            )
        return rows

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #
    @staticmethod
    def _has_row_data(row: EstimateEntryRowState) -> bool:
        return bool(
            row.name.strip()
            or row.pieces not in (0, 1)
            or any(
                (
                    row.gross,
                    row.poly,
                    row.net_weight,
                    row.purity,
                    row.wage_rate,
                    row.wage_amount,
                    row.fine_weight,
                )
            )
        )

    @staticmethod
    def _row_to_estimate_line(row: EstimateEntryRowState) -> EstimateLine:
        return row.to_estimate_line()

    @staticmethod
    def _row_to_save_item(row: EstimateEntryRowState, row_number: int) -> SaveItem:
        is_return = row.category.is_return()
        is_silver_bar = row.category.is_silver_bar()

        item = SaveItem(
            code=row.code,
            row_number=row_number,
            name=row.name,
            gross=row.gross,
            poly=row.poly,
            net_wt=row.net_weight,
            purity=row.purity,
            wage_rate=row.wage_rate,
            pieces=row.pieces,
            wage_type=row.wage_type,
            wage=row.wage_amount,
            fine=row.fine_weight,
            is_return=is_return,
            is_silver_bar=is_silver_bar,
            line_key=str(row.line_key or ""),
            tunch=row.tunch,
            snapshot_version=row.snapshot_version,
        )
        validate_estimate_item(
            asdict(item), allow_missing_code=bool(row.snapshot_version and row.line_key)
        )
        return item
