"""Range deletion must be exact, reviewed, and atomic across inventory and drafts."""

import json

import pytest

from silverestimate.domain.voucher_deletion import VoucherDeletionRange
from silverestimate.persistence import schema
from silverestimate.persistence.estimates_repository import EstimatesRepository
from tests.integration.test_repositories import FakeDB


@pytest.fixture
def database():
    db = FakeDB()
    schema.run_schema_setup(db)
    db.conn.execute("PRAGMA foreign_keys=ON")
    yield db
    db.conn.close()


def voucher(db, number, date="2026-10-04"):
    db.conn.execute(
        "INSERT INTO estimates(voucher_no,date) VALUES(?,?)", (number, date)
    )
    db.conn.execute(
        "INSERT INTO estimate_items(voucher_no,item_name,purity,fine,tunch) VALUES(?, 'Snapshot', 125.5, 12.55, 'Keep text')",
        (number,),
    )
    db.conn.commit()


def bar(db, number, status="In Stock", list_id=None):
    result = db.conn.execute(
        "INSERT INTO silver_bars(estimate_voucher_no,status,list_id,purity,fine_weight) VALUES(?,?,?,125.5,12.55)",
        (number, status, list_id),
    )
    db.conn.commit()
    return result.lastrowid


def snapshot(db):
    return {
        table: [tuple(row) for row in db.conn.execute(f"SELECT * FROM {table}")]
        for table in (
            "estimates",
            "estimate_items",
            "silver_bars",
            "bar_transfers",
            "silver_bar_lists",
            "estimate_draft",
            "items",
        )
    }


def preview(db, start="0", end="1000"):
    return EstimatesRepository(db).preview_voucher_deletion(
        VoucherDeletionRange("voucher", start, end)
    )


@pytest.mark.parametrize(
    "mode,start,end",
    [
        ("voucher", "", "1"),
        ("voucher", "1", ""),
        ("voucher", "-1", "2"),
        ("voucher", "1.2", "2"),
        ("voucher", "A1", "A2"),
        ("voucher", "2", "1"),
        ("voucher", "NaN", "10"),
        ("voucher", "1", "Infinity"),
        ("date", "2026-02-30", "2026-03-01"),
        ("date", "2026-10-05", "2026-10-04"),
        ("date", "20261004", "2026-10-05"),
        ("unknown", "1", "2"),
    ],
)
def test_invalid_ranges_are_rejected(mode, start, end):
    with pytest.raises(ValueError):
        VoucherDeletionRange(mode, start, end)


def test_numeric_comparison_handles_padding_letters_and_oversized_ids(database):
    for number in (
        "0",
        "2",
        "9",
        "10",
        "0010",
        "11",
        "100",
        "A10",
        "10A",
        str(2**63),
        "9" * 100,
    ):
        voucher(database, number)
    selected = preview(database, "9", "11")
    assert [r.voucher_no for r in selected.rows] == ["9", "0010", "10", "11"]
    assert [r.voucher_no for r in preview(database, "00010", "10").rows] == [
        "0010",
        "10",
    ]
    selected = preview(database, str(2**63), "9" * 100)
    assert [r.voucher_no for r in selected.rows] == [str(2**63), "9" * 100]
    assert EstimatesRepository(database).delete_voucher_range(
        selected
    ).deleted_vouchers == (str(2**63), "9" * 100)


def test_dates_are_inclusive_and_include_alphanumeric_vouchers(database):
    for number, day in (("A1", "03"), ("A2", "04"), ("A3", "05"), ("A4", "06")):
        voucher(database, number, f"2026-10-{day}")
    repo = EstimatesRepository(database)
    selected = repo.preview_voucher_deletion(
        VoucherDeletionRange("date", "2026-10-04", "2026-10-05")
    )
    assert [r.voucher_no for r in selected.rows] == ["A2", "A3"]
    same_day = repo.preview_voucher_deletion(
        VoucherDeletionRange("date", "2026-10-04", "2026-10-04")
    )
    assert [r.voucher_no for r in same_day.rows] == ["A2"]


@pytest.mark.parametrize(
    "protection", ["Assigned", "Issued", "list", "history", "unknown"]
)
def test_mixed_range_skips_entire_protected_voucher(database, protection):
    for number in ("1", "2", "3"):
        voucher(database, number)
    bar(database, "1")
    bar(database, "2")
    protected = bar(
        database,
        "2",
        protection if protection in ("Assigned", "Issued", "unknown") else "In Stock",
    )
    if protection == "list":
        database.conn.execute(
            "INSERT INTO silver_bar_lists(list_id,list_identifier,creation_date) VALUES(1,'List','2026-10-04')"
        )
        database.conn.execute(
            "UPDATE silver_bars SET list_id=1 WHERE bar_id=?", (protected,)
        )
    elif protection == "history":
        database.conn.execute(
            "INSERT INTO bar_transfers(silver_bar_id,from_status,to_status) VALUES(?, 'Assigned', 'In Stock')",
            (protected,),
        )
    database.conn.commit()
    before = snapshot(database)
    selected = preview(database, "1", "2")
    assert len(selected.eligible) == len(selected.skipped) == 1
    result = EstimatesRepository(database).delete_voucher_range(selected)
    assert result.succeeded and result.deleted_vouchers == ("1",)
    assert result.skipped[0].voucher_no == "2"
    after = snapshot(database)
    assert after["estimates"] == [r for r in before["estimates"] if r[0] != "1"]
    assert after["silver_bars"] == [r for r in before["silver_bars"] if r[1] != "1"]
    assert after["bar_transfers"] == before["bar_transfers"]
    assert after["silver_bar_lists"] == before["silver_bar_lists"]
    assert database.conn.execute(
        "SELECT purity,fine,tunch FROM estimate_items WHERE voucher_no='2'"
    ).fetchone()[:] == (125.5, 12.55, "Keep text")
    assert not database.conn.in_transaction


