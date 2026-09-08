"""Regression coverage for failed writes and destructive reference cascades."""

import pytest

from silverestimate.persistence import schema
from silverestimate.persistence.estimates_repository import EstimatesRepository
from silverestimate.persistence.items_repository import ItemsRepository
from silverestimate.persistence.silver_bar_command_repository import (
    SilverBarCommandRepository,
)
from tests.factories import estimate_totals, regular_item
from tests.integration.test_repositories import FakeDB


@pytest.fixture
def db():
    database = FakeDB()
    schema.run_schema_setup(database)
    database.conn.execute("PRAGMA foreign_keys = ON")
    assert ItemsRepository(database).add_item("REG001", "Original", 92.5, "WT", 10)
    yield database
    database.conn.close()


def _save(db, voucher="1", **item_changes):
    return EstimatesRepository(db).save_estimate_with_returns(
        voucher,
        "2026-09-05",
        75,
        [regular_item(**item_changes)],
        [],
        estimate_totals(note="Original"),
    )


def _snapshot(db):
    return {
        table: [tuple(row) for row in db.conn.execute(f"SELECT * FROM {table}")]
        for table in (
            "items",
            "estimates",
            "estimate_items",
            "silver_bars",
            "silver_bar_lists",
            "bar_transfers",
        )
    }


@pytest.mark.parametrize(
    "changes",
    [
        {"gross": "bad"},
        {"pieces": 2**63},
        {"gross": float("nan")},
        {"fine": float("inf")},
    ],
)
def test_failed_update_preserves_original_and_allows_next_save(db, changes):
    assert _save(db)
    before = _snapshot(db)
    assert not _save(db, **changes)
    assert db.last_error
    assert not db.conn.in_transaction
    assert _snapshot(db) == before
    assert _save(db, "2")
    assert db.last_error is None


def test_sql_failure_after_deleting_old_lines_rolls_back_header_and_lines(db):
    assert _save(db)
    before = _snapshot(db)
    # An actual database error after the UPDATE and DELETE have already run.
    db.conn.execute("""CREATE TRIGGER reject_line BEFORE INSERT ON estimate_items
        BEGIN SELECT missing_function(); END""")
    assert not _save(db, gross=20)
    assert not db.conn.in_transaction
    assert _snapshot(db) == before
    db.conn.execute("DROP TRIGGER reject_line")
    assert _save(db, "2")


def test_commit_failure_rolls_back_completed_update(db):
    assert _save(db)
    before = _snapshot(db)
    connection = db.conn

    class FailingCommit:
        def __getattr__(self, name):
            return getattr(connection, name)

        def commit(self):
            raise RuntimeError("Injected commit failure")

    db.conn = FailingCommit()
    assert not _save(db, gross=20)
    assert "commit failure" in db.last_error
    assert not connection.in_transaction
    db.conn = connection
    assert _snapshot(db) == before
    assert _save(db, "2")


@pytest.mark.parametrize(
    "field", ["total_gross", "net_fine", "last_balance_silver", "last_balance_amount"]
)
def test_nonfinite_header_does_not_change_saved_estimate(db, field):
    assert _save(db)
    before = _snapshot(db)
    assert not EstimatesRepository(db).save_estimate_with_returns(
        "1",
        "2026-09-05",
        75,
        [regular_item()],
        [],
        estimate_totals(**{field: float("nan")}),
    )
    assert "finite" in db.last_error
    assert not db.conn.in_transaction
    assert _snapshot(db) == before


@pytest.mark.parametrize(
    "voucher,sort_key",
    [(str(2**63 - 1), 2**63 - 1), (str(2**63), None), ("9" * 100, None)],
)
def test_large_numeric_voucher_keeps_text_and_safe_sort_key(db, voucher, sort_key):
    assert _save(db, voucher)
    assert tuple(
        db.conn.execute("SELECT voucher_no, voucher_no_int FROM estimates").fetchone()
    ) == (voucher, sort_key)
    assert _save(db, "2")


def test_save_does_not_rollback_a_transaction_it_did_not_start(db):
    db.conn.execute("INSERT INTO items (code, name) VALUES ('PENDING', 'Pending')")
    assert not _save(db)
    assert db.conn.in_transaction
    assert db.conn.execute("SELECT 1 FROM items WHERE code = 'PENDING'").fetchone()
    db.conn.rollback()


