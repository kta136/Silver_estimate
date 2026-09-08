"""Production encrypted query correctness across counts, filters and keyset bounds."""

import pytest

from silverestimate.persistence import schema
from silverestimate.persistence.database_manager import DatabaseManager
from silverestimate.persistence.estimates_repository import fetch_estimate_history_page
from silverestimate.persistence.items_repository import fetch_item_catalog_page
from silverestimate.persistence.silver_bars_queries import (
    build_available_bars_queries,
    build_history_bars_query,
)
from silverestimate.persistence.silver_bars_snapshot_repository import (
    SilverBarsSnapshotRepository,
)


@pytest.fixture
def paging_db(tmp_path):
    db = DatabaseManager(
        str(tmp_path / "paging.db"), "test-pass", device_secret=b"Q" * 32
    )
    with db.conn:
        db.conn.executemany(
            "INSERT INTO estimates(voucher_no,voucher_no_int,date,note) VALUES (?,?,?,?)",
            [
                (code, number, "2026-09-06", "Needle" if i % 2 else "Other")
                for i, (code, number) in enumerate(
                    [
                        ("1", 1),
                        ("02", 2),
                        ("2", 2),
                        ("10", 10),
                        ("A", None),
                        ("Z", None),
                        (str(2**63), None),
                    ]
                )
            ],
        )
        db.conn.execute(
            "INSERT INTO silver_bar_lists(list_identifier,creation_date) VALUES ('List','2026-09-06')"
        )
        db.conn.executemany(
            "INSERT INTO silver_bars(estimate_voucher_no,weight,purity,fine_weight,status,date_added,list_id) VALUES (?,?,?,?,?,?,?)",
            [
                (
                    "02" if i % 2 else "1",
                    10 + i % 3,
                    90 + i % 2,
                    9,
                    ["In Stock", "Assigned", "Issued"][i % 3],
                    [None, "", "2026-01-31", "2026-02-01"][i % 4],
                    None if i % 3 == 0 else 1,
                )
                for i in range(24)
            ],
        )
        db.conn.executemany(
            "INSERT INTO items(code,name) VALUES (?,?)",
            [(f"I{i}", f"Item {i}") for i in range(5)],
        )
    yield db
    db.close()


@pytest.mark.parametrize(
    "filters",
    [
        {},
        {"status_text": "In Stock"},
        {"status_text": "Assigned"},
        {"voucher_term": "needle"},
        {"voucher_term": "02"},
        {"weight_text": "11"},
        {"voucher_term": "needle", "weight_text": "11", "status_text": "Issued"},
        {"weight_text": "invalid"},
    ],
)
def test_history_pages_match_independent_filter_and_date_order(paging_db, filters):
    db = paging_db
    repo = SilverBarsSnapshotRepository(db.open_read_connection)
    expected = []
    for row in db.conn.execute(
        "SELECT sb.*, e.note FROM silver_bars sb LEFT JOIN estimates e ON e.voucher_no=sb.estimate_voucher_no"
    ):
        if filters.get("status_text") and row["status"] != filters["status_text"]:
            continue
        term = filters.get("voucher_term", "").lower()
        if (
            term
            and term not in row["estimate_voucher_no"].lower()
            and term not in row["note"].lower()
        ):
            continue
        weight = filters.get("weight_text")
        if weight and weight != "invalid" and row["weight"] != float(weight):
            continue
        expected.append(dict(row))
    expected.sort(
        key=lambda row: (row["date_added"] or "", row["bar_id"]), reverse=True
    )
    found, cursor = [], None
    for _ in range(30):
        page = repo.search_history_bars_page(**filters, cursor=cursor, limit=2)
        assert page.total == len(expected)
        found.extend(row["bar_id"] for row in page.items)
        if not page.has_more:
            break
        cursor = page.next_cursor
    else:
        pytest.fail("Cursor failed to terminate")
    assert found == [row["bar_id"] for row in expected]
    assert len(found) == len(set(found))


