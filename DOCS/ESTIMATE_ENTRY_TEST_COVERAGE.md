# Estimate Entry Test Coverage Analysis

**Date**: 2025-11-01
**Phase**: 1.3 - Identify Coverage Gaps

---

## Current Test Suite

### Test Files and Counts

| Test File | Test Count | Focus Area |
|-----------|------------|------------|
| `tests/unit/test_estimate_entry_presenter.py` | 9 tests | Presenter business logic |
| `tests/unit/test_estimate_logic.py` | 11 tests | Logic mixin methods |
| `tests/unit/test_estimate_entry_view_model.py` | 3 tests | View model state |
| `tests/ui/test_estimate_entry_widget.py` | 6 tests | Widget integration |
| **Total** | **29 tests** | |

---

## Coverage Analysis by Component

### ✅ Well-Covered Areas

#### 1. EstimateEntryPresenter (9 tests)
- ✅ Voucher generation
- ✅ Save workflow with regular items
- ✅ Save workflow with return items
- ✅ Save workflow with silver bars
- ✅ Totals calculation
- ✅ Repository integration
- ✅ Error handling in save

**Files**: `tests/unit/test_estimate_entry_presenter.py`

#### 2. EstimateLogic Mixins (11 tests)
- ✅ Net weight calculation
- ✅ Fine weight calculation
- ✅ Wage amount calculation
- ✅ Row type visuals
- ✅ Empty row handling
- ✅ Cell processing

**Files**: `tests/unit/test_estimate_logic.py`

#### 3. EstimateEntryViewModel (3 tests)
- ✅ Row management
- ✅ Mode state (return, silver bar)
- ✅ State capture

**Files**: `tests/unit/test_estimate_entry_view_model.py`

#### 4. Widget Integration (6 tests)
- ✅ Widget initialization
- ✅ Voucher generation on init
- ✅ State capture from table
- ✅ Totals display update
- ✅ Mixed item types

**Files**: `tests/ui/test_estimate_entry_widget.py`

---

## ⚠️ Coverage Gaps Identified

### Critical Gaps (High Priority)

#### 1. Load Estimate Workflow
**Status**: ❌ Not Covered
**Risk**: High
**Components**:
- `safe_load_estimate()` method
- Unsaved changes detection before load
- User prompt dialog
- Estimate data population in UI
- Delete button state after load

**Recommended Tests**:
```python
def test_safe_load_estimate_with_unsaved_changes_cancels()
def test_safe_load_estimate_with_unsaved_changes_discards()
def test_safe_load_estimate_populates_table_correctly()
def test_safe_load_estimate_enables_delete_button()
def test_load_estimate_with_invalid_voucher_shows_error()
```

#### 2. Delete Estimate Workflow
**Status**: ❌ Not Covered
**Risk**: High
**Components**:
- `delete_current_estimate()` method
- Confirmation dialog
- Delete button enabled/disabled state
- Form clear after delete
- Database deletion

**Recommended Tests**:
```python
def test_delete_estimate_requires_loaded_estimate()
def test_delete_estimate_shows_confirmation_dialog()
def test_delete_estimate_clears_form_on_success()
def test_delete_estimate_generates_new_voucher()
def test_delete_estimate_disables_delete_button_after()
```

#### 3. Keyboard Shortcuts
**Status**: ❌ Not Covered
**Risk**: Medium
**Shortcuts**:
- Ctrl+R (toggle return mode)
- Ctrl+B (toggle silver bar mode)
- Ctrl+D (delete row)
- Ctrl+H (show history)
- Ctrl+N (new estimate/clear form)

**Recommended Tests**:
```python
def test_ctrl_r_toggles_return_mode()
def test_ctrl_b_toggles_silver_bar_mode()
def test_ctrl_d_deletes_current_row()
def test_ctrl_h_opens_history_dialog()
def test_ctrl_n_clears_form_with_confirmation()
```

#### 4. Unsaved Changes Tracking
**Status**: ⚠️ Partially Covered
**Risk**: Medium
**Components**:
- `has_unsaved_changes()` method
- `_on_unsaved_state_changed()` callback
- Badge display
- Window modified indicator

