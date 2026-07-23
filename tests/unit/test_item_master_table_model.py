from PySide6.QtCore import Qt

from silverestimate.ui.models import ItemMasterTableModel


def test_item_master_table_model_exposes_headers_and_tooltips():
    model = ItemMasterTableModel()

    assert (
        model.headerData(0, Qt.Orientation.Horizontal, Qt.ItemDataRole.DisplayRole)
        == "Code"
    )
    assert (
        model.headerData(1, Qt.Orientation.Horizontal, Qt.ItemDataRole.DisplayRole)
        == "Name"
    )
    assert (
        model.headerData(2, Qt.Orientation.Horizontal, Qt.ItemDataRole.ToolTipRole)
        == "Optional Tunch text"
    )
    assert (
        model.headerData(3, Qt.Orientation.Horizontal, Qt.ItemDataRole.ToolTipRole)
        == "Default Purity"
    )


def test_item_master_table_model_loads_rows_and_sorts_text_and_numeric_columns():
    model = ItemMasterTableModel()
    model.set_rows(
        [
            {
                "code": "B2",
                "name": "Bracelet",
                "tunch": None,
                "purity": 80.0,
                "wage_type": "WT",
                "wage_rate": 15.0,
            },
            {
                "code": "A1",
                "name": "Anklet",
                "tunch": "92 + loss",
                "purity": 92.5,
                "wage_type": "PC",
                "wage_rate": 10.0,
            },
        ]
    )

    assert model.rowCount() == 2
    assert model.data(model.index(0, 0), Qt.ItemDataRole.DisplayRole) == "B2"
    assert model.data(model.index(0, 2), Qt.ItemDataRole.DisplayRole) == ""
    assert model.data(model.index(1, 2), Qt.ItemDataRole.DisplayRole) == "92 + loss"
    assert model.data(model.index(1, 3), Qt.ItemDataRole.DisplayRole) == "92.5"

    model.sort(2, Qt.SortOrder.AscendingOrder)
    assert model.row_payload(0)["code"] == "A1"
    assert model.row_payload(1)["code"] == "B2"

    model.sort(5, Qt.SortOrder.DescendingOrder)
    assert model.row_payload(0)["code"] == "B2"
    assert model.row_payload(1)["code"] == "A1"
