from PyQt5.QtCore import Qt

from silverestimate.ui.models import (
    AvailableSilverBarsTableModel,
    HistorySilverBarsTableModel,
)


def test_management_silver_bar_model_exposes_loaded_and_total_aggregates(qt_app):
    del qt_app
    model = AvailableSilverBarsTableModel()
    model.set_rows(
        [
            {
                "bar_id": 1,
                "estimate_voucher_no": "V001",
                "estimate_note": "Alpha",
                "weight": 10.5,
                "purity": 99.9,
                "fine_weight": 10.489,
                "date_added": "2026-02-15 10:00:00",
                "status": "In Stock",
            },
            {
                "bar_id": 2,
                "estimate_voucher_no": "V002",
                "estimate_note": "Beta",
                "weight": "9.0",
                "purity": 98.0,
                "fine_weight": "8.820",
                "date_added": "2026-02-14 10:00:00",
                "status": "Assigned",
            },
        ],
        total_count=7,
    )

    assert model.loaded_count() == 2
    assert model.total_count() == 7
    assert model.total_weight() == 19.5
    assert model.total_fine_weight() == 19.309


def test_management_silver_bar_model_clear_rows_resets_counts(qt_app):
    del qt_app
    model = AvailableSilverBarsTableModel()
    model.set_rows(
        [
            {
                "bar_id": 1,
                "weight": 10.5,
                "fine_weight": 10.489,
            }
        ],
        total_count=3,
    )

    model.clear_rows()

    assert model.loaded_count() == 0
    assert model.total_count() == 0
    assert model.total_weight() == 0.0
    assert model.total_fine_weight() == 0.0


def test_management_silver_bar_model_sorts_by_voucher_only(qt_app):
    del qt_app
    model = AvailableSilverBarsTableModel()
    model.set_rows(
        [
            {
                "bar_id": 2,
                "estimate_voucher_no": "10",
                "estimate_note": "Zulu",
                "weight": 10.0,
                "purity": 99.0,
                "fine_weight": 9.9,
                "date_added": "2026-02-15 10:00:00",
                "status": "In Stock",
            },
            {
                "bar_id": 3,
                "estimate_voucher_no": "10",
                "estimate_note": "Alpha",
                "weight": 11.0,
                "purity": 99.0,
                "fine_weight": 10.89,
                "date_added": "2026-02-15 11:00:00",
                "status": "In Stock",
            },
            {
                "bar_id": 1,
                "estimate_voucher_no": "2",
                "estimate_note": "Beta",
                "weight": 8.0,
                "purity": 99.0,
                "fine_weight": 7.92,
                "date_added": "2026-02-15 09:00:00",
                "status": "In Stock",
            },
        ]
    )

    model.sort(0, Qt.AscendingOrder)

    assert [model.bar_id_at(row) for row in range(model.rowCount())] == [1, 2, 3]


def test_history_silver_bar_model_sorts_by_voucher_only(qt_app):
    del qt_app
    model = HistorySilverBarsTableModel()
    model.set_rows(
        [
            {
                "bar_id": 2,
                "estimate_voucher_no": "10",
                "estimate_note": "Zulu",
                "weight": 10.0,
                "purity": 99.0,
                "fine_weight": 9.9,
                "date_added": "2026-02-15 10:00:00",
                "status": "Assigned",
                "list_id": 10,
                "list_identifier": "LIST-010",
            },
            {
                "bar_id": 3,
                "estimate_voucher_no": "10",
                "estimate_note": "Alpha",
                "weight": 11.0,
                "purity": 99.0,
                "fine_weight": 10.89,
                "date_added": "2026-02-15 11:00:00",
                "status": "Assigned",
                "list_id": 10,
                "list_identifier": "LIST-010",
            },
            {
                "bar_id": 1,
                "estimate_voucher_no": "2",
                "estimate_note": "Beta",
                "weight": 8.0,
                "purity": 99.0,
                "fine_weight": 7.92,
                "date_added": "2026-02-15 09:00:00",
                "status": "In Stock",
                "list_id": None,
                "list_identifier": None,
            },
        ]
    )

    model.sort(1, Qt.AscendingOrder)

    assert [model.bar_id_at(row) for row in range(model.rowCount())] == [1, 2, 3]
