"""Item repository handling CRUD operations for the items table."""

from __future__ import annotations

import logging
import sqlite3
from typing import Any, Iterable, Optional

from silverestimate.domain.item_validation import ItemValidationError, validate_item

ITEM_CATALOG_COLUMNS = "code, name, purity, wage_type, wage_rate"


def fetch_item_catalog_rows(
    cursor: sqlite3.Cursor,
    search_term: str,
) -> list[sqlite3.Row]:
    """Return item-master rows while preserving current search semantics."""
    term = (search_term or "").strip()
    if not term:
        cursor.execute(
            f"SELECT {ITEM_CATALOG_COLUMNS} FROM items ORDER BY code COLLATE NOCASE"
        )
        return cursor.fetchall()

    prefix_pattern = f"{term}%"
    cursor.execute(
        f"""
        SELECT {ITEM_CATALOG_COLUMNS} FROM items WHERE code LIKE ? COLLATE NOCASE
        UNION ALL
        SELECT {ITEM_CATALOG_COLUMNS} FROM items
        WHERE name LIKE ? COLLATE NOCASE
          AND code NOT LIKE ? COLLATE NOCASE
        ORDER BY code COLLATE NOCASE
        """,
        (prefix_pattern, prefix_pattern, prefix_pattern),
    )
    prefix_rows = cursor.fetchall()
    if prefix_rows:
        return prefix_rows

    if len(term) < 2:
        return []

    pattern = f"%{term}%"
    cursor.execute(
        f"""
        SELECT {ITEM_CATALOG_COLUMNS} FROM items WHERE code LIKE ? COLLATE NOCASE
        UNION ALL
        SELECT {ITEM_CATALOG_COLUMNS} FROM items
        WHERE name LIKE ? COLLATE NOCASE
          AND code NOT LIKE ? COLLATE NOCASE
        ORDER BY code COLLATE NOCASE
        """,
        (pattern, pattern, pattern),
    )
    return cursor.fetchall()


