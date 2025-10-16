"""Item cache utilities shared across database/persistence layers."""
from __future__ import annotations

import logging
import sqlite3
import threading
from typing import Dict, Optional


class ItemCacheController:
    """Coordinate background warming and simple invalidation for item lookups."""

    def __init__(self, logger: Optional[logging.Logger] = None) -> None:
        self._logger = logger or logging.getLogger(__name__)
        self._cache: Dict[str, object] = {}
        self._thread: Optional[threading.Thread] = None
        self._preloaded = False
        self._lock = threading.Lock()

    @property
    def cache(self) -> Dict[str, object]:
        return self._cache

    def get(self, code: str):
        if not code:
            return None
        return self._cache.get(code.upper())

    def store(self, code: str, value) -> None:
        if not code:
            return
        to_store = value
        if value is not None and not isinstance(value, dict):
            try:
                to_store = dict(value)
            except Exception:
                to_store = value
        self._cache[code.upper()] = to_store

    def invalidate(self, code: str) -> None:
        if not code:
            return
        self._cache.pop(code.upper(), None)

    def start_preload(self, db_path: Optional[str]) -> None:
        """Warm the cache using a dedicated SQLite connection in the background."""
        if not db_path:
            return
        if self._preloaded:
            return
        if self._thread and self._thread.is_alive():
            return

        def _worker() -> None:
            local_cache = {}
            conn = None
            try:
                conn = sqlite3.connect(db_path)
                conn.row_factory = sqlite3.Row
                cur = conn.cursor()
                cur.execute(
                    "SELECT code, name, purity, wage_type, wage_rate FROM items"
                )
                rows = cur.fetchall()
                for row in rows:
                    try:
                        key = (row["code"] or "").upper()
                        local_cache[key] = {
                            "code": row["code"],
                            "name": row["name"],
                            "purity": row["purity"],
                            "wage_type": row["wage_type"],
                            "wage_rate": row["wage_rate"],
                        }
                    except Exception:
                        continue
            except Exception as exc:
                try:
                    self._logger.debug("Item cache preload failed: %s", exc)
                except Exception:
                    pass
            else:
                with self._lock:
                    self._cache = local_cache
                    self._preloaded = True
                try:
                    self._logger.debug(
                        "Preloaded item cache with %s items", len(local_cache)
                    )
                except Exception:
                    pass
            finally:
                if conn is not None:
                    try:
                        conn.close()
                    except Exception:
                        pass

        thread = threading.Thread(target=_worker, name="ItemCacheWarmup", daemon=True)
        self._thread = thread
        try:
            thread.start()
        except Exception:
            self._thread = None







