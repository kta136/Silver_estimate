# Presenter Testing Example (Without Qt)

This document demonstrates how to test business logic **without Qt** using the presenter pattern.

## Key Benefit

**Problem**: Qt tests require `QApplication`, making them slow (~100-500ms per test)
**Solution**: Test presenter directly with mocks, achieving ~1-5ms per test

## Example: Testing Totals Calculation

### The Presenter Method

```python
# silverestimate/presenter/estimate_entry_presenter.py

def refresh_totals(self) -> TotalsResult:
    """Recompute totals based on the current view state."""
    state = self._view.capture_state()
    totals = compute_totals(
        state.lines,
        silver_rate=state.silver_rate,
        last_balance_silver=state.last_balance_silver,
        last_balance_amount=state.last_balance_amount,
    )
    self._view.apply_totals(totals)
    return totals
```

### The Test (No Qt Required!)

```python
# tests/unit/test_presenter_example.py

from unittest.mock import Mock
from silverestimate.presenter import (
    EstimateEntryPresenter,
    EstimateEntryViewState,
)
from silverestimate.domain.estimate_models import EstimateLine


def test_refresh_totals_no_qt_required():
    """Demonstrate testing business logic without Qt dependencies."""

    # 1. Create mock view (no Qt!)
    mock_view = Mock()
    mock_view.capture_state.return_value = EstimateEntryViewState(
        lines=[
            EstimateLine(
                code="RING001",
                name="Gold Ring",
                gross=10.0,
                poly=1.0,
                net_weight=9.0,
                purity=92.5,
                wage_rate=10.0,
                pieces=1,
                wage_amount=90.0,
                fine_weight=8.325,
                category="regular",
            ),
        ],
        silver_rate=5000.0,
        last_balance_silver=0.0,
        last_balance_amount=0.0,
    )

    # 2. Create mock repository (no database!)
    mock_repo = Mock()

    # 3. Create presenter
    presenter = EstimateEntryPresenter(mock_view, mock_repo)

    # 4. Execute business logic (FAST - no Qt initialization!)
    result = presenter.refresh_totals()

    # 5. Verify results
    assert result.total_gross == 10.0
    assert result.total_net_wt == 9.0
    assert result.total_fine_wt == 8.325
    assert result.total_wage == 90.0

    # 6. Verify view was updated
    mock_view.apply_totals.assert_called_once()
    call_args = mock_view.apply_totals.call_args[0][0]
    assert call_args.total_fine_wt == 8.325
```

### Test Execution Time Comparison

| Test Type | Time per Test | Example |
|-----------|--------------|---------|
| **Presenter Test** (no Qt) | ~1-5ms | `test_refresh_totals_no_qt_required` |
| **Widget Integration Test** | ~100-500ms | `test_widget_calculates_totals` |

**Speedup**: 20-100x faster for presenter tests!

---

## Example 2: Testing Item Lookup

### The Presenter Method

```python
# silverestimate/presenter/estimate_entry_presenter.py

def handle_item_code(self, row_index: int, code: str) -> bool:
    """Resolve an item code for the specified row, populating the view."""
    normalized = (code or "").strip().upper()
    if not normalized:
        self._view.show_status("Enter item code first", 1500)
        return False

    item = self._repository.fetch_item(normalized)
    if item:
        self._view.populate_row(row_index, item)
        self._view.focus_after_item_lookup(row_index)
        self._view.show_status(f"Item '{normalized}' loaded.", 2000)
        return True

    # ... handle item selection dialog ...
```

### The Test (No Qt!)

```python
def test_handle_item_code_found():
    """Test item lookup when item exists in repository."""

    # Setup
    mock_view = Mock()
    mock_repo = Mock()
    mock_repo.fetch_item.return_value = {
        "code": "RING001",
        "name": "Gold Ring",
        "purity": 92.5,
        "wage_rate": 10.0,
    }

    presenter = EstimateEntryPresenter(mock_view, mock_repo)

    # Execute
    result = presenter.handle_item_code(row_index=0, code="ring001")

    # Verify
    assert result is True
    mock_repo.fetch_item.assert_called_once_with("RING001")
    mock_view.populate_row.assert_called_once_with(
        0,
        {"code": "RING001", "name": "Gold Ring", "purity": 92.5, "wage_rate": 10.0}
    )
    mock_view.focus_after_item_lookup.assert_called_once_with(0)
    mock_view.show_status.assert_called_with("Item 'RING001' loaded.", 2000)


def test_handle_item_code_empty():
    """Test item lookup with empty code."""

    # Setup
    mock_view = Mock()
    mock_repo = Mock()
    presenter = EstimateEntryPresenter(mock_view, mock_repo)

    # Execute
    result = presenter.handle_item_code(row_index=0, code="  ")

    # Verify
    assert result is False
    mock_repo.fetch_item.assert_not_called()
    mock_view.show_status.assert_called_with("Enter item code first", 1500)
```

