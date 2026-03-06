from PyQt5.QtCore import Qt

from silverestimate.ui.models import ItemMasterTableModel


def test_item_master_table_model_exposes_headers_and_tooltips():
    model = ItemMasterTableModel()

    assert model.headerData(0, Qt.Horizontal, Qt.DisplayRole) == "Code"
    assert model.headerData(1, Qt.Horizontal, Qt.DisplayRole) == "Name"
    assert model.headerData(2, Qt.Horizontal, Qt.ToolTipRole) == "Default Purity"


def test_item_master_table_model_loads_rows_and_sorts_numeric_columns():
    model = ItemMasterTableModel()
    model.set_rows(
        [
            {
                "code": "B2",
                "name": "Bracelet",
                "purity": 80.0,
                "wage_type": "WT",
                "wage_rate": 15.0,
            },
            {
                "code": "A1",
                "name": "Anklet",
                "purity": 92.5,
                "wage_type": "PC",
                "wage_rate": 10.0,
            },
        ]
    )

    assert model.rowCount() == 2
    assert model.data(model.index(0, 0), Qt.DisplayRole) == "B2"
    assert model.data(model.index(1, 2), Qt.DisplayRole) == "92.5"

    model.sort(2, Qt.AscendingOrder)
    assert model.row_payload(0)["code"] == "B2"
    assert model.row_payload(1)["code"] == "A1"

    model.sort(4, Qt.DescendingOrder)
    assert model.row_payload(0)["code"] == "B2"
    assert model.row_payload(1)["code"] == "A1"
