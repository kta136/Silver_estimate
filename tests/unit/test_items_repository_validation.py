import logging
import sqlite3

from silverestimate.persistence.items_repository import ItemsRepository


class _DbStub:
    def __init__(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.cursor = self.conn.cursor()
        self.logger = logging.getLogger("items-repo-test")
        self.item_cache_controller = None
        self.cursor.execute("""
            CREATE TABLE items (
                code TEXT PRIMARY KEY,
                name TEXT,
                purity REAL,
                wage_type TEXT,
                wage_rate REAL
            )
            """)
        self.conn.commit()

    def request_flush(self):
        return None


def test_add_item_rejects_invalid_purity():
    db = _DbStub()
    repo = ItemsRepository(db)

    assert not repo.add_item("BAD1", "Bad", 123.0, "WT", 10.0)
    db.cursor.execute("SELECT COUNT(*) AS c FROM items")
    assert db.cursor.fetchone()["c"] == 0


def test_update_item_rejects_negative_wage_rate():
    db = _DbStub()
    repo = ItemsRepository(db)
    assert repo.add_item("OK1", "Valid", 95.0, "WT", 10.0)

    assert not repo.update_item("OK1", "Still Valid", 95.0, "WT", -1.0)
    db.cursor.execute("SELECT wage_rate FROM items WHERE code = 'OK1'")
    assert db.cursor.fetchone()["wage_rate"] == 10.0
