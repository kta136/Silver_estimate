"""End-to-end save invariants using the production encrypted database and adapter."""

from copy import deepcopy

import pytest

from silverestimate.persistence.database_manager import DatabaseManager
from silverestimate.services.estimate_repository import DatabaseEstimateRepository
from tests.factories import estimate_totals, regular_item, return_item, silver_bar_item


@pytest.fixture
def inventory_db(tmp_path):
    db = DatabaseManager(
        str(tmp_path / "inventory.db"), "test-pass", device_secret=b"I" * 32
    )
    for code in ("REG001", "RET001", "BAR001"):
        assert db.add_item(code, code, 99, "WT", 0)
    assert db.conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    yield db
    db.close()


def _bar(key="bar-a", weight=5, purity=99):
    return silver_bar_item(
        line_key=key,
        gross=weight,
        net_wt=weight,
        purity=purity,
        fine=weight * (purity / 100),
    )


def _save(db, bars, *, voucher="1", note="Original", regular=None):
    return DatabaseEstimateRepository(db).save_estimate(
        voucher,
        "2026-09-05",
        75,
        [regular_item(line_key="regular")] if regular is None else regular,
        [return_item(line_key="return"), *bars],
        estimate_totals(note=note),
    )


def _snapshot(db):
    return {
        table: [tuple(row) for row in db.conn.execute(f"SELECT * FROM {table}")]
        for table in (
            "estimates",
            "estimate_items",
            "silver_bars",
            "silver_bar_lists",
            "bar_transfers",
        )
    }


def _bars(db):
    return {
        row["source_line_key"]: dict(row)
        for row in db.conn.execute("SELECT * FROM silver_bars ORDER BY bar_id")
    }


def _protect(db, bar_id, state):
    commands = db.silver_bar_command_repo
    list_id = commands.create_list("Lifecycle")
    assert commands.assign_bar_to_list(bar_id, list_id)
    if state in ("issued", "returned"):
        assert commands.mark_list_as_issued(list_id)
    if state == "returned":
        assert commands.reactivate_list(list_id)
        assert commands.remove_bar_from_list(bar_id)


def test_single_commit_inserts_updates_reorders_and_removes_unused_bars(inventory_db):
    db = inventory_db
    statements = []
    db.conn.set_trace_callback(statements.append)
    try:
        first = _save(db, [_bar(), _bar("bar-b", 7)])
    finally:
        db.conn.set_trace_callback(None)
    assert first.success and first.bars_added == 2
    assert [sql for sql in statements if sql in ("BEGIN IMMEDIATE", "COMMIT")] == [
        "BEGIN IMMEDIATE",
        "COMMIT",
    ]
    original = _bars(db)
    changed = _save(db, [_bar("bar-b", 8), _bar()], note="Reordered")
    assert changed.success and changed.bars_updated == 1
    rows = _bars(db)
    for key in original:
        assert rows[key]["bar_id"] == original[key]["bar_id"]
        assert rows[key]["date_added"] == original[key]["date_added"]
    assert rows["bar-b"]["weight"] == 8
    assert rows["bar-b"]["fine_weight"] == pytest.approx(7.92)
    unchanged = _save(db, [_bar(), _bar("bar-b", 8)])
    assert unchanged.success and unchanged.bars_added == unchanged.bars_updated == 0
    removed = _save(db, [])
    assert removed.success and removed.bars_removed == 2
    assert not _bars(db)
    assert (
        db.conn.execute(
            "SELECT COUNT(*) FROM estimate_items WHERE is_silver_bar=1"
        ).fetchone()[0]
        == 0
    )


@pytest.mark.parametrize("state", ["assigned", "issued", "returned"])
@pytest.mark.parametrize(
    "change",
    ["weight", "purity", "tiny_weight", "remove", "rekey", "return", "regular"],
)
def test_protected_bar_edits_roll_back_the_entire_estimate(inventory_db, state, change):
    db = inventory_db
    assert _save(db, [_bar(), _bar("free", 7)]).success
    _protect(db, _bars(db)["bar-a"]["bar_id"], state)
    before = _snapshot(db)
    bar = _bar()
    regular = [regular_item(line_key="regular", gross=20, net_wt=20, fine=18.5)]
    if change in ("weight", "tiny_weight"):
        bar = _bar(weight=6 if change == "weight" else 5.0000001)
    elif change == "purity":
        bar = _bar(purity=98)
    elif change == "rekey":
        bar["line_key"] = "replacement"
    elif change == "return":
        bar["is_return"] = True
    elif change == "regular":
        regular.append(regular_item(line_key="bar-a"))
    desired = [_bar("free", 8), _bar("new", 11)]
    if change not in ("remove", "regular"):
        desired.append(bar)
    result = _save(db, desired, note="Must not commit", regular=regular)
    assert not result.success
    assert "transfer history" in result.error_detail
    assert result.bars_added == result.bars_updated == result.bars_removed == 0
    assert _snapshot(db) == before
    assert not db.conn.in_transaction
    assert _save(db, [_bar(), _bar("free", 7)]).success


