"""Estimate-to-inventory silver-bar synchronization component."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class SilverBarSyncResult:
    added: int
    failed: int

    @property
    def succeeded(self) -> bool:
        return self.failed == 0


class SilverBarSynchronizationRepository:
    """Own reconciliation of estimate rows with mutable inventory rows."""

    def __init__(self, backend: Any) -> None:
        self._backend = backend

    def synchronize(
        self,
        voucher_no: str,
        bars: Iterable[Mapping[str, Any]],
    ) -> SilverBarSyncResult:
        added, failed = self._backend.sync_silver_bars_for_estimate(voucher_no, bars)
        return SilverBarSyncResult(added=int(added), failed=int(failed))


__all__ = ["SilverBarSynchronizationRepository", "SilverBarSyncResult"]
