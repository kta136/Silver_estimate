"""Item repository handling CRUD operations for the items table."""
from __future__ import annotations

import logging
import sqlite3
from typing import Any


class ItemsRepository:
    """Encapsulate item-related database operations."""

    def __init__(self, db_manager: Any) -> None:
        self._db = db_manager
        self._logger = getattr(db_manager, "logger", logging.getLogger(__name__))
        self._fallback_cache = {}

    @property
    def _conn(self):
        return getattr(self._db, "conn", None)

    @property
    def _cache_controller(self):
        return getattr(self._db, "item_cache_controller", None)

    @property
    def _cursor(self):
        return getattr(self._db, "cursor", None)

    def get_item_by_code(self, code: str):
        cursor = self._cursor
        if not cursor:
            return None
        try:
            key = (code or "").upper()
            cache_ctrl = self._cache_controller
            if cache_ctrl:
                cached = cache_ctrl.get(code)
                if cached is not None:
                    return cached
            else:
                cached = self._fallback_cache.get(key)
                if cached is not None:
                    return cached

            row = None
            try:
                stmt = getattr(self._db, "_sql_get_item_by_code", None)
                prepared = getattr(self._db, "_c_get_item_by_code", None)
                if prepared and stmt:
                    prepared.execute(stmt, (code,))
                    row = prepared.fetchone()
            except Exception:
                row = None

            if row is None:
                cursor.execute('SELECT * FROM items WHERE code = ? COLLATE NOCASE', (code,))
                row = cursor.fetchone()
            if row is not None:
                if cache_ctrl:
                    cache_ctrl.store(code, row)
                else:
                    self._fallback_cache[key] = row
            return row
        except sqlite3.Error as exc:
            self._logger.error("DB Error get_item_by_code: %s", exc, exc_info=True)
            return None

    def search_items(self, search_term: str):
        cursor = self._cursor
        if not cursor:
            return []
        try:
            pattern = f"%{search_term}%"
            cursor.execute(
                'SELECT * FROM items WHERE LOWER(code) LIKE LOWER(?) OR LOWER(name) LIKE LOWER(?) ORDER BY code',
                (pattern, pattern),
            )
            return cursor.fetchall()
        except sqlite3.Error as exc:
            self._logger.error("DB Error search_items: %s", exc, exc_info=True)
            return []

    def get_all_items(self):
        cursor = self._cursor
        if not cursor:
            return []
        try:
            cursor.execute('SELECT * FROM items ORDER BY code')
            return cursor.fetchall()
        except sqlite3.Error as exc:
            self._logger.error("DB Error get_all_items: %s", exc, exc_info=True)
            return []

    def add_item(self, code: str, name: str, purity: float, wage_type: str, wage_rate: float) -> bool:
        conn, cursor = self._conn, self._cursor
        if not conn or not cursor:
            return False
        try:
            cursor.execute(
                'INSERT INTO items (code, name, purity, wage_type, wage_rate) VALUES (?, ?, ?, ?, ?)',
                (code, name, purity, wage_type, wage_rate),
            )
            conn.commit()
            self._request_flush()
            self._invalidate_cache(code)
            return True
        except sqlite3.Error as exc:
            self._logger.error("DB Error adding item: %s", exc, exc_info=True)
            conn.rollback()
            return False

    def update_item(self, code: str, name: str, purity: float, wage_type: str, wage_rate: float) -> bool:
        conn, cursor = self._conn, self._cursor
        if not conn or not cursor:
            return False
        try:
            cursor.execute(
                'UPDATE items SET name = ?, purity = ?, wage_type = ?, wage_rate = ? WHERE code = ?',
                (name, purity, wage_type, wage_rate, code),
            )
            conn.commit()
            if cursor.rowcount > 0:
                self._request_flush()
                self._invalidate_cache(code)
                return True
            return False
        except sqlite3.Error as exc:
            self._logger.error("DB Error updating item: %s", exc, exc_info=True)
            conn.rollback()
            return False

    def delete_item(self, code: str) -> bool:
        conn, cursor = self._conn, self._cursor
        if not conn or not cursor:
            return False
        try:
            cursor.execute('DELETE FROM items WHERE code = ?', (code,))
            conn.commit()
            if cursor.rowcount > 0:
                self._request_flush()
                self._invalidate_cache(code)
                return True
            return False
        except sqlite3.Error as exc:
            self._logger.error("DB Error deleting item: %s", exc, exc_info=True)
            conn.rollback()
            return False

    # --- helpers -----------------------------------------------------------------

    def _request_flush(self) -> None:
        try:
            requester = getattr(self._db, "request_flush", None)
            if callable(requester):
                requester()
        except Exception as exc:  # pragma: no cover - log only
            self._logger.error("Exception during post-item flush: %s", exc, exc_info=True)

    def _invalidate_cache(self, code: str) -> None:
        try:
            cache_ctrl = self._cache_controller
            if cache_ctrl:
                cache_ctrl.invalidate(code)
            else:
                self._fallback_cache.pop((code or "").upper(), None)
        except Exception:
            pass

