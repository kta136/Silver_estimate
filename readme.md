# 🧾 Silver Estimation App — v1.72.7

A desktop application built with PyQt5 and an encrypted SQLite database for managing silver sales estimates — item-wise entries, silver bar inventory, returns, and print‑ready outputs.

![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)
![PyQt5](https://img.shields.io/badge/PyQt5-5.15+-green.svg)
![License](https://img.shields.io/badge/License-Proprietary-red.svg)
![Version](https://img.shields.io/badge/version-v1.72.7-orange.svg)

## 📋 Table of Contents
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
- [Version History](#-version-history-highlights)

## 🎯 Overview

The app helps silver shops to:
- Generate itemized estimates with accurate calculations
- Track gross, net, and fine weights; wages (PC/WT)
- Manage silver bar inventory and returns
- Print formatted estimate slips with Indian rupee formatting
- Store all data locally with file‑level encryption
- Import/export item catalogs

## 🏗️ Architecture

```
┌─────────────────┐     ┌─────────────────────┐
│   PyQt5 UI      │◄──►│ EstimateEntryLogic   │
│   Components    │     │ Business Logic &    │
│      (Views)    │     │ Calculations        │
└─────────────────┘     └─────────────────────┘
         │                           │
         ▼                           ▼
┌─────────────────┐     ┌─────────────────────┐
│ DatabaseManager │◄──►│   Encrypted SQLite   │
│   Operations    │     │   Database          │
│ Encryption/CRUD │     │                     │
└─────────────────┘     └─────────────────────┘
         │
         ▼
┌─────────────────┐
│ Support Modules │
│ • PrintManager  │
│ • Settings      │
│ • Logger        │
│ • ItemManager   │
└─────────────────┘
```

### Key Design Principles
- Separation of concerns: UI, logic, and data access are separated
- Security‑first: Encrypted DB, hashed credentials, safe settings
- Modular: Focused modules for UI, logic, and persistence
- Responsive: Signal/slot updates and debounced work
- Integrity: Validations and transaction boundaries

See also: `DOCS/project-architecture.md`.

## ✨ Features

### 💼 Core
- Estimate management: create/edit/track with inline validations
- Item catalog: maintain items and rates
- Silver bar tracking: inventory and history
- Return processing and last balance handling

### 🔒 Security
- Encrypted database: AES-256-GCM file-level encryption
- Password hashing: Argon2 with hashes stored in the OS keyring (Python `keyring`)
- Secure settings store: non-sensitive preferences via QSettings

### 🖨️ Printing & Reporting
- Print‑ready estimate layouts with INR formatting
- Print preview and configurable fonts/sizes

### 🔄 Import/Export
- Import items from delimited files
- Export item catalogs for backup
- Duplicate handling with safe merges

## 📸 Screenshots

Capture screenshots from the running app and store them in `DOCS/images/` (keep filenames consistent so links stay valid):

- Estimate entry workflow → `DOCS/images/estimate-entry.png`
- Item master catalog → `DOCS/images/item-master.png`
- Silver bar management → `DOCS/images/silver-bar-management.png`
- Print preview → `DOCS/images/print-preview.png`

(Add the PNG files when ready; the repository currently omits large assets.)

## 🛠️ Installation

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

> 🔐 The app relies on the operating system keyring for storing password hashes. Windows Credential Manager and macOS Keychain work out of the box. On Linux, install a SecretService-compatible keyring (for example `gnome-keyring`) or configure an alternative backend before launching the app.

## ▶️ Usage

Run the application:

```bash
python main.py
```

First run notes:
- You will be prompted to create a password.
- The password encrypts the local database file at `database/estimation.db`.
- Keep this password safe - encrypted data cannot be recovered without it.
- Hashed credentials are stored in the system keyring; ensure your OS user account can access the default credential vault.

## 🔒 Security

- Encryption: AES-256-GCM with per-install salt stored via QSettings
- Passwords: Argon2 hashing (passlib) with hashes persisted in the OS keyring (Python `keyring`)
- Files: Encrypted DB at `database/estimation.db` (ignored in Git)
- Logs: Written to `logs/` (ignored); avoid logging sensitive data

## ⚙️ Configuration

- Settings: Qt QSettings (`SETTINGS_ORG`, `SETTINGS_APP`) in `silverestimate/infrastructure/app_constants.py`
- Paths: DB path via `DB_PATH` in `silverestimate/infrastructure/app_constants.py`
- Printing: Fonts and sizes configurable via Settings dialog

## 🧑‍💻 Development

Project structure (key files):

```
silverestimate/infrastructure/app_constants.py    # App name/version, constants, paths
silverestimate/infrastructure/logger.py          # Logging setup (Qt and Python)
silverestimate/persistence/database_manager.py   # Encrypted SQLite management
silverestimate/ui/estimate_entry.py              # Main estimate UI + interactions
silverestimate/ui/estimate_entry_ui.py           # UI helpers and widgets
silverestimate/ui/estimate_entry_logic.py        # Calculation helpers and validations
silverestimate/ui/item_master.py                 # Item catalog management
silverestimate/ui/silver_bar_management.py       # Silver bar inventory flows
silverestimate/ui/silver_bar_history.py          # Silver bar movements/history
silverestimate/ui/item_selection_dialog.py       # Item selection and filtering
silverestimate/ui/settings_dialog.py             # App settings dialog
silverestimate/ui/print_manager.py               # Print/preview formatting and INR currency
silverestimate/ui/message_bar.py                 # Inline status/messages
main.py                                          # Application entry point and main window
scripts/build_windows.ps1                        # Local Windows build script
.github/workflows/release-windows.yml            # CI release build (Windows)
DOCS/                                            # Deep-dive docs
```

## ✅ Testing

Refer to `DOCS/testing-implementation-playbook.md` for the current pytest plan. Focus coverage on calculations, encryption round-trips, history queries, and print formatting, and extend the suite as new workflows land.

## 🚀 Deployment

### Build Locally (Windows)
- Prereqs: Python 3.11+, PowerShell
- Run: `pwsh scripts/build_windows.ps1`
- One‑file exe: add `-OneFile` (bundles keyring and Argon2 hidden imports)
- Output: `dist/SilverEstimate.exe` or versioned zip from script

### GitHub Release (Windows CI)
- Update version in `silverestimate/infrastructure/app_constants.py` (`APP_VERSION`)
- Create and push a tag (workflow triggers on tags):
  - `git commit -am "chore: bump version to vX.YY"`
  - `git tag vX.YY`
  - `git push origin master --tags`
- CI builds the exe and attaches `SilverEstimate-vX.YY-win64.zip` to the GitHub Release

For more details, see `DOCS/deployment-guide.md`.

## 🤝 Contributing

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

## 📞 Support

For support and troubleshooting:
- GitHub Issues: report bugs and request features
- Documentation: see the `DOCS/` folder for deep dives

Troubleshooting resources:
- [Common issues and solutions](DOCS/troubleshooting-maintenance.md)
- [Performance optimization tips](DOCS/performance-optimization.md)
- [Changelog](CHANGELOG.md)
- [Changelog archive](DOCS/changelog-archive.md)

## 📄 License

This project is proprietary software. All rights reserved.

© 2023–2025 Silver Estimation App

---

## 🔄 Version History (highlights)

### v1.72.7 (2025‑09‑16)
- Harden shutdown so duplicate DatabaseManager closes no longer raise false critical temp-file warnings.

### v1.72.5 (2025‑09‑14)
- Ensure encryption reads a complete WAL snapshot before sealing, eliminating session-only data loss.
- Serialise encryption with explicit locks and postpone shutdown until flush work completes.
- Improve Item Master persistence messaging and flush lifecycle logs.

### v1.72.4 (2025‑09‑14)
- Add refresh button next to Live Silver Rate.
- Async live rate fetch (broadcast/API fallback).
- Fix Estimate History action methods location.
- Minor layout polish and tooltips.

### v1.72.3 (2025‑09‑13)
- Faster startup via lazy imports; prepared cursors
- Indexed lookups and batched inserts
- Async flush hygiene on close; inline "Saving…" hint

### v1.72.2 (2025‑09‑13)
- Debounced async encryption flush
- Optimized history aggregations and UI batching
- Debounced totals; minor fixes

[See full changelog](CHANGELOG.md)


