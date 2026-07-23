import logging
from datetime import datetime
from types import SimpleNamespace

import pytest
from sqlcipher3 import dbapi2 as sqlite3

from silverestimate.infrastructure.item_cache import ItemCacheController
from silverestimate.persistence import schema
from silverestimate.persistence.estimates_repository import EstimatesRepository
from silverestimate.persistence.items_repository import ItemsRepository
from silverestimate.persistence.silver_bars_repository import SilverBarsRepository
from tests.factories import estimate_totals, regular_item, return_item, silver_bar_item


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


def test_estimate_lookup_resolves_current_master_tunch(fake_db):
    items_repo = ItemsRepository(fake_db)
    estimates_repo = EstimatesRepository(fake_db)
    assert items_repo.add_item(
        "LIVE1", "Live Tunch Item", 92.5, "WT", 10.0, tunch="91.25%"
    )
    fake_db.cursor.execute(
        "INSERT INTO estimates (voucher_no, date) VALUES ('T-1', '2026-07-19')"
    )
    fake_db.cursor.execute(
        "INSERT INTO estimate_items (voucher_no, item_code, item_name) "
        "VALUES ('T-1', 'LIVE1', 'Live Tunch Item')"
    )
    fake_db.conn.commit()

    loaded = estimates_repo.get_estimate_by_voucher("T-1")
    assert loaded["items"][0]["tunch"] == "91.25%"

    assert items_repo.update_item(
        "LIVE1", "Live Tunch Item", 92.5, "WT", 10.0, tunch="Market"
    )
    loaded = estimates_repo.get_estimate_by_voucher("T-1")
    assert loaded["items"][0]["tunch"] == "Market"

    assert items_repo.update_item("LIVE1", "Live Tunch Item", 92.5, "WT", 10.0)
    loaded = estimates_repo.get_estimate_by_voucher("T-1")
    assert loaded["items"][0]["tunch"] is None


def test_items_tunch_database_accepts_text(fake_db):
    fake_db.cursor.execute(
        "INSERT INTO items "
        "(code, name, purity, wage_type, wage_rate, tunch) "
        "VALUES ('TEXTT', 'Text Tunch', 90, 'WT', 0, '92 + wastage')"
    )

    row = fake_db.cursor.execute(
        "SELECT tunch, typeof(tunch) AS storage_type FROM items WHERE code='TEXTT'"
    ).fetchone()
    assert (row["tunch"], row["storage_type"]) == ("92 + wastage", "text")


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


def test_schema_setup_creates_current_v8_schema(fake_db):
    fake_db.cursor.execute("SELECT MAX(version) AS v FROM schema_version")
    row = fake_db.cursor.fetchone()
    assert row["v"] == 8
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
    saved = repo.save_estimate_with_returns(
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
    )
    assert saved
    data = repo.get_estimate_by_voucher("100")
    assert data["header"]["voucher_no"] == "100"
    assert len(data["items"]) == 1
    assert data["items"][0]["wage_type"] == "WT"


def test_estimates_repository_history_rows_include_regular_item_aggregates(fake_db):
    repo = EstimatesRepository(fake_db)
    items_repo = ItemsRepository(fake_db)
    assert items_repo.add_item("REG001", "Regular", 92.5, "WT", 10.0)
    assert items_repo.add_item("RET001", "Return", 80.0, "PC", 5.0)

    assert repo.save_estimate_with_returns(
        voucher_no="500",
        date="2025-02-01",
        silver_rate=75000.0,
        regular_items=[
            regular_item(
                code="REG001",
                name="Regular",
                gross=10.0,
                poly=1.0,
                net_wt=9.0,
                purity=92.5,
                wage_rate=10.0,
                pieces=1,
                wage=90.0,
                fine=8.325,
            )
        ],
        return_items=[
            return_item(
                code="RET001",
                name="Return",
                gross=3.0,
                poly=0.5,
                net_wt=2.5,
                purity=80.0,
                wage_rate=5.0,
                pieces=2,
                wage=10.0,
                fine=2.0,
            )
        ],
        totals=estimate_totals(
            total_gross=13.0,
            total_net=11.5,
            net_fine=6.325,
            net_wage=80.0,
            note="History row",
            last_balance_amount=15.0,
        ),
    )

    rows = repo.get_estimate_history_rows(
        date_from="2025-02-01",
        date_to="2025-02-28",
        voucher_search="50",
    )

    assert len(rows) == 1
    row = rows[0]
    assert row["voucher_no"] == "500"
    assert row["total_gross"] == 10.0
    assert row["total_net"] == 9.0
    assert row["note"] == "History row"
    assert row["last_balance_amount"] == 15.0


