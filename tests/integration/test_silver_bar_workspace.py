import threading

import pytest

from silverestimate.domain.numeric_policy import fixed_decimal
from silverestimate.domain.silver_bar_workspace import normalize_weight_prefix
from silverestimate.persistence.repository_results import RepositoryFailureKind
from silverestimate.persistence.silver_bars_snapshot_repository import (
    SilverBarsSnapshotRepository,
)
from tests.silver_bar_workspace_support import seed_workspace_db


@pytest.fixture
def db(tmp_path):
    database = seed_workspace_db(tmp_path)
    yield database
    database.close()


def test_prefix_search_entire_inventory_duplicates_and_decimal_policy(db):
    page = db.search_silver_bar_weight_prefix("40", limit=2)
    assert [bar["weight"] for bar in page.items] == [40, 40]
    following = db.search_silver_bar_weight_prefix(
        "40", cursor=page.next_cursor, limit=2
    )
    assert [bar["weight"] for bar in following.items] == [40.25, 402.5]
    assert not following.has_more
    assert [b["weight"] for b in db.search_silver_bar_weight_prefix("040.").items] == [
        40,
        40,
        40.25,
    ]
    db.conn.execute("UPDATE silver_bars SET weight = 40.005 WHERE bar_id = 1")
    db.conn.commit()
    assert db.search_silver_bar_weight_prefix("40.01").items[0]["bar_id"] == 1


@pytest.mark.parametrize(
    "text", ["", "nan", "inf", "-40", "4e1", "%", "40.001", "40_", "40.."]
)
def test_invalid_prefix_cannot_broaden_search(text):
    with pytest.raises(ValueError):
        normalize_weight_prefix(text)


@pytest.mark.parametrize("text", ["", "   "])
def test_blank_search_pages_all_available_inventory_in_weight_order(db, text):
    db.add_bars_to_list([3]).unwrap()
    issued = db.add_bars_to_list([4]).unwrap()
    db.issue_printed_list(issued.list_id, issued.signature).unwrap()
    reader = SilverBarsSnapshotRepository(db.open_read_connection)
    rows, cursor = [], None
    while True:
        page = reader.search_weight_prefix(text, cursor=cursor, limit=2)
        rows.extend(page.items)
        cursor = page.next_cursor
        if cursor is None:
            break
    assert [bar["bar_id"] for bar in rows] == [6, 1, 2, 7, 5]
    assert rows[0]["purity"] == 125.5
    assert rows[0]["fine_weight"] == 12.55
    assert all(bar["status"] == "In Stock" and bar["list_id"] is None for bar in rows)
    assert list(db.search_silver_bar_weight_prefix(text).items) == rows


@pytest.mark.parametrize("text", ["nan", "inf", "-40", "4e1", "%", "40.001", "40_"])
def test_invalid_query_does_not_fall_back_to_all_inventory(db, text):
    with pytest.raises(ValueError):
        db.search_silver_bar_weight_prefix(text)


def test_add_autocreates_one_list_reserves_and_removes_without_identity_loss(db):
    snapshot = db.add_bars_to_list([1], note="Morning").unwrap()
    assert len(snapshot.bars) == 1
    assert snapshot.details["list_note"] == "Morning"
    assert snapshot.bars[0]["status"] == "Assigned"
    assert 1 not in [
        b["bar_id"] for b in db.search_silver_bar_weight_prefix("40").items
    ]
    assert db.add_bars_to_list([1]).failure.kind == RepositoryFailureKind.CONFLICT
    assert len(db.get_silver_bar_lists()) == 1
    removed = db.remove_list_bars(snapshot.list_id, [1]).unwrap()
    assert not removed.bars
    assert (
        db.conn.execute(
            "SELECT source_line_key FROM silver_bars WHERE bar_id=1"
        ).fetchone()[0]
        == "bar-0"
    )
    assert [
        r[0]
        for r in db.conn.execute(
            "SELECT to_status FROM bar_transfers WHERE silver_bar_id=1 ORDER BY id"
        )
    ] == ["Assigned", "In Stock"]