---

## Running Presenter Tests

```bash
# Run all presenter tests (FAST)
pytest tests/unit/test_estimate_entry_presenter.py -v

# Compare speed
pytest tests/unit/test_estimate_entry_presenter.py -v --durations=10  # See individual timings
```

### Example Output

```
tests/unit/test_estimate_entry_presenter.py::test_refresh_totals_no_qt_required PASSED [11%] (0.002s)
tests/unit/test_estimate_entry_presenter.py::test_handle_item_code_found PASSED [22%] (0.001s)
tests/unit/test_estimate_entry_presenter.py::test_handle_item_code_empty PASSED [33%] (0.001s)
tests/unit/test_estimate_entry_presenter.py::test_save_estimate_success PASSED [44%] (0.003s)

====== 9 passed in 0.03s ======
```

**vs Widget Tests:**

```
tests/ui/test_estimate_entry_widget.py::test_widget_calculates_totals PASSED (0.342s)
tests/ui/test_estimate_entry_widget.py::test_widget_multi_row_totals PASSED (0.389s)

====== 3 passed in 1.24s ======
```

---

## Architecture Pattern

### Without Presenter (Old Approach)

```python
# Everything in widget - can't test without Qt!
class EstimateEntryWidget(QWidget):
    def calculate_totals(self):
        # Business logic mixed with UI
        lines = []
        for row in range(self.table.rowCount()):
            code = self.table.item(row, 0).text()
            gross = float(self.table.item(row, 1).text())
            # ... extract all values from table ...
            lines.append(EstimateLine(...))

        totals = compute_totals(lines, self.silver_rate)

        # Update UI
        self.total_gross_label.setText(str(totals.total_gross))
        # ... update all labels ...
```

**Problem**: Can't test `calculate_totals()` without creating entire Qt widget!

---

### With Presenter (New Approach)

```python
# Presenter: Pure Python, no Qt
class EstimateEntryPresenter:
    def refresh_totals(self) -> TotalsResult:
        state = self._view.capture_state()  # View provides data
        totals = compute_totals(state.lines, state.silver_rate)
        self._view.apply_totals(totals)  # View updates UI
        return totals

# Widget: Thin UI coordinator
class EstimateEntryWidget(QWidget):
    def calculate_totals(self):
        self.presenter.refresh_totals()  # Delegate to presenter!
```

**Benefit**: Test presenter with mock view (no Qt) + Test widget integration (with Qt)

---

## Best Practices

### 1. Presenter Tests (Fast, Focused)

**What to test:**
- ✅ Business logic (calculations, validations)
- ✅ Data transformations (loading estimates, saving)
- ✅ Coordination (fetching items, managing silver bars)
- ✅ Error handling

**What NOT to test:**
- ❌ UI layout
- ❌ Button clicks
- ❌ Focus management
- ❌ Signal/slot wiring

### 2. Widget Tests (Slower, Integration)

**What to test:**
- ✅ Component integration
- ✅ Signal/slot wiring
- ✅ User workflows (click button → see result)
- ✅ Adapter layer (Model/View compatibility)

**What NOT to test:**
- ❌ Business logic details (delegate to presenter tests)
- ❌ Calculation formulas (covered by service tests + presenter tests)

---

## Actual Tests in Codebase

The project already has 9 presenter tests demonstrating this pattern:

| Test | What It Tests | Time |
|------|--------------|------|
| `test_open_history_successful_load` | History loading workflow | ~2ms |
| `test_save_estimate_success_adds_new_bar` | Save + silver bar sync | ~3ms |
| `test_load_estimate_transforms_repository_response` | Data transformation | ~1ms |
| `test_delete_estimate_delegates_to_repository` | Delete operation | ~1ms |

**Total test time**: ~30ms for all 9 tests
**Equivalent widget tests**: Would take ~3000ms (100x slower)

---

## Summary

The presenter pattern enables:

1. **Fast Tests**: 20-100x faster than Qt tests
2. **Focused Tests**: Test business logic in isolation
3. **Reusable Logic**: Presenter usable in CLI, API, batch scripts
4. **Clear Separation**: UI concerns vs business logic

**Example from our codebase:**

```bash
# All presenter tests
pytest tests/unit/test_estimate_entry_presenter.py
# ~0.03 seconds for 9 tests

# Compare to widget tests
pytest tests/ui/test_estimate_entry_widget.py
# ~1.5 seconds for 3 tests
```

**Key Takeaway**: Write presenter tests for business logic, widget tests for integration.
