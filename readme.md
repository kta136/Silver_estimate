# Silver Estimation App - v1.72.7

A desktop application built with PyQt5 and an encrypted SQLite database for managing silver sales estimates - item-wise entries, silver bar inventory, returns, and print-ready outputs.

![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)
![PyQt5](https://img.shields.io/badge/PyQt5-5.15+-green.svg)
![License](https://img.shields.io/badge/License-Proprietary-red.svg)
![Version](https://img.shields.io/badge/version-v1.72.7-orange.svg)

## Table of Contents
- [Overview](#overview)
- [Architecture](#architecture)
- [Features](#features)
- [Screenshots](#screenshots)
- [Installation](#installation)
- [Usage](#usage)
- [Security](#security)
- [Configuration](#configuration)
- [Development](#development)
- [Testing](#testing)
- [Deployment](#deployment)
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

## Screenshots

Capture screenshots from the running app and store them in `DOCS/images/` (keep filenames consistent so links stay valid):

- Estimate entry workflow -> `DOCS/images/estimate-entry.png`
- Item master catalog -> `DOCS/images/item-master.png`
- Silver bar management -> `DOCS/images/silver-bar-management.png`
- Print preview -> `DOCS/images/print-preview.png`

(Add the PNG files when ready; the repository currently omits large assets.)

## Installation

1. Install Python 3.11+
2. Clone the repository
3. Create a virtual environment
4. Install dependencies

```powershell
# Windows (PowerShell)
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

```bash
# macOS/Linux
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
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
- `scripts/build_windows.ps1` – local Windows build script (PyInstaller).
- `DOCS/` – deep-dive documentation (architecture, API reference, deployment, security, etc.).

## Testing

Tests live under `tests/` and use pytest (with `pytest-qt` for UI hooks). Run `pytest` to exercise calculations, encryption round-trips, history queries, and print formatting. Add coverage for new workflows as they land.

## Deployment

### Build Locally (Windows)
- Prereqs: Python 3.11+, PowerShell
- Run: `pwsh scripts/build_windows.ps1`
- One-file exe: add `-OneFile` (bundles keyring and Argon2 hidden imports)
- Output: `dist/SilverEstimate/` plus a versioned zip generated by the script

### GitHub Release (Windows CI)
- Update version in `silverestimate/infrastructure/app_constants.py` (`APP_VERSION`)
- Create and push a tag (workflow triggers on tags):
  - `git commit -am "chore: bump version to vX.YY"`
  - `git tag vX.YY`
  - `git push origin master --tags`
- CI builds the exe and attaches `SilverEstimate-vX.YY-win64.zip` to the GitHub Release

For more details, see `DOCS/deployment-guide.md`.

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
  - [Performance optimization](DOCS/performance-optimization.md)

## License

This project is proprietary software. All rights reserved.

c 2023-2025 Silver Estimation App

---

## Version History (highlights)

### v1.72.7 (2025-09-16)
- Harden shutdown so duplicate DatabaseManager closes no longer raise false critical temp-file warnings.

### v1.72.5 (2025-09-14)
- Ensure encryption reads a complete WAL snapshot before sealing, eliminating session-only data loss.
- Serialise encryption with explicit locks and postpone shutdown until flush work completes.
- Improve Item Master persistence messaging and flush lifecycle logs.

### v1.72.4 (2025-09-14)
- Add refresh button next to Live Silver Rate.
- Async live rate fetch (broadcast/API fallback).
- Fix Estimate History action methods location.
- Minor layout polish and tooltips.

### v1.72.3 (2025-09-13)
- Faster startup via lazy imports; prepared cursors
- Indexed lookups and batched inserts
- Async flush hygiene on close; inline "Saving." hint

### v1.72.2 (2025-09-13)
- Debounced async encryption flush
- Optimized history aggregations and UI batching
- Debounced totals; minor fixes

[See full changelog](CHANGELOG.md)

