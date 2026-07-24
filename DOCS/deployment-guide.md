# Deployment and Release Guide

## Supported platform

Packaged releases support Windows 10/11 x64 only. The executable is produced
with Qt's `pyside6-deploy` wrapper and Nuitka, then verified on
`windows-latest`. macOS and Linux are untested development environments and
are not release targets.

## Reproducible environment

Python 3.14 and the committed `uv.lock` are required:

```powershell
uv sync --frozen --extra dev
```

Do not install an ad-hoc release dependency set. PR, main, and tag workflows
all run the same frozen development sync so tests, security tools, SBOM
generation, `pyside6-deploy`, Nuitka 4.1.3, and zstandard 0.25.0 use the locked
graph.

## Local validation

```powershell
uv run nox -s ruff
uv run nox -s mypy
uv run nox -s bandit
uv run nox -s tests_full
$env:QT_QPA_PLATFORM = "offscreen"
uv run nox -s smoke_ui
uv run nox -s build_standalone
uv run nox -s standalone_artifact_smoke
uv run nox -s build_clean
uv run nox -s artifact_smoke
uv run python scripts/check_startup_budgets.py --artifact dist\SilverEstimate-v3.10.exe --samples 5 --p95-budget-ms 3000
```

The standalone build is a diagnostic artifact at
`dist/SilverEstimate.dist/main.exe`. Its smoke gate inspects the unpacked
PySide6/Shiboken6, SQLCipher, Qt plugin, icon, license, notice, and provenance
inventory before the one-file build is accepted.

The clean one-file build produces:

- `dist/SilverEstimate.exe`;
- `dist/SilverEstimate-v<APP_VERSION>.exe`;
- `dist/SilverEstimate-v<APP_VERSION>-win64.zip`.

For a local release build, run `scripts\build_windows_local.cmd`. The launcher
quotes the PowerShell script path so repositories stored in workspace paths
containing spaces are supported. The PowerShell script
requires the locked `uv` environment and Python 3.14, removes the stale
unversioned artifact before compilation, builds the one-file loader with MSVC,
and runs the frozen artifact under a system-only `PATH`. It also inspects the
outer PE import table and rejects the build if it requires anything beyond
`KERNEL32.dll` and `SHELL32.dll`. This prevents accidental dependencies on a
developer machine's Universal CRT installation. The script rejects copy
mismatches and prints the deliverable's SHA-256 hash.

The frozen application writes an early bootstrap trace to
`logs/SilverEstimate-startup.log` beside the executable. If that directory is
not writable, diagnostics and normal logs fall back to
`%LOCALAPPDATA%\SilverEstimate\logs`. Early import failures use a native Windows
error dialog, so they remain visible even when Qt itself cannot load. The
one-file executable attaches to an existing console without creating one for
normal Explorer launches; run it from Command Prompt to capture loader output.

The application executable can be moved, but an initialized encrypted database
is bound to the Windows PC that created or migrated it. Place the executable in
a user-writable directory. Do not run it directly from inside the zip or from a
protected directory such as `Program Files` unless its data directory has
explicitly been made writable.

The canonical configuration is `pysidedeploy.spec`. It selects the Windows
platform, icon/SVG/image, widget, and print-support components; embeds required
assets and notices; forces the dynamic keyring and SQLCipher imports; includes
the direct `argon2-cffi` password service; rejects Passlib from the compilation
report; and excludes unused Qt/QML/media plugins. The committed compiler
selection lets Nuitka use its supported Windows toolchain with the same command
locally and on hosted runners.

`--artifact-smoke` initializes the Windows Qt platform, icon and SVG support,
Windows Credential Manager backend, PDF renderer, and encrypted SQLCipher
runtime, then exits without authentication or customer data. It also verifies
that writable data resolves beside the release executable rather than inside
the one-file extraction directory.

## Pull requests

PR validation runs:

- Ruff formatting/lint and mypy;
- blocking Bandit medium/high findings;
- the complete non-smoke test suite on Windows;
- 75% global coverage and 90% changed-line coverage;
- deterministic performance gates;
- offscreen Qt full-startup smoke;
- curated standalone inventory and artifact startup;
- clean `pyside6-deploy` one-file build and artifact startup.

## Main branch

Main repeats frozen quality/security gates and complete Windows validation. Coverage, performance telemetry, smoke screenshots, executable, and zip are uploaded as workflow artifacts.

## Release tags

`.github/workflows/release-windows.yml` runs for `v*` tags. Before any publish step it:

1. verifies the tag equals `v<APP_VERSION>`;
2. runs Ruff, mypy, blocking Bandit, complete tests, coverage, performance, and offscreen smoke;
3. builds with the canonical `pysidedeploy.spec` through `nox -s build_clean`;
4. optionally signs the executable when certificate secrets exist;
5. starts the frozen executable in artifact-smoke mode;
6. creates the Windows zip, CycloneDX JSON SBOM, and SHA-256 checksums;
7. publishes only after every required gate succeeds.

The release SBOM starts from the frozen build environment and is then augmented
and validated by `scripts/augment_release_sbom.py`. Its root component preserves
the application version, and explicit CPython and native Qt components record
the interpreter and framework embedded in the Windows executable. PySide6,
PySide6 Addons/Essentials, and Shiboken6 wheel versions must match that native
Qt version or the release stops.

The `main` source version may be newer than the latest published package. The
[GitHub Releases page](https://github.com/kta136/Silver_estimate/releases/latest)
is authoritative for supported downloads; a release is not current until its
matching tag workflow completes successfully.

Signing is intentionally non-blocking until `WINDOWS_SIGNING_CERTIFICATE_BASE64` and `WINDOWS_SIGNING_CERTIFICATE_PASSWORD` are configured. Once production credentials are available, remove `continue-on-error` after validating the timestamp and certificate chain.

Nuitka 4.1.3 is the selected stable release for the current toolchain and
adds Python 3.14 support, but still labels Python 3.14 experimental during the
build. The executable must not be promoted until the hosted Windows build,
artifact smoke, complete tests, and startup budget all pass with the locked
Python 3.14 patch release.

The selected `pyside6-deploy` artifact is evaluated against current PySide6
release requirements. It is not compared with the retired M0 PyQt6 executable.

## Manual release smoke

Before promoting a stable release, verify the committed SQLCipher 4.17.x wheel against its recorded SHA-256 and native inventory, probe the installed and frozen runtimes, reject plaintext and unsupported schemas, exercise local two-file-to-machine-bound migration, prove that a copied DB and backup fail under a foreign device secret, exercise encrypted backup/restore and copy-switch password rotation with injected interruption, and verify estimate/paging/rate/print workflows. Rebuilding the native wheel is required only when deliberately replacing the bundled dependency.

Normal runtime database files, WAL, and journals are SQLCipher encrypted. Production devices should still use Windows device encryption/BitLocker and a trusted account because SQLCipher does not protect live process memory, hibernation, or a compromised user.

The retired `SILVDB01` importer is not part of release validation. Any separately
retained pre-SQLCipher backup requires an older release or an external recovery
procedure and is never selected as the live database.
