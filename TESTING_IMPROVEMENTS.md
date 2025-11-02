# Testing Improvements for Estimate Entry Widget

## Problems Identified

### 1. Adapter Layer Not Tested
The `insertRow`, `removeRow`, `setCurrentCell`, and `editItem` AttributeErrors weren't caught because:

1. **Tests bypass the adapter layer** - Tests call `widget.add_empty_row()` directly instead of clicking the "Add Row" button
2. **Signals are disconnected** - Tests disconnect `cellChanged` signal to avoid event chains
3. **No integration tests** - No tests simulate real user interactions (button clicks, typing, etc.)
4. **Manual data population** - Tests manually create QTableWidgetItem objects instead of using the adapter

### 2. Timer-Delayed Operations Not Tested ⚠️ CRITICAL
The `editItem` error was particularly insidious because:

1. **QTimer.singleShot delays execution** - `force_focus_to_first_cell()` is called 100ms after widget creation
2. **Tests complete before timers fire** - Synchronous tests call `widget.deleteLater()` immediately
3. **No event loop waiting** - Tests don't wait for pending Qt events/timers to complete

This is a **classic async testing gap** that's common in Qt applications!

## Recommended Test Additions

### Critical Priority - Async/Timer Tests ⚠️

```python
def test_widget_initialization_with_timers(qt_app, fake_db):
    """Test delayed initialization operations execute properly."""
    from PyQt5.QtTest import QTest

    widget = _make_widget(fake_db)
    try:
        # CRITICAL: Wait for QTimer.singleShot operations to complete
        QTest.qWait(200)  # Wait for 100ms timer + buffer

        # Now test the delayed operation
        current_index = widget.item_table.currentIndex()
        assert current_index.isValid()
        assert current_index.column() == COL_CODE
    finally:
        widget.deleteLater()
```

**Key Technique**: Always use `QTest.qWait()` when testing code that uses:
- `QTimer.singleShot()`
- `QTimer` with intervals
- Signal emissions that trigger delayed operations
- Any async Qt operations

### High Priority - Integration Tests

```python
def test_add_row_button_creates_new_row(qt_app, fake_db):
    """Test that clicking Add Row button actually adds a row via adapter."""
    widget = _make_widget(fake_db)
    initial_count = widget.item_table.rowCount()

    # Simulate button click (triggers EstimateTableAdapter.add_empty_row)
    widget.secondary_actions.add_row_button.click()

    assert widget.item_table.rowCount() == initial_count + 1
    widget.deleteLater()


def test_adapter_populate_row_with_model_view(qt_app, fake_db):
    """Test that adapter's populate_row works with Model/View architecture."""
    widget = _make_widget(fake_db)

    # This should exercise EstimateTableAdapter.populate_row
    # which calls insertRow(), item(), setItem(), etc.
    widget.table_adapter.add_empty_row()
    widget.table_adapter.populate_row(0, {
        "code": "TEST01",
        "name": "Test Item",
        "purity": 92.5,
        "wage_rate": 10.0
    })

    table = widget.item_table
    assert table.item(0, COL_CODE).text() == "TEST01"
    assert table.item(0, COL_ITEM_NAME).text() == "Test Item"
    widget.deleteLater()


def test_typing_in_cell_triggers_adapter_logic(qt_app, fake_db):
    """Test that typing in cells triggers the full signal chain."""
    widget = _make_widget(fake_db)
    # Don't disconnect signals - test the full flow

    # Simulate user typing in code cell
    table = widget.item_table
    index = table.model().index(0, COL_CODE)
    table.model().setData(index, "ABC123", Qt.EditRole)

    # Verify signal propagation worked
    assert table.item(0, COL_CODE).text() == "ABC123"
    widget.deleteLater()
```

### Medium Priority - Component Tests

```python
def test_estimate_table_view_compatibility_methods(qt_app):
    """Test QTableWidget compatibility methods on EstimateTableView."""
    from silverestimate.ui.estimate_entry_components import EstimateTableView

    table = EstimateTableView()

    # Test insertRow
    initial_count = table.rowCount()
    table.insertRow(0)
    assert table.rowCount() == initial_count + 1

    # Test item() returns ModelBackedTableItem
    item = table.item(0, 0)
    assert item is not None

    # Test setItem updates model
    from PyQt5.QtWidgets import QTableWidgetItem
    new_item = QTableWidgetItem("test")
    table.setItem(0, 0, new_item)
    assert table.item(0, 0).text() == "test"

    table.deleteLater()


def test_model_backed_item_syncs_with_model(qt_app):
    """Test that ModelBackedTableItem updates the underlying model."""
    from silverestimate.ui.estimate_entry_components import EstimateTableView

    table = EstimateTableView()
    table.insertRow(0)

    item = table.item(0, 0)
    item.setText("updated")

    # Verify model was updated
    index = table.model().index(0, 0)
    assert table.model().data(index, Qt.DisplayRole) == "updated"

    table.deleteLater()
```

### Low Priority - Edge Cases

```python
def test_adapter_with_empty_table(qt_app, fake_db):
    """Test adapter operations on completely empty table."""
    widget = _make_widget(fake_db)
    widget.clear_all_rows()

    # Should create row if needed
    widget.table_adapter.focus_on_empty_row()
    assert widget.item_table.rowCount() > 0
    widget.deleteLater()


def test_adapter_prevents_duplicate_empty_rows(qt_app, fake_db):
    """Test that adapter doesn't add multiple empty rows."""
    widget = _make_widget(fake_db)
    initial_count = widget.item_table.rowCount()

    # Call add_empty_row multiple times
    widget.table_adapter.add_empty_row()
    widget.table_adapter.add_empty_row()

    # Should only add one row (focuses existing empty row)
    assert widget.item_table.rowCount() == initial_count + 1
    widget.deleteLater()
```

## Testing Strategy Changes

### Current Approach (Limited)
```python
# Tests manually populate data
table.setItem(row, col, QTableWidgetItem(value))
widget.calculate_totals()
```

**Issues:**
- Bypasses adapter layer
- Doesn't test signal routing
- Misses compatibility issues

### Recommended Approach (Comprehensive)
```python
# Test via user interactions
widget.secondary_actions.add_row_button.click()
widget.table_adapter.populate_row(row, item_data)
# OR simulate typing
table.editItem(table.item(row, col))
```

**Benefits:**
- Tests full code paths
- Catches integration issues
- Validates signal routing
- Exercises compatibility layer

## Implementation Plan

1. **Phase 1**: Add 3-5 integration tests that exercise adapter methods
2. **Phase 2**: Add component-level tests for EstimateTableView compatibility
3. **Phase 3**: Refactor existing tests to use adapter instead of manual setItem
4. **Phase 4**: Add pytest-qt fixtures for simulating user interactions

## Success Metrics

- **Current**: ~13% coverage, adapter errors not caught
- **Target**:
  - 50%+ coverage including adapter layer
  - All user interaction paths tested
  - QTableWidget compatibility verified in tests
  - No more runtime-only errors

## Files to Update

- `tests/ui/test_estimate_entry_widget.py` - Add integration tests
- `tests/ui/test_estimate_table_view.py` - **NEW FILE** - Component tests
- `tests/ui/test_estimate_table_adapter.py` - **NEW FILE** - Adapter tests
- `tests/conftest.py` - Add helpers for user interaction simulation
