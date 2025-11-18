# EstimateEntryWidget Public API Documentation

**File**: `silverestimate/ui/estimate_entry.py`
**Class**: `EstimateEntryWidget`
**Version**: 2.0.x
**Last Updated**: 2025-11-01

---

## Overview

`EstimateEntryWidget` is the main widget for creating and managing silver item estimates. It provides a table-based interface for entering item details, calculating values, and managing vouchers.

### Inheritance Hierarchy
```
EstimateEntryWidget
├── QWidget (PyQt5)
├── EstimateUI (layout mixin)
└── EstimateLogic (business logic composite mixin)
    ├── _EstimateBaseMixin (logging, settings)
    ├── _EstimateDialogsMixin (dialog interactions)
    ├── _EstimatePersistenceMixin (save/load/delete)
    └── _EstimateTableMixin (table operations, calculations)
```

---

## Constructor

### `__init__(db_manager, main_window, repository)`

Initializes the estimate entry widget with database access and presenter coordination.

**Parameters:**
- `db_manager` (DatabaseManager): Database connection manager
- `main_window` (MainWindow): Reference to the main application window
- `repository` (EstimateRepository): Repository for estimate persistence

**Initialization Sequence:**
1. Sets up database manager and presenter
2. Initializes view model and tracking variables
3. Creates UI layout (table, toolbar, totals panel)
4. Restores column widths and font sizes from settings
5. Sets up numeric input validators
6. Connects Qt signals and slots
7. Registers keyboard shortcuts
8. Generates initial voucher number
9. Loads settings (fonts, column widths)

**Post-Initialization State:**
- One empty row in the table
- New voucher number generated
- Focus on first cell (Code column)
- Delete button disabled
- No unsaved changes

---

## Public Methods

### Core Widget Methods

#### `show_status(message: str, timeout: int = 3000, level: str = 'info') -> None`
Display a status message in the inline status label.

**Parameters:**
- `message`: Text to display
- `timeout`: Duration in milliseconds (default: 3000)
- `level`: Message severity ('info', 'warning', 'error')

**Usage:**
```python
widget.show_status("Estimate saved successfully")
widget.show_status("Invalid item code", level="error")
```

---

#### `show_inline_status(message: str, timeout: int = 3000, level: str = 'info') -> None`
Alias for `show_status()`. Displays transient status messages.

---

#### `has_unsaved_changes() -> bool`
Check if the estimate form has unsaved modifications.

**Returns:** `True` if there are unsaved changes, `False` otherwise

**Usage:**
```python
if widget.has_unsaved_changes():
    # Prompt user before closing
    response = confirm_discard_changes()
```

---

#### `safe_load_estimate(voucher_no: str = None) -> None`
Load an estimate by voucher number with unsaved changes protection.

**Parameters:**
- `voucher_no`: Voucher number to load (if None, uses current voucher field value)

**Behavior:**
- Checks for unsaved changes and prompts user if needed
- Delegates to `presenter.load_estimate()`
- Updates UI with loaded data
- Marks estimate as loaded (enables delete button)

**Usage:**
```python
widget.safe_load_estimate("EST-2025-001")
```

---

#### `force_focus_to_first_cell() -> None`
Set keyboard focus to the first cell (Code column, row 0).

**Usage:**
```python
widget.force_focus_to_first_cell()
```

---

#### `clear_all_rows() -> None`
Remove all rows from the estimate table.

**Usage:**
```python
widget.clear_all_rows()
```

---

#### `request_totals_recalc() -> None`
Request a debounced recalculation of totals.

**Behavior:**
- Debounced by 100ms to avoid excessive recalculations during rapid input
- Triggers `calculate_totals()` after delay

---

### Mode Control

#### `toggle_return_mode() -> None`
Toggle between regular and return item entry modes.

**Keyboard Shortcut:** `Ctrl+R`

**Behavior:**
- Switches `return_mode` flag
- Updates mode indicator UI
- Changes row type for new entries
- Updates tooltip text

---

#### `toggle_silver_bar_mode() -> None`
Toggle between regular and silver bar entry modes.

**Keyboard Shortcut:** `Ctrl+B`

**Behavior:**
- Switches `silver_bar_mode` flag
- Updates mode indicator UI
- Changes row type for new entries
- Updates tooltip text

---

### Font Management

#### `_apply_table_font_size(size: int) -> None`
Apply font size to the estimate table.

**Parameters:**
- `size`: Font size in points

**Called by:** Settings dialog, initialization

---

#### `_apply_breakdown_font_size(size: int) -> None`
Apply font size to the breakdown panel.

**Parameters:**
- `size`: Font size in points

---

#### `_apply_final_calc_font_size(size: int) -> None`
Apply font size to the final calculation panel.

**Parameters:**
- `size`: Font size in points

---

### Event Handlers (Qt Overrides)

#### `keyPressEvent(event: QKeyEvent) -> None`
Handle keyboard events for navigation and shortcuts.

**Handled Keys:**
- Enter/Return: Move to next cell or process item code
- Tab: Move to next cell
- Shift+Tab: Move to previous cell
- Backspace: Navigate to previous cell (Code column only)

