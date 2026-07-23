# PySide6 Migration Execution Plan

| Field | Value |
|---|---|
| Overall status | In progress |
| Current milestone | M8 - Final PyQt removal and workstream closure |
| Next action | Run the M8 live-reference, installed-distribution, final Windows, SQLCipher, and Graphify closure gates locally; keep all changes unpushed until the owner requests the final main update. |
| Roadmap workstream | Phase 4 - PyQt6-to-PySide6 migration |
| Last updated | 2026-07-23 |
| Last reviewed against commit | `765d478580ca870341d127dd426207de64feba0c` |
| Primary platform | Windows 10/11 x64, Python 3.14 |
| Owner | Unassigned |

This is the living implementation plan for the binding migration described in
the [modernization roadmap](modernization-roadmap.md#9-phase-4-pyqt6-to-pyside6-migration).
It is intentionally more operational than the roadmap. Future agents should
work from this document, update it as evidence is produced, and leave it in a
state from which another agent can resume without reconstructing prior work.

## 1. How future agents must use this plan

At the beginning of every migration task:

1. Read the repository `AGENTS.md`, this plan, and roadmap sections 9, 15, 18.4,
   and 20.
2. Run `git status --short` and `git rev-parse HEAD`. Preserve unrelated user
   changes and update **Last reviewed against commit** only after inspecting the
   new delta.
3. When `graphify-out/graph.json` exists, query Graphify for the milestone being
   worked. The graph can be stale, so corroborate its result against the current
   source tree.
4. Change only one milestone, or one explicitly named slice of a milestone, per
   task. Do not mix UI redesign, facade decomposition, Passlib removal, or
   unrelated cleanup into the binding migration.
5. Before editing, set the milestone status to **In progress**, add the agent or
   task identifier if available, and state the exact intended slice in the
   progress log.
6. Run the milestone's focused checks before the full gates. Record commands,
   outcomes, artifact locations, and intentional deviations in the evidence
   table. A checkbox alone is not completion evidence.
7. Mark a milestone **Complete** only when every exit criterion is satisfied.
   If work stops early, leave it **In progress** or **Blocked**, document the
   first failing command and the next safe action, and do not imply completion.
8. After source changes, run `graphify update .` as required by the repository
   instructions. Record the update result but do not hand-edit graph output.
9. Update this document, the roadmap implementation record, documentation index,
   and user-facing PyQt/PySide references when their facts change.

Use these status values consistently:

| Status | Meaning |
|---|---|
| Not started | No implementation work has been accepted. |
| In progress | Work or validation is active; remaining items are identified. |
| Blocked | A concrete external or technical condition prevents safe progress. |
| Complete | All exit criteria pass and evidence is recorded. |
| Superseded | A recorded decision replaced this milestone or approach. |

## 2. Migration objective and boundaries

The target state is a PySide6-only application and development environment with
the same supported workflows, data behavior, print output, performance budgets,
and Windows packaging guarantees captured by the retained M0 PyQt6 baseline.

Non-negotiable rules:

- Do not introduce a permanent `qt_compat.py`, dual-binding loader, or fallback
  from PySide6 to PyQt6.
- Do not change estimate, inventory, silver-bar, authentication, database, or
  print business rules to make the migration easier.
- Do not combine the migration with estimate-entry composition, settings
  decomposition, print-controller decomposition, or the packaging-tool
  benchmark. Those are later roadmap workstreams.
- Do not remove Passlib in this workstream. Phase 5 follows this migration and
  has its own compatibility requirements.
- Keep the controlled SQLCipher wheel, runtime verification, encrypted-storage
  tests, single-instance behavior, and artifact smoke gates intact.
- Treat generated screenshots and PDFs as test evidence, never as permission
  to silently accept a visual regression.
- Use Qt's `pyside6-deploy` wrapper with the locked Nuitka toolchain. Validate
  the new PySide6 artifact against current release requirements; do not compare
  it with the retired M0 executable.
- Use synthetic test data only. Never capture production databases, credentials,
  logs, or customer identifiers in artifacts.

## 3. Current baseline and affected surface

The following facts were measured at the commit listed above. The first agent
working M0 must re-run the inventory commands and update these values if the
tree changed.

| Item | Known baseline |
|---|---|
| Production files containing PyQt imports/signals | 66 |
| Test files containing PyQt imports/signals | 39 |
| Total affected Python files | 105 |
| PyQt import/signal reference lines | 278 |
| pytest-qt backend | `pyqt6` in `pyproject.toml` |
| Runtime binding | `PyQt6>=6.11,<6.12` plus Windows `PyQt6-Qt6==6.11.1` |
| Development typing | `PyQt6-stubs` plus a `PyQt6.*` mypy override |
| Freezer | PyInstaller with `PyQt6/Qt6/...` filtering in `SilverEstimate.spec` |
| UI smoke evidence | 13 PNGs produced by `nox -s smoke_ui` |
| Print evidence | Classic/Modern semantic golden text and generated PDF tests |

Re-run the inventory with:

```powershell
$productionFiles = rg -l "from PyQt6|import PyQt6|pyqtSignal|pyqtSlot|pyqtProperty" silverestimate --glob '*.py'
$testFiles = rg -l "from PyQt6|import PyQt6|pyqtSignal|pyqtSlot|pyqtProperty" tests --glob '*.py'
"production_files=$($productionFiles.Count)"
"test_files=$($testFiles.Count)"
rg -n "from PyQt6|import PyQt6|pyqtSignal|pyqtSlot|pyqtProperty" silverestimate tests --glob '*.py'
```

Primary touchpoints:

| Area | Important locations | Why it is sensitive |
|---|---|---|
| Dependencies and tooling | `pyproject.toml`, `uv.lock`, `.pre-commit-config.yaml` | Runtime binding, Qt wheel, stubs, pytest-qt, and typing policy must change together. |
| Application startup | `main.py`, `silverestimate/infrastructure/application.py`, `qt_bootstrap.py`, `logger.py` | QApplication lifetime, message handler, high-DPI behavior, QLockFile, and a literal `PyQt6` module-name check. |
| QObject workers/signals | `latest_request_runner.py`, `dda_rate_stream.py`, `live_rate_service.py`, `main_commands.py`, preview workers | Signal descriptors, queued delivery, QThread ownership, cancellation, and deletion semantics can differ. |
| Object validity | estimate-entry adapter, layout/table/totals controllers, `inline_status.py` | These files use `PyQt6.sip.isdeleted`; PySide6 uses Shiboken validity semantics. |
| Models and editing | table models, views, delegates, item selection, keyboard tests | Enum values, role data, event filters, focus, edit progression, and selection must remain stable. |
| Settings and dialogs | `settings.py`, `settings_dialog.py`, live-rate/print settings pages, login | QSettings coercion, signals, validation, modal result handling, and cancel behavior. |
| Printing | `print_manager.py`, renderers, page settings, `print_preview_controller.py`, related tests | QPrinter/QPrintPreview, fonts, pagination, PDF export, actions, and plugin inclusion. |
| Packaging | `pysidedeploy.spec`, `noxfile.py`, `scripts/build_windows_local.ps1` | Nuitka discovery and exclusions must be proven from the standalone artifact and compilation report. |
| CI and release | `.github/workflows/*.yml`, PR template, notices, deployment guide | Windows validation, screenshots, frozen startup, metadata, SBOM, and licensing must name the selected binding. |

Known semantic hotspots that must not be treated as search-and-replace work:

- Replace each `PyQt6.sip.isdeleted` decision with a reviewed
  `shiboken6.isValid` equivalent and test both live and deleted wrappers.
- Replace the literal `type(app).__module__.startswith("PyQt6.")` startup check
  with behavior that is correct for a real PySide6 QApplication and existing
  test doubles.
- Adapt `pyqtSignal`, `pyqtSlot`, and `pyqtProperty` to `Signal`, `Slot`, and
  `Property`; update tests that inspect the concrete signal descriptor type.
- Update string-based monkeypatch targets such as
  `PyQt6.QtWidgets.QApplication.quit` and `PyQt6.QtWidgets.QMenu.exec`.
- Review QObject parentage, references held by Python, `deleteLater()`, thread
  cleanup, and event-loop draining. A passing import is not proof of safe
  lifetime behavior.
- Review print preview internals and font metrics even if the Qt major/minor
  version appears equivalent.

## 4. Milestone dashboard

| ID | Milestone | Status | Owner | Evidence |
|---|---|---|---|---|
| M0 | Freeze PyQt6 reference baseline | Complete | Codex | `artifacts/pyside6-migration/m0/765d478-pyqt6-reference/README.md` |
| M1 | Select and lock PySide6 toolchain | Complete | Codex | `pyproject.toml`, `uv.lock`, and the M1 verification record below |
| M2 | Mechanical source and test conversion | Complete | Codex | 127 production modules import, 609 tests collect, and source/test zero-reference searches are clean |
| M3 | Semantic compatibility audit and fixes | Complete | Codex | 615 regular tests plus the opt-in full-startup smoke pass under PySide6 6.11.1; M2-F1 through M2-F3 resolved |
| M4 | Typing, tests, and performance stabilization | Complete | Codex | `artifacts/pyside6-migration/m4/765d478-pyside6-quality/README.md` |
| M5 | Visual, keyboard, and print approval | Complete | Codex | `artifacts/pyside6-migration/m5/765d478-pyside6-approval/README.md` |
| M6 | `pyside6-deploy`, frozen artifact, and CI cutover | In progress | Codex | Local standalone/one-file artifacts and `artifacts/pyside6-deploy/nuitka-report.xml`; hosted workflow execution pending |
| M7 | Documentation, licensing, and release metadata | Complete | Codex | `artifacts/pyside6-migration/m7/765d478-docs-metadata/README.md` |
| M8 | Final PyQt removal and workstream closure | Complete locally | Codex | `artifacts/pyside6-migration/m8/765d478-pyside6-closure/README.md`; hosted main validation pending |

Dependency order:

```text
M0 -> M1 -> M2 -> M3 -> M4 -> M5 -> M6 -> M7 -> M8
```

M3 can be divided by risk area after M2, but M4 must not be declared complete
until every M3 slice is integrated. M5 and M6 may be investigated in parallel
only after the source suite is stable. At the owner's direction, local M7/M8
work may proceed before the hosted M6 jobs because the migration will be pushed
to main only at the end; M6 remains in progress until those hosted jobs pass.

## 5. M0 - Freeze the PyQt6 reference baseline

**Goal:** Create reproducible evidence for behavior, appearance, print output,
performance, and packaging before any binding change.

### M0.1 Environment record

- [x] Record Windows edition/build, architecture, Python patch version, PyQt6
      version, Qt runtime version, pytest-qt version, PyInstaller version, display
      scale, resolution, default printer configuration, and commit SHA.
- [x] Confirm `git status --short` is understood and unrelated changes are not
      included.
- [x] Run `uv sync --frozen --extra dev` without changing `uv.lock`.
- [x] Verify the installed SQLCipher runtime using the same two commands as the
      Windows workflows.

Reference commands:

```powershell
git status --short
git rev-parse HEAD
uv sync --frozen --extra dev
uv run python -c "import sys; from PyQt6.QtCore import PYQT_VERSION_STR, QT_VERSION_STR; print(sys.version); print(PYQT_VERSION_STR, QT_VERSION_STR)"
uv run python -m pytest --version
uv run python -m PyInstaller --version
uv run python scripts/verify_sqlcipher_runtime.py --wheel vendor/sqlcipher/sqlcipher3-0.6.2+silverestimate.4.17.0.1-cp314-cp314-win_amd64.whl --provenance vendor/sqlcipher/PROVENANCE.json
uv run python scripts/verify_sqlcipher_runtime.py --provenance vendor/sqlcipher/PROVENANCE.json
```

### M0.2 Automated behavioral baseline

- [x] `uv run nox -s ruff` passes.
- [x] `uv run nox -s mypy` passes.
- [x] `uv run nox -s bandit` passes.
- [x] `uv run nox -s tests_full` passes with the current coverage and performance
      results recorded.
- [x] The test count, coverage percentage, and `perf-metrics.log` summary are
      recorded below.

### M0.3 Screenshot and keyboard baseline

- [x] Run `uv run nox -s smoke_ui` under the documented offscreen environment.
- [x] Preserve all 13 generated images from `artifacts/smoke-ui/` as CI or task
      evidence tied to the baseline commit.
- [x] Record dimensions and SHA-256 for each screenshot.
- [x] Exercise and record the critical keyboard workflows: table Enter/Tab/Backspace
      progression, row navigation, item lookup, Ctrl+R return mode, Ctrl+B
      silver-bar mode, dialog accept/cancel, and context-menu actions.
- [x] Note that offscreen screenshots are comparison evidence; final approval
      still requires a normal Windows display at the recorded scale factor.

Expected screenshot set:

```text
01-login-setup.png
02-login-existing-password.png
03-main-window.png
04-estimate-entry.png
05-item-master.png
06-estimate-history.png
07-settings.png
08-custom-font.png
09-item-selection.png
10-silver-bar-management.png
11-silver-bar-optimization.png
12-silver-bar-history.png
13-print-preview.png
```

### M0.4 Print and PDF baseline

- [x] Run the focused print suites and record exact test results.
- [x] Preserve representative Classic and Modern PDFs for A4 portrait,
      multipage content, large fonts, long names, tunch visibility, and silver-bar
      inventory/list reports.
- [x] Record page count, page size, extracted semantic text hash, rasterized page
      hash, and the Qt/font environment for each approved reference.
- [x] Verify preview format switching, zoom defaults, PDF atomic replacement,
      quick-print failure behavior, and printer-unavailable behavior.

Reference focused command:

```powershell
uv run pytest tests/ui/test_print_manager.py tests/unit/test_print_preview_controller.py tests/unit/test_estimate_print_renderer.py -v
```

### M0.5 Packaged baseline

- [x] `uv run nox -s build_clean` passes on Windows.
- [x] `uv run nox -s artifact_smoke` passes.
- [x] Record executable/archive sizes and frozen startup measurements.
- [x] Inspect the PyInstaller build inventory and record required Qt plugins,
      especially platform, image format, SVG icon, and print-support plugins.
- [x] Store the evidence location and retention policy in the table below.

**M0 exit criteria:** All current gates pass on one documented Windows/Python
environment; the 13 screenshots, representative PDFs, performance metrics, and
artifact inventory can be traced to a commit; deviations are explained. Do not
start M1 without this baseline unless the project owner explicitly accepts the
missing evidence in the decision log.

## 6. M1 - Select and lock the PySide6 toolchain

**Goal:** Establish one resolvable, reproducible PySide6 environment for Python
3.14 and Windows without retaining PyQt6.

- [x] Confirm that the selected PySide6 patch release provides a Windows x64
      Python 3.14 wheel and installs in a clean environment.
- [x] Record the selected PySide6, Shiboken6, Qt, pytest-qt, and PyInstaller
      versions plus the reason for any non-latest pin.
- [x] Replace the `PyQt6` and explicit `PyQt6-Qt6` runtime dependencies with
      PySide6.
- [x] Remove `PyQt6-stubs`; use PySide6's distributed type information.
- [x] Update project keywords and classifiers from PyQt6 to PySide6/Qt as
      supported by packaging metadata.
- [x] Change pytest-qt's `qt_api` from `pyqt6` to `pyside6`.
- [x] Remove the `PyQt6.*` mypy missing-import override. Do not add a blanket
      `PySide6.*` ignore merely to make mypy green.
- [x] Regenerate `uv.lock` deliberately and review the diff for PyQt/PySide Qt
      packages and unrelated dependency churn.
- [x] Prove a minimal QApplication can start and exit under both `offscreen` and
      normal Windows platform plugins.
- [x] Confirm `uv sync --frozen --extra dev` succeeds from the committed lock.

Selected M1 toolchain:

| Component | Selected version | Selection note |
|---|---:|---|
| Python | 3.14.4 | Supported project interpreter used for clean and local verification |
| PySide6 | 6.11.1 | Latest stable compatible release; `cp310-abi3-win_amd64` wheel covers CPython 3.14 |
| PySide6 Addons/Essentials | 6.11.1 | Matching packages resolved by the PySide6 meta-package |
| Shiboken6 | 6.11.1 | Matching release required by PySide6 |
| Qt | 6.11.1 | Reported at runtime by `qVersion()` |
| pytest-qt | 4.5.0 | Latest stable release at selection time |
| PyInstaller | 6.21.0 | Latest stable release at selection time |

`PySide6>=6.11.1,<6.12` admits compatible 6.11 patches while the reviewed lock
selects 6.11.1 exactly. No component above is held below its latest compatible
stable release. PyPI's standardized Trove classifier list has no PySide6 or
generic Qt framework classifier, so the obsolete `Framework :: PyQt6`
classifier was removed and the supported `pyside6`/`qt6` terms were added to
project keywords.

Suggested dependency-edit workflow:

```powershell
uv add "PySide6<next-incompatible-version>"
uv remove PyQt6 PyQt6-Qt6
uv remove --optional dev PyQt6-stubs
uv lock
uv sync --frozen --extra dev
$env:QT_QPA_PLATFORM = "offscreen"
uv run python -c "from PySide6.QtCore import qVersion; from PySide6.QtWidgets import QApplication; app=QApplication([]); print(qVersion()); app.quit()"
```

The version constraint is intentionally not hard-coded here. The implementing
agent must select it from packages actually available for the supported Python
and platform, then replace the placeholder with the reviewed constraint.

**M1 exit criteria:** A fresh frozen sync contains PySide6/Shiboken6 and no
PyQt6 distribution, pytest-qt selects `pyside6`, and a minimal QApplication
starts on the supported platform. Application test failures caused by
unconverted imports are expected until M2.

## 7. M2 - Mechanical source and test conversion

**Goal:** Make the entire source and test tree import PySide6 using the direct
binding API, with behavior changes deferred to reviewed M3 fixes.

- [x] Replace `PyQt6` module imports with the corresponding `PySide6` imports in
      production code, tests, string-based monkeypatch targets, comments, and
      executable runtime checks.
- [x] Replace `pyqtSignal`, `pyqtSlot`, and `pyqtProperty` with `Signal`, `Slot`,
      and `Property` imports and declarations.
- [x] Replace `PyQt6.sip` imports. Use `shiboken6.isValid` only after confirming
      the caller's intended live/deleted-object semantics; list every changed
      validity check in M3 evidence.
- [x] Update `TYPE_CHECKING` imports and annotations.
- [x] Update tests that assert PyQt-specific descriptor types or names so they
      assert the required behavior under PySide6.
- [x] Do not introduce aliases named `pyqtSignal` or `sip` to hide incomplete
      conversion.
- [x] Run Ruff formatting and import sorting after the mechanical change.
- [x] Run the zero-reference searches below and attach their output.

Required searches:

```powershell
rg -n "PyQt6|PyQt6-Qt6|PyQt6-stubs|pyqtSignal|pyqtSlot|pyqtProperty" silverestimate tests main.py noxfile.py pyproject.toml pysidedeploy.spec scripts .github readme.md DOCS THIRD_PARTY_NOTICES.md
rg -n "from PyQt6 import sip|sip\.isdeleted" silverestimate tests
```

The first search may still find intentionally unconverted packaging and
documentation references assigned to M6/M7. Every remaining match must be
listed; no source or test match is acceptable at M2 exit.

**M2 exit criteria:** All production and test Python modules import under
PySide6, there are no PyQt signal names or SIP calls in source/tests, and the
remaining failures are categorized in the M3 compatibility matrix.

## 8. M3 - Semantic compatibility audit and fixes

**Goal:** Prove behavior across the areas where SIP and Shiboken or the two
bindings can differ. Each row is an independently reviewable slice.

| Slice | Required review | Focused evidence | Status |
|---|---|---|---|
| M3-A Startup/bootstrap | Message handler, QApplication reuse, hidden dialog parent, high DPI, QLockFile, app module check, exit code | application builder/bootstrap tests plus offscreen startup | Complete; bootstrap tests and opt-in full-startup smoke pass |
| M3-B Signals/workers | Signal signatures, queued delivery, cross-thread values, latest-result suppression, cancellation, shutdown, `deleteLater()` | live-rate, DDA stream, latest-request, preview-worker tests | Complete; explicit idempotent voucher signal ownership and all worker/service tests pass |
| M3-C Object validity | Every former `sip.isdeleted` call, deleted wrappers, timers, views/models, host proxies | focused lifecycle tests that exercise both valid and invalid objects | Complete; all 18 decisions audited and six focused live/deleted-wrapper tests pass |
| M3-D Models/enums | QModelIndex, roles, flags, dataChanged, selection models, enum equality/conversion | all table-model and state-controller tests | Complete; direct alignment flags replace integer coercions and all model tests pass |
| M3-E Editing/input | QTest events, delegates, event filters, focus, Enter/Tab/Backspace, context menu | estimate-entry integration, table-view, mode-toggle tests | Complete; integration, table-view, and mode-toggle suites pass without modal hangs |
| M3-F Dialogs/settings | `exec()` results, accept/reject, QSettings types, dirty/apply/cancel, file/font dialogs | login, settings, item/history/silver-bar dialog tests | Complete; all dialog/settings tests and startup smoke pass |
| M3-G Printing/preview | QPrinter enums, QPrintPreview internals, QAction placement, page layout, PDF APIs, fonts | print manager, renderer, page settings, preview tests | Complete; print/preview tests and startup preview smoke pass |
| M3-H Icons/theme/windows | QIcon/QPixmap, palette, SVG, scale factor, taskbar icon integration | theme/icon/control tests and normal Windows smoke | Complete; icon/theme/control tests and Windows-hosted offscreen smoke pass |

M2 compatibility findings resolved in M3:

| ID | Slice | Observed PySide6 difference | Resolution |
|---|---|---|---|
| M2-F1 | M3-B Signals/workers | Disconnecting a bound method that is not currently connected emits a libpyside `RuntimeWarning` and raises `SystemError` under the warnings-as-errors policy. | Voucher `returnPressed` ownership is explicit and idempotent; voucher generation no longer disconnects/reconnects it, and stale no-op disconnects were removed from UI test helpers. |
| M2-F2 | M3-E Editing/input | Monkeypatching `PySide6.QtWidgets.QMenu.exec` does not intercept the already imported Shiboken method used by `EstimateTableView`; the context-menu test enters the real modal `exec()` and blocks. | The test substitutes a real `QMenu` subclass at the consumer module seam, captures actions, and never enters the modal native implementation. |
| M2-F3 | M3-D Models/enums | Passing an `int` converted from `Qt.AlignmentFlag` to `QTableWidgetItem.setTextAlignment()` raises a PySide6 deprecation warning under the warnings-as-errors policy. | Settings preview and silver-bar models now pass/return `Qt.AlignmentFlag` combinations directly; alignment behavior is asserted by tests. |

M3-C must audit these 18 mechanically inverted object-validity decisions:

- `silverestimate/ui/adapters/estimate_table_adapter.py`: lines 39 and 48;
- `silverestimate/ui/estimate_entry_totals_controller.py`: line 120;
- `silverestimate/ui/estimate_entry_table_controller.py`: lines 47, 403, 425,
  442, 456, and 473;
- `silverestimate/ui/estimate_entry_layout_controller.py`: lines 413, 450,
  617, 649, 655, 692, 724, and 820;
- `silverestimate/ui/inline_status.py`: line 34.

Rules for M3 fixes:

- Prefer the direct documented PySide6 API over emulating PyQt behavior.
- Add a regression test before or with each non-mechanical compatibility fix.
- Keep lifetime owners explicit; do not fix premature collection by adding
  unbounded global references.
- Do not weaken thread assertions, remove cleanup, or replace deterministic
  waits with arbitrary sleeps.
- Do not loosen enum/type assertions globally. Adapt only call sites whose
  contract actually differs.
- Record unexpected but accepted differences in the decision log, including why
  they do not alter user-visible behavior.

**M3 exit criteria:** Every slice is Complete, focused suites pass without Qt
warnings or shutdown crashes, and all compatibility fixes have behavioral tests.

## 9. M4 - Typing, tests, and performance stabilization

**Goal:** Restore every non-visual quality gate under PySide6 without hiding
binding problems behind configuration suppressions.

- [x] `uv run nox -s ruff` passes.
- [x] `uv run nox -s mypy` passes using PySide6's type information.
- [x] `uv run nox -s bandit` passes.
- [x] `uv run nox -s tests_fast` passes.
- [x] `uv run nox -s tests_full` passes on Windows.
- [x] Coverage remains at or above the enforced threshold and does not drop on
      changed lines.
- [x] All deterministic performance budgets pass.
- [x] Startup stages and time to first editable input are compared with M0.
- [x] Any performance change is measured across enough samples to distinguish it
      from noise; budgets are not raised merely to make the migration pass.
- [x] Warnings are fixed or narrowly justified. Do not add a broad warning
      filter for PySide6/Shiboken.

**M4 exit criteria:** The full source-based gate is green on the supported
Windows/Python environment with no unexplained coverage, warning, or performance
regression.

## 10. M5 - Visual, keyboard, and print approval

**Goal:** Compare PySide6 output with the approved M0 reference and explicitly
accept or fix every material difference.

- [x] Generate the same 13 smoke screenshots using the same screen geometry,
      scale, platform, fonts, and seeded data as M0.
- [x] Compare each screen for clipping, missing controls, font substitution,
      alignment, focus indicators, selected rows, scrollbars, dialog sizing, and
      icon rendering.
- [x] Re-run the critical keyboard workflow checklist on a normal Windows
      display, not only offscreen.
- [x] Generate the same representative Classic, Modern, multipage, large-font,
      and silver-bar PDFs as M0.
- [x] Compare PDF page size, page count, extracted text, required sections,
      totals, headers, rasterized layout, clipping, and pagination.
- [x] Exercise print preview format switching, page navigation, zoom, printer
      selection, page setup, PDF export, quick print, and error paths.
- [x] Record reviewer/owner approval for every intentional visual or print
      difference.

Do not require byte-identical PNG or PDF hashes across bindings. Font metadata
and PDF producer details can differ. Approval must combine semantic assertions
with controlled visual comparison and documented tolerances.

**M5 exit criteria:** All critical workflows are approved; there are no
unexplained visual, keyboard, or print regressions; comparison artifacts and
review notes are retained.

## 11. M6 - `pyside6-deploy`, frozen artifact, and CI cutover

**Goal:** Produce a clean Windows artifact containing the intended PySide6/Qt
runtime and only required plugins.

- [x] Generate and commit the canonical `pysidedeploy.spec`; lock the latest
      stable Nuitka release that supports the Python 3.14 target.
- [x] Build an inspectable standalone artifact before the one-file executable.
- [x] Retain required SQLCipher dynamic libraries, provenance, license, notices,
      keyring backends, and Passlib hidden import until Phase 5.
- [x] Verify that excluded Qt modules remain absent and required Qt DLLs/plugins
      remain present.
- [x] Add focused standalone-inventory, compilation-report, and frozen
      self-report validators with regression tests.
- [x] Update Nox, the local Windows build script, and PR/main/release workflows
      to use `pyside6-deploy`.
- [x] `uv run nox -s build_standalone standalone_artifact_smoke` passes.
- [x] `uv run nox -s build_clean artifact_smoke` passes.
- [x] The release startup-budget check passes for at least five samples.
- [x] Inspect the built artifact/report for PyQt6, duplicate Qt runtimes, missing
      Shiboken6, and unintended plugins.
- [x] Verify SQLCipher open, icons/SVG, Windows keyring, PDF, Windows Qt
      platform, and print-support initialization from the frozen artifact.
- [x] Run the complete local quality/test suite after the build-tool cutover.
- [ ] Run the updated PR, main, and release workflows on hosted Windows runners.

Canonical release-style commands:

```powershell
uv run nox -s build_standalone standalone_artifact_smoke
uv run nox -s build_clean artifact_smoke
uv run python scripts/check_startup_budgets.py --artifact dist\SilverEstimate-v3.07.exe --samples 5 --p95-budget-ms 3000
```

**M6 exit criteria:** PR, main, and release Windows workflows build and smoke a
PySide6-only artifact; required plugins and notices are present; no PyQt6 or
second Qt runtime is packaged. Acceptance is against the current PySide6
release contract, not a comparison with the M0 executable.

## 12. M7 - Documentation, licensing, and release metadata

**Goal:** Make every maintained statement describe the shipped PySide6 stack.

- [x] Update README description, badges, architecture, testing, build, and change
      history references.
- [x] Update `DOCS/README.md`, architecture, deployment, security, API, and other
      maintained pages that claim PyQt6 behavior.
- [x] Update project keywords/classifiers and the PR template's test configuration.
- [x] Replace PyQt6 notices with accurate PySide6, Shiboken6, and Qt licensing
      and source information in `THIRD_PARTY_NOTICES.md`.
- [x] Confirm the release SBOM identifies the selected Python and native Qt
      components.
- [x] Update `CHANGELOG.md` with the binding migration, test evidence, known
      differences, and rollback considerations.
- [x] Update the modernization roadmap implementation record without marking
      Phase 4 complete while the M6 hosted runs remain pending.
- [x] Verify documentation links and commands.

**M7 exit criteria:** Source metadata, docs, notices, workflows, and release
artifacts consistently identify PySide6; there are no stale user-facing PyQt6
claims except historical release notes clearly labeled as such.

## 13. M8 - Final PyQt removal and workstream closure

**Goal:** Prove that PySide6 is the sole supported binding and hand off a stable
base for Phase 5 and later architecture work.

- [x] Search the repository for `PyQt6`, `PyQt6-Qt6`, `PyQt6-stubs`,
      `pyqtSignal`, `pyqtSlot`, `pyqtProperty`, and PyQt SIP usage.
- [x] Classify any historical-document matches; no live code, test, config,
      workflow, packaging, or current documentation match may remain.
- [x] Confirm installed and locked distributions contain no PyQt package.
- [x] Run the complete final gate below on Windows.
- [x] Confirm the migration did not add a binding compatibility layer.
- [x] Confirm SQLCipher tests/runtime identity and all data workflows still pass.
- [x] Run `graphify update .` and query the graph for PyQt6/PySide6 live paths.
- [x] Mark roadmap Phase 4 locally complete, retain its hosted-validation
      qualifier, and set the next planned workstream to Phase 5 Passlib removal.
- [x] Add a final progress-log entry with the release/commit, evidence links,
      known limitations, and rollback point.

Final gate:

```powershell
uv sync --frozen --extra dev
uv run --frozen --extra dev nox -s ruff mypy bandit tests_full smoke_ui
uv run --frozen --extra dev nox -s build_standalone standalone_artifact_smoke
uv run --frozen --extra dev nox -s build_clean artifact_smoke
uv run --frozen --extra dev python scripts/check_startup_budgets.py --artifact dist\SilverEstimate-v3.07.exe --samples 10 --p95-budget-ms 3000
uv run --frozen --extra dev python scripts/verify_sqlcipher_runtime.py --provenance vendor/sqlcipher/PROVENANCE.json
rg -n -i "from PyQt6|import PyQt6|pyqtSignal|pyqtSlot|pyqtProperty|sip\.isdeleted|PyQt6-Qt6|PyQt6-stubs" silverestimate tests main.py noxfile.py pyproject.toml uv.lock pysidedeploy.spec scripts .github
```

**M8 exit criteria:** All Phase 4 roadmap acceptance criteria are satisfied,
PySide6 is the only live Qt binding, final Windows evidence is recorded, and
future work can begin without a dual-binding transition state.

## 14. Stop conditions and rollback policy

Stop and record a **Blocked** status instead of improvising when:

- no compatible PySide6 Windows x64 wheel exists for the supported Python 3.14
  version;
- a clean frozen sync requires an unreviewed Python or Qt platform change;
- the baseline cannot be reproduced well enough to evaluate a visual or print
  difference;
- required print, SVG, image, platform, keyring, or SQLCipher functionality is
  missing from the frozen artifact;
- QObject ownership, worker shutdown, or deleted-wrapper behavior causes an
  intermittent crash that is not understood;
- resolving a failure would require changing business rules, database formats,
  or another roadmap workstream;
- a generated artifact includes both PyQt6 and PySide6/Qt runtimes.

Rollback rules:

- Keep the last green PyQt6 commit/tag and its M0 evidence until M8 is complete.
- Revert the migration changes as a unit if the selected PySide6 toolchain cannot
  meet M4-M6 gates. Do not ship a runtime fallback that imports PyQt6.
- Never roll back or replace user databases as part of a Qt-binding rollback;
  the migration must not change the SQLCipher format.
- Do not delete baseline or failure artifacts until the decision is recorded.

## 15. Evidence register

Add one row for each meaningful gate or artifact set. Use repository-relative
paths for committed evidence and a durable CI/task URL or artifact identifier
for external evidence. Never record secrets or production data.

| Date | Commit | Milestone | Environment | Command/check | Result | Evidence location | Notes |
|---|---|---|---|---|---|---|---|
| 2026-07-22 | `5037646` | Plan creation | Windows workspace inspection | Source/graph inventory | Plan only | This document | Baseline counts must be re-verified by M0. |
| 2026-07-22 | `5037646` plus documented working-tree changes | Plan creation | Windows, Graphify 0.9.18, DeepSeek `deepseek-v4-flash` | `graphify extract . --backend deepseek`, community labeling, graph query, and multigraph diagnostic | 4,584 nodes, 9,433 edges; plan discoverable; integrity diagnostic clean | `graphify-out/` | Extraction used 60,834 input and 40,995 output tokens (estimated $0.0200). Old saved-query memory omissions and PDF/PNG ID collisions were reported as non-fatal warnings. |
| 2026-07-23 | `765d478` plus documented M0 working-tree changes | M0.1-M0.3 | Windows 11 build 26200, Python 3.14.4, PyQt6 6.11.0, Qt runtime 6.11.1, 1920x1200 at 125% | Frozen sync, SQLCipher verification, Ruff, mypy, Bandit, `tests_full`, `smoke_ui`, and focused keyboard workflows | Passed; 608 regular plus 1 smoke test, 83% coverage, all seven performance budgets, 13 screenshots | `artifacts/pyside6-migration/m0/765d478-pyqt6-reference/README.md` | Normalized one source file's mixed line endings; shortcut tests now drain deferred widget deletion before testing window-scoped shortcuts; no application behavior changed. |
| 2026-07-23 | `765d478` plus documented M0 working-tree changes | M0.4-M0.5 | Same environment; Arial/Courier New registered for offscreen PDF rendering; default Brother printer detected | 40 focused print tests, 9 PDF variants, Poppler 144-DPI visual inspection, `build_clean`, `artifact_smoke`, 5 startup samples, PyInstaller inventory | Passed; 11 PDF pages visually clean; frozen p95 1516.18 ms; artifact smoke reported SQLCipher 4.17.0/OpenSSL/SQLite 3.53.3 | `artifacts/pyside6-migration/m0/765d478-pyqt6-reference/` | Retain through M8; evidence uses synthetic data only. |
| 2026-07-23 | `765d478` plus documented M0-M4 working-tree changes | M4 | Windows 11 build 26200, Python 3.14.4, PySide6/Shiboken6/Qt 6.11.1 | Ruff, mypy, Bandit, fast/full tests, warnings-as-errors, global and diff coverage, deterministic performance, 20-sample startup-stage comparison, and paired profiles | Passed; 616 regular plus 1 smoke test, 83% global coverage, 90% changed-line coverage, all seven performance budgets; first-editable p95 244.12 ms versus M0 136.09 ms | `artifacts/pyside6-migration/m4/765d478-pyside6-quality/README.md` | The measured source-stage delta is attributable to one-time Shiboken signature initialization; no warning filter or performance-budget increase was added. |
| 2026-07-23 | `765d478` plus documented M0-M5 working-tree changes | M5 | Windows 11 build 26200, Python 3.14.4, PySide6/Shiboken6/Qt 6.11.1, 1920x1200 at 125% | 13-state offscreen and native Windows visual review, normal-display keyboard workflow, 9 controlled PDFs/11 raster pages, and focused native print-preview suite | Passed; 10 screenshots pixel-identical, all 13 native states approved, 83 keyboard tests and 40 print tests passed, all PDF text and geometry matched M0 | `artifacts/pyside6-migration/m5/765d478-pyside6-approval/README.md` | Fixed native-DPI screenshot padding and estimate-history summary-label clipping; all remaining timestamp, font-resolution, PDF metadata, and minor raster differences were explicitly approved. |
| 2026-07-23 | `765d478` plus documented M0-M6 working-tree changes | M6 local | Windows 11 x64, Python 3.14.4, PySide6/Shiboken6/Qt 6.11.1, Nuitka 4.1.3 | Curated standalone inventory, Nuitka report, frozen self-report, one-file build, five startup samples, complete local suite | Passed; 64-file standalone payload, required native/plugin/legal inventory, no PyQt6, one-file p95 1872.52 ms under 3000 ms | `artifacts/pyside6-migration/m6/765d478-pyside6-deploy/README.md` | Artifact accepted against the current release contract; hosted PR/main/release runs pending. |
| 2026-07-23 | `765d478` plus documented M0-M7 working-tree changes | M7 | Windows 11 x64, Python 3.14.4, PySide6/Shiboken6/Qt 6.11.1 | Maintained-doc/reference audit, link validation, license review, wheel metadata build, release-SBOM augmentation, workflow YAML parse, Ruff, mypy, 622 tests plus smoke, Bandit | Passed; current docs identify PySide6, 119-component SBOM identifies CPython 3.14.4 and native Qt 6.11.1 with no local file URLs, 83% coverage | `artifacts/pyside6-migration/m7/765d478-docs-metadata/README.md` | M7 completed locally before hosted M6 at owner direction; no push or release action. |
| 2026-07-23 | `765d478` plus documented M0-M8 working-tree changes | M8 local | Windows 11 x64, Python 3.14.4, PySide6/Shiboken6/Qt 6.11.1, Nuitka 4.1.3 | Live binding/dependency scan, installed/locked audit, Ruff, mypy, Bandit, 622 tests plus smoke, UI smoke, SQLCipher wheel/runtime provenance, fresh standalone/one-file builds, frozen smoke, 10-sample startup confirmation, release SBOM | Passed locally; no live PyQt/SIP path or compatibility loader, 64-file standalone payload, one-file p95 2727.15 ms under 3000 ms, 119-component SBOM with no PyQt/SIP component | `artifacts/pyside6-migration/m8/765d478-pyside6-closure/README.md` | One earlier five-sample run caught a 3621.09 ms outlier and failed; the controlled repeat and longer confirmation passed without code or budget changes. Hosted main validation remains pending; no remote action. |

## 16. Decision log

Record decisions that alter sequencing, constraints, selected versions, or
accepted behavior. Append entries; do not rewrite prior decisions without a new
superseding entry.

| Date | Decision | Reason | Consequences | Approved by |
|---|---|---|---|---|
| 2026-07-22 | Execute PySide6 migration before Phase 5 and facade decomposition. | SQLCipher phases are complete and the roadmap orders the binding migration next. | Baseline capture is the immediate task; Passlib and architecture changes remain out of scope. | Project plan |
| 2026-07-22 | Do not use a permanent dual-binding compatibility module. | It would preserve dependency and typing complexity after cutover. | Conversion must be direct and complete; rollback occurs through version control. | Modernization roadmap |
| 2026-07-23 | Accept the measured M4 source-stage increase without changing a budget. | Twenty fresh-process samples and paired profiles isolate the increase to PySide6/Shiboken's one-time signature bootstrap; first editable input remains below 250 ms p95 and all application performance budgets pass with wide headroom. | Preserve the evidence and re-check the complete frozen-process budget in M6; do not use undocumented binding switches or shift work merely to improve one telemetry stage. | M4 verification |
| 2026-07-23 | Approve the M5 PySide6 visual, keyboard, print-preview, and PDF output. | Controlled offscreen and native Windows comparison found no unexplained regression; the only application defect found was a clipped estimate-history summary label and it was fixed and recaptured. | M6 may begin. Dynamic timestamps, native font-family resolution, binding-specific PDF metadata, and three minor but semantically identical PDF raster differences remain documented accepted behavior. | M5 verification |
| 2026-07-23 | Adopt `pyside6-deploy`/Nuitka as the Windows executable builder and do not compare its output with M0. | The owner selected Qt's official deployment wrapper after M5 stabilized the PySide6 application. The artifact should satisfy the current release contract directly. | PyInstaller, `SilverEstimate.spec`, and its hook packages are removed; standalone inventory validation precedes one-file release builds. M0 remains historical migration evidence only. | Project owner |
| 2026-07-23 | Complete M7 and M8 locally before pushing the migration directly to main at the end. | The owner does not want intermediate branch/PR pushes. | M6 remains in progress for hosted runs while local M7/M8 proceeds; no remote, tag, or release action is authorized until the final main update. | Project owner |
| 2026-07-23 | Record M8 and Phase 4 as locally complete while retaining the hosted-validation qualifier. | Every local binding, source, UI, SQLCipher, packaging, startup, and SBOM gate passes, but the owner deferred the main push until the end. | Phase 5 is the next planned workstream but must not start until the final main push and hosted Phase 4 validation complete. | M8 verification and project-owner sequencing |

## 17. Progress and handoff log

Append a short entry whenever an agent starts, completes, pauses, or hands off a
slice. Include only verified facts.

### 2026-07-22 - Plan established

- State: M0 is ready to start; no migration code or dependency changes were made.
- Repository baseline inspected at `5037646077c7dd15462b17fbcdb733033ecf7ff9`.
- Known affected surface: 66 production files, 39 test files, 105 total Python
  files at the inspected commit.
- Immediate next action: execute M0 and fill the evidence register.
- Graphify was refreshed with the DeepSeek backend after plan creation. The
  refreshed graph resolves this plan and passed its post-build multigraph
  diagnostic; future queries must still be corroborated after source changes.

### 2026-07-23 - Codex started M0 reference-baseline capture

- State: In progress; the intended slice is M0.1 through M0.5 only.
- Changes: Marked M0 active before collecting evidence; no binding, dependency,
  business-rule, or application source change is in scope.
- Verification: Pending.
- Evidence: Pending under `artifacts/pyside6-migration/m0/`.
- Decisions: None.
- Remaining: Capture environment, inventory, automated gates, smoke images,
  print/PDF checks, and packaged-artifact evidence.
- Next safe action: Record the current environment and run the frozen sync and
  SQLCipher runtime verification.
- Risks/blockers: None identified at start.

### 2026-07-23 - Codex completed M0 reference-baseline capture

- State: Complete; all M0.1 through M0.5 exit criteria are satisfied.
- Changes: Normalized mixed line endings throughout
  `silverestimate/security/credential_store.py`; made the three window-scoped
  shortcut tests drain deferred widget deletion and show their target window;
  recorded the baseline plan and evidence. No binding, dependency, business
  rule, database, or production UI behavior changed.
- Verification: Frozen sync and both SQLCipher checks passed; Ruff, mypy,
  Bandit, 608 regular tests plus 1 smoke test, 83% coverage, all performance
  budgets, 13-screen smoke capture, 40 focused print tests, clean PyInstaller
  build, artifact smoke, and five frozen-startup samples passed. `graphify
  update .` rebuilt the code graph with 4,568 nodes, 10,080 edges, and 325
  communities; it reported the existing non-fatal zero-node
  `PROVENANCE.json` warning.
- Evidence:
  `artifacts/pyside6-migration/m0/765d478-pyqt6-reference/README.md`.
- Decisions: None.
- Remaining: M1 through M8.
- Next safe action: Start M1 by selecting and locking a PySide6 release that
  supports Windows x64 and Python 3.14, then prove minimal QApplication startup.
- Risks/blockers: Normal-display visual approval remains intentionally assigned
  to M5; the M0 screenshots are controlled offscreen comparison evidence.

### 2026-07-23 - Codex started M1 toolchain selection

- State: In progress; the intended slice is M1 only.
- Changes: Marked M1 active before dependency or configuration edits.
- Verification: Pending current package and Python 3.14 wheel checks.
- Evidence: Pending in this document and the reviewed `uv.lock` diff.
- Decisions: Prefer the latest compatible stable PySide6 patch release unless
  current wheel or runtime verification proves a concrete incompatibility.
- Remaining: Select versions, update project metadata and lockfile, remove PyQt
  distributions from the environment, and prove minimal offscreen/Windows
  QApplication startup.
- Next safe action: Verify the latest stable PySide6 Windows x64 Python 3.14
  wheel and its matching Shiboken6/Qt versions from current package sources.
- Risks/blockers: Application imports remain PyQt6 until M2, so application
  suite import failures are expected after the M1 environment cutover.

### 2026-07-23 - Codex completed M1 toolchain selection

- State: Complete; no M2 source conversion was included.
- Changes: Replaced the PyQt6 runtime and stub dependencies with
  `PySide6>=6.11.1,<6.12`; selected `pyside6` for pytest-qt; removed the
  `PyQt6.*` mypy exception and invalid PyQt6 classifier; updated Qt keywords,
  the pull-request test template, and the isolated pre-commit mypy dependency.
  Pre-commit hooks now use Ruff 0.15.22, mypy 2.3.0, pre-commit-hooks 6.0.0,
  and Bandit 1.9.4.
- Verification: `uv lock --check`, `uv sync --frozen --extra dev`,
  `uv run --isolated --frozen --extra dev ...`, `pre-commit validate-config`,
  `pre-commit run check-toml --all-files`, `pre-commit run check-yaml
  --all-files`, `ruff check .`, and `git diff --check` passed. pytest-qt
  reported `api=pyside6`, `is_pyside=True`, and `is_pyqt=False`. Minimal
  applications reported `platform=offscreen Qt=6.11.1` and
  `platform=windows Qt=6.11.1`.
- Evidence: The isolated Python 3.14.4 install contained `PySide6`,
  `PySide6_Addons`, `PySide6_Essentials`, and `shiboken6`, with no PyQt
  distribution. The selected Windows x64 PySide6 wheel is
  `pyside6-6.11.1-cp310-abi3-win_amd64.whl` with SHA-256
  `0968877ab1fb4ef3587a284da6fe05e8647ada56a6a3750b6395188e01f4aba6`.
- Decisions: Used the latest stable compatible releases available on
  2026-07-23. The full lock upgrade also refreshed compatible non-Qt packages;
  reviewed direct changes include Ruff 0.15.22, Hypothesis 6.160.0,
  diff-cover 10.4.0, and pre-commit 4.6.1. No non-latest toolchain exception
  was required.
- Remaining: M2 through M8.
- Next safe action: Perform the M2 mechanical source/test import and symbol
  conversion, then collect and run the focused M2 checks before semantic fixes.
- Risks/blockers: The application and its tests still import PyQt6 by design;
  collection/runtime failures are expected until M2 completes.

### 2026-07-23 - Codex completed M2 mechanical conversion

- State: Complete; behavior changes remain deferred to M3.
- Changes: Converted 66 production and 40 test modules from `PyQt6` to
  `PySide6`; replaced binding-specific signal/slot/property declarations with
  `Signal`, `Slot`, and `Property`; updated string monkeypatch targets and the
  literal application-module check; replaced SIP imports and inverted 18
  deleted-object decisions to direct `shiboken6.isValid` checks. Ruff fixed
  import order in the five modules that gained Shiboken imports.
- Verification: `compileall` passed; all 127 production modules imported with
  zero failures and no loaded `PyQt6` module; pytest-qt collected all 609 tests
  under PySide6 6.11.1/Qt 6.11.1. Ruff lint and formatting passed. Focused
  execution passed 304 unaffected unit tests, 110 service/controller tests, 55
  integration tests, 54 unaffected UI tests, and two root security tests; the
  full startup smoke remains opt-in and was skipped.
- Zero-reference evidence: Both required source/test searches returned no
  matches, including the broader case-insensitive `pyqt|sip` search. The broad
  repository search has eight intentional remaining files:
  `SilverEstimate.spec` is assigned to M6; `readme.md`,
  `THIRD_PARTY_NOTICES.md`, `DOCS/api-reference.md`,
  `DOCS/project-architecture.md`, and `DOCS/README.md` are assigned to M7;
  `DOCS/modernization-roadmap.md` and this execution plan retain historical,
  checklist, and acceptance references.
- Compatibility findings: M2-F1 through M2-F3 above capture the only observed
  failure categories. Unconnected signal disconnect blocks estimate-entry
  construction, a patched `QMenu.exec` test enters the real modal menu, and
  integer alignment arguments raise a deprecation warning. No M3 fix was
  folded into the mechanical milestone.
- Decisions: Used direct PySide6 names without a compatibility layer or aliases.
  Directly imported `shiboken6.isValid`; its `True` result represents a wrapper
  whose underlying object remains callable, the inverse of the former
  `sip.isdeleted` decisions.
- Remaining: M3 through M8.
- Next safe action: Start M3-B by making signal connection/disconnection
  lifecycle explicit and regression-tested, then address M2-F2 and M2-F3.
- Risks/blockers: The full suite cannot pass until the three recorded M3
  findings are fixed; the context-menu test must not be run unattended because
  it currently enters a real modal `QMenu.exec()`.

### 2026-07-23 - Codex completed M3 semantic compatibility

- State: Complete; every M3-A through M3-H slice and the M3 exit criteria are
  satisfied.
- Changes: Replaced defensive unconnected signal disconnection with an explicit
  idempotent voucher-load connection; removed the unnecessary signal churn from
  voucher generation and stale UI test helpers; changed the context-menu test
  to substitute a real `QMenu` subclass at the consumer module boundary; passed
  alignment flags directly to Qt APIs and returned typed flags from silver-bar
  models; audited all 18 Shiboken validity decisions and restored the required
  `None`-is-unavailable behavior in the three shared lifetime guards.
- Verification: The full regular suite collected 616 tests and completed with
  615 passed and the single opt-in smoke test skipped. Running that smoke test
  separately with `--run-smoke` passed, covering startup, authentication,
  estimate entry, dialogs, silver-bar screens, settings, icons/theme, and print
  preview. The six new lifetime tests cover `None`, ordinary Python objects,
  live Qt wrappers, deleted Qt wrappers, invalid timers, invalid tables, and
  layout operations after deletion. Focused regressions for signal ownership,
  context menus, settings alignment, silver-bar models, and mode toggles pass
  under the warnings-as-errors policy.
- Evidence: `tests/unit/test_qt_object_lifetime.py`,
  `tests/ui/test_estimate_entry_widget.py::test_load_estimate_signal_connection_is_idempotent`,
  `tests/unit/test_estimate_table_view.py::test_context_menu_actions_have_icons`,
  `tests/ui/test_settings_dialog.py::test_settings_dialog_uses_visible_arrow_controls`,
  and the M3 compatibility matrix above.
- Decisions: PySide6 signal connections are owned rather than probed by
  disconnecting; Shiboken validity checks retain the former fallback behavior
  for ordinary Python test doubles but explicitly reject `None`; Qt enum/flag
  objects stay typed at binding boundaries; native extension methods are tested
  through replaceable consumer-module types rather than patched in place.
- Remaining: M4 through M8.
- Next safe action: Start M4 with the repository-wide Ruff and mypy sessions,
  then run coverage and performance gates under PySide6.
- Risks/blockers: None for M3. Normal-display visual approval remains assigned
  to M5, and frozen-artifact validation remains assigned to M6.

### 2026-07-23 - Codex completed M4 quality and performance stabilization

- State: Complete; every M4 checklist item and the source-based exit criteria
  are satisfied.
- Changes: Resolved 62 PySide6 mypy errors across 17 source files without new
  ignores; adopted native fractional `QFont` APIs and `QTextDocument.print_()`;
  widened model overrides for persistent indexes; added explicit `QSettings`
  coercion; tightened typed event, validator, object-lifetime, and preview
  ownership boundaries. Added a changed-line coverage regression test, isolated
  column-width tests from persisted settings, and added the repeatable
  `scripts/measure_startup_stages.py` comparison harness.
- Verification: Ruff, mypy, and Bandit pass. `tests_fast` passes 576 selected
  tests. `tests_full` passes 616 regular tests plus the opt-in startup smoke
  with warnings as errors, 83% global coverage, and all seven deterministic
  performance budgets. Diff coverage is 90% across 434 changed executable
  lines. No PySide6/Shiboken warning filter or performance-budget increase was
  added.
- Evidence:
  `artifacts/pyside6-migration/m4/765d478-pyside6-quality/README.md`,
  `coverage.xml`, and `perf-metrics.log`.
- Decisions: The 20-sample source-stage comparison records a 244.12 ms
  first-editable p95 under PySide6 versus 136.09 ms under M0 PyQt6. Paired
  profiles attribute the material delta to Shiboken's one-time signature
  bootstrap; application performance gates remain effectively flat and well
  below their unchanged budgets. Frozen one-file startup remains assigned to
  M6.
- Remaining: M5 through M8.
- Next safe action: Start M5 by regenerating the same 13 smoke screenshots and
  representative PDFs, then complete the normal-display keyboard and visual
  comparison against M0.
- Risks/blockers: Normal-display approval requires human-visible Windows review
  in M5. No M4 blocker remains.

### 2026-07-23 - Codex completed M5 visual, keyboard, and print approval

- State: Complete; every M5 checklist item and exit criterion is satisfied.
- Changes: Added a repeatable nine-document PDF evidence generator; made smoke
  screenshot padding DPR-safe; made the estimate-history result summary derive
  its minimum width from the rendered text; added focused regression coverage.
- Verification: All 13 offscreen and 13 native Windows states were inspected at
  the M0 1920x1200, 125% display configuration. Ten offscreen PNGs are
  byte-identical to M0; the other three contain the approved width correction
  or generated time values. The normal-Windows keyboard set passes 83 tests,
  the native print/preview set passes the same 40 tests as M0, Ruff passes, and
  the canonical mypy session reports no issues in 128 source files.
- PDF evidence: Nine documents and 11 raster pages retain the M0 page counts,
  media boxes, extracted text, required sections, totals, headers, and
  pagination. Eight raster pages are pixel-identical; three minor
  font-placement differences were visually reviewed and approved.
- Evidence:
  `artifacts/pyside6-migration/m5/765d478-pyside6-approval/README.md`.
- Decisions: Approved dynamic timestamp changes, native Arial resolution,
  PySide6 PDF producer metadata, and the three semantically identical raster
  differences. No unexplained regression remains.
- Remaining: M6 through M8.
- Next safe action: Start M6 by adopting `pyside6-deploy`, validating an
  inspectable standalone artifact, then producing the one-file Windows release
  candidate.
- Risks/blockers: None for M5.

### 2026-07-23 - Codex started M6 pyside6-deploy cutover

- State: In progress; local packaging gates pass and hosted workflow execution
  remains.
- Changes: Removed PyInstaller and `SilverEstimate.spec`; locked Nuitka 4.1.3
  and zstandard 0.25.0; added the canonical `pysidedeploy.spec`; updated Nox,
  the local Windows builder, and PR/main/release workflows. Added Nuitka-aware
  writable path handling plus standalone inventory and frozen self-report
  validators.
- Verification: The curated standalone artifact contains 64 files and
  109,596,192 bytes. It includes PySide6, Shiboken6, SQLCipher, qwindows,
  icon/SVG/image, Windows style, print support, assets, licenses, and
  provenance while rejecting PyQt6, QML/Quick/media, and optional plugin
  inventory. Standalone and one-file artifact smoke both initialize the
  Windows Qt platform, Windows keyring, icon/SVG, PDF rendering, and SQLCipher
  4.17.0/OpenSSL/SQLite 3.53.3. The complete 619-test suite, startup smoke,
  83% coverage, Ruff, mypy, Bandit, deterministic performance gates, and
  `uv lock --check` pass. One-file startup is 1872.52 ms p95 over five
  samples against the unchanged 3000 ms budget.
- Evidence:
  `artifacts/pyside6-migration/m6/765d478-pyside6-deploy/README.md`.
- Decisions: The new artifact is validated independently against the current
  PySide6 release contract. It is not compared with M0.
- Remaining: Execute the updated hosted PR, main, and release Windows
  workflows.
- Next safe action: Push the migration branch and confirm the PR Windows
  standalone/one-file jobs before merging.
- Risks/blockers: Nuitka 4.1.3 is the newest stable release and builds Python
  3.14 successfully, but it still emits an upstream experimental-support
  warning for Python 3.14. Hosted workflow validation remains mandatory.

### 2026-07-23 - Codex completed local M7 documentation and metadata

- State: Complete locally; M6 hosted workflow execution remains intentionally
  deferred until the final main push.
- Changes: Updated maintained PySide6 runtime/architecture/deployment/API
  claims, package keywords and Windows classifier, changelog, roadmap, notices,
  and release workflow. Corrected Nuitka licensing to AGPL-3.0-or-later with
  its Runtime Library Exception. Added deterministic release-SBOM augmentation
  for the root application, CPython, native Qt, and Qt-wheel consistency.
- Verification: All local links across 17 maintained Markdown/template files
  resolve. The built wheel metadata is correct. The 119-component release SBOM
  records Silver Estimate 3.07, CPython 3.14.4, Qt/PySide6/Shiboken6 6.11.1,
  and no machine-local file URLs. Four workflow YAML files parse. Ruff, mypy,
  622 regular tests plus startup smoke, 83% coverage, deterministic
  performance, Bandit, and `uv lock --check` pass.
- Evidence:
  `artifacts/pyside6-migration/m7/765d478-docs-metadata/README.md`.
- Decisions: Proceed locally through M8 and push only at the end directly to
  main; do not mark Phase 4 complete until hosted M6 and M8 closure pass.
- Remaining: M8 plus hosted M6 execution.
- Next safe action: Start M8 with a live PyQt/SIP reference scan and installed
  distribution audit.
- Risks/blockers: None for local M7. Remote validation is intentionally
  deferred by owner instruction.

### 2026-07-23 - Codex completed local M8 PySide6-only closure

- State: Complete locally; Phase 4 remains globally in progress only for the
  final main push and hosted M6/main/release validation.
- Changes: Removed the obsolete M4 dual-binding startup-measurement harness,
  made its generated evidence label binding-neutral, recorded final M8
  evidence, and updated the roadmap and execution plan for local closure.
- Verification: The installed and locked environment contains PySide6,
  Addons, Essentials, and Shiboken6 6.11.1 with no PyQt/SIP distribution.
  pytest-qt selects PySide6. The exact live-reference scan is empty. Ruff,
  mypy, Bandit, 622 regular tests plus startup smoke, 83% coverage,
  deterministic performance, UI smoke, SQLCipher wheel/runtime provenance,
  fresh standalone and one-file builds, both frozen smokes, and
  `uv lock --check` pass. The final 10-sample executable startup p95 is
  2727.15 ms under the unchanged 3000 ms budget. The refreshed Graphify graph
  contains 4655 nodes, 10306 edges, and 343 communities; its PyQt6 concept has
  only one edge, a historical reference from this execution plan, and no live
  executable path. Relative links across 14 maintained Markdown files, all
  four workflow YAML files, patch whitespace, and the unmerged-path audit also
  pass.
- Evidence:
  `artifacts/pyside6-migration/m8/765d478-pyside6-closure/README.md`.
- Decisions: Phase 5 Passlib removal is next but remains unstarted until the
  migration is pushed directly to main and its hosted validation completes.
- Remaining: After owner approval, commit and push directly to main and verify
  the hosted main/release workflows.
- Next safe action: Review the accumulated M0-M8 worktree with the owner, then
  commit and push directly to main only when explicitly requested.
- Risks/blockers: Nuitka 4.1.3 still labels Python 3.14 support experimental.
  One initial startup run failed due to a single 3621.09 ms outlier; a
  five-sample controlled repeat and ten-sample confirmation passed without a
  product or budget change. Hosted validation is intentionally deferred.

Copy this template for subsequent handoffs:

```markdown
### YYYY-MM-DD - <agent/task and milestone>

- State: <Not started/In progress/Blocked/Complete and exact slice>
- Changes: <files and behavior changed>
- Verification: <commands and outcomes>
- Evidence: <paths or durable artifact identifiers>
- Decisions: <decision-log rows added, or none>
- Remaining: <specific unchecked items>
- Next safe action: <one concrete action>
- Risks/blockers: <concrete condition, or none>
```
