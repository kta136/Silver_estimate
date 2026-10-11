"""Historical snapshots survive catalog changes, upgrades and encrypted restore."""

import pytest

from silverestimate.persistence.database_manager import DatabaseManager
from silverestimate.ui.estimate_print_document import EstimatePrintDocument
from tests.factories import estimate_totals, regular_item


def _database_state(db):
    return {
        table: [tuple(row) for row in db.conn.execute(f"SELECT * FROM {table}")]
        for table in (
            "sqlite_master",
            "schema_version",
            "items",
            "estimates",
            "estimate_items",
            "silver_bars",
            "bar_transfers",
        )
    }


@pytest.fixture
def snapshot_db(tmp_path):
    db = DatabaseManager(
        str(tmp_path / "snapshots.db"), "password", device_secret=b"S" * 32
    )
    assert db.add_item("REG001", "Catalog original", 92.5, "WT", 10, tunch="91 + loss")
    assert db.save_estimate_atomic(
        "1",
        "2026-09-05",
        75,
        [regular_item(name="Saved name", line_key="original")],
        [],
        estimate_totals(),
    ).success
    yield db
    db.close()


def saved_payload(data):
    return [
        dict(row, code=row["item_code"], name=row["item_name"]) for row in data["items"]
    ]


@pytest.mark.parametrize("replacement", [False, True])
def test_catalog_removal_preserves_saved_and_reprinted_lines(snapshot_db, replacement):
    db = snapshot_db
    before = db.get_estimate_by_voucher("1")
    document = EstimatePrintDocument.from_mapping(before)
    if replacement:
        assert db.upsert_item_catalog(
            [
                dict(
                    code="NEW",
                    name="Replacement",
                    purity=80,
                    wage_type="PC",
                    wage_rate=5,
                )
            ],
            replace_existing=True,
        )
    else:
        assert db.delete_item("REG001")
    after = db.get_estimate_by_voucher("1")
    assert after == before
    assert EstimatePrintDocument.from_mapping(after) == document
    assert db.conn.execute("SELECT item_code FROM estimate_items").fetchone()[0] is None
    assert db.save_estimate_atomic(
        "1",
        "2026-09-05",
        75,
        saved_payload(after),
        [],
        estimate_totals(note="Note changed"),
    ).success
    assert db.get_estimate_by_voucher("1")["items"][0]["tunch"] == "91 + loss"
    assert not db.save_estimate_atomic(
        "2", "2026-09-05", 75, saved_payload(after), [], estimate_totals()
    ).success
    assert db.get_estimate_by_voucher("2") is None


def test_reused_code_keeps_old_tunch_and_new_lines_capture_current_tunch(snapshot_db):
    db = snapshot_db
    old = db.get_estimate_by_voucher("1")
    assert db.delete_item("REG001")
    assert db.add_item("REG001", "Reused", 50, "PC", 20, tunch="New tunch")
    assert db.save_estimate_atomic(
        "1",
        "2026-09-05",
        75,
        saved_payload(old) + [regular_item(line_key="new")],
        [],
        estimate_totals(),
    ).success
    rows = {row["line_key"]: row for row in db.get_estimate_by_voucher("1")["items"]}
    assert rows["original"]["tunch"] == "91 + loss"
    assert rows["original"]["item_name"] == "Saved name"
    assert rows["new"]["tunch"] == "New tunch"


def test_null_tunch_is_a_snapshot_and_does_not_fall_back(snapshot_db):
    db = snapshot_db
    assert db.add_item("EMPTY", "No Tunch", 90, "WT", 10)
    assert db.save_estimate_atomic(
        "2",
        "2026-09-05",
        75,
        [regular_item(code="EMPTY", line_key="empty")],
        [],
        estimate_totals(),
    ).success
    assert db.update_item("EMPTY", "Updated", 50, "PC", 1, tunch="Added later")
    assert db.get_estimate_by_voucher("2")["items"][0]["tunch"] is None


@pytest.mark.parametrize("mutation", ["key", "code", "blank"])
def test_detached_line_exemption_cannot_be_used_for_new_or_changed_codes(
    snapshot_db, mutation
):
    db = snapshot_db
    data = db.get_estimate_by_voucher("1")
    assert db.delete_item("REG001")
    payload = saved_payload(data)
    payload[0][{"key": "line_key", "code": "code", "blank": "code"}[mutation]] = (
        "" if mutation == "blank" else "NOT-SAVED"
    )
    assert not db.save_estimate_atomic(
        "1", "2026-09-05", 75, payload, [], estimate_totals()
    ).success
    assert db.get_estimate_by_voucher("1") == data
    assert not db.conn.in_transaction


def test_print_layout_remains_identical_after_catalog_changes(snapshot_db):
    from silverestimate.ui.estimate_print_layout import build_modern_estimate_layout

    db = snapshot_db
    document = EstimatePrintDocument.from_mapping(
        db.get_estimate_by_voucher("1"), show_tunch=True
    )
    before = build_modern_estimate_layout(document).normalized_text()
    assert db.update_item("REG001", "Changed", 20, "PC", 99, tunch="Changed")
    assert db.delete_item("REG001")
    document = EstimatePrintDocument.from_mapping(
        db.get_estimate_by_voucher("1"), show_tunch=True
    )
    assert build_modern_estimate_layout(document).normalized_text() == before
