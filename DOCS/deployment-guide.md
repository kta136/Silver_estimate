# Deployment and Release Guide

## Supported platform

Packaged releases support Windows 10/11 x64 only. The executable is produced
locally with Qt's `pyside6-deploy` wrapper and Nuitka. macOS and Linux are
untested development environments and are not release targets.

## Reproducible environment

Python 3.14 and the committed `uv.lock` are required:

```powershell
uv sync --frozen --extra dev
```

Do not install an ad-hoc release dependency set. CI and the local build both
start from the locked development sync, so tests, lint tools, `pyside6-deploy`,
Nuitka 4.2.1, and zstandard 0.25.0 use the locked graph.

## Local validation

```powershell
uv run nox
$env:QT_QPA_PLATFORM = "offscreen"
uv run nox -s smoke_ui
uv run nox -s audit
```

`uv run nox` runs Ruff (lint, format check and security rules), mypy and the
complete non-smoke test suite. `smoke_ui` starts the whole application
offscreen and saves screenshots under `artifacts/smoke-ui/`. `audit` lists
known advisories for the locked runtime packages with `pip-audit`; it reports
and never blocks.

For a local release build, run `scripts\build_windows_local.cmd`. The launcher
quotes the PowerShell script path so repositories stored in workspace paths
containing spaces are supported. The PowerShell script
reads the exact Python patch version from `.python-version` (currently 3.14.7),
uses `uv` to find or download that interpreter, verifies the synchronized
environment matches it, and removes the stale
unversioned artifact before compilation, and builds the one-file loader with
MSVC. It inspects the outer PE import table and rejects the build if it
requires anything beyond
`KERNEL32.dll` and `SHELL32.dll`. This prevents accidental dependencies on a
developer machine's Universal CRT installation. The script rejects copy
mismatches and prints the deliverable's SHA-256 hash.

For faster local iteration, run:

```powershell
scripts\build_windows_local.cmd -Fast
```

This builds `dist/SilverEstimate-v<APP_VERSION>-fast.exe` with `--lto=no`,
skipping whole-program link-time optimization while retaining normal C
optimization, one-file compression, locked dependency synchronization, and
the native-dependency validation. An explicit
`-ArtifactSuffix my-test` overrides the default `fast` suffix. Use the default
command without `-Fast` for release builds; the fast profile may produce a
larger executable and different runtime performance. The committed deployment
specification is unchanged.

Both profiles print dependency, compilation/packaging, validation, and total
durations. They write a success/failure report to
`artifacts/local-build/build-timings[-suffix].json`, including timings for a
failed stage. A failed validation does not replace an existing versioned
executable. Compare repeated builds of the same profile after its first build:
the compiler flags affect cache keys, so the first fast build needs to populate
its own object cache.

Measured on the development workstation on 2026-09-08 with the same application
source and locked toolchain: standard build with a populated cache, 173.89 s;
first fast build, 173.85 s; repeated fast build, 104.15 s (40% less elapsed time).
The standard and repeated fast compilation reports each recorded 243 cache
hits; the first fast report recorded 243 misses. These are individual local
measurements, not a CI performance guarantee. All three executables passed the
frozen runtime and native dependency checks.

Nuitka already uses all available CPUs for C compilation and automatically
uses its MSVC `clcache`; increasing a fixed job count or clearing those caches
is not a build-speed improvement. Qt's pinned deploy wrapper cleans its
`deployment` directory at the start of each run, even with
`--keep-deployment-files`, so preserving that directory does not provide
incremental builds. See [Nuitka's compilation cache documentation](https://nuitka.net/user-documentation/tips.html).

The frozen application writes an early bootstrap trace to
`logs/SilverEstimate-startup.log` beside the executable. If that directory is
not writable, diagnostics and normal logs fall back to
`%LOCALAPPDATA%\SilverEstimate\logs`. Early import failures use a native Windows
error dialog, so they remain visible even when Qt itself cannot load. The
one-file executable attaches to an existing console without creating one for
normal Explorer launches; run it from Command Prompt to capture loader output.

The application executable can be moved, but an initialized encrypted database
is bound to the Windows PC that created it. Place the executable in
a user-writable directory. Do not run it directly from inside the zip or from a
protected directory such as `Program Files` unless its data directory has
explicitly been made writable.

The canonical configuration is `pysidedeploy.spec`. It selects the Windows
platform, icon/SVG/image, widget, print-support, network, and Windows TLS
components; embeds required assets and notices; includes the `apsw` database
engine and the direct `argon2-cffi` password service; and excludes
unused Qt/QML/media plugins. The committed compiler selection lets Nuitka use
its supported Windows toolchain.

## Continuous integration

`.github/workflows/validation.yml` runs on every push to `main` and on pull
requests. On `windows-latest` it syncs the locked environment and runs Ruff,
mypy and the complete non-smoke test suite. A last `pip-audit` step lists advisories
for the locked runtime packages without failing the run.

CI does not build, sign or publish the executable. Builds are made locally
with `scripts\build_windows_local.cmd`. Start the built executable once and
sign in before copying it to the shop PC; the build no longer does this.

Nuitka 4.2.1 is pinned for the current toolchain; the 4.2 series officially
supports Python 3.14. The executable must not be promoted until the local
build and the complete tests pass with the locked Python 3.14 patch release.

The selected `pyside6-deploy` artifact is evaluated against current PySide6
release requirements. It is not compared with the retired M0 PyQt6 executable.

## Manual release smoke

Before promoting a stable release, sign in to a copy of a live database with the frozen executable, reject plaintext and unsupported schemas, exercise local two-file-to-machine-bound migration, prove that a copied DB and backup fail under a foreign device secret, exercise encrypted backup/restore and copy-switch password rotation with injected interruption, and verify estimate/paging/rate/print workflows.

Normal runtime database files, WAL, and journals are SQLCipher encrypted. Production devices should still use Windows device encryption/BitLocker and a trusted account because SQLCipher does not protect live process memory, hibernation, or a compromised user.

The retired `SILVDB01` importer is not part of release validation. Any separately
retained pre-SQLCipher backup requires an older release or an external recovery
procedure and is never selected as the live database.
