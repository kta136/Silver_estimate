import logging
from datetime import datetime
from types import SimpleNamespace

import pytest

from silverestimate.infrastructure.item_cache import ItemCacheController
from silverestimate.persistence import schema
from silverestimate.persistence.database_driver import dbapi as sqlite3
from silverestimate.persistence.estimates_repository import EstimatesRepository
from silverestimate.persistence.items_repository import (
    ItemsRepository,
    fetch_item_catalog_page,
)
from silverestimate.persistence.silver_bar_command_repository import (
    SilverBarCommandRepository,
)
from silverestimate.persistence.silver_bar_query_repository import (
    SilverBarQueryRepository,
)
from tests.factories import (
    estimate_totals,
    insert_silver_bar,
    regular_item,
    return_item,
    silver_bar_item,
)


class FakeDB:
    def __init__(self) -> None:
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.cursor = self.conn.cursor()
        self.logger = logging.getLogger("test")
        self.item_cache_controller = ItemCacheController()
        self._c_get_item_by_code = None
        self._sql_get_item_by_code = None
        self._c_insert_estimate_item = None
        self._sql_insert_estimate_item = None
        self.last_error = None

    def _table_exists(self, table_name: str) -> bool:
        self.cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (table_name,),
        )
        return self.cursor.fetchone() is not None

    def _column_exists(self, table_name: str, column_name: str) -> bool:
        if not self._table_exists(table_name):
            return False
        self.cursor.execute(f"PRAGMA table_info({table_name})")
        return any(row["name"] == column_name for row in self.cursor.fetchall())

    def _check_schema_version(self) -> int:
        if not self._table_exists("schema_version"):
            return 0
        self.cursor.execute("SELECT MAX(version) FROM schema_version")
        row = self.cursor.fetchone()
        return row[0] if row and row[0] is not None else 0

    def _update_schema_version(self, new_version: int) -> bool:
        self.cursor.execute(
            "INSERT INTO schema_version (version, applied_date) VALUES (?, ?)",
            (new_version, datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        )
        return True


@pytest.fixture()
def fake_db():
    db = FakeDB()
    schema.run_schema_setup(db)
    yield db
    db.conn.close()


def test_items_repository_roundtrip(fake_db):
    repo = ItemsRepository(fake_db)
    added = repo.add_item(
        "ITM001", "Sample Item", 92.5, "P", 10.0, tunch="92 + wastage"
    )
    assert added
    fetched = repo.get_item_by_code("ITM001")
    assert fetched["name"] == "Sample Item"
    assert fetched["tunch"] == "92 + wastage"


def test_estimate_lookup_keeps_saved_tunch(fake_db):
    items_repo = ItemsRepository(fake_db)
    estimates_repo = EstimatesRepository(fake_db)
    assert items_repo.add_item("REG001", "Original", 92.5, "WT", 10, tunch="91.25%")
    assert estimates_repo.save_estimate_atomic(
        "T-1", "2026-07-19", 75, [regular_item()], [], estimate_totals()
    ).success
    assert items_repo.update_item("REG001", "Changed", 80, "PC", 20, tunch="Market")
    assert (
        estimates_repo.get_estimate_by_voucher("T-1")["items"][0]["tunch"] == "91.25%"
    )


def test_current_schema_setup_revalidates_mandatory_indexes_and_foreign_keys(fake_db):
    statements = []
    fake_db.conn.set_trace_callback(statements.append)

    schema.run_schema_setup(fake_db)

    normalized = [statement.strip().upper() for statement in statements]
    assert any(statement.startswith("BEGIN IMMEDIATE") for statement in normalized)
    assert any("CREATE INDEX" in statement for statement in normalized)
    assert any("FOREIGN_KEY_CHECK" in statement for statement in normalized)
    assert any(statement.startswith("COMMIT") for statement in normalized)


def test_item_catalog_keyset_pages_do_not_duplicate_rows(fake_db):
    repo = ItemsRepository(fake_db)
    result = repo.upsert_item_catalog(
        [
            {
                "code": code,
                "name": f"Item {code}",
                "purity": 90.0,
                "wage_type": "P",
                "wage_rate": 1.0,
            }
            for code in ("A001", "A002", "A003", "B001")
        ]
    )
    assert result == {"inserted": 4, "updated": 0, "deleted": 0, "total": 4}

    first = repo.search_items_page("A", limit=2)
    second = repo.search_items_page("A", cursor=first.next_cursor, limit=2)

    assert first.total == 3
    assert first.has_more is True
    assert [row["code"] for row in first.items] == ["A001", "A002"]
    assert [row["code"] for row in second.items] == ["A003"]
    assert second.next_cursor is None
    assert fake_db.item_cache_controller.get("B001")["name"] == "Item B001"


def test_tunch_search_retains_keyset_pagination():
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.execute(
        "CREATE TABLE items(code, name, tunch, purity, wage_type, wage_rate)"
    )
    connection.executemany(
        "INSERT INTO items VALUES(?, 'Ring', '92.5 + loss', 92.5, 'WT', 10)",
        [("A",), ("B",)],
    )
    first = fetch_item_catalog_page(connection.cursor(), "loss", limit=1)
    second = fetch_item_catalog_page(
        connection.cursor(), "loss", limit=1, page_cursor=first.next_cursor
    )
    assert first.total == 2 and [row["code"] for row in first.items] == ["A"]
    assert [row["code"] for row in second.items] == ["B"]
    assert second.next_cursor is None
    connection.close()


def test_estimate_history_keyset_page_reads_header_totals(fake_db):
    repo = EstimatesRepository(fake_db)
    fake_db.cursor.executemany(
        "INSERT INTO estimates "
        "(voucher_no, voucher_no_int, date, total_gross, total_net) "
        "VALUES (?, ?, '2026-07-15', ?, ?)",
        [
            ("1", 1, 10.0, 9.0),
            ("2", 2, 20.0, 18.0),
            ("3", 3, 30.0, 27.0),
        ],
    )
    fake_db.conn.commit()

    first = repo.get_estimate_history_page(limit=2)
    second = repo.get_estimate_history_page(cursor=first.next_cursor, limit=2)

    assert first.total == 3
    assert [row["voucher_no"] for row in first.items] == ["3", "2"]
    assert first.items[0]["total_gross"] == 30.0
    assert [row["voucher_no"] for row in second.items] == ["1"]


def test_schema_setup_creates_current_schema(fake_db):
    fake_db.cursor.execute("SELECT MAX(version) AS v FROM schema_version")
    row = fake_db.cursor.fetchone()
    assert row["v"] == schema.CURRENT_SCHEMA_VERSION
    assert fake_db._column_exists("items", "tunch")
    columns = {
        column["name"]: column["type"]
        for column in fake_db.conn.execute("PRAGMA table_info(items)").fetchall()
    }
    assert columns["tunch"].upper() == "TEXT"
    assert fake_db._column_exists("estimates", "voucher_no_int")
    assert fake_db._column_exists("estimate_items", "wage_type")
    assert fake_db._column_exists("estimate_items", "line_key")
    assert fake_db._column_exists("silver_bars", "source_line_key")
    fake_db.cursor.execute(
        "SELECT 1 FROM sqlite_master WHERE type='index' "
        "AND name='idx_sbars_status_list_weight_date_id'"
    )
    assert fake_db.cursor.fetchone() is not None


def test_schema_setup_rolls_back_all_domain_changes_when_version_stage_fails():
    class FailingDB(FakeDB):
        def _update_schema_version(self, new_version: int) -> bool:
            raise sqlite3.OperationalError("injected schema creation failure")

    db = FailingDB()
    try:
        with pytest.raises(sqlite3.OperationalError, match="injected"):
            schema.run_schema_setup(db)
        assert db._table_exists("schema_version") is False
        assert db._table_exists("items") is False
    finally:
        db.conn.close()


def test_schema_setup_rejects_historical_versions_without_mutation():
    db = FakeDB()
    try:
        db.cursor.execute("""
            CREATE TABLE schema_version (
                id INTEGER PRIMARY KEY,
                version INTEGER NOT NULL,
                applied_date TEXT NOT NULL
            )
        """)
        db.cursor.execute(
            "INSERT INTO schema_version (version, applied_date) VALUES (?, ?)",
            (7, datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        )
        db.conn.commit()

        with pytest.raises(RuntimeError, match="Unsupported database schema version 7"):
            schema.run_schema_setup(db)
        assert db._check_schema_version() == 7
        assert db._table_exists("items") is False
    finally:
        db.conn.close()


def test_items_repository_returns_plain_dicts(fake_db):
    repo = ItemsRepository(fake_db)
    repo.add_item("NEW123", "New Item", 91.0, "WT", 12.0)

    # simulate prior cache miss
    fake_db.item_cache_controller.invalidate("NEW123")

    fetched = repo.get_item_by_code("NEW123")
    assert isinstance(fetched, dict)
    assert fetched["name"] == "New Item"

    cached = fake_db.item_cache_controller.get("NEW123")
    assert isinstance(cached, dict)

    refetched = repo.get_item_by_code("NEW123")
    assert isinstance(refetched, dict)


def test_items_repository_search_uses_prefix_then_contains_fallback(fake_db):
    repo = ItemsRepository(fake_db)
    repo.add_item("ABC001", "Alpha Brace", 91.0, "WT", 5.0)
    repo.add_item("XABC99", "X-Ray", 91.0, "WT", 5.0)

    prefix_rows = repo.search_items("AB")
    assert [row["code"] for row in prefix_rows] == ["ABC001"]

    fallback_rows = repo.search_items("BC99")
    assert [row["code"] for row in fallback_rows] == ["XABC99"]

    assert repo.search_items("Q") == []


def test_items_repository_batch_fetch_returns_normalized_codes(fake_db):
    repo = ItemsRepository(fake_db)
    repo.add_item("abc001", "Alpha Brace", 91.0, "WT", 5.0)
    repo.add_item("PC001", "Pendant", 88.0, "PC", 12.0)

    rows = repo.get_items_by_codes(["ABC001", "pc001", "missing"])

    assert set(rows.keys()) == {"ABC001", "PC001"}
    assert rows["ABC001"]["name"] == "Alpha Brace"
    assert rows["PC001"]["wage_type"] == "PC"


def test_items_repository_selection_search_ranking_and_limit(fake_db):
    repo = ItemsRepository(fake_db)
    repo.add_item("BAD2", "Metal Ring", 75.0, "WT", 20.0)
    repo.add_item("AD01", "Classic Chain", 91.5, "WT", 12.5)
    repo.add_item("ZZ10", "Adorn Pendant", 88.0, "PC", 3.0)
    repo.add_item("AXAD", "Roadline Anklet", 80.0, "WT", 9.75)

    rows, truncated = repo.search_items_for_selection("AD", limit=3)
    codes = [row["code"] for row in rows]
    assert codes == ["AD01", "ZZ10", "AXAD"]
    assert truncated is True

    rows_full, truncated_full = repo.search_items_for_selection("AD", limit=10)
    codes_full = [row["code"] for row in rows_full]
    assert codes_full == ["AD01", "ZZ10", "AXAD", "BAD2"]
    assert truncated_full is False


def test_estimates_repository_save_and_fetch(fake_db):
    repo = EstimatesRepository(fake_db)
    ItemsRepository(fake_db).add_item("ITM001", "Sample Item", 92.5, "WT", 10.0)
    saved = repo.save_estimate_atomic(
        voucher_no="100",
        date="2025-01-01",
        silver_rate=75000.0,
        regular_items=[
            regular_item(
                code="ITM001",
                name="Sample Item",
                gross=10.0,
                poly=0.0,
                net_wt=10.0,
                purity=92.5,
                wage_rate=10.0,
                pieces=1,
                wage=100.0,
                fine=9.25,
            )
        ],
        return_items=[],
        totals=estimate_totals(
            total_gross=10.0,
            total_net=10.0,
            net_fine=9.25,
            net_wage=100.0,
            note="Test estimate",
        ),
    ).success
    assert saved
    data = repo.get_estimate_by_voucher("100")
    assert data["header"]["voucher_no"] == "100"
    assert len(data["items"]) == 1
    assert data["items"][0]["wage_type"] == "WT"


def test_estimates_repository_returns_first_estimate_date(fake_db):
    repo = EstimatesRepository(fake_db)
    assert repo.get_first_estimate_date() is None

    repo.save_estimate_atomic(
        voucher_no="901",
        date="2025-03-10",
        silver_rate=71000.0,
        regular_items=[],
        return_items=[],
        totals=estimate_totals(
            total_gross=0.0, total_net=0.0, net_fine=0.0, net_wage=0.0
        ),
    )
    repo.save_estimate_atomic(
        voucher_no="902",
        date="2025-01-12",
        silver_rate=71000.0,
        regular_items=[],
        return_items=[],
        totals=estimate_totals(
            total_gross=0.0, total_net=0.0, net_fine=0.0, net_wage=0.0
        ),
    )
    repo.save_estimate_atomic(
        voucher_no="903",
        date="2025-02-05",
        silver_rate=71000.0,
        regular_items=[],
        return_items=[],
        totals=estimate_totals(
            total_gross=0.0, total_net=0.0, net_fine=0.0, net_wage=0.0
        ),
    )

    assert repo.get_first_estimate_date() == "2025-01-12"


def test_estimates_repository_numeric_voucher_order_and_next_value(fake_db):
    repo = EstimatesRepository(fake_db)
    for voucher in ("2", "10", "A1"):
        assert repo.save_estimate_atomic(
            voucher_no=voucher,
            date="2025-03-10",
            silver_rate=71000.0,
            regular_items=[],
            return_items=[],
            totals=estimate_totals(
                total_gross=0.0, total_net=0.0, net_fine=0.0, net_wage=0.0
            ),
        ).success

    headers = repo.get_estimate_history_page(limit=10).items
    ordered = [row["voucher_no"] for row in headers]
    assert ordered[:2] == ["10", "2"]
    assert ordered[-1] == "A1"
    assert repo.generate_voucher_no() == "11"


def test_estimates_repository_generate_voucher_falls_back_when_only_non_numeric(
    fake_db,
):
    repo = EstimatesRepository(fake_db)
    for voucher in ("A-10", "B-20"):
        assert repo.save_estimate_atomic(
            voucher_no=voucher,
            date="2025-03-10",
            silver_rate=71000.0,
            regular_items=[],
            return_items=[],
            totals=estimate_totals(
                total_gross=0.0, total_net=0.0, net_fine=0.0, net_wage=0.0
            ),
        ).success
    assert repo.generate_voucher_no() == "1"


def test_save_estimate_reports_missing_item_code(fake_db):
    repo = EstimatesRepository(fake_db)
    missing_item = regular_item(
        code="MISSING001",
        name="Missing Item",
        gross=1.0,
        poly=0.0,
        net_wt=1.0,
        purity=90.0,
        wage_rate=0.0,
        pieces=1,
        wage=0.0,
        fine=0.9,
    )
    totals = estimate_totals(total_gross=1.0, total_net=1.0, net_fine=0.9, net_wage=0.0)
    saved = repo.save_estimate_atomic(
        voucher_no="404",
        date="2025-01-05",
        silver_rate=71000.0,
        regular_items=[missing_item],
        return_items=[],
        totals=totals,
    ).success
    assert not saved
    assert fake_db.last_error is not None
    assert "MISSING001" in fake_db.last_error


def test_silver_bar_query_unassigned_only_filter(fake_db):
    commands = SilverBarCommandRepository(fake_db)
    queries = SilverBarQueryRepository(fake_db)

    free_bar = insert_silver_bar(fake_db, "U1", 11.0, 99.0)
    assigned_bar = insert_silver_bar(fake_db, "U2", 12.0, 99.0)
    assert commands.add_bars_to_list([assigned_bar], note="Filter List").succeeded

    all_rows = queries.get_silver_bars()
    assert {row["bar_id"] for row in all_rows} == {free_bar, assigned_bar}

    unassigned_rows = queries.get_silver_bars(unassigned_only=True)
    assert {row["bar_id"] for row in unassigned_rows} == {free_bar}


def test_silver_bar_repository_reactivates_an_issued_list(fake_db):
    commands = SilverBarCommandRepository(fake_db)
    first_bar = insert_silver_bar(fake_db, "ISSUE1", 7.5, 99.0)
    second_bar = insert_silver_bar(fake_db, "ISSUE2", 8.5, 98.0)
    snapshot = commands.add_bars_to_list(
        [first_bar, second_bar], note="Issued List"
    ).unwrap()
    list_id = snapshot.list_id
    commands.issue_printed_list(list_id, snapshot.signature).unwrap()

    def list_state():
        issued = fake_db.conn.execute(
            "SELECT issued_date FROM silver_bar_lists WHERE list_id = ?", (list_id,)
        ).fetchone()[0]
        statuses = {
            row[0]
            for row in fake_db.conn.execute(
                "SELECT status FROM silver_bars WHERE list_id = ?", (list_id,)
            )
        }
        return issued, statuses

    issued_date, statuses = list_state()
    assert issued_date is not None
    assert statuses == {"Issued"}

    assert commands.reactivate_list(list_id)
    assert list_state() == (None, {"Assigned"})
    assert commands.reactivate_list(list_id) is False


def test_estimate_repository_load_preserves_item_types(fake_db):
    repo = EstimatesRepository(fake_db)
    items_repo = ItemsRepository(fake_db)
    items_repo.add_item("REG001", "Regular Item", 91.6, "WT", 15.0)
    items_repo.add_item("RET001", "Return Item", 80.0, "WT", 0.0)
    items_repo.add_item("BAR001", "Silver Bar", 99.9, "WT", 0.0)
    voucher = "500"
    regular_payload = regular_item(
        code="REG001",
        name="Regular Item",
        gross=12.0,
        poly=1.0,
        net_wt=11.0,
        purity=91.6,
        wage_rate=15.0,
        pieces=2,
        wage=165.0,
        fine=10.076,
    )
    return_payload = return_item(
        code="RET001",
        name="Return Item",
        gross=2.0,
        poly=0.2,
        net_wt=1.8,
        purity=80.0,
        wage_rate=0.0,
        pieces=1,
        wage=0.0,
        fine=1.44,
    )
    bar_payload = silver_bar_item(
        code="BAR001",
        name="Silver Bar",
        gross=5.0,
        poly=0.0,
        net_wt=5.0,
        purity=99.9,
        wage_rate=0.0,
        pieces=1,
        wage=0.0,
        fine=4.995,
    )
    totals = estimate_totals(
        total_gross=12.0,
        total_net=11.0,
        net_fine=10.076,
        net_wage=165.0,
        note="Test persistence",
    )

    saved = repo.save_estimate_atomic(
        voucher_no=voucher,
        date="2025-03-01",
        silver_rate=68000.0,
        regular_items=[regular_payload],
        return_items=[return_payload, bar_payload],
        totals=totals,
    ).success
    assert saved

    loaded = repo.get_estimate_by_voucher(voucher)
    assert loaded is not None
    items = {item["item_code"]: item for item in loaded["items"]}

    assert items["REG001"]["is_return"] == 0
    assert items["REG001"]["is_silver_bar"] == 0
    assert items["REG001"]["gross"] == pytest.approx(12.0)
    assert items["REG001"]["fine"] == pytest.approx(10.076)

    assert items["RET001"]["is_return"] == 1
    assert items["RET001"]["is_silver_bar"] == 0
    assert items["RET001"]["net_wt"] == pytest.approx(1.8)
    assert items["RET001"]["fine"] == pytest.approx(1.44)

    assert items["BAR001"]["is_return"] == 0
    assert items["BAR001"]["is_silver_bar"] == 1
    assert items["BAR001"]["net_wt"] == pytest.approx(5.0)
    assert items["BAR001"]["fine"] == pytest.approx(4.995)


def test_silver_bar_repository_handles_missing_database_runtime() -> None:
    db = SimpleNamespace(
        conn=None,
        cursor=None,
        logger=logging.getLogger("test.silver-bars.missing-db"),
    )
    commands = SilverBarCommandRepository(db)
    queries = SilverBarQueryRepository(db)

    assert commands.reactivate_list(1) is False
    assert queries.get_silver_bars() == []
    assert commands.delete_bars_for_estimate("1") == (0, set())
    assert commands.cleanup_empty_lists([1]) is None


def test_silver_bar_repository_storage_errors_are_contained(fake_db) -> None:
    class ErrorCursor:
        rowcount = 0
        lastrowid = None

        def execute(self, *_args, **_kwargs):
            raise sqlite3.OperationalError("injected storage fault")

        def executemany(self, *_args, **_kwargs):
            raise sqlite3.OperationalError("injected storage fault")

    fake_db.cursor = ErrorCursor()
    commands = SilverBarCommandRepository(fake_db)
    queries = SilverBarQueryRepository(fake_db)

    assert commands.reactivate_list(1) is False
    assert queries.get_silver_bars() == []
    with pytest.raises(sqlite3.OperationalError, match="injected storage fault"):
        commands.delete_bars_for_estimate("1")
    assert commands.cleanup_empty_lists([1]) is None