**Recommended Tests**:
```python
def test_has_unsaved_changes_initially_false()
def test_has_unsaved_changes_true_after_edit()
def test_has_unsaved_changes_false_after_save()
def test_unsaved_badge_appears_on_edit()
def test_unsaved_badge_disappears_on_save()
def test_window_modified_indicator_updates()
```

#### 5. Item Code Lookup
**Status**: ⚠️ Partially Covered
**Risk**: Medium
**Components**:
- `process_item_code()` method
- Direct code match
- Item not found → selection dialog
- Item selection dialog result handling

**Recommended Tests**:
```python
def test_process_item_code_with_valid_code()
def test_process_item_code_with_invalid_code_opens_dialog()
def test_process_item_code_dialog_selection_populates_row()
def test_process_item_code_dialog_cancel_keeps_row_empty()
```

### Medium Priority Gaps

#### 6. Keyboard Navigation
**Status**: ❌ Not Covered
**Risk**: Medium
**Components**:
- `keyPressEvent()` override
- Enter key navigation
- Tab/Shift+Tab navigation
- Backspace in Code column

**Recommended Tests**:
```python
def test_enter_key_processes_code_column()
def test_enter_key_moves_to_next_cell()
def test_tab_key_moves_to_next_editable_column()
def test_shift_tab_moves_to_previous_column()
def test_backspace_in_code_navigates_back()
```

#### 7. Column Management
**Status**: ❌ Not Covered
**Risk**: Low
**Components**:
- `_save_column_widths_setting()`
- `_load_column_widths_setting()`
- Column resize debouncing
- Reset column layout

**Recommended Tests**:
```python
def test_column_widths_persisted_on_resize()
def test_column_widths_restored_on_init()
def test_column_resize_debounced_save()
def test_reset_column_layout_restores_defaults()
```

#### 8. Font Size Management
**Status**: ❌ Not Covered
**Risk**: Low
**Components**:
- `_apply_table_font_size()`
- `_apply_breakdown_font_size()`
- `_apply_final_calc_font_size()`
- Font size persistence

**Recommended Tests**:
```python
def test_apply_table_font_size_changes_table()
def test_apply_breakdown_font_size_changes_panel()
def test_table_font_size_persists()
def test_breakdown_font_size_persists()
```

#### 9. History Dialog Integration
**Status**: ❌ Not Covered
**Risk**: Medium
**Components**:
- `show_history()` method
- Dialog opening
- Estimate selection from history
- Loading selected estimate

**Recommended Tests**:
```python
def test_show_history_opens_dialog()
def test_show_history_loads_selected_estimate()
def test_show_history_cancel_keeps_current_estimate()
```

#### 10. Print Functionality
**Status**: ❌ Not Covered
**Risk**: Low
**Components**:
- `print_estimate()` method
- Print dialog opening
- Print preview with data

**Recommended Tests**:
```python
def test_print_estimate_opens_print_dialog()
def test_print_estimate_with_empty_form()
def test_print_estimate_includes_all_rows()
```

### Low Priority Gaps

#### 11. Status Message Display
**Status**: ❌ Not Covered
**Risk**: Low
**Components**:
- `show_status()` method
- `show_inline_status()` method
- InlineStatusController integration

**Recommended Tests**:
```python
def test_show_status_displays_message()
def test_show_status_message_disappears_after_timeout()
def test_show_status_with_error_level()
```

#### 12. Clear Form / New Estimate
**Status**: ❌ Not Covered
**Risk**: Medium
**Components**:
- `clear_form()` method
- `clear_all_rows()` method
- Unsaved changes check
- New voucher generation

**Recommended Tests**:
```python
def test_clear_form_with_no_changes_clears_immediately()
def test_clear_form_with_unsaved_changes_prompts()
def test_clear_form_generates_new_voucher()
def test_clear_all_rows_leaves_one_empty_row()
```

#### 13. Row Type Visuals
**Status**: ⚠️ Partially Covered
**Risk**: Low
**Components**:
- `_update_row_type_visuals()` method
- Return item styling
- Silver bar item styling

