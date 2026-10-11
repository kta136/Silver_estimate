# Silver Estimate Documentation

This directory contains the maintained technical and operational documentation
for the current source tree. Packaged releases support Windows 10/11; macOS and
Linux are untested development environments.

## Start here

| Guide | Use it for |
|---|---|
| [Project architecture](project-architecture.md) | Runtime boundaries, repositories, workers, encryption flow, and extension rules |
| [Workflow and business logic](workflow-business-logic.md) | Estimate, item, silver-bar, authentication, backup, and UI workflows |
| [Data model and relationships](data-model-relationships.md) | Schema v10 tables, foreign keys, indexes, and version history |
| [Security architecture](security-architecture.md) | Authentication, SQLCipher/keyring boundaries, recovery, and threat limitations |
| [Deployment guide](deployment-guide.md) | Locked environment, validation, CI, and local Windows builds |

## Project status

- Source version: `APP_VERSION` in `silverestimate/infrastructure/app_constants.py`
- Runtime: Python 3.14, PySide6/Shiboken6 6.11, and Qt 6.11
- Packaged platform: Windows 10/11
- Change history: [CHANGELOG.md](../CHANGELOG.md)

The source tree can be newer than the latest packaged release. Windows builds
are made locally with `scripts\build_windows_local.cmd`; see the deployment
guide.

## Security note

Never attach a production encrypted database, credential-vault export, password,
derived key, or unredacted customer log to a GitHub issue. Use synthetic data and
remove customer identifiers from screenshots and diagnostics.
