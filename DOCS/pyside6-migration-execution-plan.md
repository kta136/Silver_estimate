# PySide6 Migration Execution Plan

| Field | Value |
|---|---|
| Overall status | Not started |
| Current milestone | M0 - freeze the PyQt6 reference baseline |
| Next action | Complete M0.1 through M0.5 and record the evidence in this document before changing dependencies or imports. |
| Roadmap workstream | Phase 4 - PyQt6-to-PySide6 migration |
| Last updated | 2026-07-22 |
| Last reviewed against commit | `5037646077c7dd15462b17fbcdb733033ecf7ff9` |
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
and Windows packaging guarantees as the current PyQt6 application.

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
- PyInstaller remains the freezer for this workstream. A Nuitka or
  `pyside6-deploy` comparison happens only after PySide6 is stable.
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
| Packaging | `SilverEstimate.spec`, `noxfile.py`, `scripts/build_windows_local.ps1` | PySide6 has a different package/plugin layout; exclusions must be proven from the built artifact. |
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
| M0 | Freeze PyQt6 reference baseline | Not started | Unassigned | Pending |
| M1 | Select and lock PySide6 toolchain | Not started | Unassigned | Pending |
| M2 | Mechanical source and test conversion | Not started | Unassigned | Pending |
| M3 | Semantic compatibility audit and fixes | Not started | Unassigned | Pending |
| M4 | Typing, tests, and performance stabilization | Not started | Unassigned | Pending |
| M5 | Visual, keyboard, and print approval | Not started | Unassigned | Pending |
| M6 | PyInstaller, frozen artifact, and CI cutover | Not started | Unassigned | Pending |
| M7 | Documentation, licensing, and release metadata | Not started | Unassigned | Pending |
| M8 | Final PyQt removal and workstream closure | Not started | Unassigned | Pending |

Dependency order:

```text
M0 -> M1 -> M2 -> M3 -> M4 -> M5 -> M6 -> M7 -> M8
```

M3 can be divided by risk area after M2, but M4 must not be declared complete
until every M3 slice is integrated. M5 and M6 may be investigated in parallel
only after the source suite is stable; both must pass before M7 and M8.

## 5. M0 - Freeze the PyQt6 reference baseline

**Goal:** Create reproducible evidence for behavior, appearance, print output,
performance, and packaging before any binding change.

### M0.1 Environment record

- [ ] Record Windows edition/build, architecture, Python patch version, PyQt6
      version, Qt runtime version, pytest-qt version, PyInstaller version, display
      scale, resolution, default printer configuration, and commit SHA.
- [ ] Confirm `git status --short` is understood and unrelated changes are not
      included.
- [ ] Run `uv sync --frozen --extra dev` without changing `uv.lock`.
- [ ] Verify the installed SQLCipher runtime using the same two commands as the
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

- [ ] `uv run nox -s ruff` passes.
- [ ] `uv run nox -s mypy` passes.
- [ ] `uv run nox -s bandit` passes.
- [ ] `uv run nox -s tests_full` passes with the current coverage and performance
      results recorded.
- [ ] The test count, coverage percentage, and `perf-metrics.log` summary are
      recorded below.

### M0.3 Screenshot and keyboard baseline

- [ ] Run `uv run nox -s smoke_ui` under the documented offscreen environment.
- [ ] Preserve all 13 generated images from `artifacts/smoke-ui/` as CI or task
      evidence tied to the baseline commit.
- [ ] Record dimensions and SHA-256 for each screenshot.
- [ ] Exercise and record the critical keyboard workflows: table Enter/Tab/Backspace
      progression, row navigation, item lookup, Ctrl+R return mode, Ctrl+B
      silver-bar mode, dialog accept/cancel, and context-menu actions.
- [ ] Note that offscreen screenshots are comparison evidence; final approval
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

- [ ] Run the focused print suites and record exact test results.
- [ ] Preserve representative Classic and Modern PDFs for A4 portrait,
      multipage content, large fonts, long names, tunch visibility, and silver-bar
      inventory/list reports.
- [ ] Record page count, page size, extracted semantic text hash, rasterized page
      hash, and the Qt/font environment for each approved reference.
- [ ] Verify preview format switching, zoom defaults, PDF atomic replacement,
      quick-print failure behavior, and printer-unavailable behavior.

