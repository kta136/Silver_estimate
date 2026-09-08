"""Exercise mode changes through both buttons and keyboard shortcuts."""

from functools import partial

import pytest
from PySide6.QtCore import Qt

from silverestimate.ui.estimate_entry_logic import COL_TYPE


@pytest.fixture(params=["button", "keyboard"])
def mode_controls(request, qtbot, fake_db, make_estimate_widget):
    widget = make_estimate_widget(fake_db)
    if request.param == "keyboard":
        widget.show()
    qtbot.waitUntil(lambda: widget.item_table.rowCount() > 0, timeout=2000)

    def toggle(mode):
        if request.param == "button":
            getattr(widget, f"{mode}_toggle_button").click()
        else:
            key = Qt.Key.Key_R if mode == "return" else Qt.Key.Key_B
            qtbot.keyClick(widget, key, Qt.KeyboardModifier.ControlModifier)

    return widget, toggle


def _mode_matches(widget, mode, row_type, indicator):
    return (
        widget.return_mode == (mode == "return")
        and widget.return_toggle_button.isChecked() == (mode == "return")
        and widget.silver_bar_mode == (mode == "silver_bar")
        and widget.silver_bar_toggle_button.isChecked() == (mode == "silver_bar")
        and widget.item_table.get_cell_text(widget.item_table.rowCount() - 1, COL_TYPE)
        == row_type
        and (indicator is None or widget.mode_indicator_label.text() == indicator)
    )


@pytest.mark.parametrize(
    ("mode", "row_type", "indicator"),
    [
        ("return", "Return", "Mode: Return Items"),
        ("silver_bar", "Silver Bar", "Mode: Silver Bars"),
    ],
)
def test_mode_controls_toggle_row_type(qtbot, mode_controls, mode, row_type, indicator):
    widget, toggle = mode_controls
    assert _mode_matches(widget, None, "Regular", None)
    toggle(mode)
    qtbot.waitUntil(partial(_mode_matches, widget, mode, row_type, indicator))
    toggle(mode)
    qtbot.waitUntil(lambda: _mode_matches(widget, None, "Regular", None))


def test_mode_controls_are_mutually_exclusive(qtbot, mode_controls):
    widget, toggle = mode_controls
    for mode, row_type, indicator in (
        ("return", "Return", "Mode: Return Items"),
        ("silver_bar", "Silver Bar", "Mode: Silver Bars"),
        ("return", "Return", "Mode: Return Items"),
    ):
        toggle(mode)
        qtbot.waitUntil(partial(_mode_matches, widget, mode, row_type, indicator))
