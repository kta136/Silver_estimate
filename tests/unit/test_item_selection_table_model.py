from PySide6.QtCore import Qt
from PySide6.QtGui import QColor

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
    assert (
        model.headerData(0, Qt.Orientation.Horizontal, Qt.ItemDataRole.DisplayRole)
        == "Code"
    )
    assert model.data(model.index(0, 0), Qt.ItemDataRole.DisplayRole) == "AD01"
    assert model.data(model.index(0, 2), Qt.ItemDataRole.DisplayRole) == "91.50"
    assert model.data(model.index(0, 2), Qt.ItemDataRole.TextAlignmentRole) == (
        Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
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

    code_brush = model.data(model.index(0, 0), Qt.ItemDataRole.BackgroundRole)
    name_brush = model.data(model.index(0, 1), Qt.ItemDataRole.BackgroundRole)

    assert code_brush == QColor(255, 246, 196)
    assert name_brush == QColor(255, 246, 196)
