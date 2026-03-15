import pytest

from silverestimate.persistence.database_manager import DatabaseManager
from silverestimate.services.item_catalog_transfer import (
    export_item_catalog,
    import_item_catalog,
)
from tests.factories import estimate_totals, regular_item, return_item, silver_bar_item


def test_database_manager_roundtrip(tmp_path, settings_stub):
    db_path = tmp_path / "storage" / "estimation.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)

    manager = DatabaseManager(str(db_path), "test-password")
    try:
        added = manager.items_repo.add_item("ITM001", "Sample Item", 92.5, "WT", 10.0)
        assert added
    finally:
        manager.close()

    assert db_path.exists()

    reopened = DatabaseManager(str(db_path), "test-password")
    try:
        row = reopened.items_repo.get_item_by_code("ITM001")
        assert row is not None
        assert row["name"] == "Sample Item"
    finally:
        reopened.close()

    for store in settings_stub._data.values():
        assert "security/last_temp_db_path" not in store


def test_database_manager_persists_estimates(tmp_path, settings_stub):
    db_path = tmp_path / "storage" / "persist_estimates.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)

    manager = DatabaseManager(str(db_path), "test-password")
    voucher = "910"
    manager.items_repo.add_item("REG001", "Regular", 92.0, "WT", 12.0)
    manager.items_repo.add_item("RET001", "Return", 80.0, "WT", 0.0)
    manager.items_repo.add_item("BAR001", "Bar", 99.9, "WT", 0.0)
    regular_payload = regular_item(
        code="REG001",
        name="Regular",
        gross=15.0,
        poly=1.5,
        net_wt=13.5,
        purity=92.0,
        wage_rate=12.0,
        pieces=3,
        wage=162.0,
        fine=12.42,
    )
    return_payload = return_item(
        code="RET001",
        name="Return",
        gross=2.5,
        poly=0.2,
        net_wt=2.3,
        purity=80.0,
        wage_rate=0.0,
        pieces=1,
        wage=0.0,
        fine=1.84,
    )
    bar_payload = silver_bar_item(
        code="BAR001",
        name="Bar",
        gross=6.0,
        poly=0.0,
        net_wt=6.0,
        purity=99.9,
        wage_rate=0.0,
        pieces=1,
        wage=0.0,
        fine=5.994,
    )
    totals = estimate_totals(
        total_gross=15.0,
        total_net=13.5,
        net_fine=12.42,
        net_wage=162.0,
        note="Persist test",
    )
    saved = manager.estimates_repo.save_estimate_with_returns(
        voucher_no=voucher,
        date="2025-04-01",
        silver_rate=70000.0,
        regular_items=[regular_payload],
        return_items=[return_payload, bar_payload],
        totals=totals,
    )
    assert saved
    manager.close()

    reopened = DatabaseManager(str(db_path), "test-password")
    try:
        loaded = reopened.estimates_repo.get_estimate_by_voucher(voucher)
        assert loaded is not None
        items = {item["item_code"]: item for item in loaded["items"]}

        assert items["REG001"]["is_return"] == 0
        assert items["REG001"]["is_silver_bar"] == 0
        assert items["REG001"]["net_wt"] == pytest.approx(13.5)
        assert items["REG001"]["fine"] == pytest.approx(12.42)

        assert items["RET001"]["is_return"] == 1
        assert items["RET001"]["is_silver_bar"] == 0
        assert items["RET001"]["net_wt"] == pytest.approx(2.3)
        assert items["RET001"]["fine"] == pytest.approx(1.84)

        assert items["BAR001"]["is_return"] == 0
        assert items["BAR001"]["is_silver_bar"] == 1
        assert items["BAR001"]["net_wt"] == pytest.approx(6.0)
        assert items["BAR001"]["fine"] == pytest.approx(5.994)
    finally:
        reopened.close()


