from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor

from silverestimate.ui.models import ItemSelectionRecord, ItemSelectionTableModel


def test_item_selection_table_model_displays_rows_and_alignment():
    model = ItemSelectionTableModel()
    model.set_rows(
        [
            ItemSelectionRecord(
                code="AD01",
                name="Classic Chain",
                purity=91.5,
                wage_type="WT",
                wage_rate=12.5,
                code_upper="AD01",
                name_upper="CLASSIC CHAIN",
            )
        ],
        query="AD",
    )

    assert model.rowCount() == 1
    assert model.headerData(0, Qt.Horizontal, Qt.DisplayRole) == "Code"
    assert model.data(model.index(0, 0), Qt.DisplayRole) == "AD01"
    assert model.data(model.index(0, 2), Qt.DisplayRole) == "91.50"
    assert model.data(model.index(0, 2), Qt.TextAlignmentRole) == (
        Qt.AlignRight | Qt.AlignVCenter
    )


def test_item_selection_table_model_highlights_matching_code_and_name():
    model = ItemSelectionTableModel()
    model.set_rows(
        [
            ItemSelectionRecord(
                code="AD01",
                name="Adorn Pendant",
                purity=88.0,
                wage_type="PC",
                wage_rate=3.0,
                code_upper="AD01",
                name_upper="ADORN PENDANT",
            )
        ],
        query="AD",
    )

    code_brush = model.data(model.index(0, 0), Qt.BackgroundRole)
    name_brush = model.data(model.index(0, 1), Qt.BackgroundRole)

    assert code_brush == QColor(255, 246, 196)
    assert name_brush == QColor(255, 246, 196)