---

#### `resizeEvent(event: QResizeEvent) -> None`
Handle widget resize events.

**Behavior:**
- Triggers auto-stretch for item name column if enabled
- Propagates to parent class

---

#### `closeEvent(event: QCloseEvent) -> None`
Handle widget close event.

**Behavior:**
- Saves column widths to settings
- Propagates to parent class

---

## Public Properties (via Mixins)

The following methods are available through the mixin inheritance but are considered part of the public API:

### From _EstimatePersistenceMixin

- `capture_state() -> EstimateEntryViewState`: Capture current form state
- `apply_totals(totals: TotalsResult) -> None`: Update totals display
- `apply_loaded_estimate(loaded: LoadedEstimate) -> bool`: Apply loaded estimate data
- `generate_voucher(silent: bool = False) -> None`: Generate new voucher number
- `load_estimate(voucher_no: str) -> None`: Load estimate by voucher
- `save_estimate() -> None`: Save current estimate
- `delete_current_estimate() -> None`: Delete the loaded estimate
- `print_estimate() -> None`: Print current estimate

### From _EstimateTableMixin

- `populate_row(row_index: int, item_data: Mapping) -> None`: Fill row with item data
- `populate_item_row(row: int, item: Mapping) -> None`: Populate row from item lookup
- `focus_after_item_lookup(row_index: int) -> None`: Set focus after item load
- `add_empty_row() -> None`: Add new empty row to table
- `delete_current_row() -> None`: Delete the currently selected row
- `focus_on_empty_row() -> None`: Navigate to first empty row
- `process_item_code(row: int, code: str) -> None`: Look up item by code
- `calculate_net_weight(row: int) -> None`: Calculate net weight for row
- `calculate_fine(row: int) -> None`: Calculate fine weight for row
- `calculate_wage(row: int) -> None`: Calculate wage amount for row

### From _EstimateDialogsMixin

- `show_history() -> None`: Open estimate history dialog
- `clear_form() -> None`: Clear form and start new estimate
- `prompt_item_selection(code: str) -> Optional[Mapping]`: Open item selection dialog
- `show_silver_bar_management() -> None`: Open silver bar management dialog

---

## Keyboard Shortcuts

| Shortcut | Action | Method |
|----------|--------|--------|
| `Ctrl+R` | Toggle Return Mode | `toggle_return_mode()` |
| `Ctrl+B` | Toggle Silver Bar Mode | `toggle_silver_bar_mode()` |
| `Ctrl+D` | Delete Current Row | `delete_current_row()` |
| `Ctrl+H` | Show History Dialog | `show_history()` |
| `Ctrl+N` | New Estimate (Clear Form) | `clear_form()` |
| `Enter` | Move to Next Cell / Process Code | `keyPressEvent()` |
| `Tab` | Move to Next Cell | `keyPressEvent()` |
| `Shift+Tab` | Move to Previous Cell | `keyPressEvent()` |
| `Backspace` | Navigate to Previous Cell (Code col) | `keyPressEvent()` |

**Note:** `Ctrl+S` (Save) and `Ctrl+P` (Print) are handled by MainWindow menu actions to avoid conflicts.

---

## Qt Signals

### Emitted Signals

The widget doesn't currently emit custom signals, but communicates state changes through:
- UI updates (status labels, badges)
- `main_window.setWindowModified(bool)` for unsaved state
- Presenter method calls for business logic

### Connected Signals (Internal)

- `load_button.clicked` → `safe_load_estimate()`
- `voucher_input.editingFinished` → `safe_load_estimate()`
- `item_table.cellChanged` → `handle_cell_changed()`
- `item_table.cellClicked` → `cell_clicked()`
- `item_table.currentCellChanged` → `current_cell_changed()`
- `item_table.itemSelectionChanged` → `selection_changed()`
- `_totals_timer.timeout` → `calculate_totals()`
- `_column_save_timer.timeout` → `_save_column_widths_setting()`

---

## Dependencies

### Injected Dependencies

- **DatabaseManager** (`db_manager`): Database operations
- **MainWindow** (`main_window`): Parent window reference for status bar, dialogs
- **EstimateRepository** (`repository`): Persistence layer for estimates

### Internal Dependencies

- **EstimateEntryPresenter**: Business logic coordinator
- **EstimateEntryViewModel**: Data state management
- **InlineStatusController**: Status message display
- **NumericDelegate**: Input validation for numeric columns

---

## Presenter Integration

The widget implements the `EstimateEntryView` protocol defined in the presenter layer:

```python
class EstimateEntryView(Protocol):
    def capture_state() -> EstimateEntryViewState: ...
    def apply_totals(totals: TotalsResult) -> None: ...
    def set_voucher_number(voucher_no: str) -> None: ...
    def show_status(message: str, timeout: int, level: str) -> None: ...
    def populate_row(row_index: int, item_data: Mapping) -> None: ...
    def prompt_item_selection(code: str) -> Optional[Mapping]: ...
    def focus_after_item_lookup(row_index: int) -> None: ...
    def open_history_dialog() -> Optional[str]: ...
    def show_silver_bar_management() -> None: ...
    def apply_loaded_estimate(loaded: LoadedEstimate) -> bool: ...
```