@pytest.mark.parametrize(
    "change", ["new", "removed", "header", "line", "bar", "transfer"]
)
def test_changes_after_preview_require_another_review(database, change):
    voucher(database, "1")
    bar_id = bar(database, "1")
    selected = preview(database)
    if change == "new":
        voucher(database, "2")
    elif change == "removed":
        database.conn.execute("DELETE FROM estimates WHERE voucher_no='1'")
    elif change == "header":
        database.conn.execute("UPDATE estimates SET note='Changed'")
    elif change == "line":
        database.conn.execute("UPDATE estimate_items SET item_name='Changed'")
    elif change == "bar":
        database.conn.execute("UPDATE silver_bars SET status='Issued'")
    else:
        database.conn.execute(
            "INSERT INTO bar_transfers(silver_bar_id) VALUES(?)", (bar_id,)
        )
    database.conn.commit()
    before = snapshot(database)
    result = EstimatesRepository(database).delete_voucher_range(selected)
    assert result.stale and not result.succeeded
    assert snapshot(database) == before
    assert not database.conn.in_transaction


@pytest.mark.parametrize(
    "draft_voucher,active,deleted",
    [("1", "1", True), ("EDITED", "1", True), ("3", "3", False), ("1", "3", False)],
)
def test_only_matching_recovery_draft_is_deleted(
    database, draft_voucher, active, deleted
):
    voucher(database, "1")
    database.conn.execute(
        "INSERT INTO estimate_draft VALUES(1, 'token', ?, ?, 'today')",
        (draft_voucher, json.dumps({"active_voucher_no": active})),
    )
    database.conn.commit()
    result = EstimatesRepository(database).delete_voucher_range(preview(database))
    assert (result.deleted_draft_token == "token") is deleted
    assert (
        database.conn.execute("SELECT * FROM estimate_draft").fetchone() is None
    ) is deleted


@pytest.mark.parametrize("failure", ["delete", "commit"])
def test_failure_rolls_back_every_eligible_voucher_and_draft(database, failure):
    for number in ("1", "2"):
        voucher(database, number)
        bar(database, number)
    database.conn.execute(
        "INSERT INTO estimate_draft VALUES(1,'token','1','{}','today')"
    )
    database.conn.commit()
    selected, before = preview(database), snapshot(database)
    connection = database.conn
    if failure == "delete":
        connection.execute(
            "CREATE TRIGGER reject_delete BEFORE DELETE ON estimates WHEN OLD.voucher_no='2' BEGIN SELECT RAISE(ABORT, 'injected failure'); END"
        )
    else:

        class FailingCommit:
            def __getattr__(self, name):
                return getattr(connection, name)

            def commit(self):
                raise RuntimeError("injected failure")

        database.conn = FailingCommit()
    with pytest.raises(Exception, match="injected failure"):
        EstimatesRepository(database).delete_voucher_range(selected)
    database.conn = connection
    assert snapshot(database) == before
    assert not connection.in_transaction


def test_existing_transaction_is_not_rolled_back(database):
    selected = preview(database)
    database.conn.execute("INSERT INTO items(code,name) VALUES('PENDING','Pending')")
    with pytest.raises(RuntimeError, match="transaction"):
        EstimatesRepository(database).delete_voucher_range(selected)
    assert database.conn.in_transaction
    assert database.conn.execute("SELECT * FROM items WHERE code='PENDING'").fetchone()


def test_empty_and_all_protected_ranges_are_noops(database):
    repo = EstimatesRepository(database)
    assert repo.delete_voucher_range(preview(database)).deleted_vouchers == ()
    voucher(database, "1")
    bar(database, "1", "Issued")
    before = snapshot(database)
    result = repo.delete_voucher_range(preview(database))
    assert result.succeeded and not result.deleted_vouchers and len(result.skipped) == 1
    assert snapshot(database) == before


def test_range_larger_than_one_sql_batch(database):
    database.conn.executemany(
        "INSERT INTO estimates(voucher_no,date) VALUES(?,'2026-10-04')",
        [(str(i),) for i in range(805)],
    )
    database.conn.commit()
    result = EstimatesRepository(database).delete_voucher_range(
        preview(database, "1", "803")
    )
    assert len(result.deleted_vouchers) == 803
    assert [
        r[0]
        for r in database.conn.execute(
            "SELECT voucher_no FROM estimates ORDER BY voucher_no"
        )
    ] == ["0", "804"]
