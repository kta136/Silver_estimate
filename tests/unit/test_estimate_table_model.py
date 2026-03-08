"""Tests for EstimateTableModel."""

import pytest
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QTableView

from silverestimate.domain.estimate_models import EstimateLineCategory
from silverestimate.ui.estimate_entry_logic.constants import (
    COL_CODE,
    COL_FINE_WT,
    COL_GROSS,
    COL_ITEM_NAME,
    COL_NET_WT,
    COL_PIECES,
    COL_POLY,
    COL_PURITY,
    COL_TYPE,
    COL_WAGE_AMT,
    COL_WAGE_RATE,
)
from silverestimate.ui.models.estimate_table_model import EstimateTableModel
from silverestimate.ui.numeric_font import numeric_table_font
from silverestimate.ui.view_models.estimate_entry_view_model import (
    EstimateEntryRowState,
)


@pytest.fixture
def model(qt_app):
    """Create a fresh EstimateTableModel for testing."""
    return EstimateTableModel()


def test_initial_state(model):
    """Test that model starts empty."""
    assert model.rowCount() == 0
    assert model.columnCount() == 11  # 11 columns


def test_add_row(model):
    """Test adding a row to the model."""
    row_idx = model.add_row()
    assert row_idx == 0
    assert model.rowCount() == 1


def test_add_row_with_data(model):
    """Test adding a row with specific data."""
    row_data = EstimateEntryRowState(
        code="TEST001",
        name="Test Item",
        gross=100.0,
        poly=5.0,
        net_weight=95.0,
        purity=91.6,
        wage_rate=50.0,
        pieces=1,
        wage_amount=100.0,
        fine_weight=87.02,
        category=EstimateLineCategory.REGULAR,
        row_index=0,
    )
    row_idx = model.add_row(row_data)
    assert row_idx == 0
    assert model.rowCount() == 1

    # Verify data was stored correctly
    index = model.index(0, COL_CODE)
    assert model.data(index, Qt.DisplayRole) == "TEST001"


def test_get_row(model):
    """Test retrieving row data."""
    row_data = EstimateEntryRowState(
        code="TEST002",
        name="Test Item 2",
        gross=200.0,
    )
    model.add_row(row_data)

    retrieved = model.get_row(0)
    assert retrieved is not None
    assert retrieved.code == "TEST002"
    assert retrieved.name == "Test Item 2"
    assert retrieved.gross == 200.0


def test_set_data(model):
    """Test setting data in a cell."""
    model.add_row()

    # Set code
    index = model.index(0, COL_CODE)
    success = model.setData(index, "NEWCODE", Qt.EditRole)
    assert success is True
    assert model.data(index, Qt.DisplayRole) == "NEWCODE"

    # Set gross weight
    index = model.index(0, COL_GROSS)
    success = model.setData(index, 150.5, Qt.EditRole)
    assert success is True
    assert model.data(index, Qt.DisplayRole) == "150.500"
    assert model.data(index, Qt.EditRole) == 150.5


def test_numeric_display_role_formats_using_column_precision_and_grouping(model):
    model.add_row(
        EstimateEntryRowState(
            gross=1234567.5,
            poly=12345.25,
            net_weight=1234567.5,
            purity=91.6,
            wage_rate=1500.0,
            pieces=123456,
            wage_amount=1234567.0,
            fine_weight=1130778.77,
        )
    )

    assert model.data(model.index(0, COL_GROSS), Qt.DisplayRole) == "12,34,567.500"
    assert model.data(model.index(0, COL_POLY), Qt.DisplayRole) == "12,345.250"
    assert model.data(model.index(0, COL_NET_WT), Qt.DisplayRole) == "12,34,567.50"
    assert model.data(model.index(0, COL_PURITY), Qt.DisplayRole) == "91.60"
    assert model.data(model.index(0, COL_WAGE_RATE), Qt.DisplayRole) == "1,500.00"
    assert model.data(model.index(0, COL_PIECES), Qt.DisplayRole) == "1,23,456"
    assert model.data(model.index(0, COL_WAGE_AMT), Qt.DisplayRole) == "12,34,567"
    assert model.data(model.index(0, COL_FINE_WT), Qt.DisplayRole) == "11,30,778.77"

    assert model.data(model.index(0, COL_GROSS), Qt.EditRole) == 1234567.5
    assert model.data(model.index(0, COL_PIECES), Qt.EditRole) == 123456


def test_remove_row(model):
    """Test removing a row."""
    model.add_row()
    model.add_row()
    assert model.rowCount() == 2

    success = model.remove_row(0)
    assert success is True
    assert model.rowCount() == 1


def test_clear_rows(model):
    """Test clearing all rows."""
    model.add_row()
    model.add_row()
    model.add_row()
    assert model.rowCount() == 3

    model.clear_rows()
    assert model.rowCount() == 0


