"""Readable estimate chrome and totals typography at compact window sizes."""

import os
from pathlib import Path

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QBoxLayout,
    QLabel,
    QMenuBar,
    QScrollArea,
    QTableWidget,
)

from silverestimate.infrastructure.settings import SettingsKey, get_app_settings
from silverestimate.ui.application_theme import apply_light_application_theme
from silverestimate.ui.estimate_entry_logic.constants import COL_WAGE_AMT
from silverestimate.ui.settings_appearance_page import (
    AppearanceSettingsActions,
    AppearanceSettingsState,
    SettingsAppearanceController,
)
from tests.factories import regular_item, return_item, silver_bar_item
from tests.smoke.test_full_startup_smoke import _configure_smoke_font
from tests.ui.test_estimate_entry_widget import _set_row


@pytest.mark.parametrize(
    "width,height,totals_size", [(1366, 768, 11), (1100, 700, 11), (1366, 768, 14)]
)
def test_compact_totals_use_aligned_table_and_independent_grand_total_font_size(
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
        == "Lbr"
    )
    assert isinstance(table, QTableWidget)
    headers = [
        table.horizontalHeaderItem(col).text() for col in range(table.columnCount())
    ]
    assert headers[-3:] == ["Gross", "Net", "Fine"]
    # Column widths and the scrollbar range settle in separate Qt layout events.
    qtbot.waitUntil(lambda: table.horizontalScrollBar().maximum() == 0)
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
            expected_size = (
                16 if label.property("sectionKind") == "final_calc" else totals_size
            )
            assert label.font().pointSize() == expected_size
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
        assert widget.note_edit.width() >= 120
    assert widget.toolbar.parent() is panel._sidebar_top_host
    assert "F1 Shortcuts" in widget.status_line_label.text()
    # Without a main-window menu bar only the Save/Print/New strip stays on top.
    assert widget.command_strip.isVisible()
    assert widget.command_strip.height() <= 48
    assert widget.item_table.height() >= height - 60
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


def _show_estimate_for_totals(
    qtbot, qt_application_state, make_estimate_widget, fake_db, *, final_size=16
):
    _configure_smoke_font(qt_application_state)
    apply_light_application_theme(qt_application_state)
    widget = make_estimate_widget(fake_db)
    assert widget.layout_controller.apply_final_calc_font_size(final_size)
    widget.resize(1280, 680)
    widget.show()
    qtbot.wait(80)
    return widget, widget.totals_panel


def _set_final_totals(qtbot, panel, grand_total, net_fine="0.00", net_wage="0.00"):
    panel.grand_total_label.setText(grand_total)
    panel.net_fine_label.setText(net_fine)
    panel.net_wage_label.setText(net_wage)
    panel._schedule_sidebar_item_size_sync()
    qtbot.wait(80)


@pytest.mark.parametrize(
    "grand_total", ["₹ -10,00,000.00", "₹ 10,00,01,000.00", "₹ 10,00,00,01,000.00"]
)
def test_a_large_or_negative_grand_total_shrinks_instead_of_stacking(
    qtbot, qt_application_state, make_estimate_widget, fake_db, grand_total
):
    # Stacking the total under its caption costs a line of height, which used
    # to push the panel's buttons out of a 1366x768 window.
    widget, panel = _show_estimate_for_totals(
        qtbot, qt_application_state, make_estimate_widget, fake_db
    )
    scroll = panel.findChild(QScrollArea)
    assert panel.grand_total_label.font().pointSize() == 16

    _set_final_totals(qtbot, panel, grand_total)

    label = panel.grand_total_label
    assert panel._grand_total_header_layout.direction() == (
        QBoxLayout.Direction.LeftToRight
    )
    assert label.contentsRect().width() >= label.fontMetrics().horizontalAdvance(
        label.text()
    )
    assert 11 <= label.font().pointSize() <= 16
    assert scroll.verticalScrollBar().maximum() == 0
    for button in (widget.delete_row_button, widget.delete_estimate_button):
        assert button.isVisible()
        assert button.mapTo(panel, button.rect().bottomLeft()).y() < panel.height()


