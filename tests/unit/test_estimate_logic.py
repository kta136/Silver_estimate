import pytest
from types import SimpleNamespace

from PyQt5.QtWidgets import QTableWidget, QTableWidgetItem

from silverestimate.ui.estimate_entry_logic import (
    COL_CODE,
    COL_FINE_WT,
    COL_GROSS,
    COL_NET_WT,
    COL_PIECES,
    COL_POLY,
    COL_PURITY,
    COL_TYPE,
    COL_WAGE_AMT,
    COL_WAGE_RATE,
    EstimateLogic,
)


class _LabelStub:
    def __init__(self):
        self.text = None

    def setText(self, value):
        self.text = value


def _prepare_logic_with_table(rows=1, item_lookup=None):
    logic = EstimateLogic()
    table = QTableWidget()
    table.setColumnCount(COL_TYPE + 1)
    table.setRowCount(rows)
    logic.item_table = table
    logic.current_row = 0
    logic.current_column = COL_GROSS
    if item_lookup is None:
        item_lookup = lambda code: {"wage_type": "WT"}
    logic.db_manager = SimpleNamespace(get_item_by_code=item_lookup)
    logic.request_totals_recalc = lambda: None
    return logic, table


def test_calculate_net_and_fine_updates_cells(qt_app):
    logic, table = _prepare_logic_with_table()
    table.setItem(0, COL_CODE, QTableWidgetItem("ITM001"))
    table.setItem(0, COL_GROSS, QTableWidgetItem("10.0"))
    table.setItem(0, COL_POLY, QTableWidgetItem("1.0"))
    table.setItem(0, COL_PURITY, QTableWidgetItem("92.5"))
    table.setItem(0, COL_WAGE_RATE, QTableWidgetItem("10"))
    table.setItem(0, COL_PIECES, QTableWidgetItem("2"))

    logic.calculate_net_weight()

    assert table.item(0, COL_NET_WT).text() == "9.000"
    assert table.item(0, COL_FINE_WT).text() == "8.325"
    assert table.item(0, COL_WAGE_AMT).text() == "90"


def test_calculate_totals_groups_by_type(qt_app):
    logic, table = _prepare_logic_with_table(rows=3)
    logic.silver_rate_spin = SimpleNamespace(value=lambda: 75000.0)
    logic.total_fine_label = _LabelStub()
    logic.return_fine_label = _LabelStub()
    logic.bar_fine_label = _LabelStub()
    logic.net_fine_label = _LabelStub()

    # Regular item
    table.setItem(0, COL_CODE, QTableWidgetItem("REG001"))
    table.setItem(0, COL_GROSS, QTableWidgetItem("10"))
    table.setItem(0, COL_POLY, QTableWidgetItem("1"))
    table.setItem(0, COL_NET_WT, QTableWidgetItem("9"))
    table.setItem(0, COL_FINE_WT, QTableWidgetItem("8.325"))
    table.setItem(0, COL_WAGE_AMT, QTableWidgetItem("90"))
    table.setItem(0, COL_TYPE, QTableWidgetItem("No"))

    # Return item
    table.setItem(1, COL_CODE, QTableWidgetItem("RET001"))
    table.setItem(1, COL_GROSS, QTableWidgetItem("1.5"))
    table.setItem(1, COL_POLY, QTableWidgetItem("0.5"))
    table.setItem(1, COL_NET_WT, QTableWidgetItem("1.0"))
    table.setItem(1, COL_FINE_WT, QTableWidgetItem("0.500"))
    table.setItem(1, COL_WAGE_AMT, QTableWidgetItem("0"))
    table.setItem(1, COL_TYPE, QTableWidgetItem("Return"))

    # Silver bar item
    table.setItem(2, COL_CODE, QTableWidgetItem("BAR001"))
    table.setItem(2, COL_GROSS, QTableWidgetItem("2.0"))
    table.setItem(2, COL_POLY, QTableWidgetItem("0.0"))
    table.setItem(2, COL_NET_WT, QTableWidgetItem("2.0"))
    table.setItem(2, COL_FINE_WT, QTableWidgetItem("2.000"))
    table.setItem(2, COL_WAGE_AMT, QTableWidgetItem("0"))
    table.setItem(2, COL_TYPE, QTableWidgetItem("Silver Bar"))

    logic.calculate_totals()

    assert logic.total_fine_label.text == "8.3"
    assert logic.return_fine_label.text == "0.5"
    assert logic.bar_fine_label.text == "2.0"
    assert logic.net_fine_label.text == "5.8"


