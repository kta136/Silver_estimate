# Deployment and Release Guide

## Supported platform

Packaged releases support Windows 10/11 only. PyInstaller output is verified on `windows-latest`. macOS and Linux are untested development environments and are not release targets.

## Reproducible environment

Python 3.14 and the committed `uv.lock` are required:

```powershell
uv sync --frozen --extra dev
```

Do not install an ad-hoc release dependency set. PR, main, and tag workflows all run the same frozen development sync so tests, security tools, SBOM generation, and PyInstaller use the locked graph.

## Local validation

```powershell
uv run nox -s ruff
uv run nox -s mypy
uv run nox -s bandit
uv run nox -s tests_full
$env:QT_QPA_PLATFORM = "offscreen"
uv run nox -s smoke_ui
uv run nox -s build_clean
uv run nox -s artifact_smoke
```

The clean build produces:

- `dist/SilverEstimate.exe`;
- `dist/SilverEstimate-v<APP_VERSION>.exe`;
- `dist/SilverEstimate-v<APP_VERSION>-win64.zip`.

`--artifact-smoke` imports the packaged application and version metadata, then exits without authentication or customer data.

## Pull requests

PR validation runs:

- Ruff formatting/lint and mypy;
- blocking Bandit medium/high findings;
- the complete non-smoke test suite on Windows;
- 75% global coverage and 90% changed-line coverage;
- deterministic performance gates;
- offscreen Qt full-startup smoke;
- clean PyInstaller build and frozen-artifact startup.

## Main branch

Main repeats frozen quality/security gates and complete Windows validation. Coverage, performance telemetry, smoke screenshots, executable, and zip are uploaded as workflow artifacts.

## Release tags

`.github/workflows/release-windows.yml` runs for `v*` tags. Before any publish step it:

1. verifies the tag equals `v<APP_VERSION>`;
2. runs Ruff, mypy, blocking Bandit, complete tests, coverage, performance, and offscreen smoke;
3. builds with the canonical `SilverEstimate.spec`;
4. optionally signs the executable when certificate secrets exist;
5. starts the frozen executable in artifact-smoke mode;
6. creates the Windows zip, CycloneDX JSON SBOM, and SHA-256 checksums;
7. publishes only after every required gate succeeds.

The `main` source version may be newer than the latest published package. The
[GitHub Releases page](https://github.com/kta136/Silver_estimate/releases/latest)
is authoritative for supported downloads; a release is not current until its
matching tag workflow completes successfully.

Signing is intentionally non-blocking until `WINDOWS_SIGNING_CERTIFICATE_BASE64` and `WINDOWS_SIGNING_CERTIFICATE_PASSWORD` are configured. Once production credentials are available, remove `continue-on-error` after validating the timestamp and certificate chain.

## Manual release smoke

Before promoting a stable release, verify the committed SQLCipher 4.17.x wheel against its recorded SHA-256 and native inventory, probe the installed and frozen runtimes, migrate a production `SILVDB01` copy, reject plaintext and unsupported metadata, exercise encrypted backup/restore and copy-switch password rotation with injected interruption, and verify estimate/paging/rate/print workflows. Rebuilding the native wheel is required only when deliberately replacing the bundled dependency.

Normal runtime database files, WAL, and journals are SQLCipher encrypted. The marked one-time legacy migration workspace is the only plaintext database exception and is cleaned on all exits and next startup. Production devices should still use Windows device encryption/BitLocker and a trusted account because SQLCipher does not protect live process memory, hibernation, or a compromised user.

### Installed-system SILVDB01 acceptance

Before retiring the compatibility importer on the single supported installation:

1. Back up the complete installed application/data directory.
2. Run the migration from the replacement EXE in that same directory.
3. Confirm `estimation.db`, `estimation.kdf.json`, and
   `estimation.silvdb01.backup` exist and the live file is not a `SILVDB01`
   envelope.
4. Close the application, reopen it, authenticate, and verify representative
   estimate, item, and silver-bar records.
5. Create and validate an encrypted `.sedbbackup` archive.

Keep `estimation.silvdb01.backup` until an explicit retention decision is made.
It is a retained recovery artifact, not the live database.
