from types import SimpleNamespace

import pytest
from PySide6.QtCore import QObject, QTimer
from PySide6.QtWidgets import QTableView
from shiboken6 import delete

from silverestimate.ui.adapters.estimate_table_adapter import EstimateTableAdapter
from silverestimate.ui.estimate_entry_layout_controller import (
    EstimateEntryLayoutController,
)
from silverestimate.ui.estimate_entry_table_controller import (
    EstimateEntryTableController,
)
from silverestimate.ui.estimate_entry_totals_controller import (
    EstimateEntryTotalsController,
)
from silverestimate.ui.inline_status import InlineStatusController


@pytest.mark.parametrize(
    "availability_check",
    [
        EstimateTableAdapter._qt_object_available,
        EstimateEntryTableController._qt_object_available,
        InlineStatusController._qt_object_available,
    ],
)
def test_qt_object_availability_distinguishes_none_live_and_deleted_wrappers(
    availability_check,
):
    obj = QObject()

    assert availability_check(None) is False
    assert availability_check(object()) is True
    assert availability_check(obj) is True

    delete(obj)

    assert availability_check(obj) is False


def test_totals_recalculation_falls_back_when_timer_wrapper_is_deleted(qt_app):
    timer = QTimer()
    calls = []
    controller = EstimateEntryTotalsController(
        SimpleNamespace(
            _totals_timer=timer, calculate_totals=lambda: calls.append(True)
        )
    )
    delete(timer)

    controller._schedule_totals_recalc()

    assert calls == [True]


def test_table_controller_rejects_deleted_table_wrapper(qt_app):
    table = QTableView()
    controller = EstimateEntryTableController(SimpleNamespace(item_table=table))
    delete(table)

    assert controller._is_table_valid() is False
    controller._safe_edit_item(0, 0)


def test_layout_operations_ignore_deleted_table_wrapper(qt_app):
    table = QTableView()
    host = SimpleNamespace(
        item_table=table,
        _auto_fit_columns_by_content=False,
        _column_autofit_mode="explicit",
    )
    controller = EstimateEntryLayoutController(host)
    delete(table)

    controller._apply_non_autofit_column_layout()
    controller._ensure_column_can_fit_content(0)
    controller._schedule_columns_autofit(force=True)
    controller._auto_stretch_item_name()