def test_calculate_wage_uses_item_wage_type(qt_app):
    lookup = lambda code: {"wage_type": "PC"} if code == "PC001" else {"wage_type": "WT"}
    logic, table = _prepare_logic_with_table(rows=2, item_lookup=lookup)

    table.setItem(0, COL_CODE, QTableWidgetItem("PC001"))
    table.setItem(0, COL_NET_WT, QTableWidgetItem("5.0"))
    table.setItem(0, COL_WAGE_RATE, QTableWidgetItem("12"))
    table.setItem(0, COL_PIECES, QTableWidgetItem("3"))
    logic.current_row = 0
    logic.calculate_wage()

    assert table.item(0, COL_WAGE_AMT).text() == "36"

    table.setItem(1, COL_CODE, QTableWidgetItem("WT001"))
    table.setItem(1, COL_NET_WT, QTableWidgetItem("4.5"))
    table.setItem(1, COL_WAGE_RATE, QTableWidgetItem("15"))
    table.setItem(1, COL_PIECES, QTableWidgetItem("2"))
    logic.current_row = 1
    logic.calculate_wage()

    assert table.item(1, COL_WAGE_AMT).text() == "68"


def test_calculate_totals_applies_last_balance_and_currency(qt_app):
    logic, table = _prepare_logic_with_table(rows=3)
    logic.last_balance_silver = 1.5
    logic.last_balance_amount = 500.0
    logic.silver_rate_spin = SimpleNamespace(value=lambda: 70000.0)
    logic._format_currency = lambda value: f"?{value:.0f}"

    logic.overall_gross_label = _LabelStub()
    logic.overall_poly_label = _LabelStub()
    logic.total_gross_label = _LabelStub()
    logic.total_net_label = _LabelStub()
    logic.total_fine_label = _LabelStub()
    logic.return_gross_label = _LabelStub()
    logic.return_net_label = _LabelStub()
    logic.return_fine_label = _LabelStub()
    logic.bar_gross_label = _LabelStub()
    logic.bar_net_label = _LabelStub()
    logic.bar_fine_label = _LabelStub()
    logic.net_fine_label = _LabelStub()
    logic.net_wage_label = _LabelStub()
    logic.net_value_label = _LabelStub()
    logic.grand_total_label = _LabelStub()

    # Regular item
    table.setItem(0, COL_CODE, QTableWidgetItem("REG001"))
    table.setItem(0, COL_GROSS, QTableWidgetItem("10"))
    table.setItem(0, COL_POLY, QTableWidgetItem("1"))
    table.setItem(0, COL_NET_WT, QTableWidgetItem("9"))
    table.setItem(0, COL_FINE_WT, QTableWidgetItem("8.325"))
    table.setItem(0, COL_WAGE_AMT, QTableWidgetItem("90"))
    table.setItem(0, COL_TYPE, QTableWidgetItem("No"))

    # Return item
    table.setItem(1, COL_CODE, QTableWidgetItem("RET001"))
    table.setItem(1, COL_GROSS, QTableWidgetItem("1.5"))
    table.setItem(1, COL_POLY, QTableWidgetItem("0.5"))
    table.setItem(1, COL_NET_WT, QTableWidgetItem("1.0"))
    table.setItem(1, COL_FINE_WT, QTableWidgetItem("0.500"))
    table.setItem(1, COL_WAGE_AMT, QTableWidgetItem("0"))
    table.setItem(1, COL_TYPE, QTableWidgetItem("Return"))

    # Silver bar item
    table.setItem(2, COL_CODE, QTableWidgetItem("BAR001"))
    table.setItem(2, COL_GROSS, QTableWidgetItem("2.0"))
    table.setItem(2, COL_POLY, QTableWidgetItem("0.0"))
    table.setItem(2, COL_NET_WT, QTableWidgetItem("2.0"))
    table.setItem(2, COL_FINE_WT, QTableWidgetItem("2.000"))
    table.setItem(2, COL_WAGE_AMT, QTableWidgetItem("0"))
    table.setItem(2, COL_TYPE, QTableWidgetItem("Silver Bar"))

    logic.calculate_totals()

    assert logic.overall_gross_label.text == "13.5"
    assert logic.overall_poly_label.text == "1.5"
    assert logic.total_gross_label.text == "10.0"
    assert logic.total_net_label.text == "9.0"
    assert logic.total_fine_label.text == "8.3"
    assert logic.return_gross_label.text == "1.5"
    assert logic.return_net_label.text == "1.0"
    assert logic.return_fine_label.text == "0.5"
    assert logic.bar_gross_label.text == "2.0"
    assert logic.bar_net_label.text == "2.0"
    assert logic.bar_fine_label.text == "2.0"
    assert logic.net_fine_label.text == "5.8 + 1.5 = 7.3"
    assert logic.net_wage_label.text == "?90 + ?500 = ?590"
    assert logic.net_value_label.text == "?512750"
    assert logic.grand_total_label.text == "?513340"

