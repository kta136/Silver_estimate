from PyQt5.QtCore import Qt

from silverestimate.ui.models import ItemImportPreviewRow, ItemImportPreviewTableModel


def test_item_import_preview_table_model_exposes_headers_and_rows():
    model = ItemImportPreviewTableModel()
    model.set_rows(
        [
            ItemImportPreviewRow(
                code="X001",
                name="Sample",
                wage_type="WT",
                wage_rate="10.00",
                purity="92.5",
            )
        ]
    )

    assert model.rowCount() == 1
    assert model.columnCount() == 5
    assert model.headerData(0, Qt.Horizontal, Qt.DisplayRole) == "Item Code"
    assert model.data(model.index(0, 0), Qt.DisplayRole) == "X001"
    assert model.data(model.index(0, 3), Qt.DisplayRole) == "10.00"
    assert model.row_payload(0) == ItemImportPreviewRow(
        code="X001",
        name="Sample",
        wage_type="WT",
        wage_rate="10.00",
        purity="92.5",
    )