Reference focused command:

```powershell
uv run pytest tests/ui/test_print_manager.py tests/unit/test_print_preview_controller.py tests/unit/test_estimate_print_renderer.py -v
```

### M0.5 Packaged baseline

- [ ] `uv run nox -s build_clean` passes on Windows.
- [ ] `uv run nox -s artifact_smoke` passes.
- [ ] Record executable/archive sizes and frozen startup measurements.
- [ ] Inspect the PyInstaller build inventory and record required Qt plugins,
      especially platform, image format, SVG icon, and print-support plugins.
- [ ] Store the evidence location and retention policy in the table below.

**M0 exit criteria:** All current gates pass on one documented Windows/Python
environment; the 13 screenshots, representative PDFs, performance metrics, and
artifact inventory can be traced to a commit; deviations are explained. Do not
start M1 without this baseline unless the project owner explicitly accepts the
missing evidence in the decision log.

## 6. M1 - Select and lock the PySide6 toolchain

**Goal:** Establish one resolvable, reproducible PySide6 environment for Python
3.14 and Windows without retaining PyQt6.

- [ ] Confirm that the selected PySide6 patch release provides a Windows x64
      Python 3.14 wheel and installs in a clean environment.
- [ ] Record the selected PySide6, Shiboken6, Qt, pytest-qt, and PyInstaller
      versions plus the reason for any non-latest pin.
- [ ] Replace the `PyQt6` and explicit `PyQt6-Qt6` runtime dependencies with
      PySide6.
- [ ] Remove `PyQt6-stubs`; use PySide6's distributed type information.
- [ ] Update project keywords and classifiers from PyQt6 to PySide6/Qt as
      supported by packaging metadata.
- [ ] Change pytest-qt's `qt_api` from `pyqt6` to `pyside6`.
- [ ] Remove the `PyQt6.*` mypy missing-import override. Do not add a blanket
      `PySide6.*` ignore merely to make mypy green.
- [ ] Regenerate `uv.lock` deliberately and review the diff for PyQt/PySide Qt
      packages and unrelated dependency churn.
- [ ] Prove a minimal QApplication can start and exit under both `offscreen` and
      normal Windows platform plugins.
- [ ] Confirm `uv sync --frozen --extra dev` succeeds from the committed lock.

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

- [ ] Replace `PyQt6` module imports with the corresponding `PySide6` imports in
      production code, tests, string-based monkeypatch targets, comments, and
      executable runtime checks.
- [ ] Replace `pyqtSignal`, `pyqtSlot`, and `pyqtProperty` with `Signal`, `Slot`,
      and `Property` imports and declarations.
- [ ] Replace `PyQt6.sip` imports. Use `shiboken6.isValid` only after confirming
      the caller's intended live/deleted-object semantics; list every changed
      validity check in M3 evidence.
- [ ] Update `TYPE_CHECKING` imports and annotations.
- [ ] Update tests that assert PyQt-specific descriptor types or names so they
      assert the required behavior under PySide6.
- [ ] Do not introduce aliases named `pyqtSignal` or `sip` to hide incomplete
      conversion.
- [ ] Run Ruff formatting and import sorting after the mechanical change.
- [ ] Run the zero-reference searches below and attach their output.

Required searches:

