import json

import pytest

from silverestimate.services.item_catalog_transfer import (
    ITEM_CATALOG_FORMAT,
    ITEM_CATALOG_VERSION,
    ItemCatalogTransferError,
    ensure_catalog_file_suffix,
    export_item_catalog,
    export_item_catalog_rows,
    import_item_catalog,
    load_item_catalog_file,
)


class _DbStub:
    def __init__(self, rows=None, summary=None):
        self._rows = list(rows or [])
        self._summary = (
            summary
            if summary is not None
            else {"inserted": 0, "updated": 0, "total": 0}
        )
        self.imported_items = None
        self.replace_existing = None

    def get_all_items(self):
        return list(self._rows)

    def upsert_item_catalog(self, items, *, replace_existing=False):
        self.imported_items = list(items)
        self.replace_existing = replace_existing
        return dict(self._summary)


def test_export_item_catalog_writes_native_backup_file(tmp_path):
    db = _DbStub(
        rows=[
            {
                "code": "it001",
                "name": "Sample",
                "purity": 92.5,
                "wage_type": "P",
                "wage_rate": 10.0,
            }
        ]
    )
    path = tmp_path / "catalog.seitems.json"

    count = export_item_catalog(db, str(path))

    assert count == 1
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["format"] == ITEM_CATALOG_FORMAT
    assert payload["version"] == ITEM_CATALOG_VERSION
    assert payload["items"] == [
        {
            "code": "IT001",
            "name": "Sample",
            "purity": 92.5,
            "wage_type": "PC",
            "wage_rate": 10.0,
        }
    ]


def test_export_item_catalog_rows_supports_empty_catalog(tmp_path):
    path = tmp_path / "empty.seitems.json"

    count = export_item_catalog_rows([], str(path))

    assert count == 0
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["items"] == []


def test_import_item_catalog_validates_and_normalizes_records(tmp_path):
    db = _DbStub(summary={"inserted": 1, "updated": 1, "deleted": 0, "total": 2})
    path = tmp_path / "catalog.seitems.json"
    path.write_text(
        json.dumps(
            {
                "format": ITEM_CATALOG_FORMAT,
                "version": ITEM_CATALOG_VERSION,
                "items": [
                    {
                        "code": "it001",
                        "name": "Updated",
                        "purity": 91.5,
                        "wage_type": "P",
                        "wage_rate": 9.0,
                    },
                    {
                        "code": "NEW002",
                        "name": "New",
                        "purity": 80.0,
                        "wage_type": "WT",
                        "wage_rate": 4.5,
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    summary = import_item_catalog(db, str(path), replace_existing=True)

    assert summary == {"inserted": 1, "updated": 1, "deleted": 0, "total": 2}
    assert db.replace_existing is True
    assert db.imported_items == [
        {
            "code": "IT001",
            "name": "Updated",
            "purity": 91.5,
            "wage_type": "PC",
            "wage_rate": 9.0,
        },
        {
            "code": "NEW002",
            "name": "New",
            "purity": 80.0,
            "wage_type": "WT",
            "wage_rate": 4.5,
        },
    ]


def test_import_item_catalog_rejects_duplicate_codes_in_file(tmp_path):
    db = _DbStub()
    path = tmp_path / "catalog.seitems.json"
    path.write_text(
        json.dumps(
            {
                "format": ITEM_CATALOG_FORMAT,
                "version": ITEM_CATALOG_VERSION,
                "items": [
                    {
                        "code": "IT001",
                        "name": "One",
                        "purity": 92.5,
                        "wage_type": "WT",
                        "wage_rate": 10.0,
                    },
                    {
                        "code": "it001",
                        "name": "Two",
                        "purity": 92.5,
                        "wage_type": "WT",
                        "wage_rate": 10.0,
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ItemCatalogTransferError, match="duplicate item code"):
        import_item_catalog(db, str(path))


def test_load_item_catalog_file_rejects_wrong_format(tmp_path):
    path = tmp_path / "catalog.seitems.json"
    path.write_text(
        json.dumps(
            {"format": "wrong.format", "version": ITEM_CATALOG_VERSION, "items": []}
        ),
        encoding="utf-8",
    )

    with pytest.raises(
        ItemCatalogTransferError, match="Unsupported catalog file format"
    ):
        load_item_catalog_file(str(path))


def test_load_item_catalog_file_rejects_wrong_version(tmp_path):
    path = tmp_path / "catalog.seitems.json"
    path.write_text(
        json.dumps({"format": ITEM_CATALOG_FORMAT, "version": 99, "items": []}),
        encoding="utf-8",
    )

    with pytest.raises(
        ItemCatalogTransferError, match="Unsupported catalog file version"
    ):
        load_item_catalog_file(str(path))


def test_load_item_catalog_file_rejects_malformed_json(tmp_path):
    path = tmp_path / "catalog.seitems.json"
    path.write_text("{not-json", encoding="utf-8")

    with pytest.raises(ItemCatalogTransferError, match="not valid JSON"):
        load_item_catalog_file(str(path))


def test_load_item_catalog_file_rejects_invalid_domain_data(tmp_path):
    path = tmp_path / "catalog.seitems.json"
    path.write_text(
        json.dumps(
            {
                "format": ITEM_CATALOG_FORMAT,
                "version": ITEM_CATALOG_VERSION,
                "items": [
                    {
                        "code": "BAD001",
                        "name": "Bad",
                        "purity": 101.0,
                        "wage_type": "WT",
                        "wage_rate": 10.0,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ItemCatalogTransferError, match="Invalid catalog item 1"):
        load_item_catalog_file(str(path))


def test_load_item_catalog_file_rejects_missing_file(tmp_path):
    missing_path = tmp_path / "missing.seitems.json"

    with pytest.raises(ItemCatalogTransferError, match="Catalog file not found"):
        load_item_catalog_file(str(missing_path))


def test_ensure_catalog_file_suffix_appends_native_suffix_for_plain_json_name():
    assert ensure_catalog_file_suffix("backup.json") == "backup.json.seitems.json"


def test_ensure_catalog_file_suffix_preserves_native_suffix():
    assert ensure_catalog_file_suffix("backup.seitems.json") == "backup.seitems.json"