@pytest.mark.parametrize("state", ["assigned", "issued", "returned"])
def test_protected_bars_allow_note_and_regular_edits_without_changing_inventory(
    inventory_db, state
):
    db = inventory_db
    assert _save(db, [_bar(), _bar("free", 7)]).success
    _protect(db, _bars(db)["bar-a"]["bar_id"], state)
    protected = _bars(db)["bar-a"]
    transfers = _snapshot(db)["bar_transfers"]
    result = _save(
        db, [_bar("free", 8), _bar()], note="Allowed", regular=[regular_item(gross=11)]
    )
    assert result.success and result.bars_updated == 1
    assert _bars(db)["bar-a"] == protected
    assert _snapshot(db)["bar_transfers"] == transfers
    assert db.get_estimate_by_voucher("1")["header"]["note"] == "Allowed"


@pytest.mark.parametrize("failure", ["insert", "update", "delete", "commit"])
def test_storage_failure_rolls_back_header_lines_inventory_and_recovers(
    inventory_db, failure
):
    db = inventory_db
    assert _save(db, [_bar(), _bar("removed", 7)]).success
    before = _snapshot(db)
    if failure == "commit":
        db.conn.execute(
            "CREATE TABLE commit_probe (voucher TEXT REFERENCES estimates(voucher_no) DEFERRABLE INITIALLY DEFERRED)"
        )
        db.conn.execute("""CREATE TRIGGER fail_inventory AFTER UPDATE ON silver_bars
            BEGIN INSERT INTO commit_probe VALUES ('does-not-exist'); END""")
    else:
        # INSERT fails on the second new bar, after an update, removal, and insert.
        condition = "WHEN NEW.weight = 12" if failure == "insert" else ""
        db.conn.execute(f"""CREATE TRIGGER fail_inventory BEFORE {failure.upper()} ON silver_bars
            {condition} BEGIN SELECT RAISE(ABORT, 'Injected inventory failure'); END""")
    desired = [_bar(weight=6), _bar("new", 11), _bar("last", 12)]
    result = _save(db, desired, note="Must roll back")
    assert not result.success and result.error_detail
    assert result.bars_added == result.bars_updated == result.bars_removed == 0
    assert _snapshot(db) == before
    assert not db.conn.in_transaction
    if failure == "commit":
        assert db.conn.execute("SELECT COUNT(*) FROM commit_probe").fetchone()[0] == 0
    db.conn.execute("DROP TRIGGER fail_inventory")
    assert _save(db, desired, note="Recovered").success
    with db.open_read_connection() as reader:
        assert (
            reader.execute(
                "SELECT note FROM estimates WHERE voucher_no='1'"
            ).fetchone()[0]
            == "Recovered"
        )
        assert reader.execute("SELECT COUNT(*) FROM silver_bars").fetchone()[0] == 3


def test_new_estimate_inventory_failure_leaves_no_header_or_lines(inventory_db):
    db = inventory_db
    before = _snapshot(db)
    db.conn.execute("""CREATE TRIGGER fail_inventory BEFORE INSERT ON silver_bars
        WHEN NEW.weight=7 BEGIN SELECT RAISE(ABORT, 'Injected insert failure'); END""")
    result = _save(db, [_bar(), _bar("second", 7)])
    assert not result.success
    assert _snapshot(db) == before


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), -1])
def test_invalid_bar_numbers_and_duplicate_keys_never_partially_save(inventory_db, bad):
    db = inventory_db
    assert _save(db, [_bar()]).success
    before = _snapshot(db)
    for desired in ([_bar(), _bar("bad", bad)], [_bar(), _bar("bar-a", 7)]):
        assert not _save(db, desired).success
        assert _snapshot(db) == before


