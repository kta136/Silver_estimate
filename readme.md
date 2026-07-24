# Silver Estimation App - v3.10

A Windows desktop application built with PySide6 and a local SQLCipher database
for managing silver sales estimates, item-wise entries, silver-bar inventory,
returns, and print-ready outputs.

[![Python](https://img.shields.io/badge/Python-3.14+-blue.svg)](https://www.python.org/)
[![PySide6](https://img.shields.io/badge/PySide6-6.11-green.svg)](https://doc.qt.io/qtforpython-6/)
[![License: GPL v3](https://img.shields.io/badge/License-GPL_v3-blue.svg)](LICENSE)
[![Source Version](https://img.shields.io/badge/source-v3.10-orange.svg)](CHANGELOG.md#310---2026-07-23)
[![Latest Release](https://img.shields.io/github/v/release/kta136/Silver_estimate?label=stable%20release)](https://github.com/kta136/Silver_estimate/releases/latest)
[![PR Validation](https://github.com/kta136/Silver_estimate/actions/workflows/pr-validation.yml/badge.svg)](https://github.com/kta136/Silver_estimate/actions/workflows/pr-validation.yml)
[![Main Validation](https://github.com/kta136/Silver_estimate/actions/workflows/main-validation.yml/badge.svg)](https://github.com/kta136/Silver_estimate/actions/workflows/main-validation.yml)
[![Release Windows](https://github.com/kta136/Silver_estimate/actions/workflows/release-windows.yml/badge.svg)](https://github.com/kta136/Silver_estimate/actions/workflows/release-windows.yml)
[![Formatter: Ruff](https://img.shields.io/badge/formatter-ruff-%23D7FF64)](https://docs.astral.sh/ruff/)
[![Lint: Ruff](https://img.shields.io/badge/lint-ruff-%23D7FF64)](https://docs.astral.sh/ruff/)
[![Type checking: mypy](https://img.shields.io/badge/type%20checking-mypy-blue.svg)](https://mypy-lang.org/)
[![Security: bandit](https://img.shields.io/badge/security-bandit-yellow.svg)](https://github.com/PyCQA/bandit)
[![Pre-commit](https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=pre-commit)](https://github.com/pre-commit/pre-commit)
[![Platform](https://img.shields.io/badge/packaged%20platform-Windows-lightgrey.svg)](https://github.com/kta136/Silver_estimate)

## Quick Links

- [Download latest stable release](https://github.com/kta136/Silver_estimate/releases/latest)
- [Documentation index](DOCS/README.md)
- [Changelog](CHANGELOG.md)
- [v3.10 changelog](CHANGELOG.md#310---2026-07-23)
- [Deployment guide](DOCS/deployment-guide.md)

> The source tree can be ahead of the latest packaged release. Use the release
> page for supported Windows downloads and the source-version badge for the
> current state of `main`.

## Table of Contents
- [Quick Links](#quick-links)
- [Overview](#overview)
- [Architecture](#architecture)
- [Features](#features)
- [Installation](#installation)
- [Usage](#usage)
- [Security](#security)
- [Configuration](#configuration)
- [Development](#development)
- [Testing](#testing)
- [Deployment](#deployment)
- [Release Cadence & Support](#release-cadence--support)
- [Contributing](#contributing)
- [Support](#support)
- [License](#license)
- [Version History](#version-history-highlights)

## Overview

The app helps silver shops to:
- Generate itemized estimates with accurate calculations
- Track gross, net, and fine weights; wages (PC/WT)
- Manage silver bar inventory and returns
- Print formatted estimate slips with Indian rupee formatting
- Follow live Agra Mohar rates through anonymous HTTPS/SSE updates with an offline snapshot
- Keep the desktop UI in a strict light theme across Windows dark mode, dialogs, popups, and print preview controls
- Store the live database, WAL, and journals locally with SQLCipher encryption
- Create encrypted full-database backups and explicit plaintext item-catalog exports

## Architecture

- **UI layer**: PySide6 widgets in `silverestimate/ui/` handle estimate entry, item master, silver bar management, history, and supporting dialogs.
- **Theme layer**: `silverestimate/ui/application_theme.py`, `theme_tokens.py`, `shared_screen_theme.py`, and `themed_controls.py` keep the app on a strict light theme and preserve visible combo/spinbox arrows under Qt stylesheets.
- **Presenter**: `silverestimate/presenter/estimate_entry_presenter.py` coordinates estimate workflows, keeping UI widgets thin and testable.
- **Controllers**: Startup, navigation, and live-rate controllers bootstrap the app, wire menus/toolbars, and manage background refresh cadence.
- **Services**: `MainCommands`, `SettingsService`, `LiveRateService`, and `AuthService` encapsulate reusable logic; authentication relies on the secure credential store.
- **Persistence**: `DatabaseManager`, `SqlCipherConnectionBroker`, and role-specific repositories manage direct encrypted connections, current schema-v8 creation and validation, keyset pages, encrypted WAL/journals, maintenance draining, and staged recovery.
- **Security & infrastructure**: OS keyring-backed credential storage (`silverestimate/security/credential_store.py`), Qt6 startup bootstrap (`silverestimate/infrastructure/qt_bootstrap.py`), structured logging with optional cleanup scheduler, and QSettings helpers maintain app state safely.

### DDA Agra Mohar Live Rate

- The startup/recovery snapshot is anonymous HTTPS: `https://ddajewels.com/api/v1/rates/current`.
- Instant updates use `https://ddajewels.com/sse/rates`; disconnected streams fall back to a 10-second HTTPS poll.
- Selection is by stable item ID `cmomws5tw000004i5k5t6yrnw`, never by a display name.
- The displayed customer rate is `finalRate` with unit `PER_KG`. `baseRate` is intentionally ignored and no previous-rate percentage is derived.
- No API key or authorization header is required while the endpoint remains public. A verified snapshot is retained for offline/stale display.

### Key Design Principles
- Separation of concerns: UI, presenter, services, and persistence remain loosely coupled.
- Security-first: Encrypted database, keyring-backed credentials, safe defaults for settings.
- Modular: Focused modules for UI, calculations, repositories, and infrastructure.
- Responsive: Signal/slot updates, debounced tasks, async flush handling.
- Integrity: Strong validation, transaction boundaries, and repository abstractions.

See also: `DOCS/project-architecture.md`.

## Features

### Core
- Estimate management: create/edit/track with inline validations
- Item catalog: maintain items and rates
- Silver bar tracking: inventory and history
- Return processing and last balance handling

### Security
- Encrypted database: machine-bound SQLCipher 4.17.x with a raw key derived from the password, the in-file salt, and a 256-bit device secret held in local-machine Windows Credential Manager
- Machine-bound `.sedbbackup` full-database backup and restart-activated restore; `.seitems.json` catalog exports remain plaintext by request
- Password hashing: Argon2 with hashes stored in the OS keyring (Python `keyring`)
- Secure settings store: non-sensitive preferences via QSettings

### Printing & Reporting
- Print-ready estimate layouts with INR formatting
- Compact print preview with layout/orientation controls and a More menu for printer, page-view, and navigation actions
- Shared Qt6 page setup helpers for page size, orientation, margins, printer validation, and safer PDF export

### Desktop Experience
- Consistent Indian rupee and `DD/MM/YYYY` formatting across estimates and silver-bar history
- Clear empty-table messages, saved/unsaved settings feedback, and responsive row limits for history screens
- Return and silver-bar summary cards stay hidden until those categories contain values

### Catalog Backup
- Export item catalogs to a native `.seitems.json` backup file
- Import the same backup format without legacy parsing rules
- Update existing item codes and add missing ones safely

## Installation

1. Install Python 3.14+
2. Clone the repository
3. Create a virtual environment
4. Install dependencies

Recommended for development with `uv`:

```bash
uv sync --frozen --extra dev
```

This repository now includes a committed `uv.lock` file so local development and CI can converge on the same resolved dependency set.
Before running `uv` or any repo command, ensure `python` resolves to Python 3.14 or newer in your shell. This repository includes `.python-version` for `pyenv` users.

Fallback with the standard library `venv` + `pip`:

```powershell
# Windows (PowerShell)
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

Packaged releases support Windows 10/11. macOS and Linux may be useful for untested development work, but they are not release or support targets.

## Usage

Run the application:

```bash
python main.py
```

First run notes:
- You will be prompted to create a password.
- The password encrypts the local database file at `<EXE folder>/database/estimation.db` (or the repository root during source runs).
- Keep this password and Windows installation safe: encrypted data cannot be recovered without both the password and this PC's device-binding secret.
- Hashed credentials are stored in the system keyring. The random device-binding secret is forced into local-machine Windows Credential Manager storage so it cannot roam to another PC.

## Security

- Encryption: bundled and hash-verified SQLCipher 4.17.x for CPython 3.14 x64, machine-bound Argon2id raw keys, and encrypted database/WAL/journal pages
- Passwords: direct Argon2id hashing with `argon2-cffi`; current PHC hashes are persisted in the OS keyring (Python `keyring`)
- Files: one permanent encrypted DB at `<EXE folder>/database/estimation.db` (ignored in Git); WAL/SHM and recovery journals can exist temporarily
- Device binding: copying the DB or a new `.sedbbackup` to another PC does not make it openable, even with the correct password
- Logs: Written to `logs/` (ignored); avoid logging sensitive data

The retired `SILVDB01` importer is no longer included. This release accepts only
the current machine-bound schema-v8 SQLCipher database. An authenticated local
two-file database is migrated once to the single-file format; a database copied
without this PC's device secret fails closed. Plaintext, unversioned, and historical
schema databases are rejected. Any separately retained `estimation.silvdb01.backup`
is not opened, rewritten, or deleted automatically.

## Configuration

- Settings: Qt QSettings (`SETTINGS_ORG`, `SETTINGS_APP`) in `silverestimate/infrastructure/app_constants.py`
- Paths: DB path via `DB_PATH` in `silverestimate/infrastructure/app_constants.py`
- Printing: Fonts and sizes configurable via Settings dialog
- UI: The app forces Qt's Fusion-style light palette/QSS during startup and uses non-native dialogs where needed so Windows dark mode does not leak into file dialogs
- Environment: only `SILVER_APP_DEBUG`, `SILVER_APP_LOG_DIR`, and `SILVER_SHOW_CONSOLE` are runtime controls; see `.env.example`.

## Development

Key areas of the codebase:

- `main.py` – thin application entry point.
- `silverestimate/infrastructure/application.py` – `ApplicationBuilder` and QApplication lifecycle.
- `silverestimate/infrastructure/qt_bootstrap.py` – Qt6 startup options for Windows dark-mode suppression and high-DPI rounding.
- `silverestimate/controllers/` – startup, navigation, and live-rate controllers.
- `silverestimate/presenter/estimate_entry_presenter.py` – presenter coordinating save/load logic and calculations.
- `silverestimate/ui/estimate_entry.py` – main estimate widget combining UI helpers and presenter.
- `silverestimate/ui/estimate_entry_logic/column_specs.py` – shared estimate-table column registry for headers, editability, precision, widths, and navigation order.
- `silverestimate/ui/application_theme.py`, `theme_tokens.py`, `shared_screen_theme.py`, and `themed_controls.py` – strict light theme and reusable desktop controls.
- `silverestimate/ui/print_page_settings.py` – Qt6 print/page helper functions used by settings, preview, quick print, and PDF export paths.
- `silverestimate/services/` – auth, settings, live-rate, main commands, and repository adapters.
- `silverestimate/persistence/` – `DatabaseManager`, current schema definition, SQLCipher broker, and repositories.
- `silverestimate/security/` – Argon2id password policy and keyring-backed credential storage.
- `silverestimate/infrastructure/` – logging, settings helpers, and app constants.
- `DOCS/` – indexed deep-dive documentation for architecture, deployment, security, data relationships, APIs, and business workflows.

Recommended development commands with `uv`:

```bash
uv sync --frozen --extra dev
uv run python main.py
uv run nox -s pr
uv run nox -s ci
uv run nox -s advisory
uv run pre-commit run --all-files
```

## Testing

- Tests live under `tests/` and use pytest with the `pytest-qt` PySide6 backend.
- Local smoke command: `pytest -v tests/test_security.py tests/services/test_auth_service.py`
- Full startup UI smoke with screenshots: `uv run nox -s smoke_ui`
  - Creates an isolated encrypted test database with fixed smoke passwords.
  - Captures opt-in Qt screenshots under `artifacts/smoke-ui/`.
- Full local run: `pytest -v`
- Fast local gate: `uv run --extra dev nox -s tests_fast`
- Theme/control regression checks: `uv run --extra dev pytest tests/unit/test_application_theme.py tests/unit/test_themed_controls.py tests/ui/test_settings_dialog.py -q`
- Shared validation entrypoints:
  - `uv run nox -s pr` for the required PR gate set
  - `uv run nox -s ci` for the required main-branch gate set
  - `uv run nox -s advisory` for advisory `bandit` and `safety`
- CI requires 75% global coverage and 90% changed-line coverage on pull requests.
- CI builds the deterministic scale dataset and requires all seven p95 performance metrics with 20 hot-path or five encrypted-flush samples.
- To iterate quickly on the application builder branch, run `pytest tests/unit/test_application_builder.py`.
- Ruff enforces linting and import ordering in CI.
- Ruff formatting is enforced locally via pre-commit and checked in CI.
- Run formatting and hooks before pushing: `pre-commit run --all-files`

## Deployment

### Build Locally (Windows)
- Prereqs: Python 3.14+, PowerShell
- Fast iteration: `uv run nox -s build`
- Inspectable standalone build: `uv run nox -s build_standalone standalone_artifact_smoke`
- Clean one-file rebuild: `uv run nox -s build_clean artifact_smoke`
- Output: `dist/SilverEstimate.exe`, `dist/SilverEstimate-v3.10.exe`, and `dist/SilverEstimate-v3.10-win64.zip` on Windows
- Release/CI builds use Qt's `pyside6-deploy`, the committed `pysidedeploy.spec`, and locked Nuitka 4.1.3
- Packaged releases are Windows-only; macOS/Linux are untested development environments.

### GitHub Release (Windows CI)
- Update version in `silverestimate/infrastructure/app_constants.py` (`APP_VERSION`)
- Create and push a tag (workflow triggers on tags):
  - `git commit -am "chore: bump version to vX.YY"`
  - `git tag vX.YY`
  - `git push origin main --tags`
- CI builds the exe and attaches `SilverEstimate-vX.YY-win64.zip` to the GitHub Release

For more details, see `DOCS/deployment-guide.md`.

## Release Cadence & Support

- Stable releases are published from version tags (`v*`) and retained as the primary supported download path.
- The `latest-ci` prerelease is for validation/testing only and may change without backward-compatibility guarantees.
- Use the latest stable release unless you are explicitly validating a CI candidate build.

## Contributing

1. Fork the repository
2. Set up development environment (see Installation)
3. Create a feature branch (`git checkout -b feature/xyz`)
4. Commit your changes (`git commit -m "feat: ..."`)
5. Push (`git push origin feature/xyz`)
6. Open a pull request

**Development resources:**
- Code style: PEP 8 with type hints
- Testing: Add tests for new features
- Documentation: Update docs in `DOCS/`

## Support

For support and troubleshooting:
- GitHub Issues: report bugs and request features
- Documentation quick links:
  - [Documentation index](DOCS/README.md)
  - [Project architecture](DOCS/project-architecture.md)
  - [Security architecture](DOCS/security-architecture.md)
  - [Deployment guide](DOCS/deployment-guide.md)

## License

This project is free software licensed under the
[GNU General Public License v3.0 only](LICENSE) (`GPL-3.0-only`).

Copyright (C) 2023-2026 Silver Estimation App

---

## Version History (highlights)

### v3.10 (2026-07-23)
- Introduces a simplified silver-and-rupee application icon designed for clear Windows shell rendering
- Uses the new icon consistently in runtime windows, frozen builds, and deployment validation
- Removes the superseded icon artwork and temporary versioned icon filenames

### v3.09 (2026-07-23)
- Removes the retired SILVDB01, AES-GCM envelope, and plaintext migration paths
- Creates fresh databases directly at schema v8 and rejects non-current schemas
- Removes password rehash migration, compatibility wrappers, aliases, and completed migration tooling

### v3.08 (2026-07-23)
- Migrates the complete desktop runtime from PyQt6 to PySide6 6.11
- Replaces PyInstaller with `pyside6-deploy` and a locked Nuitka toolchain
- Removes Passlib in favor of direct `argon2-cffi` password hashing with compatible rehash-on-login upgrades
- Completes the direct SQLCipher live-storage cutover and frozen Windows validation

### v3.07 (2026-07-22)
- Adds optional free-text Tunch values throughout item management, backups, and estimate printing
- Improves Modern estimate group spacing and PCS/Fine table separation
- Hides final Silver Cost and Total metrics when no silver rate is set

### v3.06 (2026-07-19)
- Replaces estimate HTML generation with typed direct painters for Classic and Modern formats
- Adds full-width aligned Modern tables, compact headings, persistent format selection, and print-font controls in preview
- Preserves the former Modern/New fixed-width design as Classic

### v3.05 (2026-07-16)
- Corrects silver-bar list and inventory printing so database values and totals render accurately

### v3.04 (2026-07-16)
- Retires the completed legacy database-location and QSettings-organization migration paths
- Accepts SQLCipher data with exact KDF metadata, migrates authenticated `SILVDB01` once, and rejects plaintext SQLite headers
- Removes PBKDF2, raw encrypted-payload support, and settings-owned database salts

### v3.03 (2026-07-16)
- Shows an explicit progress state while the estimate workspace is being prepared
- Makes the first code cell editable on the first visible event-loop turn
- Defers secondary menu and live-rate setup so keyboard input gets priority
- Preserves an immediate user click or cell selection instead of moving focus back to the first code cell

### v3.02 (2026-07-16)
- Uses the encrypted database under the executable directory through an absolute, working-directory-independent path
- Moves verified legacy database files and all legacy QSettings values into their canonical locations automatically
- Replaced QtAwesome with semantic Qt-native icons and removed its packaging/dependency residue
- Added startup performance budgets and refined estimate, totals, login, print, and silver-bar interactions

### v3.01 (2026-07-15)
- Delivered the full database, worker, encryption, DDA live-rate, architecture, performance, and Windows CI upgrade
- Uses the public Agra Mohar item ID and customer-facing `finalRate` with SSE plus HTTPS fallback
- Produced a verified Windows test build with startup smoke coverage
- Polished login, settings, histories, totals, and print preview with consistent date/rupee formatting and clearer empty or saved states
- Retired completed one-time settings migrations and removed dead compatibility wrappers, aliases, helpers, constants, and stale diagnostics

### v3.0 (2026-06-13)
- Bumped the application/package release to v3.0
- Removed unused UI helper code and stale temporary build/test artifacts from the repository
- Refreshed the project knowledge graph after cleanup
- Validated the release candidate with the full test suite and opt-in smoke test

### v2.9.0 (2026-06-13)
- Added the opt-in full-startup smoke harness with encrypted test database setup and automatic Qt screenshots
- Captured smoke coverage for login, estimate entry, item master, history, settings, custom font, item selection, silver-bar, and print-preview screens
- Improved screenshot reliability at a 1366x768 baseline and fixed offscreen main-window sizing
- Polished several UI surfaces found during screenshot review, including history tables, settings previews, item selection copy, and silver-bar layouts

### v2.8.9 (2026-05-20)
- Upgraded the app to PyQt6-only with Python 3.14-oriented dependency and packaging updates
- Added strict light theme coverage across dialogs, menus, popups, settings, management screens, and print preview controls
- Hardened Qt6 printing/PDF helpers for page size, margins, orientation, stale printers, temp-file PDF replacement, and quick print validation
- Introduced the estimate table column registry and visible-arrow themed controls for combo/spinbox widgets

### v2.8.1 (2026-03-08)
- Fixed the follow-up lint and type-check issues from the `v2.8` release so `main` validation is green again
- Hardened Windows startup typing, print-preview enum handling, and icon helper typing used by the refreshed UI work

### v2.8 (2026-03-08)
- Refined the estimate-entry header and action strips to preserve table space while tightening button grouping and icon usage
- Standardized mdi6 icons across the main workflows and cleaned up the print-preview toolbar into a single consistent icon set
- Improved print preview with live-layout switching, better page navigation, and more sensible toolbar grouping

### v2.7 (2026-03-07)
- Restored the DDASilver fallback live-rate calculation to the required purity-adjusted value for `Silver Agra Local Mohar`
- Added maintainer notes documenting that strict HTTPS does not currently work for the DDASilver homepage and broadcast feed

### v2.6.7 (2026-02-18)
- Corrected DDASilver live-rate parsing to use the `Silver Agra Local Mohar` target row value directly
- Documented and enforced the fixed live-rate source policy for `Silver Agra Local Mohar`

### v2.6.2 (2026-02-13)
- Fixed estimate history dialog async callback wiring to avoid repeat-open `rid` argument errors
- Stabilized history dialog open/close behavior during repeated usage

### v2.6 (2026-02-13)
- Updated CI workflow so Windows `.exe` build runs at completion even when earlier checks fail
- Improved summary cards drag/drop behavior with reliable swap-on-drop handling
- Enabled moving the `Final Calculation` card as part of summary ordering

### v2.54 (2026-02-13)
- Added draggable summary cards with saved custom ordering across sessions
- Enabled moving and swapping the `Final Calculation` card within the summary panel
- Improved summary-card sizing behavior and reduced drag/drop rendering glitches

### v2.53 (2026-02-13)
- Reworked estimate-grid cursor movement to avoid row-navigation loops and freezes
- Added arrow-key cursor navigation support while editing estimate rows
- Defaulted Estimate History `From` date to the earliest saved estimate date

### v2.5 (2025-11-18)
- Break down estimate entry workflow for better readability and a denser UI
- Make action bars/toolbar controls more compact for smaller resolutions
- Expand keyboard shortcuts and fix Ctrl+D row deletion crash

### v2.0.3 (2025-10-29)
- Fix UI layout issues on small screens
- Set maximum width for toggle buttons to prevent expansion
- Shorten button text when active (Return/Silver Bar modes)

### v2.0.2 (2025-10-29)
- Fix segmentation fault on startup by delaying signal connection
- Add guard to prevent auto-loading empty voucher numbers
- Fix RuntimeError with deleted QTableWidgetItem in table operations

### v2.0.1 (2025-09-16)
- Fix broadcast rate fetch and improve error handling

### v2.0.0 (2025-09-15)
- Major version bump for architectural improvements
- Enhanced stability and performance

### v1.72.7 (2025-09-16)
- Harden shutdown so duplicate DatabaseManager closes no longer raise false critical temp-file warnings

### v1.72.5 (2025-09-14)
- Ensure every secondary reader is keyed before schema access
- Serialize migration, backup, restore, rekey, and wipe through broker maintenance mode

[See full changelog](CHANGELOG.md)
