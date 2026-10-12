# Silver Estimation App

A Windows desktop application built with PySide6 and a local SQLCipher database
for managing silver sales estimates, item-wise entries, silver-bar inventory,
returns, and print-ready outputs.

[![Python](https://img.shields.io/badge/Python-3.14+-blue.svg)](https://www.python.org/)
[![PySide6](https://img.shields.io/badge/PySide6-6.11-green.svg)](https://doc.qt.io/qtforpython-6/)
[![License: GPL v3](https://img.shields.io/badge/License-GPL_v3-blue.svg)](LICENSE)
[![Validation](https://github.com/kta136/Silver_estimate/actions/workflows/validation.yml/badge.svg)](https://github.com/kta136/Silver_estimate/actions/workflows/validation.yml)
[![Formatter: Ruff](https://img.shields.io/badge/formatter-ruff-%23D7FF64)](https://docs.astral.sh/ruff/)
[![Lint: Ruff](https://img.shields.io/badge/lint-ruff-%23D7FF64)](https://docs.astral.sh/ruff/)
[![Type checking: mypy](https://img.shields.io/badge/type%20checking-mypy-blue.svg)](https://mypy-lang.org/)
[![Platform](https://img.shields.io/badge/packaged%20platform-Windows-lightgrey.svg)](https://github.com/kta136/Silver_estimate)

## Quick Links

- [Documentation index](DOCS/README.md)
- [Changelog](CHANGELOG.md)
- [Deployment guide](DOCS/deployment-guide.md)

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
- [License](#license)

## Overview

The app helps silver shops to:
- Generate itemized estimates with accurate calculations
- Track gross, net, and fine weights; wages (PC/WT)
- Manage silver bar inventory and returns
- Print formatted estimate slips and Modern silver-bar inventory/list reports
  through typed direct painters with Indian rupee formatting
- Follow live Agra Mohar rates through anonymous HTTPS/SSE updates with an offline snapshot
- Keep the desktop UI in a strict light theme across Windows dark mode, dialogs, popups, and print preview controls
- Store the live database, WAL, and journals locally with SQLCipher encryption
- Create encrypted full-database backups and explicit plaintext item-catalog exports

## Architecture

- **UI layer**: PySide6 widgets in `silverestimate/ui/` handle estimate entry, item master, silver bar management, history, and supporting dialogs.
- **Theme layer**: `silverestimate/ui/application_theme.py`, `theme_tokens.py`, `shared_screen_theme.py`, and `themed_controls.py` keep the app on a strict light theme and preserve visible combo/spinbox arrows under Qt stylesheets.
- **Presenter**: `silverestimate/presenter/estimate_entry_presenter.py` coordinates estimate workflows, keeping UI widgets thin and testable.
- **Controllers**: Startup, navigation, and live-rate controllers bootstrap the app, wire menus/toolbars, and manage background refresh cadence.
- **Services**: `MainCommands`, `SettingsService`, and `AuthService` encapsulate reusable logic; authentication relies on the secure credential store.
- **Persistence**: `DatabaseManager`, `SqlCipherConnectionBroker`, and role-specific repositories manage direct encrypted connections, schema-v10 creation and validation, keyset pages, encrypted WAL/journals, maintenance draining, and staged recovery.
- **Security & infrastructure**: Windows Credential Manager credential storage (`silverestimate/security/credential_store.py`), Qt6 startup bootstrap (`silverestimate/infrastructure/qt_bootstrap.py`), structured logging with daily rotation and optional cleanup, and QSettings helpers maintain app state safely.

### DDA Agra Mohar Live Rate

- The startup/recovery snapshot is anonymous HTTPS: `https://ddajewels.com/api/v1/rates/current`.
- Instant updates use `https://ddajewels.com/sse/rates`; disconnected streams fall back to a 10-second HTTPS poll.
- Selection is by stable item ID `cmomws5tw000004i5k5t6yrnw`, never by a display name.
- The displayed customer rate is `finalRate` with unit `PER_KG`. `baseRate` is intentionally ignored and no previous-rate percentage is derived.
- No API key or authorization header is required while the endpoint remains public. A verified snapshot is retained for offline/stale display.

### Key Design Principles
- Separation of concerns: UI, presenter, services, and persistence remain loosely coupled.
- Security-first: Encrypted database, credentials in Windows Credential Manager, safe defaults for settings.
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
- Encrypted database: machine-bound SQLCipher 4 format with a raw key derived from the password, the in-file salt, and a 256-bit device secret held in local-machine Windows Credential Manager
- Machine-bound `.sedbbackup` full-database backup and restart-activated restore; `.seitems.json` catalog exports remain plaintext by request
- Password hashing: Argon2 with hashes stored in Windows Credential Manager
- Secure settings store: non-sensitive preferences via QSettings

### Printing & Reporting
- Print-ready estimate layouts with INR formatting
- Modern silver-bar inventory and list layouts with repeated multipage headers,
  kept totals, and the same saved print-font control used by estimates
- Custom PySide6 print-preview window with one responsive toolbar, an embedded
  page canvas, persistent page navigation, and a More menu for printer and view
  actions
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
- Hashed credentials are stored in Windows Credential Manager. The random device-binding secret is forced into local-machine Windows Credential Manager storage so it cannot roam to another PC.

## Security

- Encryption: SQLCipher 4 file format through `apsw-sqlite3mc` (SQLite3 Multiple Ciphers), machine-bound Argon2id raw keys, and encrypted database/WAL/journal pages
- Passwords: direct Argon2id hashing with `argon2-cffi`; current PHC hashes are persisted in Windows Credential Manager
- Files: one permanent encrypted DB at `<EXE folder>/database/estimation.db` (ignored in Git); WAL/SHM and recovery journals can exist temporarily
- Device binding: copying the DB or a new `.sedbbackup` to another PC does not make it openable, even with the correct password
- Logs: Written to `logs/` (ignored); avoid logging sensitive data

The retired `SILVDB01` importer is no longer included. This release accepts only
the current machine-bound schema-v10 SQLCipher database. A database copied
without this PC's device secret fails closed. Plaintext, unversioned, two-file
and older-schema databases are rejected; open those once with v4.04 to v4.07,
which still upgrade them. Any separately retained `estimation.silvdb01.backup`
is not opened, rewritten, or deleted automatically.

## Configuration

- Settings: Qt QSettings (`SETTINGS_ORG`, `SETTINGS_APP`) in `silverestimate/infrastructure/app_constants.py`
- Paths: DB path via `DB_PATH` in `silverestimate/infrastructure/app_constants.py`
- Printing: Fonts and sizes configurable via Settings dialog
- UI: The app forces Qt's Fusion-style light palette/QSS during startup and uses non-native dialogs where needed so Windows dark mode does not leak into file dialogs
- Environment: only `SILVER_APP_DEBUG`, `SILVER_APP_LOG_DIR`, `SILVER_SHOW_CONSOLE`, and `SILVER_CLASSIC_TITLE_BAR` are runtime controls; see `.env.example`.

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
- `silverestimate/ui/print_preview_dialog.py` – explicit custom preview window containing the application-owned toolbar and embeddable Qt preview canvas.
- `silverestimate/ui/modern_print_primitives.py` – shared Modern typography, colors, table geometry, and printable-margin handling for estimate and silver-bar direct painters.
- `silverestimate/ui/silver_bar_print_document.py`, `silver_bar_print_layout.py`, and `silver_bar_print_renderer.py` – typed silver-bar report data, semantic layouts, pagination, and direct `QPainter` output.
- `silverestimate/services/` – auth, settings, the DDA live-rate transport, main commands, and catalog transfer.
- `silverestimate/persistence/` – `DatabaseManager`, current schema definition, SQLCipher broker, and repositories.
- `silverestimate/security/` – Argon2id password policy and Windows Credential Manager credential storage.
- `silverestimate/infrastructure/` – logging, settings helpers, and app constants.
- `DOCS/` – indexed deep-dive documentation for architecture, deployment, security, data relationships, and business workflows.

Recommended development commands with `uv`:

```bash
uv sync --frozen --extra dev
uv run python main.py
uv run nox
uv run nox -s audit
```

## Testing

- Tests live under `tests/` and use pytest with the `pytest-qt` PySide6 backend.
- Local smoke command: `pytest -v tests/unit/test_encryption.py tests/services/test_auth_service.py`
- Full startup UI smoke with screenshots: `uv run nox -s smoke_ui`
  - Creates an isolated encrypted test database with fixed smoke passwords.
  - Captures opt-in Qt screenshots under `artifacts/smoke-ui/`.
- Full local run: `pytest -v`
- Theme/control regression checks: `uv run --extra dev pytest tests/unit/test_application_theme.py tests/unit/test_themed_controls.py tests/ui/test_settings_dialog.py -q`
- Shared validation entrypoints:
  - `uv run nox` for Ruff (lint, format check and security rules), mypy and the tests; CI runs the same three
  - `uv run nox -s audit` to list known advisories for the locked runtime packages with `pip-audit`; it reports and never blocks
- To iterate quickly on the application builder branch, run `pytest tests/unit/test_application_builder.py`.
- Ruff enforces linting and import ordering in CI.
- Ruff formatting is checked in CI; run `uv run ruff format .` before pushing.

## Deployment

### Build Locally (Windows)
- Prereqs: Python 3.14+, PowerShell
- Fast validated Windows iteration: `scripts\build_windows_local.cmd -Fast` (outputs `dist/SilverEstimate-v<version>-fast.exe`)
- Validated local Windows build: `scripts\build_windows_local.cmd` (safe when the workspace path contains spaces)
- Local builds print stage durations and save `artifacts/local-build/build-timings[-suffix].json`. `-Fast` disables link-time optimization for development; use the default command for releases.
- Validated local output: `dist/SilverEstimate-v<version>.exe`.
- Builds use Qt's `pyside6-deploy`, the committed `pysidedeploy.spec`, and locked Nuitka 4.2.1. CI does not build or publish the executable.
- Packaged releases are Windows-only; macOS/Linux are untested development environments.

For more details, see `DOCS/deployment-guide.md`.

## License

This project is free software licensed under the
[GNU General Public License v3.0 only](LICENSE) (`GPL-3.0-only`).

Copyright (C) 2023-2026 Silver Estimation App
