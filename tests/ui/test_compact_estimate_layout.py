"""Readable estimate chrome and totals typography at compact window sizes."""

import os
from pathlib import Path

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QTableWidget

from silverestimate.ui.application_theme import apply_light_application_theme
from silverestimate.ui.estimate_entry_logic.constants import COL_WAGE_AMT
from silverestimate.ui.toolbar_overflow import ToolbarOverflow
from tests.factories import regular_item, return_item, silver_bar_item
from tests.smoke.test_full_startup_smoke import _configure_smoke_font
from tests.ui.test_estimate_entry_widget import _set_row


@pytest.mark.parametrize(
    "width,height,totals_size", [(1366, 768, 11), (1100, 700, 11), (1366, 768, 14)]
)
def test_compact_totals_use_aligned_table_and_shared_font_size(
    qtbot,
    qt_application_state,
    make_estimate_widget,
    fake_db,
    width,
    height,
    totals_size,
):
    _configure_smoke_font(qt_application_state)
    apply_light_application_theme(qt_application_state)
    widget = make_estimate_widget(fake_db)
    for row in range(20):
        _set_row(widget, row, regular_item(gross=10, poly=0.5, purity=92.5))
    _set_row(widget, 20, return_item(gross=5, poly=0.2, purity=91.6))
    _set_row(widget, 21, silver_bar_item(gross=100, poly=0, purity=99.9))
    widget.live_rate_value_label.setText("₹75,000.00")
    widget.live_rate_meta_label.setText("Updated 10:30")
    assert widget.layout_controller.apply_breakdown_font_size(totals_size)
    assert widget.layout_controller.apply_final_calc_font_size(16)
    widget.resize(width, height)
    widget.show()
    qtbot.wait(80)

    panel = widget.totals_panel
    table = panel.category_table
    assert (
        widget.item_table.model().headerData(COL_WAGE_AMT, Qt.Orientation.Horizontal)
        == "Lbr Amt"
    )
    assert isinstance(table, QTableWidget)
    headers = [
        table.horizontalHeaderItem(col).text() for col in range(table.columnCount())
    ]
    assert headers[-3:] == ["Gross (g)", "Net (g)", "Fine (g)"]
    assert table.horizontalScrollBar().maximum() == 0
    assert table.horizontalHeader().defaultAlignment() & Qt.AlignmentFlag.AlignRight
    assert table.horizontalHeader().font().pointSize() == totals_size
    assert all(
        table.horizontalHeaderItem(column).font().pointSize() == totals_size
        for column in range(table.columnCount())
    )
    assert table.font().pointSize() == totals_size
    for label in panel.findChildren(QLabel):
        assert label.text() not in {"Totals", "Category"}
        if label.objectName() in {
            "MetricLabel",
            "MetricValue",
            "FinalMetricLabel",
            "SectionTitle",
        }:
            assert label.font().pointSize() == totals_size
    for row in range(table.rowCount()):
        for column in range(table.columnCount()):
            label = table.cellWidget(row, column)
            if label is None:
                continue
            if label.objectName() == "MetricValue":
                assert label.alignment() & Qt.AlignmentFlag.AlignRight
            assert (
                label.contentsRect().width()
                >= label.fontMetrics().horizontalAdvance(label.text())
            )
    assert panel.grand_total_label.font().pointSize() == 16
    assert panel.width() <= 360
    if width >= 1366:
        assert widget.item_table.horizontalScrollBar().maximum() == 0
        assert widget.note_edit.width() >= 160
    assert (
        widget.findChild(QLabel, "StatusStripText").text()
        == "Ctrl+S Save  |  Ctrl+P Print  |  F1 Shortcuts"
    )
    assert widget.bottom_status_strip.height() <= 28
    toolbar = widget.findChild(ToolbarOverflow)
    assert toolbar.height() <= (48 if width >= 1366 else 66)
    assert widget.item_table.height() >= height - 110
    for button in (
        widget.last_balance_button,
        widget.history_button,
        widget.silver_bars_button,
        widget.delete_row_button,
        widget.delete_estimate_button,
    ):
        assert button.isVisible()

    if output_dir := os.environ.get("SILVER_COMPACT_CAPTURE_DIR"):
        output = Path(output_dir).resolve()
        output.mkdir(parents=True, exist_ok=True)
        assert widget.grab().save(str(output / f"estimate-{width}-{totals_size}.png"))

    previous_amount = panel.grand_total_label.text()
    widget.silver_rate_spin.setValue(widget.silver_rate_spin.maximum())
    widget.totals_controller.calculate_totals()
    qtbot.wait(80)
    assert panel.grand_total_label.text() != previous_amount
    for label in (panel._grand_total_caption, panel.grand_total_label):
        assert label.contentsRect().width() >= label.fontMetrics().horizontalAdvance(
            label.text()
        )
    if output_dir:
        assert widget.grab().save(
            str(output / f"estimate-large-total-{width}-{totals_size}.png")
        )


def test_totals_reflow_preserves_values_and_font_on_repeated_changes(
    qtbot, qt_application_state, make_estimate_widget, fake_db
):
    _configure_smoke_font(qt_application_state)
    apply_light_application_theme(qt_application_state)
    widget = make_estimate_widget(fake_db)
    widget.resize(1366, 768)
    widget.show()
    panel = widget.totals_panel
    expected = {
        "total_gross_label": "321.123",
        "total_net_label": "310.456",
        "total_fine_label": "280.789",
        "return_gross_label": "10.987",
        "return_net_label": "10.654",
        "return_fine_label": "9.321",
        "bar_gross_label": "100.000",
        "bar_net_label": "100.000",
        "bar_fine_label": "99.900",
    }
    for attr, value in expected.items():
        getattr(panel, attr).setText(value)
    modes = set()
    for size in (11, 14, 20, 11):
        panel.set_breakdown_font_size(size)
        qtbot.wait(80)
        modes.add(panel._category_layout_mode)
        assert panel.category_table.horizontalScrollBar().maximum() == 0
        for attr, value in expected.items():
            label = getattr(panel, attr)
            assert label.text() == value
            assert label.font().pointSize() == size
            assert (
                label.contentsRect().width()
                >= label.fontMetrics().horizontalAdvance(value)
            )
    assert modes == {"matrix", "groups", "details"}
