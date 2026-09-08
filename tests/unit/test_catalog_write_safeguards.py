import json

import pytest

from silverestimate.domain.item_validation import ItemValidationError, validate_item
from silverestimate.services import item_catalog_transfer as catalog


def _item(**changes):
    return {
        "code": "A",
        "name": "Original",
        "purity": 92.5,
        "wage_type": "WT",
        "wage_rate": 10,
        **changes,
    }


@pytest.mark.parametrize("field", ["purity", "wage_rate"])
@pytest.mark.parametrize(
    "value", [float("nan"), float("inf"), -float("inf"), "bad", None]
)
def test_catalog_numbers_must_be_finite(field, value):
    with pytest.raises(ItemValidationError):
        validate_item(**_item(**{field: value}))


@pytest.mark.parametrize("constant", ["NaN", "Infinity", "-Infinity"])
def test_import_rejects_nonstandard_json_numbers_even_in_metadata(tmp_path, constant):
    path = tmp_path / "catalog.json"
    payload = json.dumps(
        {"format": catalog.ITEM_CATALOG_FORMAT, "version": 2, "items": [_item()]}
    )
    path.write_text(payload[:-1] + f', "unexpected": {constant}}}', encoding="utf-8")
    with pytest.raises(catalog.ItemCatalogTransferError, match="finite|JSON"):
        catalog.load_item_catalog_file(str(path))


@pytest.mark.parametrize("failure", ["write", "replace"])
def test_failed_export_keeps_previous_backup_and_removes_temporary_file(
    tmp_path, monkeypatch, failure
):
    path = tmp_path / "catalog.json"
    original = b"previous valid backup"
    path.write_bytes(original)

    def fail(*args, **kwargs):
        raise OSError("Disk write failed")

    if failure == "replace":
        monkeypatch.setattr("os.replace", fail)
    else:
        monkeypatch.setattr("os.fsync", fail)
    with pytest.raises(OSError, match="Disk write failed"):
        catalog.export_item_catalog_rows([_item()], str(path))
    assert path.read_bytes() == original
    assert list(tmp_path.iterdir()) == [path]


def test_export_replaces_previous_backup_with_valid_json(tmp_path):
    path = tmp_path / "catalog.json"
    path.write_text("previous backup", encoding="utf-8")
    assert catalog.export_item_catalog_rows([_item()], str(path)) == 1
    assert catalog.load_item_catalog_file(str(path))[0]["code"] == "A"
    assert list(tmp_path.iterdir()) == [path]


def test_import_reports_why_referenced_catalog_replacement_was_blocked(tmp_path):
    from types import SimpleNamespace

    path = tmp_path / "catalog.json"
    catalog.export_item_catalog_rows([_item()], str(path))
    db = SimpleNamespace(
        upsert_item_catalog=lambda *args, **kwargs: None,
        last_error="Cannot remove A: used by saved estimates.",
    )
    with pytest.raises(
        catalog.ItemCatalogTransferError, match="used by saved estimates"
    ):
        catalog.import_item_catalog(db, str(path), replace_existing=True)
