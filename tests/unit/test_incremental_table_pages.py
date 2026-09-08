"""Appending a page keeps original row objects and Qt selections intact."""

import pytest
from PySide6.QtCore import QItemSelectionModel, QPersistentModelIndex, Qt
from PySide6.QtTest import QAbstractItemModelTester

from silverestimate.domain.pagination import Page
from silverestimate.infrastructure.paged_load_state import PagedLoadState
from silverestimate.ui.models.estimate_history_table_model import (
    EstimateHistoryTableModel,
)
from silverestimate.ui.models.item_master_table_model import ItemMasterTableModel
from silverestimate.ui.models.silver_bar_table_models import (
    AvailableSilverBarsTableModel,
    HistorySilverBarsTableModel,
    SelectedListSilverBarsTableModel,
)
from tests.unit.test_table_selection_identity import history_row


@pytest.mark.parametrize(
    "model_class",
    [
        EstimateHistoryTableModel,
        ItemMasterTableModel,
        AvailableSilverBarsTableModel,
        HistorySilverBarsTableModel,
        SelectedListSilverBarsTableModel,
    ],
)
@pytest.mark.parametrize(
    "order", [Qt.SortOrder.AscendingOrder, Qt.SortOrder.DescendingOrder]
)
def test_sorted_append_inserts_without_reset_or_changing_selection(
    qtbot, model_class, order
):
    model = model_class()
    tester = QAbstractItemModelTester(
        model, QAbstractItemModelTester.FailureReportingMode.Warning
    )
    assert tester.model() is model

    def rows(numbers):
        if model_class is EstimateHistoryTableModel:
            return [history_row(number) for number in numbers]
        return [
            dict(code=str(n), bar_id=n, estimate_voucher_no=str(n), weight=n)
            for n in numbers
        ]

    model.set_rows(rows([2, 4, 6]))
    model.sort(0, order)
    original = model.row_payload(1)
    persistent = QPersistentModelIndex(model.index(1, 0))
    selection = QItemSelectionModel(model)
    selection.setCurrentIndex(
        model.index(1, 0),
        QItemSelectionModel.SelectionFlag.ClearAndSelect
        | QItemSelectionModel.SelectionFlag.Rows,
    )
    resets = []
    inserted = []
    model.modelReset.connect(lambda: resets.append(True))
    model.rowsInserted.connect(
        lambda parent, first, last: inserted.append(last - first + 1)
    )
    model.append_rows(rows([7, 1, 5, 3, 3]))
    assert model.rowCount() == 8
    assert not resets and sum(inserted) == 5
    assert model.row_payload(persistent.row()) is original
    assert model.row_payload(selection.currentIndex().row()) is original
    assert model.row_payload(selection.selectedRows()[0].row()) is original
    expected = model_class()
    expected.set_rows(rows([2, 4, 6, 7, 1, 5, 3, 3]))
    expected.sort(0, order)
    assert [model.row_payload(i) for i in range(8)] == [
        expected.row_payload(i) for i in range(8)
    ]


def test_page_state_bounds_retained_rows_and_does_not_claim_an_old_total():
    state = PagedLoadState[int, int](max_rows=5)
    state.apply(Page((1, 2, 3), 20, 3))
    state.apply(Page((4, 5, 6), None, 6), append=True)
    assert state.rows == [1, 2, 3, 4, 5]
    assert state.last_page_rows == [4, 5]
    assert state.total is None
    assert state.limit_reached and not state.has_more
    state.reset()
    assert not state.limit_reached and not state.last_page_rows


@pytest.mark.parametrize(
    "model_class,column",
    [
        (AvailableSilverBarsTableModel, 4),
        (SelectedListSilverBarsTableModel, 4),
        (HistorySilverBarsTableModel, 7),
    ],
)
def test_bar_dates_sort_chronologically_across_month_boundary(
    qtbot, model_class, column
):
    model = model_class()
    model.set_rows(
        [
            dict(bar_id=1, date_added="2026-01-31"),
            dict(bar_id=2, date_added="2026-02-01"),
        ]
    )
    model.sort(column)
    assert [model.bar_id_at(i) for i in range(2)] == [1, 2]
