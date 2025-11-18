"""Tests for EstimateTableView component."""

import pytest

from silverestimate.domain.estimate_models import EstimateLineCategory
from silverestimate.ui.estimate_entry_components.estimate_table_view import (
    EstimateTableView,
)
from silverestimate.ui.view_models.estimate_entry_view_model import EstimateEntryRowState


@pytest.fixture
def table_view(qt_app):
    """Create a fresh EstimateTableView for testing."""
    return EstimateTableView()


def test_initial_state(table_view):
    """Test that table view initializes correctly."""
    model = table_view.get_model()
    assert model is not None
    assert model.rowCount() == 0
    assert model.columnCount() == 11


def test_add_row(table_view):
    """Test adding a row to the table."""
    row_idx = table_view.add_row()
    assert row_idx == 0
    assert table_view.get_model().rowCount() == 1


def test_add_row_with_data(table_view):
    """Test adding a row with specific data."""
    row_data = EstimateEntryRowState(
        code="TEST001",
        name="Test Item",
        gross=100.0,
    )
    row_idx = table_view.add_row(row_data)
    assert row_idx == 0

    retrieved = table_view.get_row(0)
    assert retrieved is not None
    assert retrieved.code == "TEST001"
    assert retrieved.name == "Test Item"


def test_delete_row(table_view):
    """Test deleting a row."""
    table_view.add_row()
    table_view.add_row()
    assert table_view.get_model().rowCount() == 2

    success = table_view.delete_row(0)
    assert success is True
    assert table_view.get_model().rowCount() == 1


def test_clear_rows(table_view):
    """Test clearing all rows."""
    table_view.add_row()
    table_view.add_row()
    table_view.add_row()
    assert table_view.get_model().rowCount() == 3

    table_view.clear_rows()
    assert table_view.get_model().rowCount() == 0


def test_get_row(table_view):
    """Test retrieving row data."""
    row_data = EstimateEntryRowState(
        code="TEST002",
        name="Test Item 2",
        gross=200.0,
    )
    table_view.add_row(row_data)

    retrieved = table_view.get_row(0)
    assert retrieved is not None
    assert retrieved.code == "TEST002"


def test_set_row(table_view):
    """Test setting row data."""
    table_view.add_row()

    new_data = EstimateEntryRowState(
        code="UPDATED",
        name="Updated Item",
        gross=500.0,
    )
    success = table_view.set_row(0, new_data)
    assert success is True

    retrieved = table_view.get_row(0)
    assert retrieved.code == "UPDATED"


def test_get_all_rows(table_view):
    """Test retrieving all rows."""
    row1 = EstimateEntryRowState(code="A", name="Item A")
    row2 = EstimateEntryRowState(code="B", name="Item B")

    table_view.add_row(row1)
    table_view.add_row(row2)

    all_rows = table_view.get_all_rows()
    assert len(all_rows) == 2
    assert all_rows[0].code == "A"
    assert all_rows[1].code == "B"


def test_set_all_rows(table_view):
    """Test setting all rows at once."""
    rows = [
        EstimateEntryRowState(code="X", name="Item X"),
        EstimateEntryRowState(code="Y", name="Item Y"),
        EstimateEntryRowState(code="Z", name="Item Z"),
    ]

    table_view.set_all_rows(rows)
    assert table_view.get_model().rowCount() == 3

    retrieved = table_view.get_all_rows()
    assert len(retrieved) == 3
    assert retrieved[0].code == "X"


def test_focus_cell(table_view):
    """Test focusing on a specific cell."""
    table_view.add_row()
    table_view.focus_cell(0, 0)

    assert table_view.get_current_row() == 0
    assert table_view.get_current_column() == 0


def test_get_current_row_when_empty(table_view):
    """Test getting current row when no row is selected."""
    assert table_view.get_current_row() == -1


def test_get_current_column_when_empty(table_view):
    """Test getting current column when no column is selected."""
    assert table_view.get_current_column() == -1


def test_save_and_restore_column_widths(table_view):
    """Test saving and restoring column widths."""
    # Set some custom widths
    table_view.setColumnWidth(0, 150)
    table_view.setColumnWidth(1, 250)

    # Save widths
    widths = table_view.save_column_widths()
    assert widths[0] == 150
    assert widths[1] == 250

    # Change widths
    table_view.setColumnWidth(0, 100)
    table_view.setColumnWidth(1, 100)

    # Restore
    table_view.restore_column_widths(widths)
    assert table_view.columnWidth(0) == 150
    assert table_view.columnWidth(1) == 250


def test_reset_column_widths(table_view):
    """Test resetting column widths to defaults."""
    # Set some custom widths
    table_view.setColumnWidth(0, 500)

    # Reset
    table_view.reset_column_widths()

    # Should be default width (100 for code column)
    assert table_view.columnWidth(0) == 100


def test_row_deleted_signal(table_view):
    """Test that row deletion emits signal."""
    table_view.add_row()
    table_view.add_row()

    deleted_rows = []
    table_view.row_deleted.connect(lambda r: deleted_rows.append(r))

    # Select first row and trigger delete
    table_view.selectRow(0)
    table_view._delete_current_row()

    assert len(deleted_rows) == 1
    assert deleted_rows[0] == 0


def test_cell_edited_signal(table_view):
    """Test that cell edits emit signal."""
    table_view.add_row()

    edits = []
    table_view.cell_edited.connect(lambda r, c: edits.append((r, c)))

    # Edit a cell through the model
    model = table_view.get_model()
    index = model.index(0, 0)
    model.setData(index, "TEST", 2)  # Qt.EditRole = 2

    assert len(edits) > 0
    assert edits[0] == (0, 0)


def test_column_layout_reset_signal(table_view):
    """Test that context menu reset emits signal."""
    reset_requested = []
    table_view.column_layout_reset_requested.connect(lambda: reset_requested.append(True))

    # Simulate context menu action
    # Note: We can't easily test the actual context menu without GUI interaction
    # but we can verify the signal exists and is connectable
    assert hasattr(table_view, 'column_layout_reset_requested')


def test_history_requested_signal(table_view):
    """Test that history signal exists."""
    assert hasattr(table_view, 'history_requested')


def test_item_lookup_requested_signal(table_view):
    """Test that item lookup signal exists."""
    assert hasattr(table_view, 'item_lookup_requested')
