from PyQt5.QtCore import Qt

from silverestimate.ui.models import EstimateHistoryRow, EstimateHistoryTableModel


def test_estimate_history_table_model_formats_display_values():
    model = EstimateHistoryTableModel()
    model.set_rows(
        [
            EstimateHistoryRow(
                voucher_no="V001",
                date="2026-03-01",
                note="Sample note",
                silver_rate=95.5,
                total_gross=2.75,
                total_net=2.5,
                net_fine=2.25,
                net_wage=100.0,
                grand_total=325.125,
            )
        ]
    )

    assert model.rowCount() == 1
    assert model.headerData(0, Qt.Horizontal, Qt.DisplayRole) == "Voucher No"
    assert model.data(model.index(0, 0), Qt.DisplayRole) == "V001"
    assert model.data(model.index(0, 3), Qt.DisplayRole) == "95.50"
    assert model.data(model.index(0, 4), Qt.DisplayRole) == "2.750"
    assert model.data(model.index(0, 8), Qt.DisplayRole) == "325.12"
    assert model.data(model.index(0, 8), Qt.TextAlignmentRole) == (
        Qt.AlignRight | Qt.AlignVCenter
    )


def test_estimate_history_table_model_sorts_numeric_columns():
    model = EstimateHistoryTableModel()
    model.set_rows(
        [
            EstimateHistoryRow(
                voucher_no="V002",
                date="2026-03-02",
                note="Later",
                silver_rate=90.0,
                total_gross=1.0,
                total_net=0.9,
                net_fine=0.8,
                net_wage=50.0,
                grand_total=122.0,
            ),
            EstimateHistoryRow(
                voucher_no="V001",
                date="2026-03-01",
                note="Earlier",
                silver_rate=95.5,
                total_gross=2.0,
                total_net=1.8,
                net_fine=1.7,
                net_wage=100.0,
                grand_total=262.35,
            ),
        ]
    )

    model.sort(8, Qt.DescendingOrder)
    assert model.row_payload(0).voucher_no == "V001"
    assert model.row_payload(1).voucher_no == "V002"

    model.sort(0, Qt.AscendingOrder)
    assert model.row_payload(0).voucher_no == "V001"
    assert model.row_payload(1).voucher_no == "V002"
