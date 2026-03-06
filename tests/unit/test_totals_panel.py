"""Tests for TotalsPanel component."""

import pytest
from PyQt5.QtCore import Qt

from silverestimate.domain.estimate_models import CategoryTotals, TotalsResult
from silverestimate.ui.estimate_entry_components.totals_panel import TotalsPanel


@pytest.fixture
def panel(qt_app):
    """Create a fresh TotalsPanel for testing."""
    return TotalsPanel()


def test_initial_state(panel):
    """Test that panel initializes with zero values."""
    assert panel.overall_gross_label.text() == "0.0"
    assert panel.overall_poly_label.text() == "0.0"
    assert panel.total_gross_label.text() == "0.0"
    assert panel.total_net_label.text() == "0.0"
    assert panel.total_fine_label.text() == "0.0"
    assert panel.return_gross_label.text() == "0.0"
    assert panel.return_net_label.text() == "0.0"
    assert panel.return_fine_label.text() == "0.0"
    assert panel.bar_gross_label.text() == "0.0"
    assert panel.bar_net_label.text() == "0.0"
    assert panel.bar_fine_label.text() == "0.0"
    assert panel.net_fine_label.text() == "0.0"
    assert panel.net_wage_label.text() == "0"
    # Note: grand_total_label shows "0" not "₹ 0" initially
    assert panel.grand_total_label.text() in ["0", "₹ 0"]


def test_set_totals(panel):
    """Test setting totals from TotalsResult."""
    totals = TotalsResult(
        overall_gross=500.0,
        overall_poly=25.0,
        regular=CategoryTotals(gross=300.0, net=275.0, fine=252.0, wage=4000.0),
        returns=CategoryTotals(gross=100.0, net=95.0, fine=87.0, wage=500.0),
        silver_bars=CategoryTotals(gross=100.0, net=95.0, fine=87.0, wage=500.0),
        net_fine_core=252.0,
        net_wage_core=5000.0,
        net_value_core=100000.0,
        net_fine=252.0,
        net_wage=5000.0,
        net_value=100000.0,
        grand_total=125000.0,
        silver_rate=0.0,
        last_balance_silver=0.0,
        last_balance_amount=0.0,
    )

    panel.set_totals(totals)

    # Verify all values are updated
    assert panel.overall_gross_label.text() == "500.00"
    assert panel.overall_poly_label.text() == "25.00"
    assert panel.total_gross_label.text() == "300.00"
    assert panel.total_net_label.text() == "275.00"
    assert panel.total_fine_label.text() == "252.00"
    assert panel.return_gross_label.text() == "100.00"
    assert panel.return_net_label.text() == "95.00"
    assert panel.return_fine_label.text() == "87.00"
    assert panel.bar_gross_label.text() == "100.00"
    assert panel.bar_net_label.text() == "95.00"
    assert panel.bar_fine_label.text() == "87.00"
    assert panel.net_fine_label.text() == "252.00"
    assert panel.net_wage_label.text() == "5000"
    assert panel.grand_total_label.text() == "₹ 125000"


def test_clear_totals(panel):
    """Test clearing all totals."""
    # First set some values
    totals = TotalsResult(
        overall_gross=500.0,
        overall_poly=25.0,
        regular=CategoryTotals(gross=300.0, net=275.0, fine=252.0, wage=4000.0),
        returns=CategoryTotals(gross=100.0, net=95.0, fine=87.0, wage=500.0),
        silver_bars=CategoryTotals(gross=100.0, net=95.0, fine=87.0, wage=500.0),
        net_fine_core=252.0,
        net_wage_core=5000.0,
        net_value_core=100000.0,
        net_fine=252.0,
        net_wage=5000.0,
        net_value=100000.0,
        grand_total=125000.0,
        silver_rate=0.0,
        last_balance_silver=0.0,
        last_balance_amount=0.0,
    )
    panel.set_totals(totals)

    # Now clear
    panel.clear_totals()

    # Verify all back to zero
    assert panel.overall_gross_label.text() == "0.0"
    assert panel.overall_poly_label.text() == "0.0"
    assert panel.total_gross_label.text() == "0.0"
    assert panel.total_net_label.text() == "0.0"
    assert panel.total_fine_label.text() == "0.0"
    assert panel.return_gross_label.text() == "0.0"
    assert panel.return_net_label.text() == "0.0"
    assert panel.return_fine_label.text() == "0.0"
    assert panel.bar_gross_label.text() == "0.0"
    assert panel.bar_net_label.text() == "0.0"
    assert panel.bar_fine_label.text() == "0.0"
    assert panel.net_fine_label.text() == "0.0"
    assert panel.net_wage_label.text() == "0"
    assert panel.grand_total_label.text() == "₹ 0"


