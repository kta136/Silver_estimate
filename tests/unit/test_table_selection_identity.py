"""Selections must continue identifying the same records after sorting."""

import pytest
from PySide6.QtCore import QItemSelectionModel, QPersistentModelIndex, Qt

from silverestimate.ui.models.estimate_history_table_model import (
    EstimateHistoryRow,
    EstimateHistoryTableModel,
)
from silverestimate.ui.models.item_master_table_model import ItemMasterTableModel
from silverestimate.ui.models.silver_bar_table_models import (
    AvailableSilverBarsTableModel,
    HistoryListBarsTableModel,
    HistorySilverBarsTableModel,
    IssuedSilverBarListsTableModel,
    SelectedListSilverBarsTableModel,
)


def history_row(voucher):
    return EstimateHistoryRow(
        str(voucher), "2026-09-05", str(voucher), 75, 10, 9, 8, 90, 690
    )


@pytest.mark.parametrize(
    "model_class",
    [
        EstimateHistoryTableModel,
        ItemMasterTableModel,
        AvailableSilverBarsTableModel,
        SelectedListSilverBarsTableModel,
        HistorySilverBarsTableModel,
        IssuedSilverBarListsTableModel,
        HistoryListBarsTableModel,
    ],
)
def test_sort_preserves_current_selection_and_persistent_cells(qtbot, model_class):
    model = model_class()
    rows = (
        [history_row(n) for n in (10, 1, 2)]
        if model_class is EstimateHistoryTableModel
        else [
            {
                "bar_id": n,
                "list_id": n,
                "code": str(n),
                "list_identifier": str(n),
                "estimate_voucher_no": str(n),
            }
            for n in (10, 1, 2)
        ]
    )
    model.set_rows(rows)
    selection = QItemSelectionModel(model)
    flags = (
        QItemSelectionModel.SelectionFlag.Select
        | QItemSelectionModel.SelectionFlag.Rows
    )
    for row in (0, 2):
        selection.select(model.index(row, 0), flags)
    selection.setCurrentIndex(
        model.index(2, 0), QItemSelectionModel.SelectionFlag.NoUpdate
    )
    selected = [model.row_payload(row) for row in (0, 2)]
    current = model.row_payload(2)
    cells = [
        (QPersistentModelIndex(model.index(row, col)), model.row_payload(row), col)
        for row in range(3)
        for col in range(model.columnCount())
    ]

    for order in (Qt.SortOrder.AscendingOrder, Qt.SortOrder.DescendingOrder):
        model.sort(0, order)
        assert model.row_payload(selection.currentIndex().row()) == current
        assert all(
            model.row_payload(index.row()) in selected
            for index in selection.selectedRows()
        )
        assert len(selection.selectedRows()) == 2
        for index, record, column in cells:
            assert model.row_payload(index.row()) == record
            assert index.column() == column


def test_history_numeric_vouchers_sort_numerically_with_deterministic_ties(qtbot):
    model = EstimateHistoryTableModel()
    model.set_rows([history_row(n) for n in ("10", "2", "1", "A1", "02", str(2**63))])
    model.sort(0)
    assert [model.row_payload(row).voucher_no for row in range(model.rowCount())] == [
        "1",
        "02",
        "2",
        "10",
        str(2**63),
        "A1",
    ]
