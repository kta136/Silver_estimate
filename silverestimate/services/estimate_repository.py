"""Repository abstraction for estimate UI logic."""

from __future__ import annotations

from typing import Any, Iterable, Mapping, Optional, Protocol, Sequence

EstimateRow = Mapping[str, Any]


class EstimateRepositoryDatabase(Protocol):
    """Minimal database-manager contract used by the estimate presenter."""

    last_error: str | None

    def get_item_by_code(self, code: str) -> EstimateRow | None: ...

    def generate_voucher_no(self) -> str: ...

    def get_estimate_by_voucher(self, voucher_no: str) -> EstimateRow | None: ...

    def estimate_exists(self, voucher_no: str) -> bool: ...

    def save_estimate_with_returns(
        self,
        voucher_no: str,
        date: str,
        silver_rate: float,
        regular_items: list[EstimateRow],
        return_items: list[EstimateRow],
        totals: dict[str, Any],
    ) -> bool: ...

    def delete_silver_bars_for_estimate(self, voucher_no: str) -> None: ...

    def get_silver_bars_for_estimate(
        self, voucher_no: str
    ) -> Sequence[EstimateRow] | None: ...

    def update_silver_bar_values(
        self, bar_id: int, weight: float, purity: float
    ) -> bool: ...

    def add_silver_bar(
        self, voucher_no: str, weight: float, purity: float
    ) -> int | None: ...

    def sync_silver_bars_for_estimate(
        self, voucher_no: str, bars: list[EstimateRow]
    ) -> tuple[int, int]: ...

    def delete_single_estimate(self, voucher_no: str) -> bool: ...


class EstimateRepository(Protocol):
    """Interface exposing persistence operations required by the estimate UI."""

    def fetch_item(self, code: str) -> Optional[EstimateRow]: ...

    def generate_voucher_no(self) -> str: ...

    def load_estimate(self, voucher_no: str) -> Optional[EstimateRow]: ...

    def estimate_exists(self, voucher_no: str) -> bool: ...

    def save_estimate(
        self,
        voucher_no: str,
        date: str,
        silver_rate: float,
        regular_items: Iterable[EstimateRow],
        return_items: Iterable[EstimateRow],
        totals: Mapping[str, Any],
    ) -> bool: ...

    def notify_silver_bars_for_estimate(self, voucher_no: str) -> None: ...

    def fetch_silver_bars_for_estimate(
        self, voucher_no: str
    ) -> Sequence[EstimateRow]: ...

    def count_silver_bars_for_estimate(self, voucher_no: str) -> int: ...

    def update_silver_bar(self, bar_id: int, weight: float, purity: float) -> bool: ...

    def add_silver_bar(
        self, voucher_no: str, weight: float, purity: float
    ) -> Optional[int]: ...

    def sync_silver_bars_for_estimate(
        self, voucher_no: str, bars: Iterable[EstimateRow]
    ) -> tuple[int, int]: ...

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

    def generate_voucher_no(self) -> str:
        return self._db.generate_voucher_no()

    def load_estimate(self, voucher_no: str) -> Optional[EstimateRow]:
        return self._db.get_estimate_by_voucher(voucher_no)

    def estimate_exists(self, voucher_no: str) -> bool:
        try:
            return bool(self._db.estimate_exists(voucher_no))
        except Exception:
            return False

    def save_estimate(
        self,
        voucher_no: str,
        date: str,
        silver_rate: float,
        regular_items: Iterable[EstimateRow],
        return_items: Iterable[EstimateRow],
        totals: Mapping[str, Any],
    ) -> bool:
        return bool(
            self._db.save_estimate_with_returns(
                voucher_no,
                date,
                silver_rate,
                list(regular_items or []),
                list(return_items or []),
                dict(totals or {}),
            )
        )

    def notify_silver_bars_for_estimate(self, voucher_no: str) -> None:
        self._db.delete_silver_bars_for_estimate(voucher_no)

    def fetch_silver_bars_for_estimate(self, voucher_no: str) -> Sequence[EstimateRow]:
        try:
            rows = self._db.get_silver_bars_for_estimate(voucher_no) or []
        except Exception:
            rows = []
        normalized_rows = [dict(row) for row in rows]
        sorted_rows = (
            sorted(
                normalized_rows,
                key=lambda row: int(row.get("bar_id", 0) or 0),
            )
            if normalized_rows
            else []
        )
        return sorted_rows

    def count_silver_bars_for_estimate(self, voucher_no: str) -> int:
        bars = self.fetch_silver_bars_for_estimate(voucher_no)
        return len(bars)

    def update_silver_bar(self, bar_id: int, weight: float, purity: float) -> bool:
        try:
            return bool(self._db.update_silver_bar_values(bar_id, weight, purity))
        except Exception:
            return False

    def add_silver_bar(
        self, voucher_no: str, weight: float, purity: float
    ) -> Optional[int]:
        try:
            return self._db.add_silver_bar(voucher_no, weight, purity)
        except Exception:
            return None

    def sync_silver_bars_for_estimate(
        self, voucher_no: str, bars: Iterable[EstimateRow]
    ) -> tuple[int, int]:
        bars_list = list(bars or [])
        try:
            added, failed = self._db.sync_silver_bars_for_estimate(
                voucher_no,
                bars_list,
            )
            return int(added or 0), int(failed or 0)
        except Exception:
            return 0, len(bars_list)

    def last_error(self) -> Optional[str]:
        return getattr(self._db, "last_error", None)

    def delete_estimate(self, voucher_no: str) -> bool:
        try:
            return bool(self._db.delete_single_estimate(voucher_no))
        except Exception:
            return False
