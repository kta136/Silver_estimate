"""Item repository handling CRUD operations for the items table."""

from __future__ import annotations

import logging
import sqlite3
from typing import Any, Optional

from silverestimate.domain.item_validation import ItemValidationError, validate_item


class ItemsRepository:
    """Encapsulate item-related database operations."""

    def __init__(self, db_manager: Any) -> None:
        self._db = db_manager
        self._logger = getattr(db_manager, "logger", logging.getLogger(__name__))
        self._fallback_cache = {}

    @property
    def _conn(self) -> Optional[sqlite3.Connection]:
        return getattr(self._db, "conn", None)

    @property
    def _cache_controller(self) -> Optional[Any]:
        return getattr(self._db, "item_cache_controller", None)

    @property
    def _cursor(self) -> Optional[sqlite3.Cursor]:
        return getattr(self._db, "cursor", None)

    def get_item_by_code(self, code: str) -> Optional[dict[str, Any]]:
        cursor = self._cursor
        if not cursor:
            return None
        try:
            key = (code or "").upper()
            cache_ctrl = self._cache_controller
            if cache_ctrl:
                cached = cache_ctrl.get(code)
                if cached is not None:
                    return self._normalize_row(cached)
            else:
                cached = self._fallback_cache.get(key)
                if cached is not None:
                    return self._normalize_row(cached)

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
                cursor.execute(
                    "SELECT * FROM items WHERE code = ? COLLATE NOCASE", (code,)
                )
                row = cursor.fetchone()
            if row is None:
                return None

            normalized = self._normalize_row(row)
            if cache_ctrl:
                cache_ctrl.store(code, normalized)
            else:
                self._fallback_cache[key] = normalized
            return normalized
        except sqlite3.Error as exc:
            self._logger.error("DB Error get_item_by_code: %s", exc, exc_info=True)
            return None

    def search_items(self, search_term: str) -> list[dict[str, Any]]:
        cursor = self._cursor
        if not cursor:
            return []
        try:
            term = (search_term or "").strip()
            if not term:
                cursor.execute("SELECT * FROM items ORDER BY code")
                return cursor.fetchall()

            # Prefix paths can leverage dedicated NOCASE indexes.
            prefix_pattern = f"{term}%"
            cursor.execute(
                """
                SELECT * FROM items WHERE code LIKE ? COLLATE NOCASE
                UNION ALL
                SELECT * FROM items
                WHERE name LIKE ? COLLATE NOCASE
                  AND code NOT LIKE ? COLLATE NOCASE
                ORDER BY code COLLATE NOCASE
                """,
                (prefix_pattern, prefix_pattern, prefix_pattern),
            )
            prefix_rows = cursor.fetchall()
            if prefix_rows:
                return prefix_rows

            # Fallback: substring search for broader matching on longer queries.
            if len(term) < 2:
                return []

            pattern = f"%{term}%"
            cursor.execute(
                """
                SELECT * FROM items WHERE code LIKE ? COLLATE NOCASE
                UNION ALL
                SELECT * FROM items
                WHERE name LIKE ? COLLATE NOCASE
                  AND code NOT LIKE ? COLLATE NOCASE
                ORDER BY code COLLATE NOCASE
                """,
                (pattern, pattern, pattern),
            )
            return cursor.fetchall()
        except sqlite3.Error as exc:
            self._logger.error("DB Error search_items: %s", exc, exc_info=True)
            return []

    def search_items_for_selection(
        self, search_term: str, *, limit: int = 500
    ) -> tuple[list[dict[str, Any]], bool]:
        """Return ranked item matches for item-selection dialogs.

        Results are capped to ``limit`` rows and ordered to prioritize:
        1) code prefix matches, 2) name prefix matches,
        3) code contains matches, 4) name contains matches.
        """
        cursor = self._cursor
        if not cursor:
            return [], False

        try:
            limit_i = int(limit)
        except (TypeError, ValueError):
            limit_i = 500
        if limit_i < 1:
            limit_i = 1
        if limit_i > 5000:
            limit_i = 5000
        fetch_size = limit_i + 1

        term = (search_term or "").strip()
        try:
            if not term:
                cursor.execute(
                    "SELECT code, name, purity, wage_type, wage_rate "
                    "FROM items ORDER BY code COLLATE NOCASE LIMIT ?",
                    (fetch_size,),
                )
                rows = cursor.fetchall()
            else:
                prefix = f"{term}%"
                contains = f"%{term}%"
                cursor.execute(
                    """
                    SELECT code, name, purity, wage_type, wage_rate
                    FROM items
                    WHERE code LIKE ? COLLATE NOCASE OR name LIKE ? COLLATE NOCASE
                    ORDER BY
                        CASE
                            WHEN code LIKE ? COLLATE NOCASE THEN 0
                            WHEN name LIKE ? COLLATE NOCASE THEN 1
                            WHEN code LIKE ? COLLATE NOCASE THEN 2
                            WHEN name LIKE ? COLLATE NOCASE THEN 3
                            ELSE 4
                        END,
                        code COLLATE NOCASE
                    LIMIT ?
                    """,
                    (
                        contains,
                        contains,
                        prefix,
                        prefix,
                        contains,
                        contains,
                        fetch_size,
                    ),
                )
                rows = cursor.fetchall()
        except sqlite3.Error as exc:
            self._logger.error(
                "DB Error search_items_for_selection: %s", exc, exc_info=True
            )
            return [], False

        truncated = len(rows) > limit_i
        if truncated:
            rows = rows[:limit_i]
        return list(rows), truncated

    def get_all_items(self) -> list[tuple[Any, ...]]:
        cursor = self._cursor
        if not cursor:
            return []
        try:
            cursor.execute("SELECT * FROM items ORDER BY code")
            return cursor.fetchall()
        except sqlite3.Error as exc:
            self._logger.error("DB Error get_all_items: %s", exc, exc_info=True)
            return []

    def add_item(
        self, code: str, name: str, purity: float, wage_type: str, wage_rate: float
    ) -> bool:
        conn, cursor = self._conn, self._cursor
        if not conn or not cursor:
            return False
        try:
            validated = validate_item(
                code=code,
                name=name,
                purity=purity,
                wage_type=wage_type,
                wage_rate=wage_rate,
            )
            cursor.execute(
                "INSERT INTO items (code, name, purity, wage_type, wage_rate) VALUES (?, ?, ?, ?, ?)",
                (
                    validated.code,
                    validated.name,
                    validated.purity,
                    validated.wage_type,
                    validated.wage_rate,
                ),
            )
            conn.commit()
            self._request_flush()
            self._invalidate_cache(validated.code)
            return True
        except ItemValidationError as exc:
            self._logger.warning("Rejected invalid item payload: %s", exc)
            return False
        except sqlite3.Error as exc:
            self._logger.error("DB Error adding item: %s", exc, exc_info=True)
            conn.rollback()
            return False

    def update_item(
        self, code: str, name: str, purity: float, wage_type: str, wage_rate: float
    ) -> bool:
        conn, cursor = self._conn, self._cursor
        if not conn or not cursor:
            return False
        try:
            validated = validate_item(
                code=code,
                name=name,
                purity=purity,
                wage_type=wage_type,
                wage_rate=wage_rate,
            )
            cursor.execute(
                "UPDATE items SET name = ?, purity = ?, wage_type = ?, wage_rate = ? WHERE code = ?",
                (
                    validated.name,
                    validated.purity,
                    validated.wage_type,
                    validated.wage_rate,
                    validated.code,
                ),
            )
            conn.commit()
            if cursor.rowcount > 0:
                self._request_flush()
                self._invalidate_cache(validated.code)
                return True
            return False
        except ItemValidationError as exc:
            self._logger.warning("Rejected invalid item update: %s", exc)
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
            cursor.execute("DELETE FROM items WHERE code = ?", (code,))
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
            self._logger.error(
                "Exception during post-item flush: %s", exc, exc_info=True
            )

    def _invalidate_cache(self, code: str) -> None:
        try:
            cache_ctrl = self._cache_controller
            if cache_ctrl:
                cache_ctrl.invalidate(code)
            else:
                self._fallback_cache.pop((code or "").upper(), None)
        except Exception:
            pass

    @staticmethod
    def _normalize_row(row: Any) -> Optional[dict[str, Any]]:
        if row is None:
            return None
        if isinstance(row, dict):
            return row
        try:
            return dict(row)
        except Exception:
            return row
