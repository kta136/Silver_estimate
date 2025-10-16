# Testing Implementation Playbook

This document provides actionable guidance for building and maintaining a robust automated test suite for the Silver Estimation App. Use it as the primary reference for current testing practices.

## Goals
- Increase confidence in core workflows (estimate entry, silver bar management, authentication).
- Prevent regressions in encryption, calculations, and database migrations.
- Enable fast feedback for developers and automation.
- Document repeatable patterns for PyQt and SQLite testing.

## Tooling Stack
- Test runner: `pytest`
- GUI support: `pytest-qt` (Qt event loop fixtures) and `pytest-xvfb` on CI
- Coverage: `coverage.py` (invoke via `pytest --cov`)
- Property-based tests: `hypothesis` for calculations and serialization helpers
- Mocking: `pytest-mock` or Python `unittest.mock`

Install extras:
```
pip install -r requirements.txt
pip install pytest pytest-qt pytest-xvfb pytest-mock hypothesis
```

## Recommended Layout
```
tests/
- conftest.py          # shared fixtures (app, settings, temp paths)
- unit/
  - test_calculations.py
  - test_security.py
  - test_services_live_rate.py
- integration/
  - test_database_manager.py
  - test_estimate_workflow.py
- ui/
  - test_main_window.py
  - test_estimate_entry_widget.py
```
Keep existing `tests/test_security.py` and `tests/test_repositories.py` until migrated.

## Core Fixtures
Add reusable fixtures in `tests/conftest.py`:

### Qt Application
```
@pytest.fixture(scope="session")
def qapp():
    from PyQt5.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app
```

### Temporary Settings
```
@pytest.fixture()
def temp_settings(tmp_path, monkeypatch):
    settings_dir = tmp_path / "settings"
    settings_dir.mkdir()
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    with monkeypatch.context() as m:
        m.setenv("XDG_CONFIG_HOME", str(settings_dir))
        yield settings_dir
```

### In-memory Database Manager
```
@pytest.fixture()
def db_manager(tmp_path):
    from silverestimate.persistence.database_manager import DatabaseManager
    temp_db = tmp_path / "estimation.db"
    manager = DatabaseManager(str(temp_db), "test-password")
    yield manager
    manager.close()
```
Wrap QSettings usage with environment overrides to prevent pollution of real settings.

## Test Case Templates

### 1. Calculation Logic
```
def test_calculate_fine_weight_rounding():
    fine = logic.calculate_fine_weight(gross=10, poly=0.5, purity=92.5)
    assert fine == pytest.approx(8.675)
```
Use `hypothesis` to explore edge cases (zero weights, purity bounds, large numbers).

### 2. Live Rate Service
```
def test_refresh_now_emits_rate(qtbot, mocker):
    service = LiveRateService(logger=test_logger)
    mocker.patch("silverestimate.services.live_rate_service.fetch_broadcast_rate_exact", return_value=(50000, True, None))
    with qtbot.waitSignal(service.rate_updated, timeout=1000) as signal:
        service.refresh_now()
    assert signal.args[0] == 50000
```
Ensure timers are stopped during teardown to avoid cross-test leakage.

### 3. Database Manager Encryption
```
def test_database_roundtrip(db_manager):
    repo = db_manager.items_repo
    repo.add_item("ITM001", "Sample", 92.5, "P", 10.0)
    db_manager.close()
    reopened = DatabaseManager(db_manager.encrypted_db_path, "test-password")
    assert reopened.items_repo.get_item_by_code("ITM001")
```
Validate temp file cleanup by asserting `security/last_temp_db_path` absence after close.

### 4. Main Window Wiring
```
def test_main_window_actions(qtbot, mocker, db_manager):
    mock_auth = mocker.patch("silverestimate.services.auth_service.run_authentication", return_value="pass")
    window = MainWindow(password="pass", logger=test_logger)
    qtbot.addWidget(window)
    assert window.commands is not None
```
Focus on verifying command registration, signal wiring, and error dialogs under mocked failures.

## Coverage Priorities
1. `silverestimate/ui/estimate_entry_logic/` - ensure totals, fines, wages, and validation paths are covered.
2. `silverestimate/persistence/database_manager.py` - validate decrypt/encrypt flows, flush scheduler triggers, migration failures.
3. `silverestimate/services/live_rate_service.py` - confirm timer behavior, fallback logic, error handling.
4. `silverestimate/services/auth_service.py` - test first-run setup, password verification, data wipe path.
5. `main.py` - guard top-level `main()` to confirm logging, authentication, and clean shutdown wiring (use dependency injection to avoid heavy UI).

## Test Data Guidelines
- Use factory helpers for estimate payloads (regular items, return items, silver bars) to keep tests readable.
- Prefer deterministic data; avoid reliance on real clocks by patching `datetime` where needed.
- Store sample fixtures under `tests/fixtures/` if JSON or CSV files are required.

## Automation Workflow
1. Run `pytest -q` locally before committing.
2. Run `pytest --cov=silverestimate --cov-report=term-missing` weekly to track coverage drift.
3. Configure CI to execute:
   - `pytest -q`
   - `pytest -q --disable-warnings --maxfail=1`
4. Publish HTML coverage to CI artifacts for debugging.

## Flake and Stability Controls
- Mark known intermittent GUI tests with `@pytest.mark.flaky` and document issue references.
- Use `qtbot.waitSignal` with timeouts instead of `sleep`.
- For threaded code, inject synchronization hooks so tests can wait for completion deterministically.

## Developer Checklist When Adding Features
- Update or add fixtures if new services require configuration.
- Implement unit tests for pure logic modules.
- Add integration tests when touching database schema or cross-module workflows.
- Document new test utilities within this playbook.
- Record significant changes in `DOCS/project-memory-bank.md` session journal.

## Roadmap
- [x] Introduced Hypothesis strategies for wage and fine calculations (see tests/factories/estimate_items.py).
- [x] Backfilled tests for navigation commands and print workflow (see tests/services/test_navigation_service.py and tests/services/test_main_commands.py).
- [x] Validated data wipe side effects with temporary settings directories (tests/services/test_auth_service.py).
- [ ] Add regression tests for recent bug fixes (see `CHANGELOG.md`).
- [ ] Integrate coverage thresholds into the CI pipeline.

Keep this document updated as the test suite evolves.
\n## Recent Additions
- Standardised integration/database tests on estimate item factories for shared payloads.
- Added navigation and print workflow coverage along with data-wipe failure handling tests.
- Added Hypothesis strategies backing net/fine/wage property tests via tests.factories.
- Added EstimateEntryWidget smoke tests covering return/silver-bar toggles and persistence reloads.\n- Introduced Hypothesis-based property tests for fine- and wage-calculation helpers (skips automatically when Hypothesis is unavailable).

