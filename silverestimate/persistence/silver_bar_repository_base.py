"""Shared database access for narrow silver-bar repositories."""

from __future__ import annotations

import logging
from typing import Iterable, List

from silverestimate.persistence.database_protocols import RepositoryDatabase


class _SilverBarRepositoryBase:
    """Provide connection access without sharing persistence operations."""

    def __init__(self, db_manager: RepositoryDatabase) -> None:
        self._db = db_manager
        self._logger = getattr(db_manager, "logger", logging.getLogger(__name__))

    @property
    def _conn(self):
        return getattr(self._db, "conn", None)

    @property
    def _cursor(self):
        return getattr(self._db, "cursor", None)

    @staticmethod
    def _normalize_bar_ids(bar_ids: Iterable[int]) -> List[int]:
        normalized: List[int] = []
        seen: set[int] = set()
        for raw_bar_id in list(bar_ids or []):
            try:
                bar_id = int(raw_bar_id)
            except TypeError, ValueError:
                continue
            if bar_id <= 0 or bar_id in seen:
                continue
            seen.add(bar_id)
            normalized.append(bar_id)
        return normalized