**Recommended Tests**:
```python
def test_return_row_visual_styling()
def test_silver_bar_row_visual_styling()
def test_regular_row_visual_styling()
```

#### 14. Focus Management
**Status**: ❌ Not Covered
**Risk**: Low
**Components**:
- `force_focus_to_first_cell()` method
- `focus_after_item_lookup()` method
- `focus_on_empty_row()` method

**Recommended Tests**:
```python
def test_force_focus_to_first_cell()
def test_focus_after_item_lookup_moves_to_gross()
def test_focus_on_empty_row_finds_first_empty()
```

---

## Recommended Test Additions

### Priority 1: Critical Integration Tests (pytest-qt)

Create `tests/integration/test_estimate_entry_workflows.py`:

```python
# Full workflow tests
def test_create_save_load_estimate_complete_workflow(qtbot)
def test_edit_existing_estimate_workflow(qtbot)
def test_delete_estimate_workflow(qtbot)
def test_return_mode_workflow(qtbot)
def test_silver_bar_mode_workflow(qtbot)
def test_item_lookup_workflow(qtbot)
```

### Priority 2: Keyboard Interaction Tests

Create `tests/ui/test_estimate_entry_keyboard.py`:

```python
def test_all_keyboard_shortcuts(qtbot)
def test_keyboard_navigation_through_table(qtbot)
def test_enter_key_behavior_by_column(qtbot)
def test_backspace_navigation(qtbot)
```

### Priority 3: State Management Tests

Create `tests/ui/test_estimate_entry_state.py`:

```python
def test_unsaved_changes_lifecycle(qtbot)
def test_mode_toggles_update_state(qtbot)
def test_delete_button_state_management(qtbot)
```

---

## Coverage Metrics (Estimated)

Based on analysis of the codebase:

| Component | Lines | Covered | Coverage % |
|-----------|-------|---------|------------|
| EstimateEntryWidget (main) | ~300 | ~100 | ~33% |
| _EstimateTableMixin | ~802 | ~350 | ~44% |
| _EstimatePersistenceMixin | ~662 | ~200 | ~30% |
| _EstimateDialogsMixin | ~165 | ~50 | ~30% |
| _EstimateBaseMixin | ~330 | ~100 | ~30% |
| EstimateEntryPresenter | ~250 | ~200 | ~80% |
| EstimateEntryViewModel | ~150 | ~120 | ~80% |
| **Overall Estimate** | **~2659** | **~1120** | **~42%** |

**Note**: These are rough estimates based on code review, not actual coverage metrics.

---

## Action Plan

### Immediate Actions (Phase 1)

1. ✅ Document current test coverage
2. ⬜ Add critical integration tests (workflows)
3. ⬜ Add keyboard shortcut tests
4. ⬜ Add unsaved changes tracking tests

### Before Refactoring (Phase 2)

5. ⬜ Achieve minimum 60% coverage on critical paths
6. ⬜ All workflow tests passing
7. ⬜ Baseline established for regression detection

### During Refactoring

8. ⬜ Maintain or increase coverage
9. ⬜ Add component-specific tests as components are created
10. ⬜ Update integration tests to use new components

### After Refactoring

11. ⬜ Achieve 70%+ coverage overall
12. ⬜ 90%+ coverage on business logic (presenter, view model)
13. ⬜ All smoke tests automated where possible

---

## Notes

- **Mocking Strategy**: Use `unittest.mock` or `pytest-mock` for external dependencies
- **Qt Testing**: Use `pytest-qt` for widget interaction testing
- **Fixtures**: Leverage existing factories in `tests/factories.py`
- **CI Integration**: Ensure tests run in CI pipeline (GitHub Actions)

---

## References

- [pytest-qt Documentation](https://pytest-qt.readthedocs.io/)
- [PyQt5 Testing Best Practices](https://doc.qt.io/qt-5/qtest-overview.html)
- [Python Test Coverage](https://coverage.readthedocs.io/)

---

**Document Version**: 1.0
**Created**: 2025-11-01
**Phase**: 1.3 - Snapshot & Guardrails
