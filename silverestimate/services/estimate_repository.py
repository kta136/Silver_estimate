"""Repository abstraction for estimate UI logic."""

from __future__ import annotations

from collections.abc import Mapping as MappingABC
from typing import Any, Iterable, Mapping, Optional, Protocol

from silverestimate.domain.estimate_save import EstimateSaveResult
from silverestimate.persistence.database_protocols import EstimateDataSource

EstimateRow = Mapping[str, Any]


EstimateRepositoryDatabase = EstimateDataSource


class EstimateRepository(Protocol):
    """Interface exposing persistence operations required by the estimate UI."""

    def fetch_item(self, code: str) -> Optional[EstimateRow]: ...

    def fetch_items_by_codes(
        self, codes: Iterable[str]
    ) -> Mapping[str, EstimateRow]: ...

    def generate_voucher_no(self) -> str: ...

    def load_estimate(self, voucher_no: str) -> Optional[EstimateRow]: ...

    def save_estimate(
        self,
        voucher_no: str,
        date: str,
        silver_rate: float,
        regular_items: Iterable[EstimateRow],
        return_items: Iterable[EstimateRow],
        totals: Mapping[str, Any],
    ) -> EstimateSaveResult: ...

    def last_error(self) -> Optional[str]: ...

    def delete_estimate(self, voucher_no: str) -> bool: ...


class DatabaseEstimateRepository:
    """Adapter that wraps the existing database manager API."""

    def __init__(self, db_manager: EstimateRepositoryDatabase) -> None:
        self._db = db_manager

    def fetch_item(self, code: str) -> Optional[EstimateRow]:
        try:
            return self._db.get_item_by_code(code)
        except Exception:
            return None

    def fetch_items_by_codes(self, codes: Iterable[str]) -> Mapping[str, EstimateRow]:
        try:
            rows = self._db.get_items_by_codes(codes)
        except Exception:
            return {}
        return rows if isinstance(rows, MappingABC) else {}

    def generate_voucher_no(self) -> str:
        return self._db.generate_voucher_no()

    def load_estimate(self, voucher_no: str) -> Optional[EstimateRow]:
        return self._db.get_estimate_by_voucher(voucher_no)

    def save_estimate(
        self,
        voucher_no: str,
        date: str,
        silver_rate: float,
        regular_items: Iterable[EstimateRow],
        return_items: Iterable[EstimateRow],
        totals: Mapping[str, Any],
    ) -> EstimateSaveResult:
        return self._db.save_estimate_atomic(
            voucher_no,
            date,
            silver_rate,
            list(regular_items or []),
            list(return_items or []),
            dict(totals or {}),
        )

    def last_error(self) -> Optional[str]:
        return getattr(self._db, "last_error", None)

    def delete_estimate(self, voucher_no: str) -> bool:
        try:
            return bool(self._db.delete_single_estimate(voucher_no))
        except Exception:
            return False
