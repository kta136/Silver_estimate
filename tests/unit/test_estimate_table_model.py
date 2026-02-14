"""Tests for EstimateTableModel."""

import pytest
from PyQt5.QtCore import Qt

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
    COL_WAGE_AMT,
    COL_WAGE_RATE,
)
from silverestimate.ui.models.estimate_table_model import EstimateTableModel
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
    assert model.data(index, Qt.DisplayRole) == 150.5


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


def test_set_data_pieces_defaults_for_wage_type(model):
    """Pieces empty input should map to WT=0 and PC=1."""
    model.add_row(EstimateEntryRowState(code="WT001", wage_type="WT", pieces=7))
    model.add_row(EstimateEntryRowState(code="PC001", wage_type="PC", pieces=5))

    assert model.setData(model.index(0, COL_PIECES), "", Qt.EditRole)
    assert model.setData(model.index(1, COL_PIECES), "", Qt.EditRole)

    assert model.data(model.index(0, COL_PIECES), Qt.DisplayRole) == 0
    assert model.data(model.index(1, COL_PIECES), Qt.DisplayRole) == 1
