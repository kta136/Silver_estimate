"""Historical snapshots survive catalog changes, upgrades and encrypted restore."""

import pytest

from silverestimate.persistence import schema
from silverestimate.persistence.database_manager import DatabaseManager
from silverestimate.persistence.estimates_repository import EstimatesRepository
from silverestimate.persistence.items_repository import ItemsRepository
from silverestimate.ui.estimate_print_document import EstimatePrintDocument
from tests.factories import estimate_totals, regular_item
from tests.integration.test_repositories import FakeDB


def downgrade_to_v8(db):
    # Remove exactly the three columns introduced by v9 to model a deployed v8 file.
    for column in ("item_code_snapshot", "tunch", "snapshot_version"):
        db.conn.execute(f"ALTER TABLE estimate_items DROP COLUMN {column}")
    db.conn.execute("DROP TABLE IF EXISTS estimate_draft")
    db.conn.execute("DELETE FROM schema_version WHERE version > 8")
    db.conn.execute(
        "INSERT INTO schema_version(version, applied_date) VALUES (8, '2026-09-05')"
    )
    db.conn.commit()


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


def test_v8_upgrade_freezes_available_metadata_and_preserves_orphans(snapshot_db):
    db = snapshot_db
    downgrade_to_v8(db)
    db.conn.execute("UPDATE estimate_items SET line_key = '', wage_type = NULL")
    db.conn.execute(
        "INSERT INTO estimate_items(voucher_no, item_name, gross, net_wt, fine, wage) VALUES ('1', 'Lost code', 2.123, 2.123, 1.234567, 8.125)"
    )
    db.conn.commit()
    before = [
        tuple(row)
        for row in db.conn.execute(
            "SELECT id, item_name, gross, net_wt, fine, wage FROM estimate_items"
        )
    ]
    schema.run_schema_setup(db)
    assert db._check_schema_version() == schema.CURRENT_SCHEMA_VERSION
    assert before == [
        tuple(row)
        for row in db.conn.execute(
            "SELECT id, item_name, gross, net_wt, fine, wage FROM estimate_items"
        )
    ]
    rows = db.get_estimate_by_voucher("1")["items"]
    assert rows[0]["tunch"] == "91 + loss"
    assert rows[0]["wage_type"] == "WT"
    assert rows[1]["item_code"] is None
    assert all(row["line_key"] for row in rows)
    assert db.update_item("REG001", "Updated", 50, "PC", 1, tunch="Later")
    schema.run_schema_setup(db)
    assert db.get_estimate_by_voucher("1")["items"][0]["tunch"] == "91 + loss"


@pytest.mark.parametrize("failure", ["version", "validation"])
def test_v8_upgrade_failure_rolls_back_columns_metadata_and_version(
    monkeypatch, failure
):
    db = FakeDB()
    try:
        schema.run_schema_setup(db)
        assert ItemsRepository(db).add_item("REG001", "Original", 92.5, "WT", 1)
        assert EstimatesRepository(db).save_estimate_with_returns(
            "1", "2026-09-05", 75, [regular_item()], [], estimate_totals()
        )
        downgrade_to_v8(db)
        before = _database_state(db)

        def fail(*args):
            raise RuntimeError("injected upgrade failure")

        with monkeypatch.context() as patch:
            patch.setattr(
                db, "_update_schema_version", fail
            ) if failure == "version" else patch.setattr(
                schema, "_validate_schema", fail
            )
            with pytest.raises(RuntimeError, match="injected"):
                schema.run_schema_setup(db)
        assert not db.conn.in_transaction
        assert _database_state(db) == before
        schema.run_schema_setup(db)
        assert db._check_schema_version() == schema.CURRENT_SCHEMA_VERSION
    finally:
        db.conn.close()


def test_encrypted_v8_backup_restores_and_upgrades_on_restart(snapshot_db, tmp_path):
    db = snapshot_db
    downgrade_to_v8(db)
    backup = db.create_encrypted_backup(tmp_path / "v8.sedbbackup")
    schema.run_schema_setup(db)
    assert db.update_item("REG001", "Current", 50, "PC", 1, tunch="Current")
    db.stage_encrypted_restore(backup.path, "password")
    db.close()
    reopened = DatabaseManager(
        str(tmp_path / "snapshots.db"), "password", device_secret=b"S" * 32
    )
    try:
        assert reopened._check_schema_version() == schema.CURRENT_SCHEMA_VERSION
        assert reopened.get_estimate_by_voucher("1")["items"][0]["tunch"] == "91 + loss"
        assert list(reopened.conn.execute("PRAGMA foreign_key_check")) == []
    finally:
        reopened.close()


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