def test_get_all_rows(model):
    """Test retrieving all rows."""
    row1 = EstimateEntryRowState(code="A", name="Item A")
    row2 = EstimateEntryRowState(code="B", name="Item B")

    model.add_row(row1)
    model.add_row(row2)

    all_rows = model.get_all_rows()
    assert len(all_rows) == 2
    assert all_rows[0].code == "A"
    assert all_rows[1].code == "B"


def test_set_all_rows(model):
    """Test setting all rows at once."""
    rows = [
        EstimateEntryRowState(code="X", name="Item X"),
        EstimateEntryRowState(code="Y", name="Item Y"),
        EstimateEntryRowState(code="Z", name="Item Z"),
    ]

    model.set_all_rows(rows)
    assert model.rowCount() == 3

    retrieved = model.get_all_rows()
    assert len(retrieved) == 3
    assert retrieved[0].code == "X"
    assert retrieved[1].code == "Y"
    assert retrieved[2].code == "Z"


def test_header_data(model):
    """Test header data retrieval."""
    # Horizontal headers
    assert model.headerData(COL_CODE, Qt.Horizontal, Qt.DisplayRole) == "Code"
    assert model.headerData(COL_ITEM_NAME, Qt.Horizontal, Qt.DisplayRole) == "Item Name"
    assert model.headerData(COL_GROSS, Qt.Horizontal, Qt.DisplayRole) == "Gross"

    # Vertical headers (row numbers)
    model.add_row()
    model.add_row()
    assert model.headerData(0, Qt.Vertical, Qt.DisplayRole) == 1
    assert model.headerData(1, Qt.Vertical, Qt.DisplayRole) == 2


def test_numeric_columns_return_font_role_derived_from_table_font(qt_app):
    table = QTableView()
    table_font = table.font()
    table_font.setPointSize(13)
    table.setFont(table_font)

    model = EstimateTableModel(table)
    model.add_row(EstimateEntryRowState())

    expected_font = numeric_table_font(table.font())
    for column in (
        COL_GROSS,
        COL_POLY,
        COL_NET_WT,
        COL_PURITY,
        COL_WAGE_RATE,
        COL_PIECES,
        COL_WAGE_AMT,
        COL_FINE_WT,
    ):
        font = model.data(model.index(0, column), Qt.FontRole)
        assert font is not None
        assert font.key() == expected_font.key()


def test_non_numeric_columns_do_not_return_font_role(model):
    model.add_row(EstimateEntryRowState())

    for column in (COL_CODE, COL_ITEM_NAME, COL_TYPE):
        assert model.data(model.index(0, column), Qt.FontRole) is None


def test_numeric_columns_keep_right_alignment(model):
    model.add_row(EstimateEntryRowState())

    for column in (
        COL_GROSS,
        COL_POLY,
        COL_NET_WT,
        COL_PURITY,
        COL_WAGE_RATE,
        COL_PIECES,
        COL_WAGE_AMT,
        COL_FINE_WT,
    ):
        assert model.data(model.index(0, column), Qt.TextAlignmentRole) == (
            Qt.AlignRight | Qt.AlignVCenter
        )


def test_data_changed_signal(model):
    """Test that data changed signal is emitted."""
    model.add_row()

    # Track if signal was emitted
    signal_emitted = []

    def on_data_changed(*args):
        signal_emitted.append(True)

    model.dataChanged.connect(on_data_changed)

    index = model.index(0, COL_CODE)
    model.setData(index, "SIGNAL_TEST", Qt.EditRole)

    assert len(signal_emitted) > 0, "dataChanged signal should have been emitted"


def test_set_data_unchanged_code_is_noop_without_signals(model):
    """Unchanged code edits should not emit change signals."""
    model.add_row(EstimateEntryRowState(code="KEEP1", purity=91.6, wage_rate=10.0))

    detailed_events = []
    changed_events = []
    model.data_changed_detailed.connect(lambda *args: detailed_events.append(args))
    model.dataChanged.connect(lambda *args: changed_events.append(args))

    index = model.index(0, COL_CODE)
    assert model.setData(index, "KEEP1", Qt.EditRole)

    assert model.data(index, Qt.DisplayRole) == "KEEP1"
    assert detailed_events == []
    assert changed_events == []


def test_set_data_unchanged_non_code_still_emits_signals(model):
    """Unchanged non-code edits should still emit signals for navigation flows."""
    model.add_row(EstimateEntryRowState(code="KEEP1", purity=91.6, wage_rate=10.0))

    detailed_events = []
    changed_events = []
    model.data_changed_detailed.connect(lambda *args: detailed_events.append(args))
    model.dataChanged.connect(lambda *args: changed_events.append(args))

    index = model.index(0, COL_PURITY)
    assert model.setData(index, 91.6, Qt.EditRole)

    assert model.data(index, Qt.DisplayRole) == "91.60"
    assert model.data(index, Qt.EditRole) == 91.6
    assert len(detailed_events) == 1
    assert len(changed_events) == 1


