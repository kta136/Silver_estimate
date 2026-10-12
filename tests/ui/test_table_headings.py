"""A table heading sits over its data: figures right, labels left."""

import pytest
from PySide6.QtCore import Qt

from silverestimate.ui.estimate_entry_logic.constants import (
    COL_CODE,
    COL_FINE_WT,
    COL_GROSS,
    COL_ITEM_NAME,
    COL_TYPE,
)
from silverestimate.ui.models.estimate_history_table_model import (
    EstimateHistoryTableModel,
)
from silverestimate.ui.models.estimate_table_model import EstimateTableModel
from silverestimate.ui.models.item_master_table_model import ItemMasterTableModel
from silverestimate.ui.models.item_selection_table_model import (
    ItemSelectionTableModel,
)
from silverestimate.ui.models.silver_bar_entry_model import SilverBarEntryModel
from silverestimate.ui.models.silver_bar_history_models import (
    SilverBarHistoryModel,
    SilverBarListsHistoryModel,
)

RIGHT = Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
LEFT = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter


def heading(model, section):
    return model.headerData(
        section, Qt.Orientation.Horizontal, Qt.ItemDataRole.TextAlignmentRole
    )


def test_estimate_table_headings(qt_app):
    model = EstimateTableModel()

    assert heading(model, COL_CODE) == LEFT
    assert heading(model, COL_ITEM_NAME) == LEFT
    assert heading(model, COL_GROSS) == RIGHT
    assert heading(model, COL_FINE_WT) == RIGHT
    assert heading(model, COL_TYPE) == (Qt.AlignmentFlag.AlignCenter)
    # Row numbers are left alone.
    assert (
        model.headerData(0, Qt.Orientation.Vertical, Qt.ItemDataRole.TextAlignmentRole)
        is None
    )


def test_estimate_history_headings(qt_app):
    model = EstimateHistoryTableModel()
    labels = {"Voucher No", "Date", "Note"}

    for section, title in enumerate(model.HEADERS):
        expected = LEFT if title in labels else RIGHT
        assert heading(model, section) == expected, title


def test_item_master_headings(qt_app):
    model = ItemMasterTableModel()
    figures = {"Purity (%)", "Labour Rate"}

    for section, title in enumerate(model.HEADERS):
        expected = RIGHT if title in figures else LEFT
        assert heading(model, section) == expected, title


def test_item_selection_headings(qt_app):
    model = ItemSelectionTableModel()

    assert [heading(model, section) for section in range(3)] == [LEFT, LEFT, RIGHT]


@pytest.mark.parametrize(
    "model_class",
    [SilverBarEntryModel, SilverBarHistoryModel, SilverBarListsHistoryModel],
)
def test_silver_bar_headings_follow_their_columns(qt_app, model_class):
    model = model_class()

    assert model.columnCount() >= 4
    for section in range(model.columnCount()):
        data = model.text_alignment(section)
        assert heading(model, section) == (data or LEFT), (model_class, section)
    # Weights are figures and the voucher or note is text.
    assert heading(model, 0) == (model.text_alignment(0) or LEFT)
