"""Qt-free estimate data shared by entry, save/load and recovery workflows."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Mapping, Optional, Sequence

from silverestimate.domain.estimate_models import EstimateLine, EstimateLineCategory


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
    wage_type: str = "WT"
    wage_amount: float = 0.0
    fine_weight: float = 0.0
    category: EstimateLineCategory = EstimateLineCategory.REGULAR
    row_index: int = 0
    line_key: str = ""
    tunch: str | None = None
    snapshot_version: int = 0

    def __post_init__(self) -> None:
        normalized = (self.wage_type or "").strip().upper()
        object.__setattr__(self, "wage_type", "PC" if normalized == "PC" else "WT")

    def is_empty(self) -> bool:
        """Return True for empty rows, retaining persisted lines whose code was lost."""
        return not self.code.strip() and not (self.snapshot_version and self.line_key)

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


@dataclass(frozen=True)
class EstimateEntryViewState:
    """Snapshot of the data required to run presenter computations."""

    lines: Sequence[EstimateLine]
    silver_rate: float
    last_balance_silver: float = 0.0
    last_balance_amount: float = 0.0


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
    wage_type: str = "WT"
    line_key: str = ""
    tunch: str | None = None
    snapshot_version: int = 0


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
    totals: Mapping[str, object]


@dataclass(frozen=True)
class SaveOutcome:
    """Result of attempting to save an estimate."""

    success: bool
    message: str
    bars_added: int = 0
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


@dataclass(frozen=True)
class EstimateEntrySnapshot:
    """Stable save input captured at the UI boundary, without a mutable view model."""

    rows: tuple[EstimateEntryRowState, ...]
    silver_rate: float
    last_balance_silver: float = 0.0
    last_balance_amount: float = 0.0
