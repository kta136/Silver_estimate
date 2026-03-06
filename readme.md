# Silver Estimation App - v2.6.8

A desktop application built with PyQt5 and an encrypted SQLite database for managing silver sales estimates - item-wise entries, silver bar inventory, returns, and print-ready outputs.

[![Python](https://img.shields.io/badge/Python-3.13+-blue.svg)](https://www.python.org/)
[![PyQt5](https://img.shields.io/badge/PyQt5-5.15+-green.svg)](https://www.riverbankcomputing.com/software/pyqt/)
[![License](https://img.shields.io/badge/License-Proprietary-red.svg)](LICENSE)
[![Version](https://img.shields.io/badge/version-v2.6.8-orange.svg)](CHANGELOG.md)
[![PR Validation](https://github.com/kta136/Silver_estimate/actions/workflows/pr-validation.yml/badge.svg)](https://github.com/kta136/Silver_estimate/actions/workflows/pr-validation.yml)
[![Main Validation](https://github.com/kta136/Silver_estimate/actions/workflows/main-validation.yml/badge.svg)](https://github.com/kta136/Silver_estimate/actions/workflows/main-validation.yml)
[![Release Windows](https://github.com/kta136/Silver_estimate/actions/workflows/release-windows.yml/badge.svg)](https://github.com/kta136/Silver_estimate/actions/workflows/release-windows.yml)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![Lint: Ruff](https://img.shields.io/badge/lint-ruff-%23D7FF64)](https://docs.astral.sh/ruff/)
[![Type checking: mypy](https://img.shields.io/badge/type%20checking-mypy-blue.svg)](http://mypy-lang.org/)
[![Security: bandit](https://img.shields.io/badge/security-bandit-yellow.svg)](https://github.com/PyCQA/bandit)
[![Pre-commit](https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=pre-commit)](https://github.com/pre-commit/pre-commit)
[![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey.svg)](https://github.com/kta136/Silver_estimate)

## Quick Links

- [Download latest release](https://github.com/kta136/Silver_estimate/releases/latest)
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
- Store all data locally with file-level encryption
- Import/export item catalogs

## Architecture

- **UI layer**: PyQt5 widgets in `silverestimate/ui/` handle estimate entry, item master, silver bar management, history, and supporting dialogs.
- **Presenter**: `silverestimate/presenter/estimate_entry_presenter.py` coordinates estimate workflows, keeping UI widgets thin and testable.
- **Controllers**: Startup, navigation, and live-rate controllers bootstrap the app, wire menus/toolbars, and manage background refresh cadence.
- **Services**: `MainCommands`, `SettingsService`, `LiveRateService`, and `AuthService` encapsulate reusable logic; authentication relies on the secure credential store.
- **Persistence**: `DatabaseManager` plus repository classes (`items`, `estimates`, `silver_bars`) manage the decrypted working copy, WAL checkpoints, and AES-GCM encryption.
- **Security & infrastructure**: OS keyring-backed credential storage (`silverestimate/security/credential_store.py`), structured logging with optional cleanup scheduler, and QSettings helpers maintain app state safely.

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
- Encrypted database: AES-256-GCM file-level encryption
- Password hashing: Argon2 with hashes stored in the OS keyring (Python `keyring`)
- Secure settings store: non-sensitive preferences via QSettings

### Printing & Reporting
- Print-ready estimate layouts with INR formatting
- Print preview and configurable fonts/sizes

### Import/Export
- Import items from delimited files
- Export item catalogs for backup
- Duplicate handling with safe merges

## Installation

1. Install Python 3.13+
2. Clone the repository
3. Create a virtual environment
4. Install dependencies

```powershell
# Windows (PowerShell)
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install .
```

```bash
# macOS/Linux
python3 -m venv .venv
source .venv/bin/activate
pip install .
```

> Note: The app relies on the operating system keyring for storing password hashes. Windows Credential Manager and macOS Keychain work out of the box. On Linux, install a SecretService-compatible keyring (for example `gnome-keyring`) or configure an alternative backend before launching the app.

## Usage

Run the application:

```bash
python main.py
```

First run notes:
- You will be prompted to create a password.
- The password encrypts the local database file at `database/estimation.db`.
- Keep this password safe - encrypted data cannot be recovered without it.
- Hashed credentials are stored in the system keyring; ensure your OS user account can access the default credential vault.

## Security

- Encryption: AES-256-GCM with per-install salt stored via QSettings
- Passwords: Argon2 hashing (passlib) with hashes persisted in the OS keyring (Python `keyring`)
- Files: Encrypted DB at `database/estimation.db` (ignored in Git)
- Logs: Written to `logs/` (ignored); avoid logging sensitive data

## Configuration

- Settings: Qt QSettings (`SETTINGS_ORG`, `SETTINGS_APP`) in `silverestimate/infrastructure/app_constants.py`
- Paths: DB path via `DB_PATH` in `silverestimate/infrastructure/app_constants.py`
- Printing: Fonts and sizes configurable via Settings dialog

## Development

Key areas of the codebase:

- `main.py` – application entry point plus main window bootstrapping.
- `silverestimate/controllers/` – startup, navigation, and live-rate controllers.
- `silverestimate/presenter/estimate_entry_presenter.py` – presenter coordinating save/load logic and calculations.
- `silverestimate/ui/estimate_entry.py` – main estimate widget combining UI helpers and presenter.
- `silverestimate/ui/estimate_entry_logic/` – table helpers, persistence mixins, and calculations wiring.
- `silverestimate/services/` – auth, settings, live-rate, main commands, and repository adapters.
- `silverestimate/persistence/` – `DatabaseManager`, repositories, migrations, and flush scheduler.
- `silverestimate/security/` – AES-GCM utilities and keyring-backed credential storage.
- `silverestimate/infrastructure/` – logging, settings helpers, and app constants.
- `DOCS/` – deep-dive documentation (architecture, API reference, deployment, security, etc.).

## Testing

- Tests live under `tests/` and use pytest (with `pytest-qt` for UI hooks).
- Local smoke command: `pytest -v tests/test_security.py tests/services/test_auth_service.py`
- Full local run: `pytest -v`
- CI enforces coverage thresholds using explicit pytest coverage flags in workflow commands.
- To iterate quickly on the application builder branch, run `pytest tests/unit/test_application_builder.py`.
- Ruff enforces linting and import ordering in CI.
- Black formatting is enforced locally via pre-commit (CI does not run Black checks).
- Run formatting and hooks before pushing: `pre-commit run --all-files`

## Deployment

### Build Locally (Windows)
- Prereqs: Python 3.13+, PowerShell
- Run: `python -m PyInstaller --clean --noconfirm SilverEstimate.spec`
- One-file exe:
  `python -m PyInstaller --noconfirm --onefile --windowed --name SilverEstimate --hidden-import passlib.handlers.argon2 --hidden-import passlib.handlers.bcrypt --hidden-import keyring.backends --hidden-import keyring.backends.Windows --hidden-import keyring.backends.win32 --hidden-import keyring.backends.fail --hidden-import keyring.backends.null main.py`
- Output: `dist/SilverEstimate/` (spec build) or `dist/SilverEstimate.exe` (one-file build)

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
  - [Project architecture](DOCS/project-architecture.md)
  - [API reference](DOCS/api-reference.md)
  - [Security architecture](DOCS/security-architecture.md)
  - [Logging guide](DOCS/logging-guide.md)
  - [Performance baseline thresholds](DOCS/performance-baseline-thresholds.md)
  - [Remaining performance tasks](DOCS/performance-remaining-tasks.md)

## License

This project is proprietary software. All rights reserved.

c 2023-2025 Silver Estimation App

---

## Version History (highlights)

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
- Ensure encryption reads a complete WAL snapshot before sealing
- Serialise encryption with explicit locks

[See full changelog](CHANGELOG.md)
