"""Native import/export helpers for item catalog backups."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from silverestimate.domain.item_validation import validate_item

ITEM_CATALOG_FORMAT = "silverestimate.item_catalog"
ITEM_CATALOG_VERSION = 1
ITEM_CATALOG_FILE_FILTER = (
    "Silver Estimate Item Catalog (*.seitems.json);;JSON Files (*.json)"
)
ITEM_CATALOG_FILE_SUFFIX = ".seitems.json"


class ItemCatalogTransferError(ValueError):
    """Raised when a catalog backup file cannot be imported or exported safely."""


def export_item_catalog(db_manager: Any, file_path: str) -> int:
    """Write the current item catalog to a native Silver Estimate backup file."""
    if not db_manager:
        raise ItemCatalogTransferError("Database connection not available.")

    raw_items = db_manager.get_all_items()
    return export_item_catalog_rows(raw_items, file_path)


def export_item_catalog_rows(raw_items: list[Any], file_path: str) -> int:
    """Write already-loaded item rows to a native Silver Estimate backup file."""
    items = [
        _normalize_item_mapping(item, context=f"catalog row {index + 1}")
        for index, item in enumerate(raw_items)
    ]
    payload = {
        "format": ITEM_CATALOG_FORMAT,
        "version": ITEM_CATALOG_VERSION,
        "exported_at": datetime.now(timezone.utc)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z"),
        "items": items,
    }

    path = Path(file_path)
    path.write_text(
        f"{json.dumps(payload, indent=2, sort_keys=True)}\n",
        encoding="utf-8",
    )
    return len(items)


def load_item_catalog_rows_from_db_path(db_path: str) -> list[dict[str, Any]]:
    """Read item rows from a temp SQLite database using a dedicated connection."""
    if not db_path:
        raise ItemCatalogTransferError("Temporary database path not available.")

    conn = None
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            "SELECT code, name, purity, wage_type, wage_rate FROM items ORDER BY code COLLATE NOCASE"
        )
        return [
            _normalize_item_mapping(row, context=f"catalog row {index + 1}")
            for index, row in enumerate(cursor.fetchall())
        ]
    except sqlite3.Error as exc:
        raise ItemCatalogTransferError(
            f"Could not read item catalog from database: {exc}"
        ) from exc
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass


def import_item_catalog(
    db_manager: Any,
    file_path: str,
    *,
    replace_existing: bool = False,
) -> dict[str, int]:
    """Load a native catalog backup file and upsert its contents atomically."""
    if not db_manager:
        raise ItemCatalogTransferError("Database connection not available.")

    items = load_item_catalog_file(file_path)
    summary = db_manager.upsert_item_catalog(items, replace_existing=replace_existing)
    if not isinstance(summary, dict):
        raise ItemCatalogTransferError("Item catalog import could not be applied.")
    return {
        "inserted": int(summary.get("inserted", 0)),
        "updated": int(summary.get("updated", 0)),
        "deleted": int(summary.get("deleted", 0)),
        "total": int(summary.get("total", len(items))),
    }


def load_item_catalog_file(file_path: str) -> list[dict[str, Any]]:
    """Parse and validate a native catalog backup file."""
    path = Path(file_path)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ItemCatalogTransferError(f"Catalog file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ItemCatalogTransferError(
            f"Catalog file is not valid JSON: line {exc.lineno} column {exc.colno}."
        ) from exc
    except OSError as exc:
        raise ItemCatalogTransferError(f"Could not read catalog file: {exc}") from exc

    if not isinstance(payload, dict):
        raise ItemCatalogTransferError("Catalog file must contain a JSON object.")
    if payload.get("format") != ITEM_CATALOG_FORMAT:
        raise ItemCatalogTransferError("Unsupported catalog file format.")
    version = payload.get("version")
    if version != ITEM_CATALOG_VERSION:
        raise ItemCatalogTransferError(
            f"Unsupported catalog file version: {version!r}."
        )

    raw_items = payload.get("items")
    if not isinstance(raw_items, list):
        raise ItemCatalogTransferError("Catalog file is missing its item list.")

    normalized_items: list[dict[str, Any]] = []
    seen_codes: set[str] = set()
    for index, raw_item in enumerate(raw_items):
        item = _normalize_item_mapping(raw_item, context=f"catalog item {index + 1}")
        code = item["code"]
        if code in seen_codes:
            raise ItemCatalogTransferError(
                f"Catalog file contains duplicate item code '{code}'."
            )
        seen_codes.add(code)
        normalized_items.append(item)
    return normalized_items


def ensure_catalog_file_suffix(file_path: str) -> str:
    """Append the native file suffix unless it is already present."""
    text = str(file_path or "").strip()
    if not text:
        return text
    lowered = text.lower()
    if lowered.endswith(ITEM_CATALOG_FILE_SUFFIX):
        return text
    return f"{text}{ITEM_CATALOG_FILE_SUFFIX}"


def _normalize_item_mapping(raw_item: Any, *, context: str) -> dict[str, Any]:
    if isinstance(raw_item, Mapping):
        data = raw_item
    else:
        try:
            data = dict(raw_item)
        except Exception as exc:
            raise ItemCatalogTransferError(
                f"{context.capitalize()} is not a valid item record."
            ) from exc

    try:
        validated = validate_item(
            code=str(data.get("code", "") or ""),
            name=str(data.get("name", "") or ""),
            purity=float(data.get("purity", 0.0)),
            wage_type=str(data.get("wage_type", "") or ""),
            wage_rate=float(data.get("wage_rate", 0.0)),
        )
    except (TypeError, ValueError) as exc:
        raise ItemCatalogTransferError(f"Invalid {context}: {exc}") from exc

    return {
        "code": validated.code,
        "name": validated.name,
        "purity": validated.purity,
        "wage_type": validated.wage_type,
        "wage_rate": validated.wage_rate,
    }
