import json

import pytest

from silverestimate.services.item_catalog_transfer import (
    ITEM_CATALOG_FORMAT,
    ITEM_CATALOG_VERSION,
    ItemCatalogTransferError,
    ensure_catalog_file_suffix,
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
                "tunch": "91.25 + loss",
                "purity": 92.5,
                "wage_type": "P",
                "wage_rate": 10.0,
            }
        ]
    )
    path = tmp_path / "catalog.seitems.json"

    count = export_item_catalog_rows(db.get_all_items(), str(path))

    assert count == 1
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["format"] == ITEM_CATALOG_FORMAT
    assert payload["version"] == ITEM_CATALOG_VERSION
    assert payload["items"] == [
        {
            "code": "IT001",
            "name": "Sample",
            "tunch": "91.25 + loss",
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
                        "tunch": "Market",
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
            "tunch": "Market",
            "purity": 91.5,
            "wage_type": "PC",
            "wage_rate": 9.0,
        },
        {
            "code": "NEW002",
            "name": "New",
            "tunch": None,
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


def _catalog_json(**overrides) -> str:
    return json.dumps(
        {
            "format": ITEM_CATALOG_FORMAT,
            "version": ITEM_CATALOG_VERSION,
            "items": [],
            **overrides,
        }
    )


@pytest.mark.parametrize(
    "content, message",
    [
        pytest.param(
            _catalog_json(format="wrong.format"),
            "Unsupported catalog file format",
            id="wrong-format",
        ),
        pytest.param(
            _catalog_json(version=99),
            "Unsupported catalog file version",
            id="wrong-version",
        ),
        pytest.param("{not-json", "not valid JSON", id="malformed-json"),
        pytest.param(
            _catalog_json(
                items=[
                    {
                        "code": "BAD001",
                        "name": "Bad",
                        "purity": -0.01,
                        "wage_type": "WT",
                        "wage_rate": 10.0,
                    }
                ]
            ),
            "Invalid catalog item 1",
            id="invalid-domain-data",
        ),
        pytest.param(None, "Catalog file not found", id="missing-file"),
    ],
)
def test_load_item_catalog_file_rejects_unusable_files(tmp_path, content, message):
    path = tmp_path / "catalog.seitems.json"
    if content is not None:
        path.write_text(content, encoding="utf-8")

    with pytest.raises(ItemCatalogTransferError, match=message):
        load_item_catalog_file(str(path))


def test_load_item_catalog_file_accepts_v1_with_blank_tunch(tmp_path):
    path = tmp_path / "catalog-v1.seitems.json"
    path.write_text(
        json.dumps(
            {
                "format": ITEM_CATALOG_FORMAT,
                "version": 1,
                "items": [
                    {
                        "code": "OLD001",
                        "name": "Legacy",
                        "purity": 90.0,
                        "wage_type": "WT",
                        "wage_rate": 5.0,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    assert load_item_catalog_file(str(path)) == [
        {
            "code": "OLD001",
            "name": "Legacy",
            "tunch": None,
            "purity": 90.0,
            "wage_type": "WT",
            "wage_rate": 5.0,
        }
    ]


@pytest.mark.parametrize(
    "name, expected",
    [
        ("backup.json", "backup.json.seitems.json"),
        ("backup.seitems.json", "backup.seitems.json"),
    ],
)
def test_ensure_catalog_file_suffix_adds_the_native_suffix_once(name, expected):
    assert ensure_catalog_file_suffix(name) == expected
