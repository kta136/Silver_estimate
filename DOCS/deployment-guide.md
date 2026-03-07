# Deployment & Packaging Guide

## Overview
- Primary target: Windows 10/11 desktops.
- Build system: PyInstaller 6.x driven from `SilverEstimate.spec`.
- Runtime Python: 3.13.
- Artifacts: a single executable in `dist/`, later zipped for release publishing.

## Local Windows Packaging
1. Open PowerShell in the repo root.
2. Create/activate a virtual environment and install dependencies:
   - `python -m venv .venv`
   - `.\.venv\Scripts\Activate.ps1`
   - `python -m pip install --upgrade pip`
   - `python -m pip install -e ".[dev]"`
3. Build with the canonical spec:
   - `python -m PyInstaller --clean --noconfirm SilverEstimate.spec`
4. Output artifact:
   - `dist/SilverEstimate.exe`
5. Optionally zip the executable manually for distribution.

### Manual PyInstaller Invocation
- Spec file: `SilverEstimate.spec` (canonical and required for builds).
- Hidden imports and other packaging settings live in the spec file.
- Add datas or icons by editing the spec file if new resources are introduced.

## Continuous Delivery (GitHub Actions)
Workflow: `.github/workflows/release-windows.yml`.
- Trigger: pushing a tag matching `v*` (e.g., `v1.72.7`).
- Jobs:
  - Checkout repository.
  - Install Python 3.13 and project dependencies from `pyproject.toml` (plus `pyinstaller` for packaging).
  - Build the executable from `SilverEstimate.spec`.
  - Rename artifact to `SilverEstimate-<tag>.exe` and zip as `SilverEstimate-<tag>-win64.zip`.
  - Publish the zip to the GitHub Release using `softprops/action-gh-release`.

### Release Checklist
1. Update `APP_VERSION` in `silverestimate/infrastructure/app_constants.py`.
2. Update `CHANGELOG.md` and relevant docs.
3. Commit changes and push to the main branch.
4. Create and push annotated tag `git tag v<version>` followed by `git push origin v<version>`.
5. Confirm the GitHub Actions build attaches the new zip to the release entry.

## Dependency Management
- Runtime dependencies are defined in `pyproject.toml` (`[project.dependencies]`).
- Development dependencies are defined in `pyproject.toml` (`[project.optional-dependencies].dev`).
- Preferred local bootstrap: `uv sync --extra dev` after `python` resolves to Python 3.13+.
- Fallback local bootstrap: `python -m venv .venv`, activate it, then `python -m pip install -e ".[dev]"`.

## Testing Before Packaging
- Run `pytest` from the repo root (requires developer dependencies such as `pytest` and `pytest-qt`).
- Ensure the application starts with `python main.py` before freezing.
- Verify encrypted database handling by launching the packaged build, creating a password (ensure the OS keyring is available), saving a sample estimate, closing, and reopening.

## Common Troubleshooting
- **Missing DLLs:** Ensure the host machine has the Microsoft Visual C++ redistributables. PyInstaller bundles the interpreter but relies on system runtimes.
- **Antivirus false positives:** Sign the executable when distributing to customers; CI output is unsigned. Consider submitting the binary to Microsoft Defender for pre-approval.
- **Stale virtual environment:** Delete `.venv/` if dependency versions are inconsistent, then reinstall with `python -m pip install -e ".[dev]"`.
- **Spec updates ignored:** Remove `build/` and `dist/` folders to force PyInstaller to regenerate caches after editing the spec.

## Future Enhancements
- Automate icon/resource inclusion inside the spec once assets are finalized.
- Capture build metadata (git commit, build time) and embed it into the executable via a version resource.
- Extend CI to produce non-onefile archives for faster startup if customer feedback prefers unpacked builds.
