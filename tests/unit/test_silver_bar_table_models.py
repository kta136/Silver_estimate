from PySide6.QtCore import Qt

from silverestimate.ui.models import HistorySilverBarsTableModel


def test_history_silver_bar_model_formats_dates_and_counts_rows(qt_app):
    del qt_app
    model = HistorySilverBarsTableModel()
    model.set_rows(
        [
            {
                "bar_id": 1,
                "estimate_voucher_no": "V001",
                "weight": 10.5,
                "fine_weight": 10.489,
                "date_added": "2026-02-15 10:00:00",
                "status": "In Stock",
            },
            {"bar_id": 2, "weight": 9.0, "fine_weight": 8.82},
        ],
        total_count=7,
    )

    assert model.rowCount() == 2
    assert model.total_count() == 7
    date_index = model.index(0, 7)
    assert model.data(date_index, Qt.ItemDataRole.DisplayRole) == "15/02/2026"
    assert model.data(date_index, Qt.ItemDataRole.ToolTipRole) == "2026-02-15 10:00:00"


def test_history_silver_bar_model_clear_rows_resets_counts(qt_app):
    del qt_app
    model = HistorySilverBarsTableModel()
    model.set_rows([{"bar_id": 1, "weight": 10.5}], total_count=3)

    model.clear_rows()

    assert model.rowCount() == 0
    assert model.total_count() == 0


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

    model.sort(1, Qt.SortOrder.AscendingOrder)

    assert [model.bar_id_at(row) for row in range(model.rowCount())] == [1, 2, 3]
