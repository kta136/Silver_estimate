import sqlite3
import logging
from datetime import datetime
from typing import Any, Optional

import pytest

from silverestimate.persistence import migrations
from silverestimate.persistence.items_repository import ItemsRepository
from silverestimate.infrastructure.item_cache import ItemCacheController
from silverestimate.persistence.estimates_repository import EstimatesRepository
from silverestimate.persistence.silver_bars_repository import SilverBarsRepository


class FakeDB:
    def __init__(self) -> None:
        self.conn = sqlite3.connect(':memory:')
        self.conn.row_factory = sqlite3.Row
        self.cursor = self.conn.cursor()
        self.logger = logging.getLogger('test')
        self.item_cache_controller = ItemCacheController()
        self._c_get_item_by_code = None
        self._sql_get_item_by_code = None
        self._c_insert_estimate_item = None
        self._sql_insert_estimate_item = None
        self._flush_requested = False

    def _table_exists(self, table_name: str) -> bool:
        self.cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table_name,))
        return self.cursor.fetchone() is not None

    def _column_exists(self, table_name: str, column_name: str) -> bool:
        if not self._table_exists(table_name):
            return False
        self.cursor.execute(f"PRAGMA table_info({table_name})")
        return any(row['name'] == column_name for row in self.cursor.fetchall())

    def _check_schema_version(self) -> int:
        if not self._table_exists('schema_version'):
            self.cursor.execute('''
                CREATE TABLE schema_version (
                    id INTEGER PRIMARY KEY,
                    version INTEGER NOT NULL,
                    applied_date TEXT NOT NULL
                )
            ''')
            self.cursor.execute(
                'INSERT INTO schema_version (version, applied_date) VALUES (?, ?)',
                (0, datetime.now().strftime('%Y-%m-%d %H:%M:%S')),
            )
            self.conn.commit()
            return 0
        self.cursor.execute('SELECT MAX(version) FROM schema_version')
        row = self.cursor.fetchone()
        return row[0] if row and row[0] is not None else 0

    def _update_schema_version(self, new_version: int) -> bool:
        self.cursor.execute(
            'INSERT INTO schema_version (version, applied_date) VALUES (?, ?)',
            (new_version, datetime.now().strftime('%Y-%m-%d %H:%M:%S')),
        )
        self.conn.commit()
        return True

    def request_flush(self) -> None:
        self._flush_requested = True


@pytest.fixture()
def fake_db():
    db = FakeDB()
    migrations.run_schema_setup(db)
    yield db
    db.conn.close()


def test_items_repository_roundtrip(fake_db):
    repo = ItemsRepository(fake_db)
    added = repo.add_item('ITM001', 'Sample Item', 92.5, 'P', 10.0)
    assert added
    fetched = repo.get_item_by_code('ITM001')
    assert fetched['name'] == 'Sample Item'
    assert fake_db._flush_requested


def test_estimates_repository_save_and_fetch(fake_db):
    repo = EstimatesRepository(fake_db)
    saved = repo.save_estimate_with_returns(
        voucher_no='100',
        date='2025-01-01',
        silver_rate=75000.0,
        regular_items=[{
            'code': 'ITM001',
            'name': 'Sample Item',
            'gross': 10.0,
            'poly': 0.0,
            'net_wt': 10.0,
            'purity': 92.5,
            'wage_rate': 10.0,
            'pieces': 1,
            'wage': 100.0,
            'fine': 9.25,
        }],
        return_items=[],
        totals={
            'total_gross': 10.0,
            'total_net': 10.0,
            'net_fine': 9.25,
            'net_wage': 100.0,
            'note': 'Test estimate',
        },
    )
    assert saved
    data = repo.get_estimate_by_voucher('100')
    assert data['header']['voucher_no'] == '100'
    assert len(data['items']) == 1


