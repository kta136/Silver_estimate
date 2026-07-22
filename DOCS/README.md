# Silver Estimate Documentation

This directory contains the maintained technical and operational documentation
for the v3.07 source tree. Packaged releases support Windows 10/11; macOS and
Linux are untested development environments.

## Start here

| Guide | Use it for |
|---|---|
| [Project architecture](project-architecture.md) | Runtime boundaries, repositories, workers, encryption flow, and extension rules |
| [Workflow and business logic](workflow-business-logic.md) | Estimate, item, silver-bar, authentication, backup, and UI workflows |
| [Data model and relationships](data-model-relationships.md) | Schema v8 tables, foreign keys, indexes, and migration history |
| [Security architecture](security-architecture.md) | Authentication, keyring storage, `SILVDB01`, recovery, and threat limitations |
| [API reference](api-reference.md) | Primary controllers, services, repositories, helpers, and UI entry points |
| [Deployment guide](deployment-guide.md) | Frozen environment, validation, Windows builds, tags, signing, and releases |
| [Performance baselines](performance-baseline-thresholds.md) | Deterministic datasets, p95 budgets, and CI enforcement |

## Project status

- Source version: `3.07`
- Runtime: Python 3.14 and PyQt6 6.11
- Packaged platform: Windows 10/11
- Stable downloads: [GitHub Releases](https://github.com/kta136/Silver_estimate/releases/latest)
- Change history: [CHANGELOG.md](../CHANGELOG.md)

The source tree can be newer than the latest packaged release. Release tags are
validated against `APP_VERSION` and pass the Windows validation/build pipeline
before publication.

## Security note

Never attach a production encrypted database, credential-vault export, password,
derived key, or unredacted customer log to a GitHub issue. Use synthetic data and
remove customer identifiers from screenshots and diagnostics.