def test_set_totals_with_zero_values(panel):
    """Test setting totals with all zeros."""
    totals = TotalsResult(
        overall_gross=0.0,
        overall_poly=0.0,
        regular=CategoryTotals(),
        returns=CategoryTotals(),
        silver_bars=CategoryTotals(),
        net_fine_core=0.0,
        net_wage_core=0.0,
        net_value_core=0.0,
        net_fine=0.0,
        net_wage=0.0,
        net_value=0.0,
        grand_total=0.0,
        silver_rate=0.0,
        last_balance_silver=0.0,
        last_balance_amount=0.0,
    )

    panel.set_totals(totals)

    # Should display "0.00" or "0" appropriately
    assert panel.overall_gross_label.text() == "0.00"
    assert panel.net_wage_label.text() == "0"
    assert panel.grand_total_label.text() == "₹ 0"


def test_decimal_formatting(panel):
    """Test that decimal values are formatted correctly."""
    totals = TotalsResult(
        overall_gross=123.456,  # Should round to 2 decimals
        overall_poly=0.0,
        regular=CategoryTotals(
            gross=0.0, net=0.0, fine=999.999, wage=0.0
        ),  # Should round to 2 decimals
        returns=CategoryTotals(),
        silver_bars=CategoryTotals(),
        net_fine_core=0.0,
        net_wage_core=0.0,
        net_value_core=0.0,
        net_fine=0.0,
        net_wage=1234.56,  # Should round to 0 decimals
        net_value=0.0,
        grand_total=0.0,
        silver_rate=0.0,
        last_balance_silver=0.0,
        last_balance_amount=0.0,
    )

    panel.set_totals(totals)

    assert panel.overall_gross_label.text() == "123.46"
    assert panel.total_fine_label.text() == "1000.00"
    assert panel.net_wage_label.text() == "1235"


def test_sidebar_section_order_can_be_reordered(qt_app):
    panel = TotalsPanel(layout_mode="sidebar")
    panel.set_section_order(["silver_bar", "return", "totals", "regular"])

    assert panel.section_order() == [
        "final_calc",
        "silver_bar",
        "return",
        "totals",
        "regular",
    ]
    ui_order = [
        panel._summary_sections_list.item(i).data(Qt.UserRole)
        for i in range(panel._summary_sections_list.count())
    ]
    assert ui_order == ["final_calc", "silver_bar", "return", "totals", "regular"]


def test_sidebar_rows_moved_emits_section_order_signal(qt_app):
    panel = TotalsPanel(layout_mode="sidebar")
    emissions = []
    panel.section_order_changed.connect(lambda order: emissions.append(order))

    moving_item = panel._summary_sections_list.takeItem(4)
    panel._summary_sections_list.insertItem(0, moving_item)
    panel._on_sidebar_section_rows_moved()

    assert emissions
    assert emissions[-1][0] == "silver_bar"
    assert panel.section_order()[0] == "silver_bar"


def test_sidebar_swap_requested_swaps_card_positions(qt_app):
    panel = TotalsPanel(layout_mode="sidebar")
    emissions = []
    panel.section_order_changed.connect(lambda order: emissions.append(order))

    panel._on_sidebar_section_swap_requested(0, 2)

    assert panel.section_order() == [
        "regular",
        "totals",
        "final_calc",
        "return",
        "silver_bar",
    ]
    ui_order = [
        panel._summary_sections_list.item(i).data(Qt.UserRole)
        for i in range(panel._summary_sections_list.count())
    ]
    assert ui_order == ["regular", "totals", "final_calc", "return", "silver_bar"]
    assert emissions[-1] == [
        "regular",
        "totals",
        "final_calc",
        "return",
        "silver_bar",
    ]


def test_sidebar_rows_moved_keeps_all_cards_visible(qt_app):
    panel = TotalsPanel(layout_mode="sidebar")
    panel.show()
    qt_app.processEvents()

    moving_item = panel._summary_sections_list.takeItem(2)
    panel._summary_sections_list.insertItem(0, moving_item)
    panel._on_sidebar_section_rows_moved()
    qt_app.processEvents()

    for idx in range(panel._summary_sections_list.count()):
        item = panel._summary_sections_list.item(idx)
        assert item is not None
        assert panel._summary_sections_list.itemWidget(item) is not None


def test_sidebar_items_are_not_drop_targets(qt_app):
    panel = TotalsPanel(layout_mode="sidebar")
    for idx in range(panel._summary_sections_list.count()):
        item = panel._summary_sections_list.item(idx)
        assert item is not None
        assert not bool(item.flags() & Qt.ItemIsDropEnabled)


def test_sidebar_cards_resize_with_available_width(qt_app):
    panel = TotalsPanel(layout_mode="sidebar")
    panel.resize(520, 760)
    panel.show()
    qt_app.processEvents()
    panel._sync_sidebar_item_sizes()

    viewport_width = panel._summary_sections_list.viewport().width()
    for idx in range(panel._summary_sections_list.count()):
        item = panel._summary_sections_list.item(idx)
        assert item is not None
        # Item width tracks the current viewport width (dynamic section sizing).
        assert item.sizeHint().width() >= max(0, viewport_width - 4)