def test_estimate_delete_cleans_silver_bars(fake_db):
    est_repo = EstimatesRepository(fake_db)
    silver_repo = SilverBarsRepository(fake_db)
    est_repo.save_estimate_with_returns(
        voucher_no='200',
        date='2025-01-02',
        silver_rate=76000.0,
        regular_items=[],
        return_items=[],
        totals={
            'total_gross': 0.0,
            'total_net': 0.0,
            'net_fine': 0.0,
            'net_wage': 0.0,
        },
    )
    bar_id = silver_repo.add_silver_bar('200', 5.0, 99.9)
    assert bar_id is not None
    list_id = silver_repo.create_list('Auto List')
    assert list_id is not None
    assert silver_repo.assign_bar_to_list(bar_id, list_id, perform_commit=True)
    deleted = est_repo.delete_single_estimate('200')
    assert deleted
    remaining_bars = silver_repo.get_silver_bars(estimate_voucher_no='200')
    assert remaining_bars == []


def test_silver_bar_assignment_cycle(fake_db):
    repo = SilverBarsRepository(fake_db)
    list_id = repo.create_list('Test List')
    assert list_id is not None
    bar_id = repo.add_silver_bar('300', 7.5, 99.0)
    assert bar_id is not None
    assert repo.assign_bar_to_list(bar_id, list_id)
    bars_in_list = repo.get_bars_in_list(list_id)
    assert len(bars_in_list) == 1
    assert repo.remove_bar_from_list(bar_id)
    bars_in_list = repo.get_bars_in_list(list_id)
    assert bars_in_list == []

def test_estimate_repository_load_preserves_item_types(fake_db):
    repo = EstimatesRepository(fake_db)
    voucher = '500'
    regular = {
        'code': 'REG001',
        'name': 'Regular Item',
        'gross': 12.0,
        'poly': 1.0,
        'net_wt': 11.0,
        'purity': 91.6,
        'wage_rate': 15.0,
        'pieces': 2,
        'wage': 165.0,
        'fine': 10.076,
    }
    return_item = {
        'code': 'RET001',
        'name': 'Return Item',
        'gross': 2.0,
        'poly': 0.2,
        'net_wt': 1.8,
        'purity': 80.0,
        'wage_rate': 0.0,
        'pieces': 1,
        'wage': 0.0,
        'fine': 1.44,
        'is_return': True,
    }
    bar_item = {
        'code': 'BAR001',
        'name': 'Silver Bar',
        'gross': 5.0,
        'poly': 0.0,
        'net_wt': 5.0,
        'purity': 99.9,
        'wage_rate': 0.0,
        'pieces': 1,
        'wage': 0.0,
        'fine': 4.995,
        'is_return': False,
        'is_silver_bar': True,
    }
    totals = {
        'total_gross': 12.0,
        'total_net': 11.0,
        'net_fine': 10.076,
        'net_wage': 165.0,
        'note': 'Test persistence',
    }

    saved = repo.save_estimate_with_returns(
        voucher_no=voucher,
        date='2025-03-01',
        silver_rate=68000.0,
        regular_items=[regular],
        return_items=[return_item, bar_item],
        totals=totals,
    )
    assert saved

    loaded = repo.get_estimate_by_voucher(voucher)
    assert loaded is not None
    items = {item['item_code']: item for item in loaded['items']}

    assert items['REG001']['is_return'] == 0
    assert items['REG001']['is_silver_bar'] == 0
    assert items['REG001']['gross'] == pytest.approx(12.0)
    assert items['REG001']['fine'] == pytest.approx(10.076)

    assert items['RET001']['is_return'] == 1
    assert items['RET001']['is_silver_bar'] == 0
    assert items['RET001']['net_wt'] == pytest.approx(1.8)
    assert items['RET001']['fine'] == pytest.approx(1.44)

    assert items['BAR001']['is_return'] == 0
    assert items['BAR001']['is_silver_bar'] == 1
    assert items['BAR001']['net_wt'] == pytest.approx(5.0)
    assert items['BAR001']['fine'] == pytest.approx(4.995)
