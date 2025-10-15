"""Repository abstraction for estimate UI logic."""
from __future__ import annotations

from typing import Any, Iterable, Mapping, Optional, Protocol, Sequence


class EstimateRepository(Protocol):
    """Interface exposing persistence operations required by the estimate UI."""

    def fetch_item(self, code: str) -> Optional[Mapping[str, Any]]:
        ...

    def generate_voucher_no(self) -> str:
        ...

    def load_estimate(self, voucher_no: str) -> Optional[Mapping[str, Any]]:
        ...

    def estimate_exists(self, voucher_no: str) -> bool:
        ...

    def save_estimate(
        self,
        voucher_no: str,
        date: str,
        silver_rate: float,
        regular_items: Iterable[Mapping[str, Any]],
        return_items: Iterable[Mapping[str, Any]],
        totals: Mapping[str, Any],
    ) -> bool:
        ...

    def notify_silver_bars_for_estimate(self, voucher_no: str) -> None:
        ...

    def fetch_silver_bars_for_estimate(self, voucher_no: str) -> Sequence[Mapping[str, Any]]:
        ...

    def count_silver_bars_for_estimate(self, voucher_no: str) -> int:
        ...

    def update_silver_bar(self, bar_id: int, weight: float, purity: float) -> bool:
        ...

    def add_silver_bar(self, voucher_no: str, weight: float, purity: float) -> Optional[int]:
        ...

    def last_error(self) -> Optional[str]:
        ...

    def delete_estimate(self, voucher_no: str) -> bool:
        ...


class DatabaseEstimateRepository:
    """Adapter that wraps the existing database manager API."""

    def __init__(self, db_manager: Any) -> None:
        self._db = db_manager

    def fetch_item(self, code: str) -> Optional[Mapping[str, Any]]:
        try:
            return self._db.get_item_by_code(code)
        except Exception:
            return None

    def generate_voucher_no(self) -> str:
        return self._db.generate_voucher_no()

    def load_estimate(self, voucher_no: str) -> Optional[Mapping[str, Any]]:
        return self._db.get_estimate_by_voucher(voucher_no)

    def estimate_exists(self, voucher_no: str) -> bool:
        return bool(self.load_estimate(voucher_no))

    def save_estimate(
        self,
        voucher_no: str,
        date: str,
        silver_rate: float,
        regular_items: Iterable[Mapping[str, Any]],
        return_items: Iterable[Mapping[str, Any]],
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
        try:
            self._db.delete_silver_bars_for_estimate(voucher_no)
        except AttributeError:
            # Legacy builds may not expose the helper; ignore quietly.
            pass

    def fetch_silver_bars_for_estimate(self, voucher_no: str):
        try:
            rows = self._db.get_silver_bars(estimate_voucher_no=voucher_no) or []
        except Exception:
            rows = []
        sorted_rows = sorted(rows, key=lambda row: row["bar_id"]) if rows else []
        return [dict(row) for row in sorted_rows]

    def count_silver_bars_for_estimate(self, voucher_no: str) -> int:
        bars = self.fetch_silver_bars_for_estimate(voucher_no)
        return len(bars)

    def update_silver_bar(self, bar_id: int, weight: float, purity: float) -> bool:
        try:
            return bool(self._db.update_silver_bar_values(bar_id, weight, purity))
        except Exception:
            return False

    def add_silver_bar(self, voucher_no: str, weight: float, purity: float) -> Optional[int]:
        try:
            return self._db.add_silver_bar(voucher_no, weight, purity)
        except Exception:
            return None

    def last_error(self) -> Optional[str]:
        return getattr(self._db, "last_error", None)

    def delete_estimate(self, voucher_no: str) -> bool:
        try:
            return bool(self._db.delete_single_estimate(voucher_no))
        except Exception:
            return False
