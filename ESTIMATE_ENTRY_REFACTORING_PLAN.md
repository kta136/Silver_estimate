# Refactoring Plan: `estimate_entry.py` Decomposition

**Status**: 🟡 Planning Phase
**Created**: 2025-11-01
**Last Updated**: 2025-11-01

---

## Table of Contents
1. [Current State Analysis](#current-state-analysis)
2. [Phase 1: Snapshot & Guardrails](#phase-1-snapshot--guardrails)
3. [Phase 2: Extract Data/Logic Layers](#phase-2-extract-datologic-layers)
4. [Phase 3: Break Up the Widget](#phase-3-break-up-the-widget)
5. [Phase 4: Presenter & Service Wiring](#phase-4-presenter--service-wiring)
6. [Phase 5: Polish & Documentation](#phase-5-polish--documentation)
7. [Success Criteria](#success-criteria)
8. [Timeline & Resources](#timeline--resources)
9. [Risk Mitigation](#risk-mitigation)
10. [Progress Log](#progress-log)

---

## Current State Analysis

### File Metrics
- **Main File**: `silverestimate/ui/estimate_entry.py` (824 lines)
- **Widget Class**: `EstimateEntryWidget` (32 methods)

### Existing Architecture
The codebase has already undergone partial refactoring:

#### Current Mixins
```
EstimateEntryWidget (824 lines)
├── QWidget
├── EstimateUI (layout)
└── EstimateLogic (composite mixin)
    ├── _EstimateBaseMixin (330 lines)
    │   └── Logging, settings management
    ├── _EstimateDialogsMixin (165 lines)
    │   └── Dialog interactions
    ├── _EstimatePersistenceMixin (662 lines)
    │   └── Save/load/delete operations
    └── _EstimateTableMixin (802 lines)
        └── Table interactions, calculations
```

#### Existing Components
- ✅ `EstimateEntryViewModel` - Data state management
- ✅ `EstimateEntryPresenter` - Business logic coordination
- ✅ `InlineStatusController` - Status message handling
- ✅ Column constants in `estimate_entry_logic/constants.py`
- ✅ `NumericDelegate` for input validation

### Dependencies
- `EstimateEntryPresenter` (presenter layer)
- `DatabaseEstimateRepository` (persistence)
- `main_window` reference (for silver bar management, status bar)
- `db_manager` (database operations)

### Test Coverage
- ✅ `tests/unit/test_estimate_entry_presenter.py`
- ✅ `tests/unit/test_estimate_entry_view_model.py`
- ✅ `tests/unit/test_estimate_logic.py`
- ✅ `tests/ui/test_estimate_entry_widget.py`

### Key Features to Preserve
1. Voucher generation and management
2. Item code lookup with dialog fallback
3. Return mode toggle (Ctrl+R)
4. Silver bar mode toggle (Ctrl+Shift+S)
5. Row deletion (Ctrl+D)
6. History dialog (Ctrl+H)
7. New estimate (Ctrl+N)
8. Auto-calculation of net weight, fine weight, wage
9. Totals calculation and display
10. Save/load/delete estimate workflows
11. Print functionality
12. Column width persistence
13. Font size customization
14. Unsaved changes tracking

---

## Phase 1: Snapshot & Guardrails

**Status**: ⬜ Not Started
**Estimated Duration**: 2-3 hours

### 1.1 Document Public API
- [ ] Create `docs/ESTIMATE_ENTRY_API.md`
- [ ] Document public methods called by MainWindow
  - [ ] `__init__(db_manager, main_window, repository)`
  - [ ] `has_unsaved_changes() -> bool`
  - [ ] `show_status(message, timeout, level)`
  - [ ] `safe_load_estimate(voucher_no)`
  - [ ] Any others exposed to main window
- [ ] Document Qt signals emitted
  - [ ] Unsaved state changes
  - [ ] Status updates
- [ ] Document keyboard shortcuts
  - [ ] Ctrl+R (Return mode)
  - [ ] Ctrl+Shift+S (Silver bar mode)
  - [ ] Ctrl+D (Delete row)
  - [ ] Ctrl+H (History)
  - [ ] Ctrl+N (New estimate)
- [ ] Document presenter interaction contract
  - [ ] Methods called on presenter
  - [ ] View protocol implementation

### 1.2 Create Smoke Test Checklist
- [ ] Create `tests/manual/ESTIMATE_ENTRY_SMOKE_TESTS.md`
- [ ] Document test workflows:
  - [ ] Load voucher by number
  - [ ] Add items via code lookup
  - [ ] Add items via selection dialog
  - [ ] Toggle return mode
  - [ ] Toggle silver bar mode
  - [ ] Save estimate
  - [ ] Load estimate from history
  - [ ] Delete estimate
  - [ ] Print estimate
  - [ ] Column resizing and reset
  - [ ] Font size changes (table, breakdown, final calc)
  - [ ] Keyboard navigation and shortcuts
  - [ ] Auto-calculation verification

### 1.3 Identify Coverage Gaps
- [ ] Review existing unit tests
- [ ] Identify missing integration tests
- [ ] Add pytest-qt tests for:
  - [ ] Widget-presenter integration
  - [ ] Signal/slot connections
  - [ ] Keyboard shortcut handling
  - [ ] Mode toggling behavior
  - [ ] Unsaved changes tracking

### 1.4 Code Freeze Prep
- [ ] Run `black` formatter on estimate_entry files
- [ ] Run `mypy` type checker
- [ ] Document existing TODOs in widget
- [ ] Create git branch: `refactor/estimate-entry-decomposition`
- [ ] Commit baseline state

---

## Phase 2: Extract Data/Logic Layers

**Status**: ⬜ Not Started
**Estimated Duration**: 4-5 hours

### 2.1 Create QAbstractTableModel
- [ ] Create `silverestimate/ui/models/` package
- [ ] Create `silverestimate/ui/models/estimate_table_model.py`
- [ ] Implement `EstimateTableModel(QAbstractTableModel)`:
  - [ ] Data storage (rows)
  - [ ] `rowCount()`, `columnCount()`, `data()`, `setData()`
  - [ ] `headerData()` for column headers
  - [ ] `flags()` for editable columns
  - [ ] Custom methods:
    - [ ] `add_row(row_data)`
    - [ ] `remove_row(index)`
    - [ ] `clear_rows()`
    - [ ] `get_row(index) -> EstimateEntryRowState`
- [ ] Move row validation from `_EstimateTableMixin`
- [ ] Emit signals for data changes
- [ ] Write unit tests for table model

### 2.2 Enhance ViewModel
- [ ] Extend `EstimateEntryViewModel` with:
  - [ ] Voucher metadata (number, date, note)
  - [ ] Mode state methods (return_mode, silver_bar_mode)
  - [ ] Unsaved changes flag
- [ ] Wire table model to view model
- [ ] Update existing view model tests

### 2.3 Extract Business Helpers
- [ ] Create `silverestimate/ui/estimate_entry_logic/calculations.py`
- [ ] Move calculation methods:
  - [ ] `calculate_net_weight(gross, poly) -> float`
  - [ ] `calculate_fine_weight(net, purity) -> float`
  - [ ] `calculate_wage(net, wage_rate, pieces) -> float`
- [ ] Keep functions pure (no Qt dependencies)
- [ ] Write unit tests for calculations

### 2.4 Update Presenter Interface
- [ ] Review `EstimateEntryPresenter` methods
- [ ] Verify DTOs are well-defined
- [ ] Update type hints to use enhanced view model
- [ ] Ensure backward compatibility
- [ ] Update presenter tests if needed

---

## Phase 3: Break Up the Widget

**Status**: ⬜ Not Started
**Estimated Duration**: 6-8 hours

### 3.1 Create Component Package
- [ ] Create `silverestimate/ui/estimate_entry_components/` package
- [ ] Create `__init__.py` with exports

### 3.2 Create VoucherToolbar Component
- [ ] Create `voucher_toolbar.py`
- [ ] Implement `VoucherToolbar(QWidget)`:
  - [ ] UI elements:
    - [ ] Voucher number display (QLineEdit, read-only)
    - [ ] Date picker (QDateEdit)
    - [ ] Note field (QLineEdit)
    - [ ] History button
    - [ ] Save button
    - [ ] Delete button
    - [ ] New estimate button
  - [ ] Signals:
    - [ ] `save_clicked`
    - [ ] `load_clicked`
    - [ ] `history_clicked`
    - [ ] `delete_clicked`
    - [ ] `new_clicked`
  - [ ] Methods:
    - [ ] `set_voucher_number(number: str)`
    - [ ] `get_voucher_number() -> str`
    - [ ] `set_date(date: QDate)`
    - [ ] `get_date() -> QDate`
    - [ ] `set_note(note: str)`
    - [ ] `get_note() -> str`
    - [ ] `enable_delete(enabled: bool)`
- [ ] Write pytest-qt tests

### 3.3 Create EstimateTableView Component
- [ ] Create `estimate_table_view.py`
- [ ] Implement `EstimateTableView(QTableView)`:
  - [ ] Use `EstimateTableModel` from Phase 2
  - [ ] Set up `NumericDelegate` for numeric columns
  - [ ] Implement keyboard shortcuts:
    - [ ] Ctrl+D for delete row
    - [ ] Ctrl+H for history
  - [ ] Implement context menu:
    - [ ] Reset column layout
  - [ ] Column management:
    - [ ] Save/restore widths
    - [ ] Auto-stretch item name column
  - [ ] Signals:
    - [ ] `item_lookup_requested(row: int, code: str)`
    - [ ] `row_deleted(row: int)`
    - [ ] `cell_edited(row: int, column: int)`
    - [ ] `history_requested`
  - [ ] Methods:
    - [ ] `add_row()`
    - [ ] `delete_row(index: int)`
    - [ ] `clear_rows()`
    - [ ] `focus_cell(row: int, column: int)`
- [ ] Write pytest-qt tests

### 3.4 Create TotalsPanel Component
- [ ] Create `totals_panel.py`
- [ ] Implement `TotalsPanel(QWidget)`:
  - [ ] UI elements:
    - [ ] Silver rate display
    - [ ] Gross weight total
    - [ ] Net weight total
    - [ ] Fine weight total
    - [ ] Wage total
    - [ ] Last balance (silver)
    - [ ] Last balance (amount)
    - [ ] Silver bar indicators
  - [ ] Methods:
    - [ ] `set_totals(totals: TotalsResult)`
    - [ ] `set_silver_rate(rate: float)`
    - [ ] `set_balances(silver: float, amount: float)`
    - [ ] `set_mode_indicators(return_mode: bool, silver_bar_mode: bool)`
- [ ] Write pytest-qt tests

### 3.5 Create ModeSwitcher Component
- [ ] Create `mode_switcher.py`
- [ ] Implement `ModeSwitcher(QWidget)`:
  - [ ] UI elements:
    - [ ] Return mode checkbox/toggle
    - [ ] Silver bar mode checkbox/toggle
    - [ ] Mode indicator labels
  - [ ] Keyboard shortcuts:
    - [ ] Ctrl+R (Return mode)
    - [ ] Ctrl+Shift+S (Silver bar mode)
  - [ ] Signals:
    - [ ] `return_mode_toggled(enabled: bool)`
    - [ ] `silver_bar_mode_toggled(enabled: bool)`
  - [ ] Methods:
    - [ ] `set_return_mode(enabled: bool)`
    - [ ] `set_silver_bar_mode(enabled: bool)`
    - [ ] `get_return_mode() -> bool`
    - [ ] `get_silver_bar_mode() -> bool`
- [ ] Write pytest-qt tests

### 3.6 Refactor EstimateEntryWidget
- [ ] Slim down `EstimateEntryWidget`:
  - [ ] Remove direct UI creation (use components)
  - [ ] Compose the 4 components:
    - [ ] VoucherToolbar
    - [ ] EstimateTableView
    - [ ] TotalsPanel
    - [ ] ModeSwitcher
  - [ ] Wire component signals:
    - [ ] Toolbar signals → presenter methods
    - [ ] Table signals → presenter methods
    - [ ] Mode signals → view model updates
  - [ ] Implement view protocol methods:
    - [ ] `capture_state()`
    - [ ] `apply_totals()`
    - [ ] `set_voucher_number()`
    - [ ] `show_status()`
    - [ ] `populate_row()`
    - [ ] `prompt_item_selection()`
    - [ ] `focus_after_item_lookup()`
    - [ ] `open_history_dialog()`
    - [ ] `show_silver_bar_management()`
    - [ ] `apply_loaded_estimate()`
  - [ ] Keep only coordination logic
- [ ] Target: ~200-300 lines
- [ ] Update widget tests

---

## Phase 4: Presenter & Service Wiring

**Status**: ⬜ Not Started
**Estimated Duration**: 3-4 hours

### 4.1 Update Presenter Integration
- [ ] Review `EstimateEntryPresenter` with new structure
- [ ] Ensure method signatures stable (backward compatible)
- [ ] Update presenter to work with components
- [ ] Add unit tests for presenter-component interactions

### 4.2 Repository Flow Verification
- [ ] Test `DatabaseEstimateRepository` interactions
- [ ] Verify save workflow:
  - [ ] Capture state from components
  - [ ] Build save payload
  - [ ] Persist to database
- [ ] Verify load workflow:
  - [ ] Load from database
  - [ ] Apply to components
- [ ] Verify delete workflow
- [ ] Check transaction boundaries maintained

### 4.3 Dependency Audit
- [ ] Review imports in all refactored files
- [ ] Remove unused mixin imports
- [ ] Update `__all__` exports:
  - [ ] `estimate_entry_components/__init__.py`
  - [ ] `models/__init__.py`
- [ ] Ensure clean separation of concerns
- [ ] Verify no circular dependencies

### 4.4 Integration Testing
- [ ] Create integration tests:
  - [ ] Component composition in widget
  - [ ] Signal propagation through layers
  - [ ] End-to-end save/load
  - [ ] Keyboard shortcuts
  - [ ] Mode toggling
  - [ ] Item lookup flow
- [ ] Run full test suite
- [ ] Fix any failures

---

## Phase 5: Polish & Documentation

**Status**: ⬜ Not Started
**Estimated Duration**: 2-3 hours

### 5.1 Documentation Updates
- [ ] Refresh module docstrings:
  - [ ] `EstimateEntryWidget`
  - [ ] Each component
  - [ ] Table model
  - [ ] Calculations module
- [ ] Add inline comments explaining:
  - [ ] Component responsibilities
  - [ ] Signal flow
  - [ ] Coordination logic
- [ ] Create architecture diagram (ASCII or Mermaid):
  - [ ] Show component hierarchy
  - [ ] Show signal flow
  - [ ] Show presenter integration
- [ ] Update `README.md` if architecture documented there

### 5.2 Code Quality
- [ ] Run full test suite: `pytest tests/`
- [ ] Run type checker: `mypy silverestimate/`
- [ ] Run formatter: `black silverestimate/`
- [ ] Run linter: `ruff check silverestimate/`
- [ ] Fix all errors and warnings
- [ ] Achieve 100% test pass rate

### 5.3 Manual Testing
- [ ] Walk through smoke test checklist (from Phase 1)
- [ ] Test with actual database and real data
- [ ] Verify UI responsiveness
- [ ] Test window resizing
- [ ] Test column management (resize, reset)
- [ ] Test font size changes
- [ ] Verify all keyboard shortcuts work
- [ ] Test mode toggling (return, silver bar)

### 5.4 Migration Notes
- [ ] Create `docs/REFACTORING_NOTES.md`:
  - [ ] Architectural changes summary
  - [ ] Component responsibility matrix
  - [ ] How to extend the new structure
  - [ ] Guidelines for adding features
  - [ ] Patterns to follow for future UI work
  - [ ] Lessons learned
- [ ] Document next refactoring target:
  - [ ] `silver_bar_management.py` (apply same patterns)

### 5.5 Cleanup & Merge
- [ ] Remove deprecated code comments
- [ ] Remove unused imports
- [ ] Archive old mixin files if fully replaced
- [ ] Squash/organize commits
- [ ] Create pull request
- [ ] Code review
- [ ] Merge to `master` branch
- [ ] Tag release if appropriate

---

## Success Criteria

### Functional Requirements
- ✅ All existing tests pass
- ✅ Manual smoke test checklist completes successfully
- ✅ No regression in functionality
- ✅ All features work as before

### Non-Functional Requirements
- ✅ `EstimateEntryWidget` reduced from 824 to ~250 lines
- ✅ Clear component boundaries established
- ✅ Each component < 300 lines
- ✅ Components are reusable and testable
- ✅ Type hints on all public methods
- ✅ 100% test pass rate

### Documentation Requirements
- ✅ All modules have docstrings
- ✅ Architecture diagram created
- ✅ API documentation complete
- ✅ Smoke test checklist available
- ✅ Refactoring notes document created

### Future Readiness
- ✅ Patterns established for refactoring `silver_bar_management.py`
- ✅ Component architecture can be applied to other widgets
- ✅ New developers can understand structure easily

---

## Timeline & Resources

### Estimated Duration
- **Phase 1**: 2-3 hours
- **Phase 2**: 4-5 hours
- **Phase 3**: 6-8 hours
- **Phase 4**: 3-4 hours
- **Phase 5**: 2-3 hours
- **Total**: 17-23 hours

### Work Sessions
- **Session 1**: Phase 1 (complete)
- **Session 2**: Phase 2 (complete)
- **Session 3**: Phase 3 (partial - create 2 components)
- **Session 4**: Phase 3 (complete remaining components)
- **Session 5**: Phase 4 + Phase 5

### Resources Needed
- Development environment with PyQt5
- Test database with sample data
- Access to existing test suite
- Git for version control

---

## Risk Mitigation

### Technical Risks

**Risk**: Breaking existing functionality
**Mitigation**:
- Work in feature branch
- Comprehensive test coverage before refactoring
- Run tests after every change
- Manual smoke testing at each phase

**Risk**: Signal/slot disconnections
**Mitigation**:
- Document all signals in Phase 1
- Create integration tests for signal flow
- Test signal propagation explicitly

**Risk**: Performance degradation
**Mitigation**:
- Use QAbstractTableModel efficiently
- Minimize signal emissions
- Profile before and after if needed

**Risk**: Type errors and lint failures
**Mitigation**:
- Run mypy frequently during development
- Use type hints consistently
- Fix issues incrementally

### Process Risks

**Risk**: Scope creep
**Mitigation**:
- Follow the phase plan strictly
- Don't add new features during refactoring
- Track only decomposition tasks

**Risk**: Lost context between sessions
**Mitigation**:
- Update this document after each session
- Commit frequently with clear messages
- Document decisions in progress log

**Risk**: Merge conflicts
**Mitigation**:
- Create feature branch immediately
- Communicate with team about ongoing work
- Merge from master regularly

---

## Progress Log

### 2025-11-01
- ✅ Created refactoring plan document
- ✅ Analyzed current codebase structure
- ✅ Identified existing components and test coverage
- 🟡 **Next**: Begin Phase 1 - Document public API

### [Date TBD]
- Phase 1 tasks...

### [Date TBD]
- Phase 2 tasks...

### [Date TBD]
- Phase 3 tasks...

### [Date TBD]
- Phase 4 tasks...

### [Date TBD]
- Phase 5 tasks...

---

## Notes & Decisions

### Architectural Decisions
- **Decision**: Use QAbstractTableModel instead of QTableWidget
  **Rationale**: Better separation of data and presentation, more testable, follows Qt best practices

- **Decision**: Create 4 main components (Toolbar, Table, Totals, ModeSwitcher)
  **Rationale**: Each has clear responsibility, can be developed and tested independently

- **Decision**: Keep presenter interface stable
  **Rationale**: Minimize changes to already-tested business logic layer

### Open Questions
- [ ] Should we extract the inline status controller into a component?
- [ ] Should font size management be its own service?
- [ ] How to handle column width persistence in the new table view?

### Future Improvements
- Consider using signals/slots instead of direct method calls between components
- Consider implementing undo/redo for row operations
- Consider adding validation layer between components and presenter

---

## References
- [Existing Architecture Memory](file:///.serena/memory/architecture.md)
- [Codebase Structure Memory](file:///.serena/memory/codebase_structure.md)
- [Qt Model/View Documentation](https://doc.qt.io/qt-5/model-view-programming.html)
- [PyQt5 Best Practices](https://www.riverbankcomputing.com/static/Docs/PyQt5/)

---

**End of Refactoring Plan**

*This is a living document. Update progress, decisions, and notes as work progresses.*
