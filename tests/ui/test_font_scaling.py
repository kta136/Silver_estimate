"""Font-aware acceptance checks that allow different table reflow at high DPI."""

import os
from pathlib import Path

from PySide6.QtWidgets import QLabel

from silverestimate.ui.application_theme import apply_light_application_theme
from tests.factories import regular_item
from tests.smoke.test_full_startup_smoke import _configure_smoke_font
from tests.ui.test_estimate_entry_widget import _set_row


def test_estimate_text_and_actions_remain_readable_at_current_scale(
    qtbot, qt_application_state, make_estimate_widget, fake_db
):
    _configure_smoke_font(qt_application_state)
    apply_light_application_theme(qt_application_state)
    widget = make_estimate_widget(fake_db)
    _set_row(widget, 0, regular_item(gross=1234.567, poly=0.5, purity=92.5))
    widget.silver_rate_spin.setValue(238.25)
    widget.totals_controller.calculate_totals()
    widget.resize(1366, 768)
    widget.show()
    qtbot.wait(150)
    panel = widget.totals_panel
    assert widget.item_table.fontMetrics().inFont("A")
    assert widget.item_table.horizontalHeader().font().pointSize() == 11
    assert panel.grand_total_label.font().pointSize() == 16
    assert panel.category_table.horizontalScrollBar().maximum() == 0
    for label in panel.findChildren(QLabel):
        if label.objectName() in {
            "MetricValue",
            "MetricLabel",
            "FinalMetricLabel",
            "GrandTotalValue",
        }:
            assert (
                label.contentsRect().width()
                >= label.fontMetrics().horizontalAdvance(label.text())
            )
            assert label.height() >= label.fontMetrics().height()
    for button in (
        widget.save_button,
        widget.print_button,
        widget.primary_actions.new_button,
        widget.last_balance_button,
        widget.history_button,
        widget.silver_bars_button,
        widget.delete_row_button,
        widget.delete_estimate_button,
    ):
        assert button.isVisible()
        assert button.width() >= button.fontMetrics().horizontalAdvance(button.text())
    assert widget.item_table.viewport().height() >= 450
    if output_dir := os.environ.get("SILVER_SCALE_CAPTURE_DIR"):
        output = Path(output_dir)
        output.mkdir(parents=True, exist_ok=True)
        assert widget.grab().save(str(output / "estimate.png"))