All business logic (save, load, calculate totals) flows through the presenter to maintain separation of concerns.

---

## Usage Examples

### Creating the Widget

```python
from silverestimate.ui.estimate_entry import EstimateEntryWidget
from silverestimate.services.estimate_repository import DatabaseEstimateRepository

# In MainWindow initialization:
repository = DatabaseEstimateRepository(db_manager)
estimate_widget = EstimateEntryWidget(
    db_manager=self.db,
    main_window=self,
    repository=repository
)

# Add to navigation stack
self.navigation_service.add_widget("estimate_entry", estimate_widget)
```

### Checking Unsaved Changes

```python
def closeEvent(self, event):
    if self.estimate_widget.has_unsaved_changes():
        reply = QMessageBox.question(
            self,
            "Unsaved Changes",
            "You have unsaved changes. Discard them?",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.No:
            event.ignore()
            return
    event.accept()
```

### Loading an Estimate Programmatically

```python
# Load specific voucher
widget.safe_load_estimate("EST-2025-001")

# Or let user enter voucher number in the UI
# widget.voucher_input.setText("EST-2025-001")
# widget.safe_load_estimate()  # Uses voucher from input field
```

### Applying Font Size

```python
# From settings dialog
new_size = font_size_spinbox.value()
widget._apply_table_font_size(new_size)
widget._apply_breakdown_font_size(new_size)
widget._apply_final_calc_font_size(new_size)
```

---

## Settings Persistence

The widget automatically persists and restores:

### Column Widths
- **Setting Key**: `estimate_entry/column_widths`
- **Format**: JSON array of integers
- **Auto-save**: Debounced by 350ms on resize

### Table Font Size
- **Setting Key**: `estimate_entry/table_font_size`
- **Default**: 10 points

### Breakdown Panel Font Size
- **Setting Key**: `estimate_entry/breakdown_font_size`
- **Default**: 10 points

### Final Calculation Font Size
- **Setting Key**: `estimate_entry/final_calc_font_size`
- **Default**: 12 points

---

## State Management

### Internal State Flags

- `initializing` (bool): Prevents premature signal handlers during init
- `_loading_estimate` (bool): Prevents recursive estimate loads
- `processing_cell` (bool): Prevents reentrancy in cell processing
- `return_mode` (bool): Entry mode for return items
- `silver_bar_mode` (bool): Entry mode for silver bars
- `_estimate_loaded` (bool): Tracks if an estimate was loaded (enables delete)
- `_unsaved_changes` (bool): Tracks modification state

### View Model State

The `EstimateEntryViewModel` maintains:
- Row data (`EstimateEntryRowState` objects)
- Silver rate
- Last balance (silver and amount)
- Mode flags (return_mode, silver_bar_mode)

---

## Threading Considerations

- All UI operations must occur on the main Qt thread
- Database operations are synchronous (blocking UI)
- Totals recalculation is debounced but synchronous
- No background threads currently used in this widget

---

## Known Limitations

1. **Silver Bar Mode Shortcut**: Currently `Ctrl+B`, plan mentions `Ctrl+Shift+S` in refactoring doc
2. **No Undo/Redo**: Row deletions and edits are immediate and irreversible
3. **Synchronous DB Ops**: Saving/loading blocks the UI (acceptable for current data size)
4. **Column Layout**: Cannot reorder columns, only resize
5. **Single Estimate**: Cannot have multiple estimate tabs/windows open simultaneously

---

## Testing Hooks

For testing, the following can be accessed:

```python
# Access table directly
widget.item_table.setItem(row, col, QTableWidgetItem("value"))

# Access presenter
widget.presenter.generate_voucher()

# Access view model
widget.view_model.set_rows([row1, row2])

# Trigger calculations
widget.calculate_totals()

# Access UI elements
widget.voucher_input.setText("EST-001")
widget.save_button.click()
```

---

## Future Refactoring Plans

See [ESTIMATE_ENTRY_REFACTORING_PLAN.md](../ESTIMATE_ENTRY_REFACTORING_PLAN.md) for detailed decomposition plans:

- Extract `VoucherToolbar` component
- Extract `EstimateTableView` component
- Extract `TotalsPanel` component
- Extract `ModeSwitcher` component
- Create `QAbstractTableModel` for table data
- Reduce main widget to ~250 lines (coordination only)

---

## References

- [EstimateEntryPresenter](../silverestimate/presenter/estimate_entry_presenter.py)
- [EstimateEntryViewModel](../silverestimate/ui/view_models/estimate_entry_view_model.py)
- [Estimate Entry Logic Mixins](../silverestimate/ui/estimate_entry_logic/)
- [Refactoring Plan](../ESTIMATE_ENTRY_REFACTORING_PLAN.md)

---

**Document Version**: 1.0
**Created**: 2025-11-01
**Phase**: 1.1 - Snapshot & Guardrails