@pytest.mark.parametrize("replace", [False, True])
def test_incomplete_snapshot_blocks_catalog_removal(db, replace):
    assert _save(db)
    db.conn.execute("UPDATE estimate_items SET item_code_snapshot = NULL")
    db.conn.commit()
    repository = ItemsRepository(db)
    cached = dict(repository.get_item_by_code("REG001"))
    before = _snapshot(db)
    if replace:
        assert (
            repository.upsert_item_catalog(
                [
                    {
                        "code": "NEW",
                        "name": "Replacement",
                        "purity": 90,
                        "wage_type": "WT",
                        "wage_rate": 5,
                    }
                ],
                replace_existing=True,
            )
            is None
        )
    else:
        assert not repository.delete_item("REG001")
    assert "REG001" in db.last_error
    assert "estimate" in db.last_error.lower()
    assert not db.conn.in_transaction
    assert _snapshot(db) == before
    assert repository.get_item_by_code("REG001") == cached


def test_unreferenced_catalog_item_can_still_be_removed(db):
    assert ItemsRepository(db).delete_item("REG001")
    assert not db.conn.execute("SELECT 1 FROM items").fetchone()


def test_catalog_replacement_can_keep_referenced_codes_and_remove_unused_ones(db):
    assert _save(db)
    items = ItemsRepository(db)
    assert items.add_item("UNUSED", "Unused", 90, "WT", 1)
    summary = items.upsert_item_catalog(
        [
            {
                "code": "REG001",
                "name": "Updated",
                "purity": 92.5,
                "wage_type": "WT",
                "wage_rate": 10,
            }
        ],
        replace_existing=True,
    )
    assert summary == {"inserted": 0, "updated": 1, "deleted": 1, "total": 1}
    assert db.last_error is None
    assert (
        db.conn.execute("SELECT item_code FROM estimate_items").fetchone()[0]
        == "REG001"
    )
    assert items.get_item_by_code("REG001")["name"] == "Updated"


def test_reference_guard_protects_legacy_lowercase_catalog_code(db):
    db.conn.execute("INSERT INTO items (code, name) VALUES ('legacy', 'Legacy')")
    db.conn.execute(
        "INSERT INTO estimates (voucher_no, date) VALUES ('legacy', '2026-09-05')"
    )
    db.conn.execute(
        "INSERT INTO estimate_items (voucher_no, item_code) VALUES ('legacy', 'legacy')"
    )
    db.conn.commit()
    before = _snapshot(db)
    assert ItemsRepository(db).upsert_item_catalog([], replace_existing=True) is None
    assert "legacy" in db.last_error
    assert _snapshot(db) == before


@pytest.mark.parametrize("state", ["Assigned", "Issued", "Returned to stock"])
@pytest.mark.parametrize("with_command_repository", [False, True])
def test_estimate_deletion_preserves_allocated_bars_and_transfer_history(
    db, state, with_command_repository
):
    assert _save(db)
    commands = SilverBarCommandRepository(db)
    if with_command_repository:
        db.silver_bar_command_repo = commands
    bar = commands.add_silver_bar("1", 5, 99.9)
    bar_list = commands.create_list("Protected")
    assert commands.assign_bar_to_list(bar, bar_list)
    if state == "Issued":
        db.conn.execute(
            "UPDATE silver_bars SET status = 'Issued' WHERE bar_id = ?", (bar,)
        )
        db.conn.commit()
    elif state == "Returned to stock":
        assert commands.remove_bar_from_list(bar)
    before = _snapshot(db)
    assert not EstimatesRepository(db).delete_single_estimate("1")
    assert "silver bar" in db.last_error.lower()
    assert not db.conn.in_transaction
    assert _snapshot(db) == before


def test_unused_in_stock_bar_does_not_block_estimate_deletion(db):
    assert _save(db)
    assert SilverBarCommandRepository(db).add_silver_bar("1", 5, 99.9)
    assert EstimatesRepository(db).delete_single_estimate("1")
    assert not db.conn.execute("SELECT 1 FROM silver_bars").fetchone()