def test_calculate_totals_handles_return_only(qt_app):
    logic, table = _prepare_logic_with_table(rows=2)
    logic.silver_rate_spin = SimpleNamespace(value=lambda: 65000.0)
    logic.total_fine_label = _LabelStub()
    logic.return_fine_label = _LabelStub()
    logic.bar_fine_label = _LabelStub()
    logic.net_fine_label = _LabelStub()

    table.setItem(0, COL_CODE, QTableWidgetItem("RET001"))
    table.setItem(0, COL_GROSS, QTableWidgetItem("3.0"))
    table.setItem(0, COL_POLY, QTableWidgetItem("0.5"))
    table.setItem(0, COL_NET_WT, QTableWidgetItem("2.5"))
    table.setItem(0, COL_FINE_WT, QTableWidgetItem("2.000"))
    table.setItem(0, COL_WAGE_AMT, QTableWidgetItem("0"))
    table.setItem(0, COL_TYPE, QTableWidgetItem("Return"))

    table.setItem(1, COL_CODE, QTableWidgetItem("RET002"))
    table.setItem(1, COL_GROSS, QTableWidgetItem("1.0"))
    table.setItem(1, COL_POLY, QTableWidgetItem("0.0"))
    table.setItem(1, COL_NET_WT, QTableWidgetItem("1.0"))
    table.setItem(1, COL_FINE_WT, QTableWidgetItem("1.000"))
    table.setItem(1, COL_WAGE_AMT, QTableWidgetItem("0"))
    table.setItem(1, COL_TYPE, QTableWidgetItem("Return"))

    logic.calculate_totals()

    assert logic.total_fine_label.text == "0.0"
    assert logic.return_fine_label.text == "3.0"
    assert logic.bar_fine_label.text == "0.0"
    assert logic.net_fine_label.text == "-3.0"


def test_calculate_fine_zero_inputs(qt_app):
    logic, table = _prepare_logic_with_table()
    logic.current_row = 0
    table.setItem(0, COL_PURITY, QTableWidgetItem("0"))
    table.setItem(0, COL_NET_WT, QTableWidgetItem("0"))

    logic.calculate_fine()

    assert table.item(0, COL_FINE_WT).text() == "0.000"


def test_calculate_fine_full_purity(qt_app):
    logic, table = _prepare_logic_with_table()
    logic.current_row = 0
    table.setItem(0, COL_PURITY, QTableWidgetItem("100"))
    table.setItem(0, COL_NET_WT, QTableWidgetItem("4.321"))


try:
    from hypothesis import given, strategies as st
    _HYPOTHESIS_AVAILABLE = True
except ModuleNotFoundError:
    _HYPOTHESIS_AVAILABLE = False

if _HYPOTHESIS_AVAILABLE:

    @given(
        net=st.floats(min_value=0.0, max_value=200.0, allow_nan=False, allow_infinity=False),
        purity=st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False),
    )
    def test_calculate_fine_property(qt_app, net, purity):
        logic, table = _prepare_logic_with_table()
        logic.current_row = 0
        table.setItem(0, COL_NET_WT, QTableWidgetItem(f"{net}"))
        table.setItem(0, COL_PURITY, QTableWidgetItem(f"{purity}"))

        logic.calculate_fine()

        expected = 0.0 if purity <= 0 else net * (purity / 100.0)
        actual = float(table.item(0, COL_FINE_WT).text())
        assert actual == pytest.approx(round(expected, 3), abs=1e-3)

    @given(
        net=st.floats(min_value=0.0, max_value=200.0, allow_nan=False, allow_infinity=False),
        rate=st.floats(min_value=0.0, max_value=200.0, allow_nan=False, allow_infinity=False),
        pieces=st.integers(min_value=0, max_value=20),
    )
    def test_calculate_wage_property(qt_app, net, rate, pieces):
        lookup = lambda code: {"wage_type": "PC"} if code == "PC001" else {"wage_type": "WT"}
        logic, table = _prepare_logic_with_table(rows=2, item_lookup=lookup)

        table.setItem(0, COL_CODE, QTableWidgetItem("WT001"))
        table.setItem(0, COL_NET_WT, QTableWidgetItem(f"{net}"))
        table.setItem(0, COL_WAGE_RATE, QTableWidgetItem(f"{rate}"))
        table.setItem(0, COL_PIECES, QTableWidgetItem("1"))
        logic.current_row = 0
        logic.calculate_wage()
        expected_wt = net * rate
        actual_wt = float(table.item(0, COL_WAGE_AMT).text())
        assert actual_wt == pytest.approx(round(expected_wt), abs=1)

        table.setItem(1, COL_CODE, QTableWidgetItem("PC001"))
        table.setItem(1, COL_NET_WT, QTableWidgetItem(f"{net}"))
        table.setItem(1, COL_WAGE_RATE, QTableWidgetItem(f"{rate}"))
        table.setItem(1, COL_PIECES, QTableWidgetItem(f"{pieces}"))
        logic.current_row = 1
        logic.calculate_wage()
        expected_pc = pieces * rate
        actual_pc = float(table.item(1, COL_WAGE_AMT).text())
        assert actual_pc == pytest.approx(round(expected_pc), abs=1)

else:

    @pytest.mark.skip(reason="hypothesis not installed")
    def test_calculate_fine_property(qt_app):  # pragma: no cover - dependency optional
        pytest.skip("hypothesis not installed")

    @pytest.mark.skip(reason="hypothesis not installed")
    def test_calculate_wage_property(qt_app):  # pragma: no cover - dependency optional
        pytest.skip("hypothesis not installed")