@pytest.mark.parametrize("has_keys", [False, True])
def test_legacy_bars_acquire_keys_by_unchanged_values_without_row_order_guesses(
    inventory_db,
    has_keys,
):
    db = inventory_db
    assert _save(db, [_bar(), _bar("second", 7)]).success
    _protect(db, _bars(db)["bar-a"]["bar_id"], "returned")
    original_ids = {row["weight"]: row["bar_id"] for row in _bars(db).values()}
    transfers = _snapshot(db)["bar_transfers"]
    db.conn.execute("UPDATE silver_bars SET source_line_key = NULL")
    # Linking legacy inventory must preserve recorded fine weight as well as history.
    db.conn.execute("UPDATE silver_bars SET fine_weight = 4.9 WHERE weight = 5")
    db.conn.execute("UPDATE estimate_items SET line_key = NULL WHERE is_silver_bar=1")
    db.conn.commit()
    payload = [
        _bar("new-second" if has_keys else "", 7),
        _bar("new-first" if has_keys else ""),
    ]
    untouched = deepcopy(payload)
    result = _save(db, payload)
    assert result.success and result.bars_added == 0
    assert payload == untouched
    rows = _bars(db)
    assert all(rows)
    for row in rows.values():
        assert row["bar_id"] == original_ids[row["weight"]]
        if row["weight"] == 5:
            assert row["fine_weight"] == 4.9
    assert _snapshot(db)["bar_transfers"] == transfers
    lines = db.conn.execute(
        "SELECT line_key FROM estimate_items WHERE is_silver_bar=1"
    ).fetchall()
    assert {row[0] for row in lines} == set(rows)


@pytest.mark.parametrize(
    "case", ["changed", "removed", "ambiguous", "duplicate_inventory_key"]
)
def test_unresolvable_legacy_links_preserve_all_records(inventory_db, case):
    db = inventory_db
    assert _save(db, [_bar(), _bar("second", 7)]).success
    if case == "duplicate_inventory_key":
        db.conn.execute("UPDATE silver_bars SET source_line_key='bar-a'")
    else:
        db.conn.execute("UPDATE silver_bars SET source_line_key=NULL")
    if case == "ambiguous":
        db.conn.execute("UPDATE silver_bars SET weight=5, fine_weight=4.95")
    db.conn.commit()
    before = _snapshot(db)
    desired = (
        [_bar(weight=6), _bar("second", 7)]
        if case == "changed"
        else [_bar(), _bar("second", 7)]
    )
    if case == "removed":
        desired = []
    result = _save(db, desired)
    assert not result.success and result.error_detail
    assert _snapshot(db) == before


def test_failed_begin_does_not_rollback_another_callers_transaction(inventory_db):
    db = inventory_db
    assert _save(db, [_bar()]).success
    db.conn.execute("BEGIN IMMEDIATE")
    db.conn.execute("UPDATE estimates SET note='Pending'")
    result = _save(db, [_bar(weight=6)])
    assert not result.success and db.conn.in_transaction
    assert db.conn.execute("SELECT note FROM estimates").fetchone()[0] == "Pending"
    db.conn.rollback()
    assert _bars(db)["bar-a"]["weight"] == 5


def test_existing_schema_gains_transfer_lookup_index_without_changing_records(
    inventory_db,
):
    from silverestimate.persistence.schema import run_schema_setup

    db = inventory_db
    assert _save(db, [_bar()]).success
    _protect(db, _bars(db)["bar-a"]["bar_id"], "returned")
    before = _snapshot(db)
    version = db._check_schema_version()
    db.conn.execute("DROP INDEX idx_bar_transfers_bar")
    db.conn.commit()
    run_schema_setup(db)
    assert db._check_schema_version() == version
    assert _snapshot(db) == before
    statements = []
    db.conn.set_trace_callback(statements.append)
    try:
        assert _save(db, [_bar()]).success
    finally:
        db.conn.set_trace_callback(None)
    query = next(sql for sql in statements if "AS has_transfers" in sql)
    plan = "\n".join(row[3] for row in db.conn.execute("EXPLAIN QUERY PLAN " + query))
    assert "USING COVERING INDEX idx_bar_transfers_bar" in plan
    assert "SCAN transfers" not in plan
