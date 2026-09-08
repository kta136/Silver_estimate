"""Presenter for the estimate entry experience."""

from __future__ import annotations

from typing import Dict, Mapping, Optional, Protocol, Sequence

from silverestimate.domain.estimate_entry import (
    EstimateEntryViewState as EstimateEntryViewState,
)
from silverestimate.domain.estimate_entry import (
    LoadedEstimate as LoadedEstimate,
)
from silverestimate.domain.estimate_entry import (
    SaveItem as SaveItem,
)
from silverestimate.domain.estimate_entry import (
    SaveOutcome as SaveOutcome,
)
from silverestimate.domain.estimate_entry import (
    SavePayload as SavePayload,
)
from silverestimate.domain.estimate_models import TotalsResult
from silverestimate.services.estimate_calculator import compute_totals
from silverestimate.services.estimate_repository import EstimateRepository


class EstimateEntryView(Protocol):
    """Interface implemented by the Qt widget so the presenter can talk to it."""

    def capture_state(self) -> EstimateEntryViewState:
        """Return the current state needed for calculations."""

    def apply_totals(self, totals: TotalsResult) -> None:
        """Update UI totals and related labels."""

    def set_voucher_number(self, voucher_no: str) -> None:
        """Display a voucher number in the UI."""

    def show_status(
        self, message: str, timeout: int = 3000, level: str = "info"
    ) -> None:
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
        fallback_wage_types = self._load_wage_type_fallbacks(raw_items)
        items: list[SaveItem] = []
        for idx, raw in enumerate(raw_items, start=1):
            item: SaveItem | None = None
            try:
                code = str(raw.get("item_code", "") or "").strip()
                item = SaveItem(
                    code=code,
                    row_number=int(raw.get("id", idx) or idx),
                    name=str(raw.get("item_name", "") or ""),
                    gross=float(raw.get("gross", 0.0) or 0.0),
                    poly=float(raw.get("poly", 0.0) or 0.0),
                    net_wt=float(raw.get("net_wt", 0.0) or 0.0),
                    purity=float(raw.get("purity", 0.0) or 0.0),
                    wage_rate=float(raw.get("wage_rate", 0.0) or 0.0),
                    pieces=int(raw.get("pieces", 1) or 0),
                    wage_type=self._resolve_loaded_wage_type(
                        raw,
                        fallback_wage_types.get(code.upper()),
                    ),
                    wage=float(raw.get("wage", 0.0) or 0.0),
                    fine=float(raw.get("fine", 0.0) or 0.0),
                    is_return=bool(raw.get("is_return", 0)),
                    is_silver_bar=bool(raw.get("is_silver_bar", 0)),
                    line_key=str(raw.get("line_key", "") or ""),
                    tunch=raw.get("tunch"),
                    snapshot_version=int(raw.get("snapshot_version", 0) or 0),
                )
            except AttributeError, TypeError, ValueError:
                item = None
            if item is not None:
                items.append(item)

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
            regular_dicts = [self._item_to_dict(item) for item in payload.regular_items]
            return_dicts = [self._item_to_dict(item) for item in payload.return_items]
            result = self._repository.save_estimate(
                payload.voucher_no,
                payload.date,
                payload.silver_rate,
                regular_dicts,
                return_dicts,
                payload.totals,
            )
            if not result.success:
                return SaveOutcome(
                    success=False,
                    message=f"Failed to save estimate '{payload.voucher_no}'.",
                    error_detail=result.error_detail,
                )

            message_parts = [f"Estimate '{payload.voucher_no}' saved successfully."]
            if result.bars_added:
                message_parts.append(f"{result.bars_added} silver bar(s) created.")
            if result.bars_updated:
                message_parts.append(f"{result.bars_updated} silver bar(s) updated.")
            if result.bars_removed:
                message_parts.append(
                    f"{result.bars_removed} unused silver bar(s) removed."
                )
            message = " ".join(message_parts)

            return SaveOutcome(
                success=True,
                message=message,
                bars_added=result.bars_added,
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
            "wage_type": EstimateEntryPresenter._normalize_wage_type(item.wage_type),
            "wage": float(item.wage),
            "fine": float(item.fine),
            "is_return": bool(item.is_return),
            "is_silver_bar": bool(item.is_silver_bar),
            "line_key": str(item.line_key or ""),
        }

    @staticmethod
    def _normalize_wage_type(value: object) -> str:
        return "PC" if str(value or "").strip().upper() == "PC" else "WT"

    def _load_wage_type_fallbacks(
        self, raw_items: Sequence[Mapping[str, object]]
    ) -> dict[str, str]:
        unresolved_codes = [
            code
            for raw in raw_items
            if self._raw_wage_type(raw) is None
            for code in [str(raw.get("item_code", "") or "").strip().upper()]
            if code
        ]
        if not unresolved_codes:
            return {}
        rows = self._repository.fetch_items_by_codes(unresolved_codes)
        resolved: dict[str, str] = {}
        for code, row in dict(rows or {}).items():
            normalized_code = str(code or "").strip().upper()
            if not normalized_code:
                continue
            resolved[normalized_code] = self._normalize_wage_type(
                (row or {}).get("wage_type")
            )
        return resolved

    @classmethod
    def _resolve_loaded_wage_type(
        cls,
        raw_item: Mapping[str, object],
        fallback_wage_type: Optional[str],
    ) -> str:
        raw_wage_type = cls._raw_wage_type(raw_item)
        if raw_wage_type is not None:
            return raw_wage_type
        if fallback_wage_type is not None:
            return cls._normalize_wage_type(fallback_wage_type)
        return "WT"

    @classmethod
    def _raw_wage_type(cls, raw_item: Mapping[str, object]) -> Optional[str]:
        normalized = str((raw_item or {}).get("wage_type", "") or "").strip().upper()
        if normalized in {"PC", "WT"}:
            return cls._normalize_wage_type(normalized)
        return None

    def delete_estimate(self, voucher_no: str) -> bool:
        """Delete an estimate by voucher number."""
        return self._repository.delete_estimate(voucher_no)

    def open_silver_bar_management(self) -> None:
        """Trigger the silver bar management workflow."""
        try:
            self._view.show_silver_bar_management()
        except Exception as exc:
            self._view.show_status(f"Error opening Silver Bar Management: {exc}", 5000)