def test_the_grand_total_grows_back_when_the_amount_gets_shorter(
    qtbot, qt_application_state, make_estimate_widget, fake_db
):
    _, panel = _show_estimate_for_totals(
        qtbot, qt_application_state, make_estimate_widget, fake_db
    )
    _set_final_totals(qtbot, panel, "₹ 1,00,00,00,01,000.00")
    assert panel.grand_total_label.font().pointSize() < 16

    _set_final_totals(qtbot, panel, "₹ 1,250.00")

    assert panel.grand_total_label.font().pointSize() == 16
    # The size the user chose in Settings is what comes back, not the shrunk one.
    assert panel._final_calc_font_size == 16


def test_a_stacked_total_is_given_its_height_and_gives_it_back(
    qtbot, qt_application_state, make_estimate_widget, fake_db
):
    # Beyond what shrinking can hold, a value drops under its caption. The
    # card must be as tall as that needs (the rows once overlapped), and the
    # panel must settle again when the numbers get small.
    _, panel = _show_estimate_for_totals(
        qtbot, qt_application_state, make_estimate_widget, fake_db
    )
    sections = panel._summary_sections_list
    _set_final_totals(qtbot, panel, "₹ 0.00")
    normal_height = sections.height()
    card = sections.itemWidget(sections.item(0))
    card_hint = sections.item(0).sizeHint().height()

    _set_final_totals(
        qtbot, panel, "₹ 1,00,00,00,01,000.00", "10.00", "10,00,00,00,000.00"
    )
    assert panel.net_wage_label.geometry().bottom() <= card.height()
    assert sections.item(0).sizeHint().height() > card_hint
    assert sections.height() > normal_height

    _set_final_totals(qtbot, panel, "₹ 0.00")
    assert sections.height() == normal_height


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


def test_startup_and_apply_keep_controls_headers_and_totals_consistent(
    qtbot, qt_application_state, settings_stub, make_estimate_widget, fake_db
):
    app = qt_application_state
    settings = get_app_settings()
    settings.set(SettingsKey.UI_TABLE_FONT_SIZE, 14)
    settings.set(SettingsKey.UI_BREAKDOWN_FONT_SIZE, 9)
    settings.set(SettingsKey.UI_FINAL_CALC_FONT_SIZE, 12)
    # Simulate Windows' distinct class fonts, including on offscreen CI.
    for widget_class in ("QMenu", "QMenuBar", "QHeaderView"):
        app.setFont(QFont("Segoe UI", 9), widget_class)
    apply_light_application_theme(app)
    widget = make_estimate_widget(fake_db)
    widget.resize(1366, 768)
    widget.show()
    menu = QMenuBar(widget)
    menu.addMenu("File")
    qtbot.wait(80)
    panel = widget.totals_panel
    assert menu.font().pointSize() == 14
    assert widget.item_table.horizontalHeader().font().pointSize() == 14
    assert panel.category_table.horizontalHeader().font().pointSize() == 9
    assert panel.grand_total_label.font().pointSize() == 12

    controller = widget.layout_controller
    appearance = SettingsAppearanceController(
        settings,
        AppearanceSettingsActions(
            apply_print_font=lambda _font: True,
            apply_table_font_size=controller.apply_table_font_size,
            apply_breakdown_font_size=controller.apply_breakdown_font_size,
            apply_final_calc_font_size=controller.apply_final_calc_font_size,
        ),
    )
    appearance.apply_state(AppearanceSettingsState())
    qtbot.wait(80)
    assert widget.save_button.font().pointSize() == 11
    assert menu.font().pointSize() == 11
    assert widget.item_table.font().pointSize() == 11
    assert widget.item_table.horizontalHeader().font().pointSize() == 11
    assert panel.category_table.horizontalHeader().font().pointSize() == 11
    assert panel.net_fine_label.font().pointSize() == 16
    assert panel.grand_total_label.font().pointSize() == 16
    assert appearance.load_state() == AppearanceSettingsState()