def test_set_row(model):
    """Test setting an entire row."""
    model.add_row()

    new_row_data = EstimateEntryRowState(
        code="UPDATED",
        name="Updated Item",
        gross=500.0,
    )

    success = model.set_row(0, new_row_data)
    assert success is True

    retrieved = model.get_row(0)
    assert retrieved.code == "UPDATED"
    assert retrieved.name == "Updated Item"
    assert retrieved.gross == 500.0


def test_pieces_flags_depend_on_wage_type(model):
    """Pieces column should be editable only for PC rows."""
    wt_row = EstimateEntryRowState(code="WT001", wage_type="WT", pieces=0)
    pc_row = EstimateEntryRowState(code="PC001", wage_type="PC", pieces=1)
    model.add_row(wt_row)
    model.add_row(pc_row)

    wt_flags = model.flags(model.index(0, COL_PIECES))
    pc_flags = model.flags(model.index(1, COL_PIECES))

    assert not bool(wt_flags & Qt.ItemIsEditable)
    assert bool(pc_flags & Qt.ItemIsEditable)


def test_set_row_wage_type_updates_flags_and_normalizes(model):
    """set_row_wage_type should normalize values and change editability."""
    model.add_row(EstimateEntryRowState(code="TEST", wage_type="PC", pieces=1))

    assert bool(model.flags(model.index(0, COL_PIECES)) & Qt.ItemIsEditable)
    assert model.set_row_wage_type(0, "wt")
    assert not bool(model.flags(model.index(0, COL_PIECES)) & Qt.ItemIsEditable)

    row = model.get_row(0)
    assert row is not None
    assert row.wage_type == "WT"


def test_calculated_columns_have_distinct_visual_roles(model):
    """Calculated columns should read as non-editable outputs."""
    model.add_row(
        EstimateEntryRowState(
            code="TEST1",
            net_weight=10.0,
            wage_amount=100.0,
            fine_weight=9.1,
        )
    )

    for column in (COL_NET_WT, COL_WAGE_AMT, COL_FINE_WT):
        index = model.index(0, column)
        background = model.data(index, Qt.BackgroundRole)
        foreground = model.data(index, Qt.ForegroundRole)
        assert background is not None
        assert foreground is not None


def test_type_column_keeps_category_background_role(model):
    """Type column background should still reflect the line category."""
    model.add_row(
        EstimateEntryRowState(code="RET1", category=EstimateLineCategory.RETURN)
    )
    index = model.index(0, COL_TYPE)
    background = model.data(index, Qt.BackgroundRole)
    assert background is not None


def test_type_column_displays_regular_for_regular_rows(model):
    model.add_row(
        EstimateEntryRowState(code="REG1", category=EstimateLineCategory.REGULAR)
    )

    assert model.data(model.index(0, COL_TYPE), Qt.DisplayRole) == "Regular"


def test_type_column_uses_semantic_mode_colors(model):
    model.add_row(
        EstimateEntryRowState(code="REG1", category=EstimateLineCategory.REGULAR)
    )
    model.add_row(
        EstimateEntryRowState(code="RET1", category=EstimateLineCategory.RETURN)
    )
    model.add_row(
        EstimateEntryRowState(code="BAR1", category=EstimateLineCategory.SILVER_BAR)
    )

    regular_bg = model.data(model.index(0, COL_TYPE), Qt.BackgroundRole)
    regular_fg = model.data(model.index(0, COL_TYPE), Qt.ForegroundRole)
    return_bg = model.data(model.index(1, COL_TYPE), Qt.BackgroundRole)
    return_fg = model.data(model.index(1, COL_TYPE), Qt.ForegroundRole)
    bar_bg = model.data(model.index(2, COL_TYPE), Qt.BackgroundRole)
    bar_fg = model.data(model.index(2, COL_TYPE), Qt.ForegroundRole)

    assert regular_bg.color().name() == "#f8fafc"
    assert regular_fg.color().name() == "#334155"
    assert return_bg.color().name() == "#dbeafe"
    assert return_fg.color().name() == "#1d4ed8"
    assert bar_bg.color().name() == "#fff7ed"
    assert bar_fg.color().name() == "#b45309"


def test_set_data_pieces_defaults_for_wage_type(model):
    """Pieces empty input should map to WT=0 and PC=1."""
    model.add_row(EstimateEntryRowState(code="WT001", wage_type="WT", pieces=7))
    model.add_row(EstimateEntryRowState(code="PC001", wage_type="PC", pieces=5))

    assert model.setData(model.index(0, COL_PIECES), "", Qt.EditRole)
    assert model.setData(model.index(1, COL_PIECES), "", Qt.EditRole)

    assert model.data(model.index(0, COL_PIECES), Qt.DisplayRole) == "0"
    assert model.data(model.index(1, COL_PIECES), Qt.DisplayRole) == "1"
    assert model.data(model.index(0, COL_PIECES), Qt.EditRole) == 0
    assert model.data(model.index(1, COL_PIECES), Qt.EditRole) == 1
