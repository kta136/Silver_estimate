# Silver Estimate v2.8.9 Release Notes

Release date: 2026-05-20

## Summary

Version 2.8.9 is the PyQt6 migration and UI hardening release. The app is now PyQt6-only, uses Python 3.14-oriented packaging, and applies a strict light theme across Windows dark mode, dialogs, popup menus, combo boxes, calendar popups, management screens, settings, estimate history, and print preview.

## What Changed

- Upgraded the desktop runtime and packaging path from PyQt5/Qt5 to PyQt6/Qt6.
- Added strict light palette and QSS coverage for the application, management screens, menus, tooltips, message boxes, input/progress dialogs, combo popups, and calendar popups.
- Added visible-arrow themed controls for combo boxes, spin boxes, double spin boxes, font combo boxes, and date edits.
- Added high-DPI-aware sizing helpers for secondary windows.
- Hardened print/PDF handling with shared Qt6 page settings, stale-printer checks, and safer temp-file PDF replacement.
- Modernized estimate-table internals with a column-spec registry while preserving the existing fast-entry workflow.
- Refreshed settings, login, item selection, item master, silver-bar management/history, estimate history, custom font, and print preview UI surfaces.

## Release Artifacts

Published Windows artifacts attached to the GitHub Release:

| Artifact | Source | SHA256 |
| --- | --- | --- |
| `SilverEstimate-v2.8.9.exe` | Local clean build from commit `c7253ed4a6a456912aa5fe7cac2e757b34d781f2` | `2B9C3C6BE689A41DBD92C92E3EF5BA22AC67E0C2260FEB358237BF130281A001` |
| `SilverEstimate-v2.8.9-win64.zip` | GitHub Actions tag build from `v2.8.9` | `008A630404F60C14823A0F7EFFF3FEC2676702329CD4B195019BFD9C8132EFBA` |

The release also includes `.sha256` sidecar files for both download formats.

## Verification

- `uv run --extra dev nox -s ruff`
- Focused PyQt6 UI/theme suite: 58 passed
- `git diff --check`
- `uv run --extra dev nox -s build_clean`
- `graphify update .`
- No PyQt5/Qt5/`exec_()` residue found in the final source/test/build metadata scan.

## Manual Smoke Checklist

- Launch `dist/SilverEstimate-v2.8.9.exe`.
- With Windows dark mode enabled, inspect login, main estimate entry, settings, item selection, item master, silver-bar management, silver-bar history, estimate history, custom font, print preview, menus, tooltips, combo popups, calendar popups, message boxes, input dialogs, progress dialogs, and file dialogs.
- Export/preview Classic, Modern, Thermal, silver-bar inventory, and silver-bar list PDF outputs.
- Try quick print with no printer, stale printer, and a valid printer where available.