```powershell
rg -n "PyQt6|PyQt6-Qt6|PyQt6-stubs|pyqtSignal|pyqtSlot|pyqtProperty" silverestimate tests main.py noxfile.py pyproject.toml SilverEstimate.spec scripts .github readme.md DOCS THIRD_PARTY_NOTICES.md
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
| M3-A Startup/bootstrap | Message handler, QApplication reuse, hidden dialog parent, high DPI, QLockFile, app module check, exit code | application builder/bootstrap tests plus offscreen startup | Not started |
| M3-B Signals/workers | Signal signatures, queued delivery, cross-thread values, latest-result suppression, cancellation, shutdown, `deleteLater()` | live-rate, DDA stream, latest-request, preview-worker tests | Not started |
| M3-C Object validity | Every former `sip.isdeleted` call, deleted wrappers, timers, views/models, host proxies | focused lifecycle tests that exercise both valid and invalid objects | Not started |
| M3-D Models/enums | QModelIndex, roles, flags, dataChanged, selection models, enum equality/conversion | all table-model and state-controller tests | Not started |
| M3-E Editing/input | QTest events, delegates, event filters, focus, Enter/Tab/Backspace, context menu | estimate-entry integration, table-view, mode-toggle tests | Not started |
| M3-F Dialogs/settings | `exec()` results, accept/reject, QSettings types, dirty/apply/cancel, file/font dialogs | login, settings, item/history/silver-bar dialog tests | Not started |
| M3-G Printing/preview | QPrinter enums, QPrintPreview internals, QAction placement, page layout, PDF APIs, fonts | print manager, renderer, page settings, preview tests | Not started |
| M3-H Icons/theme/windows | QIcon/QPixmap, palette, SVG, scale factor, taskbar icon integration | theme/icon/control tests and normal Windows smoke | Not started |

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

- [ ] `uv run nox -s ruff` passes.
- [ ] `uv run nox -s mypy` passes using PySide6's type information.
- [ ] `uv run nox -s bandit` passes.
- [ ] `uv run nox -s tests_fast` passes.
- [ ] `uv run nox -s tests_full` passes on Windows.
- [ ] Coverage remains at or above the enforced threshold and does not drop on
      changed lines.
- [ ] All deterministic performance budgets pass.
- [ ] Startup stages and time to first editable input are compared with M0.
- [ ] Any performance change is measured across enough samples to distinguish it
      from noise; budgets are not raised merely to make the migration pass.
- [ ] Warnings are fixed or narrowly justified. Do not add a broad warning
      filter for PySide6/Shiboken.

**M4 exit criteria:** The full source-based gate is green on the supported
Windows/Python environment with no unexplained coverage, warning, or performance
regression.

## 10. M5 - Visual, keyboard, and print approval

**Goal:** Compare PySide6 output with the approved M0 reference and explicitly
accept or fix every material difference.

- [ ] Generate the same 13 smoke screenshots using the same screen geometry,
      scale, platform, fonts, and seeded data as M0.
- [ ] Compare each screen for clipping, missing controls, font substitution,
      alignment, focus indicators, selected rows, scrollbars, dialog sizing, and
      icon rendering.
- [ ] Re-run the critical keyboard workflow checklist on a normal Windows
      display, not only offscreen.
- [ ] Generate the same representative Classic, Modern, multipage, large-font,
      and silver-bar PDFs as M0.
- [ ] Compare PDF page size, page count, extracted text, required sections,
      totals, headers, rasterized layout, clipping, and pagination.
- [ ] Exercise print preview format switching, page navigation, zoom, printer
      selection, page setup, PDF export, quick print, and error paths.
- [ ] Record reviewer/owner approval for every intentional visual or print
      difference.

Do not require byte-identical PNG or PDF hashes across bindings. Font metadata
and PDF producer details can differ. Approval must combine semantic assertions
with controlled visual comparison and documented tolerances.

**M5 exit criteria:** All critical workflows are approved; there are no
unexplained visual, keyboard, or print regressions; comparison artifacts and
review notes are retained.

## 11. M6 - PyInstaller, frozen artifact, and CI cutover

**Goal:** Produce a clean Windows artifact containing the intended PySide6/Qt
runtime and only required plugins.

- [ ] Determine the actual PySide6 destination and source paths emitted by the
      installed PyInstaller hooks; do not guess by replacing
      `PyQt6/Qt6/` with a hard-coded string.
- [ ] Update `SilverEstimate.spec` filtering for PySide6's platform, image format,
      SVG icon, and print-support plugin layout.
- [ ] Retain required SQLCipher dynamic libraries, provenance, license, notices,
      keyring backends, and Passlib hidden import until Phase 5.
- [ ] Verify that excluded Qt modules remain absent and required Qt DLLs/plugins
      remain present.
- [ ] Add or update focused tests for spec filtering where practical.
- [ ] Update build scripts and workflow metadata that name PyQt6 or assume its
      directory layout.
- [ ] `uv run nox -s build_clean` passes on a clean Windows environment.
- [ ] `uv run nox -s artifact_smoke` passes.
- [ ] The release startup-budget check passes for at least five samples.
- [ ] Inspect the built artifact/SBOM for PyQt6, duplicate Qt runtimes, missing
      Shiboken6, and unintended plugins.
- [ ] Verify login, SQLCipher open, main window, icons/SVG, keyring, preview,
      PDF, and print-support initialization from the frozen artifact.

Canonical release-style commands:

```powershell
uv run python -m PyInstaller --clean --noconfirm SilverEstimate.spec
uv run python scripts/check_startup_budgets.py --artifact dist\SilverEstimate.exe --samples 5 --p95-budget-ms 3000
```

**M6 exit criteria:** PR, main, and release Windows workflows build and smoke a
PySide6-only artifact; required plugins and notices are present; no PyQt6 or
second Qt runtime is packaged.

## 12. M7 - Documentation, licensing, and release metadata

**Goal:** Make every maintained statement describe the shipped PySide6 stack.

- [ ] Update README description, badges, architecture, testing, build, and change
      history references.
- [ ] Update `DOCS/README.md`, architecture, deployment, security, API, and other
      maintained pages that claim PyQt6 behavior.
- [ ] Update project keywords/classifiers and the PR template's test configuration.
- [ ] Replace PyQt6 notices with accurate PySide6, Shiboken6, and Qt licensing
      and source information in `THIRD_PARTY_NOTICES.md`.
- [ ] Confirm the release SBOM identifies the selected Python and native Qt
      components.
- [ ] Update `CHANGELOG.md` with the binding migration, test evidence, known
      differences, and rollback considerations.
- [ ] Update the modernization roadmap implementation record and Phase 4 status
      only after M0-M6 are complete.
- [ ] Verify documentation links and commands.

**M7 exit criteria:** Source metadata, docs, notices, workflows, and release
artifacts consistently identify PySide6; there are no stale user-facing PyQt6
claims except historical release notes clearly labeled as such.

## 13. M8 - Final PyQt removal and workstream closure

**Goal:** Prove that PySide6 is the sole supported binding and hand off a stable
base for Phase 5 and later architecture work.

- [ ] Search the repository for `PyQt6`, `PyQt6-Qt6`, `PyQt6-stubs`,
      `pyqtSignal`, `pyqtSlot`, `pyqtProperty`, and PyQt SIP usage.
- [ ] Classify any historical-document matches; no live code, test, config,
      workflow, packaging, or current documentation match may remain.
- [ ] Confirm installed and locked distributions contain no PyQt package.
- [ ] Run the complete final gate below on Windows.
- [ ] Confirm the migration did not add a binding compatibility layer.
- [ ] Confirm SQLCipher tests/runtime identity and all data workflows still pass.
- [ ] Run `graphify update .` and query the graph for PyQt6/PySide6 live paths.
- [ ] Mark roadmap Phase 4 complete and set the roadmap's next workstream to
      Phase 5 Passlib removal.
- [ ] Add a final progress-log entry with the release/commit, evidence links,
      known limitations, and rollback point.

Final gate:

```powershell
uv sync --frozen --extra dev
uv run nox -s ruff
uv run nox -s mypy
uv run nox -s bandit
uv run nox -s tests_full
uv run nox -s smoke_ui
uv run nox -s build_clean
uv run nox -s artifact_smoke
uv run python scripts/verify_sqlcipher_runtime.py --provenance vendor/sqlcipher/PROVENANCE.json
rg -n "PyQt6|PyQt6-Qt6|PyQt6-stubs|pyqtSignal|pyqtSlot|pyqtProperty|sip\.isdeleted" silverestimate tests main.py noxfile.py pyproject.toml uv.lock SilverEstimate.spec scripts .github readme.md DOCS THIRD_PARTY_NOTICES.md
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

## 16. Decision log

Record decisions that alter sequencing, constraints, selected versions, or
accepted behavior. Append entries; do not rewrite prior decisions without a new
superseding entry.

| Date | Decision | Reason | Consequences | Approved by |
|---|---|---|---|---|
| 2026-07-22 | Execute PySide6 migration before Phase 5 and facade decomposition. | SQLCipher phases are complete and the roadmap orders the binding migration next. | Baseline capture is the immediate task; Passlib and architecture changes remain out of scope. | Project plan |
| 2026-07-22 | Do not use a permanent dual-binding compatibility module. | It would preserve dependency and typing complexity after cutover. | Conversion must be direct and complete; rollback occurs through version control. | Modernization roadmap |

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