def test_database_manager_does_not_retain_plaintext_password(tmp_path, settings_stub):
    db_path = tmp_path / "storage" / "secure_session.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)

    manager = DatabaseManager(str(db_path), "initial-password")
    try:
        assert not hasattr(manager, "password")
        old_key = manager.key
        assert manager.reencrypt_with_new_password("rotated-password") is True
        assert manager.key != old_key
        assert not hasattr(manager, "password")
    finally:
        manager.close()

    reopened = DatabaseManager(str(db_path), "rotated-password")
    try:
        assert reopened is not None
    finally:
        reopened.close()


def test_database_manager_item_catalog_backup_roundtrip(tmp_path, settings_stub):
    db_path = tmp_path / "storage" / "catalog-source.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    backup_path = tmp_path / "catalog.seitems.json"

    source = DatabaseManager(str(db_path), "test-password")
    try:
        assert source.items_repo.add_item("ITM001", "Original", 92.5, "WT", 10.0)
        assert source.items_repo.add_item("ITM002", "Second", 80.0, "P", 5.0)
        exported = export_item_catalog(source, str(backup_path))
        assert exported == 2
    finally:
        source.close()

    target_path = tmp_path / "storage" / "catalog-target.db"
    target = DatabaseManager(str(target_path), "test-password")
    try:
        assert target.items_repo.add_item("ITM001", "Old Name", 70.0, "WT", 1.0)
        assert target.items_repo.add_item("KEEP01", "Keep", 75.0, "WT", 3.0)

        summary = import_item_catalog(target, str(backup_path))

        assert summary == {"inserted": 1, "updated": 1, "deleted": 0, "total": 2}
        assert target.items_repo.get_item_by_code("ITM001") == {
            "code": "ITM001",
            "name": "Original",
            "purity": 92.5,
            "wage_type": "WT",
            "wage_rate": 10.0,
        }
        assert target.items_repo.get_item_by_code("ITM002") == {
            "code": "ITM002",
            "name": "Second",
            "purity": 80.0,
            "wage_type": "PC",
            "wage_rate": 5.0,
        }
        assert target.items_repo.get_item_by_code("KEEP01") == {
            "code": "KEEP01",
            "name": "Keep",
            "purity": 75.0,
            "wage_type": "WT",
            "wage_rate": 3.0,
        }
    finally:
        target.close()


def test_database_manager_item_catalog_restore_can_replace_existing_catalog(
    tmp_path, settings_stub
):
    db_path = tmp_path / "storage" / "catalog-replace-source.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    backup_path = tmp_path / "catalog-replace.seitems.json"

    source = DatabaseManager(str(db_path), "test-password")
    try:
        assert source.items_repo.add_item("ITM001", "Original", 92.5, "WT", 10.0)
        assert source.items_repo.add_item("ITM002", "Second", 80.0, "P", 5.0)
        assert export_item_catalog(source, str(backup_path)) == 2
    finally:
        source.close()

    target_path = tmp_path / "storage" / "catalog-replace-target.db"
    target = DatabaseManager(str(target_path), "test-password")
    try:
        assert target.items_repo.add_item("ITM001", "Old Name", 70.0, "WT", 1.0)
        assert target.items_repo.add_item("DROP01", "Drop Me", 75.0, "WT", 3.0)

        summary = import_item_catalog(
            target,
            str(backup_path),
            replace_existing=True,
        )

        assert summary == {"inserted": 1, "updated": 1, "deleted": 1, "total": 2}
        assert target.items_repo.get_item_by_code("ITM001") == {
            "code": "ITM001",
            "name": "Original",
            "purity": 92.5,
            "wage_type": "WT",
            "wage_rate": 10.0,
        }
        assert target.items_repo.get_item_by_code("ITM002") == {
            "code": "ITM002",
            "name": "Second",
            "purity": 80.0,
            "wage_type": "PC",
            "wage_rate": 5.0,
        }
        assert target.items_repo.get_item_by_code("DROP01") is None
    finally:
        target.close()