def test_storage_failure_rolls_back_first_add_and_optimizer_batch(db):
    db.conn.execute("""CREATE TRIGGER reject_bar BEFORE UPDATE ON silver_bars
                    WHEN NEW.bar_id = 2 BEGIN SELECT RAISE(ABORT, 'Injected failure'); END""")
    db.conn.commit()
    result = db.add_bars_to_list([1, 2])
    assert result.failure.kind == RepositoryFailureKind.STORAGE
    assert not db.get_silver_bar_lists()
    assert db.conn.execute("SELECT count(*) FROM bar_transfers").fetchone()[0] == 0
    assert (
        db.conn.execute("SELECT status FROM silver_bars WHERE bar_id=1").fetchone()[0]
        == "In Stock"
    )


def test_conflicting_bulk_remove_is_atomic_and_issued_list_is_read_only(db):
    snapshot = db.add_bars_to_list([1, 2]).unwrap()
    assert db.remove_list_bars(snapshot.list_id, [1, 3]).failure
    assert len(db.get_silver_bar_list_snapshot(snapshot.list_id).bars) == 2
    issued = db.issue_printed_list(snapshot.list_id, snapshot.signature).unwrap()
    assert issued.issued and all(b["status"] == "Issued" for b in issued.bars)
    assert db.add_bars_to_list([3], issued.list_id).failure
    assert db.remove_list_bars(issued.list_id).failure
    assert db.save_active_list_note(issued.list_id, "changed").failure
    assert db.delete_active_list(issued.list_id).failure


def test_issue_detects_printed_snapshot_changes_and_rollback(db):
    snapshot = db.add_bars_to_list([1, 2]).unwrap()
    db.save_active_list_note(snapshot.list_id, "Changed").unwrap()
    assert db.issue_printed_list(snapshot.list_id, snapshot.signature).failure
    current = db.get_silver_bar_list_snapshot(snapshot.list_id)
    db.conn.execute("""CREATE TRIGGER reject_issue BEFORE UPDATE ON silver_bars
                    WHEN NEW.bar_id = 2 AND NEW.status = 'Issued'
                    BEGIN SELECT RAISE(ABORT, 'Issue failure'); END""")
    db.conn.commit()
    assert db.issue_printed_list(current.list_id, current.signature).failure
    after = db.get_silver_bar_list_snapshot(current.list_id)
    assert after.signature == current.signature
    assert not after.issued


def test_above_100_purity_survives_reopen_print_issue_and_reactivation(db):
    snapshot = db.add_bars_to_list([6]).unwrap()
    assert snapshot.weight == 10
    assert snapshot.fine_weight == 12.55
    from silverestimate.ui.silver_bar_print_document import SilverBarListPrintDocument

    document = SilverBarListPrintDocument.from_rows(snapshot.details, snapshot.bars)
    assert document.bars[0].purity == 125.5
    assert document.bars[0].fine_weight == 12.55
    issued = db.issue_printed_list(snapshot.list_id, snapshot.signature).unwrap()
    assert db.reactivate_silver_bar_list(issued.list_id)
    reopened = db.get_silver_bar_list_snapshot(issued.list_id)
    assert not reopened.issued
    assert fixed_decimal(reopened.fine_weight, 2) == "12.55"


def test_snapshot_worker_uses_separate_connection_and_same_prefix_rules(db):
    snapshot = db.add_bars_to_list([6]).unwrap()
    output = []

    def read():
        reader = SilverBarsSnapshotRepository(db.open_read_connection)
        output.append(reader.search_weight_prefix("40"))
        output.append(reader.get_list_snapshot(snapshot.list_id))

    thread = threading.Thread(target=read)
    thread.start()
    thread.join(timeout=10)
    assert not thread.is_alive()
    assert len(output[0].items) == 4
    assert output[1].signature == snapshot.signature


def test_delete_and_clear_release_every_bar_and_preserve_history(db):
    snapshot = db.add_bars_to_list([1, 2, 3]).unwrap()
    assert not db.remove_list_bars(snapshot.list_id).unwrap().bars
    assert db.add_bars_to_list([1, 2], snapshot.list_id).succeeded
    assert db.delete_active_list(snapshot.list_id).succeeded
    assert not db.get_silver_bar_lists()
    assert (
        db.conn.execute(
            "SELECT count(*) FROM silver_bars WHERE status='In Stock'"
        ).fetchone()[0]
        == 7
    )
    assert db.conn.execute("SELECT count(*) FROM bar_transfers").fetchone()[0] == 10