def test_estimates_repository_returns_first_estimate_date(fake_db):
    repo = EstimatesRepository(fake_db)
    assert repo.get_first_estimate_date() is None

    repo.save_estimate_with_returns(
        voucher_no="901",
        date="2025-03-10",
        silver_rate=71000.0,
        regular_items=[],
        return_items=[],
        totals=estimate_totals(
            total_gross=0.0, total_net=0.0, net_fine=0.0, net_wage=0.0
        ),
    )
    repo.save_estimate_with_returns(
        voucher_no="902",
        date="2025-01-12",
        silver_rate=71000.0,
        regular_items=[],
        return_items=[],
        totals=estimate_totals(
            total_gross=0.0, total_net=0.0, net_fine=0.0, net_wage=0.0
        ),
    )
    repo.save_estimate_with_returns(
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
        assert repo.save_estimate_with_returns(
            voucher_no=voucher,
            date="2025-03-10",
            silver_rate=71000.0,
            regular_items=[],
            return_items=[],
            totals=estimate_totals(
                total_gross=0.0, total_net=0.0, net_fine=0.0, net_wage=0.0
            ),
        )

    headers = repo.get_estimate_headers()
    ordered = [row["voucher_no"] for row in headers]
    assert ordered[:2] == ["10", "2"]
    assert ordered[-1] == "A1"
    assert repo.generate_voucher_no() == "11"


def test_get_estimates_uses_bulk_item_query(fake_db):
    repo = EstimatesRepository(fake_db)
    items_repo = ItemsRepository(fake_db)
    assert items_repo.add_item("ITM001", "Sample Item", 92.5, "WT", 10.0)

    for voucher_no, gross in (("100", 10.0), ("101", 12.0)):
        assert repo.save_estimate_with_returns(
            voucher_no=voucher_no,
            date="2025-01-01",
            silver_rate=75000.0,
            regular_items=[
                regular_item(
                    code="ITM001",
                    name="Sample Item",
                    gross=gross,
                    poly=0.0,
                    net_wt=gross,
                    purity=92.5,
                    wage_rate=10.0,
                    pieces=1,
                    wage=gross * 10.0,
                    fine=gross * 0.925,
                )
            ],
            return_items=[],
            totals=estimate_totals(
                total_gross=gross,
                total_net=gross,
                net_fine=gross * 0.925,
                net_wage=gross * 10.0,
            ),
        )

    statements: list[str] = []
    fake_db.conn.set_trace_callback(statements.append)
    try:
        estimates = repo.get_estimates()
    finally:
        fake_db.conn.set_trace_callback(None)

    assert len(estimates) == 2
    item_queries_bulk = [
        stmt
        for stmt in statements
        if "from estimate_items ei" in stmt.lower()
        and "ei.voucher_no in" in stmt.lower()
    ]
    item_queries_per_voucher = [
        stmt
        for stmt in statements
        if "from estimate_items ei" in stmt.lower()
        and "ei.voucher_no =" in stmt.lower()
    ]
    assert len(item_queries_bulk) == 1
    assert item_queries_per_voucher == []


def test_estimates_repository_generate_voucher_falls_back_when_only_non_numeric(
    fake_db,
):
    repo = EstimatesRepository(fake_db)
    for voucher in ("A-10", "B-20"):
        assert repo.save_estimate_with_returns(
            voucher_no=voucher,
            date="2025-03-10",
            silver_rate=71000.0,
            regular_items=[],
            return_items=[],
            totals=estimate_totals(
                total_gross=0.0, total_net=0.0, net_fine=0.0, net_wage=0.0
            ),
        )
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
    saved = repo.save_estimate_with_returns(
        voucher_no="404",
        date="2025-01-05",
        silver_rate=71000.0,
        regular_items=[missing_item],
        return_items=[],
        totals=totals,
    )
    assert not saved
    assert fake_db.last_error is not None
    assert "MISSING001" in fake_db.last_error


def test_estimate_delete_cleans_silver_bars(fake_db):
    est_repo = EstimatesRepository(fake_db)
    silver_repo = SilverBarsRepository(fake_db)
    est_repo.save_estimate_with_returns(
        voucher_no="200",
        date="2025-01-02",
        silver_rate=76000.0,
        regular_items=[],
        return_items=[],
        totals=estimate_totals(
            total_gross=0.0, total_net=0.0, net_fine=0.0, net_wage=0.0
        ),
    )
    bar_id = silver_repo.add_silver_bar("200", 5.0, 99.9)
    assert bar_id is not None
    list_id = silver_repo.create_list("Auto List")
    assert list_id is not None
    assert silver_repo.assign_bar_to_list(bar_id, list_id, perform_commit=True)
    deleted = est_repo.delete_single_estimate("200")
    assert deleted
    remaining_bars = silver_repo.get_silver_bars(estimate_voucher_no="200")
    assert remaining_bars == []


def test_silver_bar_assignment_cycle(fake_db):
    repo = SilverBarsRepository(fake_db)
    list_id = repo.create_list("Test List")
    assert list_id is not None
    bar_id = repo.add_silver_bar("300", 7.5, 99.0)
    assert bar_id is not None
    assert repo.assign_bar_to_list(bar_id, list_id)
    bars_in_list = repo.get_bars_in_list(list_id)
    assert len(bars_in_list) == 1
    assert repo.remove_bar_from_list(bar_id)
    bars_in_list = repo.get_bars_in_list(list_id)
    assert bars_in_list == []


def test_silver_bar_bulk_assignment_and_removal(fake_db):
    repo = SilverBarsRepository(fake_db)
    list_id = repo.create_list("Bulk List")
    assert list_id is not None

    bar_ids = []
    for idx in range(3):
        bar_id = repo.add_silver_bar(f"BULK{idx}", float(idx + 1), 99.0)
        assert bar_id is not None
        bar_ids.append(bar_id)

    assigned, failed_assign = repo.assign_bars_to_list_bulk(bar_ids, list_id)
    assert assigned == 3
    assert failed_assign == []

    bars_in_list = repo.get_bars_in_list(list_id)
    assert {row["bar_id"] for row in bars_in_list} == set(bar_ids)

    removed, failed_remove = repo.remove_bars_from_list_bulk(bar_ids)
    assert removed == 3
    assert failed_remove == []

    bars_in_list_after = repo.get_bars_in_list(list_id)
    assert bars_in_list_after == []


def test_silver_bar_bulk_assignment_reports_failures(fake_db):
    repo = SilverBarsRepository(fake_db)
    list_id = repo.create_list("Bulk Fail List")
    assert list_id is not None

    bar_id = repo.add_silver_bar("BULKFAIL", 5.0, 99.0)
    assert bar_id is not None
    assert repo.assign_bar_to_list(bar_id, list_id)

    assigned, failed = repo.assign_bars_to_list_bulk([bar_id, 999999], list_id)
    assert assigned == 0
    assert set(failed) == {bar_id, 999999}


def test_silver_bar_query_limit_and_offset(fake_db):
    repo = SilverBarsRepository(fake_db)
    bar_ids = []
    for i in range(1, 5):
        bar_id = repo.add_silver_bar(f"V{i}", float(i), 99.0)
        assert bar_id is not None
        bar_ids.append(bar_id)

    limited = repo.get_silver_bars(limit=2)
    assert len(limited) == 2
    # get_silver_bars orders by date_added DESC, bar_id DESC
    assert [row["bar_id"] for row in limited] == sorted(
        [row["bar_id"] for row in limited], reverse=True
    )

    offset_rows = repo.get_silver_bars(limit=1, offset=1)
    assert len(offset_rows) == 1
    assert offset_rows[0]["bar_id"] == limited[1]["bar_id"]


def test_silver_bar_query_unassigned_only_filter(fake_db):
    repo = SilverBarsRepository(fake_db)
    list_id = repo.create_list("Filter List")
    assert list_id is not None

    free_bar = repo.add_silver_bar("U1", 11.0, 99.0)
    assigned_bar = repo.add_silver_bar("U2", 12.0, 99.0)
    assert free_bar is not None
    assert assigned_bar is not None
    assert repo.assign_bar_to_list(assigned_bar, list_id)

    all_rows = repo.get_silver_bars()
    assert {row["bar_id"] for row in all_rows} == {free_bar, assigned_bar}

    unassigned_rows = repo.get_silver_bars(unassigned_only=True)
    assert {row["bar_id"] for row in unassigned_rows} == {free_bar}


def test_silver_bar_sync_for_estimate_updates_and_inserts_in_one_call(fake_db):
    repo = SilverBarsRepository(fake_db)
    first = repo.add_silver_bar("SYNC1", 5.0, 99.0)
    second = repo.add_silver_bar("SYNC1", 6.0, 99.0)
    assert first is not None
    assert second is not None

    added, failed = repo.sync_silver_bars_for_estimate(
        "SYNC1",
        [
            {"weight": 5.5, "purity": 99.5},
            {"weight": 6.0, "purity": 99.0},
            {"weight": 7.0, "purity": 98.0},
        ],
    )

    assert added == 1
    assert failed == 0
    rows = repo.get_silver_bars_for_estimate("SYNC1")
    assert len(rows) == 3
    assert float(rows[0]["weight"]) == pytest.approx(5.5)
    assert float(rows[0]["purity"]) == pytest.approx(99.5)
    assert float(rows[2]["weight"]) == pytest.approx(7.0)
    assert float(rows[2]["purity"]) == pytest.approx(98.0)


def test_silver_bar_sync_for_estimate_uses_line_key_instead_of_row_order(fake_db):
    repo = SilverBarsRepository(fake_db)

    added, failed = repo.sync_silver_bars_for_estimate(
        "SYNCKEY",
        [
            {"line_key": "line-one", "weight": 5.0, "purity": 99.0},
            {"line_key": "line-two", "weight": 6.0, "purity": 98.0},
        ],
    )
    assert added == 2
    assert failed == 0

    added, failed = repo.sync_silver_bars_for_estimate(
        "SYNCKEY",
        [
            {"line_key": "line-two", "weight": 6.5, "purity": 98.5},
            {"line_key": "line-one", "weight": 5.0, "purity": 99.0},
        ],
    )

    assert added == 0
    assert failed == 0
    rows = {
        row["source_line_key"]: row
        for row in repo.get_silver_bars_for_estimate("SYNCKEY")
    }
    assert float(rows["line-one"]["weight"]) == pytest.approx(5.0)
    assert float(rows["line-one"]["purity"]) == pytest.approx(99.0)
    assert float(rows["line-two"]["weight"]) == pytest.approx(6.5)
    assert float(rows["line-two"]["purity"]) == pytest.approx(98.5)


def test_silver_bar_sync_for_estimate_does_not_mutate_assigned_bar_values(fake_db):
    repo = SilverBarsRepository(fake_db)
    added, failed = repo.sync_silver_bars_for_estimate(
        "SYNCASSIGN",
        [{"line_key": "line-a", "weight": 7.0, "purity": 99.0}],
    )
    assert added == 1
    assert failed == 0

    rows = repo.get_silver_bars_for_estimate("SYNCASSIGN")
    assert len(rows) == 1
    bar_id = int(rows[0]["bar_id"])
    list_id = repo.create_list("Assigned list")
    assert list_id is not None
    assert repo.assign_bar_to_list(bar_id, list_id)

    added, failed = repo.sync_silver_bars_for_estimate(
        "SYNCASSIGN",
        [{"line_key": "line-a", "weight": 7.5, "purity": 98.0}],
    )

    assert added == 0
    assert failed == 1
    row = repo.get_silver_bars_for_estimate("SYNCASSIGN")[0]
    assert float(row["weight"]) == pytest.approx(7.0)
    assert float(row["purity"]) == pytest.approx(99.0)


def test_silver_bar_list_query_limit_and_offset(fake_db):
    repo = SilverBarsRepository(fake_db)
    list_id = repo.create_list("Limited List")
    assert list_id is not None

    created = []
    for i in range(1, 5):
        bar_id = repo.add_silver_bar(f"L{i}", float(i), 98.5)
        assert bar_id is not None
        assert repo.assign_bar_to_list(bar_id, list_id)
        created.append(bar_id)

    limited = repo.get_bars_in_list(list_id, limit=2)
    assert len(limited) == 2
    # get_bars_in_list orders by bar_id ASC
    assert [row["bar_id"] for row in limited] == sorted(
        [row["bar_id"] for row in limited]
    )

    offset_rows = repo.get_bars_in_list(list_id, limit=1, offset=1)
    assert len(offset_rows) == 1
    assert offset_rows[0]["bar_id"] == limited[1]["bar_id"]


def test_silver_bar_keyset_pages_preserve_stable_order(fake_db):
    repo = SilverBarsRepository(fake_db)
    created = [
        repo.add_silver_bar(f"PAGE-{index}", float(index), 99.0)
        for index in range(1, 5)
    ]
    assert all(bar_id is not None for bar_id in created)

    first = repo.get_available_bars_keyset_page(limit=2)
    second = repo.get_available_bars_keyset_page(
        cursor=first.next_cursor,
        limit=2,
    )

    ids = [row["bar_id"] for row in (*first.items, *second.items)]
    assert first.total == 4
    assert len(ids) == len(set(ids)) == 4
    assert ids == sorted(ids, reverse=True)


def test_silver_bar_repository_available_page_and_history_search(fake_db):
    repo = SilverBarsRepository(fake_db)
    list_id = repo.create_list("Page List")
    assert list_id is not None

    free_bar = repo.add_silver_bar("PAGE1", 10.0, 99.0)
    assigned_bar = repo.add_silver_bar("PAGE2", 11.0, 98.0)
    assert free_bar is not None
    assert assigned_bar is not None
    assert repo.assign_bar_to_list(assigned_bar, list_id)

    available_rows, total_count = repo.get_available_bars_page(limit=10)
    assert total_count == 1
    assert [row["bar_id"] for row in available_rows] == [free_bar]

    history_rows = repo.search_history_bars(
        voucher_term="PAGE2",
        weight_text="11.0",
        status_text="Assigned",
        limit=2000,
    )
    assert [row["bar_id"] for row in history_rows] == [assigned_bar]


def test_silver_bar_repository_counts_rows_by_list_and_cycles_issue_state(fake_db):
    repo = SilverBarsRepository(fake_db)
    list_id = repo.create_list("Issued List")
    assert list_id is not None

    first_bar = repo.add_silver_bar("ISSUE1", 7.5, 99.0)
    second_bar = repo.add_silver_bar("ISSUE2", 8.5, 98.0)
    assert first_bar is not None
    assert second_bar is not None
    assert repo.assign_bar_to_list(first_bar, list_id)
    assert repo.assign_bar_to_list(second_bar, list_id)

    assert repo.count_bars_by_list_ids([list_id, 999999]) == {list_id: 2}

    issued_at = "2026-02-27 09:30:00"
    assert repo.mark_list_as_issued(list_id, issued_at)
    details = repo.get_list_details(list_id)
    assert details["issued_date"] == issued_at
    assert {row["status"] for row in repo.get_bars_in_list(list_id)} == {"Issued"}

    assert repo.reactivate_list(list_id)
    details = repo.get_list_details(list_id)
    assert details["issued_date"] is None
    assert {row["status"] for row in repo.get_bars_in_list(list_id)} == {"Assigned"}


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

    saved = repo.save_estimate_with_returns(
        voucher_no=voucher,
        date="2025-03-01",
        silver_rate=68000.0,
        regular_items=[regular_payload],
        return_items=[return_payload, bar_payload],
        totals=totals,
    )
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


def test_save_estimate_accepts_mixed_case_item_codes(fake_db):
    repo = EstimatesRepository(fake_db)
    items_repo = ItemsRepository(fake_db)
    items_repo.add_item("mix001", "Mixed Item", 92.5, "WT", 10.0)

    payload = regular_item(
        code="MIX001",
        name="Mixed Item",
        gross=10.0,
        poly=0.0,
        net_wt=10.0,
        purity=92.5,
        wage_rate=10.0,
        pieces=1,
        wage=100.0,
        fine=9.25,
    )
    totals = estimate_totals(
        total_gross=10.0, total_net=10.0, net_fine=9.25, net_wage=100.0
    )

    saved = repo.save_estimate_with_returns(
        voucher_no="405",
        date="2025-01-06",
        silver_rate=72000.0,
        regular_items=[payload],
        return_items=[],
        totals=totals,
    )

    assert saved
    assert fake_db.last_error is None


def test_silver_bar_repository_handles_missing_database_runtime() -> None:
    db = SimpleNamespace(
        conn=None,
        cursor=None,
        logger=logging.getLogger("test.silver-bars.missing-db"),
    )
    repo = SilverBarsRepository(db)

    assert repo.generate_list_identifier().startswith("ERR-L-")
    assert repo.create_list("offline") is None
    assert repo.get_lists() == []
    assert repo.get_list_details(1) is None
    assert repo.get_list_details_result(1).succeeded is False
    assert repo.update_list_note(1, "note") is False
    assert repo.mark_list_as_issued(1) is False
    assert repo.reactivate_list(1) is False
    assert repo.delete_list(1) == (False, "No database connection")
    assert repo.delete_list_result(1).succeeded is False
    assert repo.assign_bar_to_list(1, 1) is False
    assert repo.assign_bars_to_list_bulk([1], 1) == (0, [])
    assert repo.remove_bar_from_list(1) is False
    assert repo.remove_bars_from_list_bulk([1]) == (0, [])
    assert repo.get_available_bars_page() == ([], 0)
    assert repo.get_available_bars_keyset_page().items == ()
    assert repo.get_bars_in_list_page(1) == ([], 0)
    assert repo.get_bars_in_list_keyset_page(1).items == ()
    assert repo.get_bars_in_list(1) == []
    assert repo.get_available_bars() == []
    assert repo.search_history_bars() == []
    assert repo.search_history_bars_page().items == ()
    assert repo.count_bars_by_list_ids([1]) == {}
    assert repo.get_silver_bars_for_estimate("1") == []
    assert repo.sync_silver_bars_for_estimate("1", []) == (0, 0)
    assert repo.add_silver_bar("1", 1.0, 99.9) is None
    assert repo.get_silver_bars() == []
    assert repo.delete_bars_for_estimate("1") == (0, set())
    assert repo.cleanup_empty_lists([1]) is None


def test_silver_bar_repository_storage_errors_are_contained(fake_db) -> None:
    class ErrorCursor:
        rowcount = 0
        lastrowid = None

        def execute(self, *_args, **_kwargs):
            raise sqlite3.OperationalError("injected storage fault")

        def executemany(self, *_args, **_kwargs):
            raise sqlite3.OperationalError("injected storage fault")

    fake_db.cursor = ErrorCursor()
    repo = SilverBarsRepository(fake_db)

    assert repo.generate_list_identifier().startswith("L-")
    assert repo.create_list("fault") is None
    assert repo.get_lists() == []
    assert repo.get_list_details(1) is None
    assert repo.update_list_note(1, "fault") is False
    assert repo.mark_list_as_issued(1) is False
    assert repo.reactivate_list(1) is False
    deleted, message = repo.delete_list(1)
    assert deleted is False
    assert "injected storage fault" in message
    assert repo.assign_bar_to_list(1, 1) is False
    assert repo.assign_bars_to_list_bulk([1], 1) == (0, [1])
    assert repo.remove_bar_from_list(1) is False
    assert repo.remove_bars_from_list_bulk([1]) == (0, [1])
    assert repo.get_available_bars_page() == ([], 0)
    with pytest.raises(sqlite3.OperationalError, match="injected storage fault"):
        repo.get_available_bars_keyset_page()
    assert repo.get_bars_in_list_page(1) == ([], 0)
    with pytest.raises(sqlite3.OperationalError, match="injected storage fault"):
        repo.get_bars_in_list_keyset_page(1)
    assert repo.get_available_bars() == []
    assert repo.search_history_bars() == []
    with pytest.raises(sqlite3.OperationalError, match="injected storage fault"):
        repo.search_history_bars_page()
    assert repo.count_bars_by_list_ids([1]) == {}
    assert repo.get_silver_bars_for_estimate("1") == []
    assert repo.sync_silver_bars_for_estimate("1", [{"weight": 1, "purity": 99}]) == (
        0,
        1,
    )
    assert repo.add_silver_bar("1", 1.0, 99.9) is None
    assert repo.get_silver_bars() == []
    with pytest.raises(sqlite3.OperationalError, match="injected storage fault"):
        repo.delete_bars_for_estimate("1")
    assert repo.cleanup_empty_lists([1]) is None


def test_silver_bar_repository_exercises_edge_outcomes(fake_db) -> None:
    repo = SilverBarsRepository(fake_db)
    list_id = repo.create_list("edge cases")
    assert list_id is not None

    fake_db.cursor.execute(
        "UPDATE silver_bar_lists SET list_identifier = 'malformed' WHERE list_id = ?",
        (list_id,),
    )
    assert repo.generate_list_identifier().endswith("-001")
    assert repo.update_list_note(-1, "missing") is False
    assert repo.mark_list_as_issued(-1) is False
    assert repo.reactivate_list(-1) is False
    assert repo.assign_bar_to_list(-1, list_id) is False

    bar_id = repo.add_silver_bar("edge", 2.5, 95.0)
    assert bar_id is not None
    assert repo.assign_bar_to_list(bar_id, -1) is False
    assert repo.assign_bars_to_list_bulk([], list_id) == (0, [])
    assert repo.assign_bars_to_list_bulk([bar_id], -1) == (0, [bar_id])
    assert repo.assign_bars_to_list_bulk([-1, "bad", bar_id, bar_id], list_id) == (
        1,
        [],
    )
    assert repo.remove_bars_from_list_bulk([]) == (0, [])
    assert repo.remove_bars_from_list_bulk([-1, "bad"]) == (0, [])
    assert repo.remove_bars_from_list_bulk([bar_id, 999999]) == (1, [999999])
    assert repo.remove_bar_from_list(bar_id) is False

    result = repo.delete_list(999999)
    assert result == (False, "List not found")
    typed = repo.delete_list_result(999999)
    assert typed.succeeded is False

    rows = repo.get_silver_bars(
        status="In Stock",
        weight_query="invalid",
        estimate_voucher_no="edge",
        unassigned_only=True,
        min_purity="invalid",
        max_purity="invalid",
        date_range=("2000-01-01", "2099-01-01"),
        limit=1,
        offset=1,
    )
    assert rows == []
    assert repo.count_bars_by_list_ids([]) == {}
    assert repo.get_silver_bars_for_estimate("") == []

    added, failed = repo.sync_silver_bars_for_estimate(
        "edge-sync",
        [
            {"weight": object(), "purity": 99},
            {"weight": 1, "purity": 99, "line_key": "same"},
            {"weight": 2, "purity": 98, "line_key": "same"},
        ],
    )
    assert (added, failed) == (1, 2)