class ItemsRepository:
    """Encapsulate item-related database operations."""

    def __init__(self, db_manager: Any) -> None:
        self._db = db_manager
        self._logger = getattr(db_manager, "logger", logging.getLogger(__name__))
        self._fallback_cache: dict[str, dict[str, Any]] = {}

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
            if normalized is None:
                return None
            if cache_ctrl:
                cache_ctrl.store(code, normalized)
            else:
                self._fallback_cache[key] = normalized
            return normalized
        except sqlite3.Error as exc:
            self._logger.error("DB Error get_item_by_code: %s", exc, exc_info=True)
            return None

    def search_items(self, search_term: str) -> list[sqlite3.Row]:
        cursor = self._cursor
        if not cursor:
            return []
        try:
            return fetch_item_catalog_rows(cursor, search_term)
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

    def get_all_items(self) -> list[sqlite3.Row]:
        cursor = self._cursor
        if not cursor:
            return []
        try:
            return fetch_item_catalog_rows(cursor, "")
        except sqlite3.Error as exc:
            self._logger.error("DB Error get_all_items: %s", exc, exc_info=True)
            return []

    def get_items_by_codes(self, codes: Iterable[str]) -> dict[str, dict[str, Any]]:
        cursor = self._cursor
        if not cursor:
            return {}

        normalized_codes = list(
            dict.fromkeys(
                code
                for code in (
                    str(raw_code or "").strip().upper() for raw_code in (codes or [])
                )
                if code
            )
        )
        if not normalized_codes:
            return {}

        rows_by_code: dict[str, dict[str, Any]] = {}
        chunk_size = 900
        for start in range(0, len(normalized_codes), chunk_size):
            chunk = normalized_codes[start : start + chunk_size]
            placeholders = ",".join("?" for _ in chunk)
            try:
                cursor.execute(
                    f"SELECT {ITEM_CATALOG_COLUMNS} FROM items WHERE UPPER(code) IN ({placeholders})",  # nosec B608
                    chunk,
                )
                for row in cursor.fetchall():
                    normalized = self._normalize_row(row)
                    if normalized is None:
                        continue
                    code = str(normalized.get("code", "") or "").strip().upper()
                    if not code:
                        continue
                    rows_by_code[code] = normalized
            except sqlite3.Error as exc:
                self._logger.error(
                    "DB Error get_items_by_codes: %s", exc, exc_info=True
                )
                return {}

        cache_ctrl = self._cache_controller
        if cache_ctrl:
            for code, row in rows_by_code.items():
                cache_ctrl.store(code, row)
        else:
            self._fallback_cache.update(rows_by_code)
        return rows_by_code

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

    def upsert_item_catalog(
        self,
        items: Iterable[dict[str, Any]],
        *,
        replace_existing: bool = False,
    ) -> Optional[dict[str, int]]:
        """Synchronize item catalog rows in one transaction."""
        conn, cursor = self._conn, self._cursor
        if not conn or not cursor:
            return None

        normalized_items = []
        seen_codes: set[str] = set()
        try:
            for raw_item in items or []:
                payload = raw_item if isinstance(raw_item, dict) else dict(raw_item)
                validated = validate_item(
                    code=str(payload.get("code", "") or ""),
                    name=str(payload.get("name", "") or ""),
                    purity=float(payload.get("purity", 0.0)),
                    wage_type=str(payload.get("wage_type", "") or ""),
                    wage_rate=float(payload.get("wage_rate", 0.0)),
                )
                if validated.code in seen_codes:
                    self._logger.warning(
                        "Rejected item catalog payload with duplicate code %s",
                        validated.code,
                    )
                    return None
                seen_codes.add(validated.code)
                normalized_items.append(validated)
        except (ItemValidationError, TypeError, ValueError) as exc:
            self._logger.warning("Rejected invalid item catalog payload: %s", exc)
            return None

        existing_codes = self._load_all_item_codes()
        inserted = 0
        updated = 0
        deleted = 0
        try:
            conn.execute("BEGIN")
            for item in normalized_items:
                if item.code in existing_codes:
                    cursor.execute(
                        "UPDATE items SET name = ?, purity = ?, wage_type = ?, wage_rate = ? WHERE code = ?",
                        (
                            item.name,
                            item.purity,
                            item.wage_type,
                            item.wage_rate,
                            item.code,
                        ),
                    )
                    updated += 1
                    continue

                cursor.execute(
                    "INSERT INTO items (code, name, purity, wage_type, wage_rate) VALUES (?, ?, ?, ?, ?)",
                    (
                        item.code,
                        item.name,
                        item.purity,
                        item.wage_type,
                        item.wage_rate,
                    ),
                )
                existing_codes.add(item.code)
                inserted += 1

            if replace_existing:
                obsolete_codes = existing_codes - seen_codes
                deleted = self._delete_codes(cursor, obsolete_codes)

            conn.commit()
        except sqlite3.Error as exc:
            self._logger.error("DB Error upserting item catalog: %s", exc, exc_info=True)
            conn.rollback()
            return None

        self._request_flush()
        for code in seen_codes:
            self._invalidate_cache(code)
        if replace_existing:
            for code in existing_codes - seen_codes:
                self._invalidate_cache(code)
        return {
            "inserted": inserted,
            "updated": updated,
            "deleted": deleted,
            "total": len(normalized_items),
        }

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
        except Exception as exc:
            self._logger.debug("Failed to invalidate item cache for %s: %s", code, exc)

    @staticmethod
    def _normalize_row(row: Any) -> Optional[dict[str, Any]]:
        if row is None:
            return None
        if isinstance(row, dict):
            return row
        try:
            return dict(row)
        except Exception:
            return None

    def _load_all_item_codes(self) -> set[str]:
        cursor = self._cursor
        if not cursor:
            return set()
        try:
            cursor.execute("SELECT code FROM items")
            return {
                str(row[0] or "").strip().upper()
                for row in cursor.fetchall()
                if row and str(row[0] or "").strip()
            }
        except sqlite3.Error as exc:
            self._logger.error("DB Error loading item codes: %s", exc, exc_info=True)
            return set()

    def _delete_codes(self, cursor: sqlite3.Cursor, codes: set[str]) -> int:
        if not codes:
            return 0

        deleted = 0
        chunk = 900
        normalized_codes = sorted(codes)
        for start in range(0, len(normalized_codes), chunk):
            code_chunk = normalized_codes[start : start + chunk]
            placeholders = ",".join("?" for _ in code_chunk)
            cursor.execute(
                f"DELETE FROM items WHERE UPPER(code) IN ({placeholders})",  # nosec B608
                code_chunk,
            )
            deleted += max(cursor.rowcount, 0)
        return deleted