@pytest.mark.parametrize(
    "filters",
    [
        {},
        {"weight_query": 10},
        {"min_purity": 91},
        {"date_range": ("2026-01-01", "2026-02-01")},
    ],
)
def test_available_pages_match_full_filtered_result(paging_db, filters):
    repo = SilverBarsSnapshotRepository(paging_db.open_read_connection)
    expected, total = repo.get_available_bars_page(**filters)
    found, cursor = [], None
    for _ in range(30):
        page = repo.get_available_bars_keyset_page(**filters, cursor=cursor, limit=2)
        assert page.total == total
        found.extend(page.items)
        if not page.has_more:
            break
        cursor = page.next_cursor
    assert found == expected


def test_mixed_voucher_pages_preserve_numeric_null_and_tie_order(paging_db):
    expected = [
        row[0]
        for row in paging_db.conn.execute(
            "SELECT voucher_no FROM estimates ORDER BY COALESCE(voucher_no_int,-1) DESC,voucher_no DESC"
        )
    ]
    found, cursor = [], None
    for _ in range(10):
        page = fetch_estimate_history_page(
            paging_db.conn.cursor(), page_cursor=cursor, limit=2
        )
        found.extend(row["voucher_no"] for row in page.items)
        if not page.has_more:
            break
        cursor = page.next_cursor
    assert found == expected


def test_append_can_skip_counts_without_reusing_stale_totals(paging_db):
    traces = []

    def connect(cancel_event=None):
        conn = paging_db.open_read_connection(cancel_event)
        conn.set_trace_callback(traces.append)
        return conn

    repo = SilverBarsSnapshotRepository(connect)
    first = repo.search_history_bars_page(limit=2)
    traces.clear()
    page = repo.search_history_bars_page(
        cursor=first.next_cursor, limit=2, include_total=False
    )
    assert page.total is None
    assert len(page.items) == 2
    assert not any("COUNT(" in sql.upper() for sql in traces)
    for loader, kwargs in [
        (repo.get_available_bars_keyset_page, {}),
        (repo.get_bars_in_list_keyset_page, {"list_id": 1}),
    ]:
        traces.clear()
        assert loader(**kwargs, limit=2, include_total=False).total is None
        assert not any("COUNT(" in sql.upper() for sql in traces)
    paging_db.conn.set_trace_callback(traces.append)
    traces.clear()
    assert (
        fetch_estimate_history_page(paging_db.conn.cursor(), include_total=False).total
        is None
    )
    assert (
        fetch_item_catalog_page(paging_db.conn.cursor(), "", include_total=False).total
        is None
    )
    assert not any("COUNT(" in sql.upper() for sql in traces)


def test_unfiltered_and_status_counts_do_not_join_display_tables(paging_db):
    traces = []

    def connect(cancel_event=None):
        conn = paging_db.open_read_connection(cancel_event)
        conn.set_trace_callback(traces.append)
        return conn

    repo = SilverBarsSnapshotRepository(connect)
    for status in ("All Statuses", "In Stock"):
        traces.clear()
        repo.search_history_bars_page(status_text=status)
        counts = [sql for sql in traces if "COUNT(*)" in sql.upper()]
        assert len(counts) == 1 and "JOIN" not in counts[0].upper()


def test_order_indexes_upgrade_existing_v9_without_changing_records(paging_db):
    db = paging_db
    names = [
        "idx_estimates_history_order",
        "idx_sbars_history_order",
        "idx_sbars_status_history_order",
        "idx_sbars_available_order",
    ]
    for name in names:
        db.conn.execute(f"DROP INDEX {name}")
    db.conn.commit()
    before = [tuple(row) for row in db.conn.execute("SELECT * FROM silver_bars")]
    schema.run_schema_setup(db)
    assert db._check_schema_version() == 10
    assert before == [
        tuple(row) for row in db.conn.execute("SELECT * FROM silver_bars")
    ]
    statements = [
        build_history_bars_query(),
        build_history_bars_query(status_text="In Stock"),
        build_available_bars_queries(limit=2).query,
    ]
    for statement in statements:
        plan = " ".join(
            str(row[3])
            for row in db.conn.execute(
                "EXPLAIN QUERY PLAN " + statement.query, statement.params
            )
        )
        assert "TEMP B-TREE" not in plan
