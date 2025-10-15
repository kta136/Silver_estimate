"""Presenter for the estimate entry experience."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Mapping, Optional, Protocol, Sequence

from silverestimate.domain.estimate_models import EstimateLine, TotalsResult
from silverestimate.services.estimate_calculator import compute_totals
from silverestimate.services.estimate_repository import EstimateRepository


@dataclass(frozen=True)
class EstimateEntryViewState:
    """Snapshot of the data required to run presenter computations."""

    lines: Sequence[EstimateLine]
    silver_rate: float
    last_balance_silver: float = 0.0
    last_balance_amount: float = 0.0


class EstimateEntryView(Protocol):
    """Interface implemented by the Qt widget so the presenter can talk to it."""

    def capture_state(self) -> EstimateEntryViewState:
        """Return the current state needed for calculations."""

    def apply_totals(self, totals: TotalsResult) -> None:
        """Update UI totals and related labels."""

    def set_voucher_number(self, voucher_no: str) -> None:
        """Display a voucher number in the UI."""

    def show_status(self, message: str, timeout: int = 3000, level: str = "info") -> None:
        """Display a status message to the user."""

    def populate_row(self, row_index: int, item_data: Mapping[str, object]) -> None:
        """Fill the specified row with item data."""

    def prompt_item_selection(self, code: str) -> Optional[Mapping[str, object]]:
        """Open the item selection dialog and return chosen item data."""

    def focus_after_item_lookup(self, row_index: int) -> None:
        """Move focus to the next field after successfully loading an item."""

    def open_history_dialog(self) -> Optional[str]:
        """Open the estimate history dialog and return selected voucher number."""

    def show_silver_bar_management(self) -> None:
        """Trigger the silver bar management workflow."""

    def apply_loaded_estimate(self, loaded: "LoadedEstimate") -> bool:
        """Apply a loaded estimate to the view."""


@dataclass(frozen=True)
class SaveItem:
    """Representation of a row prepared for persistence."""

    code: str
    row_number: int
    name: str
    gross: float
    poly: float
    net_wt: float
    purity: float
    wage_rate: float
    pieces: int
    wage: float
    fine: float
    is_return: bool
    is_silver_bar: bool


@dataclass(frozen=True)
class SavePayload:
    """Aggregate data required to persist an estimate."""

    voucher_no: str
    date: str
    silver_rate: float
    note: str
    last_balance_silver: float
    last_balance_amount: float
    items: Sequence[SaveItem]
    regular_items: Sequence[SaveItem]
    return_items: Sequence[SaveItem]
    totals: Mapping[str, float]


@dataclass(frozen=True)
class SaveOutcome:
    """Result of attempting to save an estimate."""

    success: bool
    message: str
    bars_added: int = 0
    bars_failed: int = 0
    error_detail: Optional[str] = None


@dataclass(frozen=True)
class LoadedEstimate:
    """Representation of a fully loaded estimate."""

    voucher_no: str
    date: str
    silver_rate: float
    note: str
    last_balance_silver: float
    last_balance_amount: float
    items: Sequence[SaveItem]


class EstimateEntryPresenter:
    """Orchestrates estimate-entry workflows independent of the Qt widget."""

    def __init__(self, view: EstimateEntryView, repository: EstimateRepository) -> None:
        self._view = view
        self._repository = repository

    @property
    def repository(self) -> EstimateRepository:
        """Expose the underlying repository (useful for testing)."""
        return self._repository

    def generate_voucher(self, *, silent: bool = False) -> str:
        """Generate a voucher number via the repository and push it to the view."""
        voucher_no = self._repository.generate_voucher_no()
        self._view.set_voucher_number(voucher_no)
        if not silent:
            self._view.show_status(f"Generated new voucher: {voucher_no}", 2500)
        return voucher_no

    def refresh_totals(self) -> TotalsResult:
        """Recompute totals based on the current view state."""
        state = self._view.capture_state()
        totals = compute_totals(
            state.lines,
            silver_rate=state.silver_rate,
            last_balance_silver=state.last_balance_silver,
            last_balance_amount=state.last_balance_amount,
        )
        self._view.apply_totals(totals)
        return totals

    def load_estimate(self, voucher_no: str) -> Optional[LoadedEstimate]:
        """Retrieve an estimate and convert it into presenter-friendly objects."""
        data = self._repository.load_estimate(voucher_no)
        if not data:
            return None

        header = data.get("header") or {}
        raw_items = data.get("items") or []
        items: list[SaveItem] = []
        for idx, raw in enumerate(raw_items, start=1):
            try:
                items.append(
                    SaveItem(
                        code=str(raw.get("item_code", "") or "").strip(),
                        row_number=int(raw.get("id", idx) or idx),
                        name=str(raw.get("item_name", "") or ""),
                        gross=float(raw.get("gross", 0.0) or 0.0),
                        poly=float(raw.get("poly", 0.0) or 0.0),
                        net_wt=float(raw.get("net_wt", 0.0) or 0.0),
                        purity=float(raw.get("purity", 0.0) or 0.0),
                        wage_rate=float(raw.get("wage_rate", 0.0) or 0.0),
                        pieces=int(raw.get("pieces", 1) or 0),
                        wage=float(raw.get("wage", 0.0) or 0.0),
                        fine=float(raw.get("fine", 0.0) or 0.0),
                        is_return=bool(raw.get("is_return", 0)),
                        is_silver_bar=bool(raw.get("is_silver_bar", 0)),
                    )
                )
            except Exception:
                continue

        return LoadedEstimate(
            voucher_no=str(header.get("voucher_no", voucher_no) or voucher_no),
            date=str(header.get("date", "") or ""),
            silver_rate=float(header.get("silver_rate", 0.0) or 0.0),
            note=str(header.get("note", "") or ""),
            last_balance_silver=float(header.get("last_balance_silver", 0.0) or 0.0),
            last_balance_amount=float(header.get("last_balance_amount", 0.0) or 0.0),
            items=tuple(items),
        )

    def open_history(self) -> None:
        """Let the user pick a historic estimate and load it into the view."""
        try:
            voucher = self._view.open_history_dialog()
        except Exception as exc:
            self._view.show_status(f"History Error: {exc}", 5000)
            return
        if not voucher:
            self._view.show_status("No estimate selected from history.", 2000)
            return

        try:
            loaded = self.load_estimate(voucher)
        except Exception as exc:
            self._view.show_status(f"Error loading estimate {voucher}: {exc}", 5000)
            return
        if loaded is None:
            self._view.show_status(f"Estimate {voucher} not found.", 4000)
            return

        success = self._view.apply_loaded_estimate(loaded)
        if success:
            self._view.show_status(f"Loaded estimate {voucher} from history.", 3000)
        else:
            self._view.show_status(f"Estimate {voucher} could not be loaded.", 4000)

    def handle_item_code(self, row_index: int, code: str) -> bool:
        """Resolve an item code for the specified row, populating the view."""
        normalized = (code or "").strip().upper()
        if not normalized:
            self._view.show_status("Enter item code first", 1500)
            return False

        item = self._repository.fetch_item(normalized)
        if item:
            self._view.populate_row(row_index, item)
            self._view.focus_after_item_lookup(row_index)
            self._view.show_status(f"Item '{normalized}' loaded.", 2000)
            return True

        selected = self._view.prompt_item_selection(normalized)
        if selected:
            self._view.populate_row(row_index, selected)
            self._view.focus_after_item_lookup(row_index)
            chosen_code = selected.get("code", normalized)
            self._view.show_status(f"Item '{chosen_code}' selected.", 2000)
            return True

        self._view.show_status(f"Item '{normalized}' not found.", 2000)
        return False

    def save_estimate(self, payload: SavePayload) -> SaveOutcome:
        """Persist the estimate and synchronize related silver bar metadata."""
        try:
            exists = self._repository.estimate_exists(payload.voucher_no)
            if exists:
                self._repository.notify_silver_bars_for_estimate(payload.voucher_no)

            regular_dicts = [self._item_to_dict(item) for item in payload.regular_items]
            return_dicts = [self._item_to_dict(item) for item in payload.return_items]
            success = self._repository.save_estimate(
                payload.voucher_no,
                payload.date,
                payload.silver_rate,
                regular_dicts,
                return_dicts,
                payload.totals,
            )
            if not success:
                detail = self._repository.last_error()
                return SaveOutcome(
                    success=False,
                    message=f"Failed to save estimate '{payload.voucher_no}'.",
                    error_detail=detail,
                )

            bars_added = 0
            bars_failed = 0

            existing_bars = list(
                self._repository.fetch_silver_bars_for_estimate(payload.voucher_no)
            )
            current_bar_items = [
                item for item in payload.items if item.is_silver_bar and not item.is_return
            ]

            for existing, current in zip(existing_bars, current_bar_items):
                new_w = current.net_wt or 0.0
                new_p = current.purity or 0.0
                if (
                    abs(new_w - float(existing.get("weight", 0.0))) > 1e-6
                    or abs(new_p - float(existing.get("purity", 0.0))) > 1e-6
                ):
                    if not self._repository.update_silver_bar(existing["bar_id"], new_w, new_p):
                        bars_failed += 1

            existing_count = len(existing_bars)
            desired_count = len(current_bar_items)
            if existing_count < desired_count:
                for item in current_bar_items[existing_count:]:
                    bar_id = self._repository.add_silver_bar(
                        payload.voucher_no, item.net_wt, item.purity
                    )
                    if bar_id is not None:
                        bars_added += 1
                    else:
                        bars_failed += 1

            message_parts = [f"Estimate '{payload.voucher_no}' saved successfully."]
            if bars_added:
                message_parts.append(f"{bars_added} silver bar(s) created.")
            if bars_failed:
                message_parts.append(f"{bars_failed} bar update(s) failed.")
            message = " ".join(message_parts)

            return SaveOutcome(
                success=True,
                message=message,
                bars_added=bars_added,
                bars_failed=bars_failed,
            )
        except Exception as exc:
            return SaveOutcome(
                success=False,
                message=f"Unexpected error saving estimate '{payload.voucher_no}'.",
                error_detail=str(exc),
            )

    @staticmethod
    def _item_to_dict(item: SaveItem) -> Dict[str, object]:
        """Convert a SaveItem into repository-friendly mapping."""
        return {
            "code": item.code,
            "name": item.name,
            "gross": float(item.gross),
            "poly": float(item.poly),
            "net_wt": float(item.net_wt),
            "purity": float(item.purity),
            "wage_rate": float(item.wage_rate),
            "pieces": int(item.pieces),
            "wage": float(item.wage),
            "fine": float(item.fine),
            "is_return": bool(item.is_return),
            "is_silver_bar": bool(item.is_silver_bar),
        }

    def delete_estimate(self, voucher_no: str) -> bool:
        """Delete an estimate by voucher number."""
        return self._repository.delete_estimate(voucher_no)

    def open_silver_bar_management(self) -> None:
        """Trigger the silver bar management workflow."""
        try:
            self._view.show_silver_bar_management()
        except Exception as exc:
            self._view.show_status(f"Error opening Silver Bar Management: {exc}", 5000)
