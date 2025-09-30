# Deployment & Packaging Guide

## Overview
- Primary target: Windows 10/11 desktops.
- Build system: PyInstaller 6.x driven from a PowerShell helper script.
- Runtime Python: 3.11 (matches `on: windows-latest` CI image).
- Artifacts: unpacked directory build plus optional one-file executable zip.

## Local Windows Packaging
1. Open PowerShell in the repo root.
2. Run `pwsh scripts/build_windows.ps1`.
3. The script creates `.venv/`, installs `requirements.txt`, and runs PyInstaller with `SilverEstimate.spec` when present.
4. Output directories:
   - `dist/SilverEstimate/` contains the default windowed build with all dependencies.
   - `dist/SilverEstimate-v<version>-win64.zip` is created automatically from the folder above. Version is read from `silverestimate/infrastructure/app_constants.py`.

### One-File Executable
`pwsh scripts/build_windows.ps1 -OneFile`
- Invokes PyInstaller directly with `--onefile --windowed`.
- Produces `dist/SilverEstimate.exe`; the helper script still zips the file as `SilverEstimate-v<version>-win64.zip`.
- Expect slightly longer startup time while PyInstaller unpacks the bundle.

### Manual PyInstaller Invocation
- Spec file: `SilverEstimate.spec` (the build script uses `silverestimate.spec`, case-insensitive on Windows).
- Hidden imports already listed for Argon2/bcrypt handlers.
- Add datas or icons by editing the spec file if new resources are introduced.
- Temporary workaround: run `python -m PyInstaller --noconfirm SilverEstimate.spec` to reuse cached venv dependencies.

## Continuous Delivery (GitHub Actions)
Workflow: `.github/workflows/release-windows.yml`.
- Trigger: pushing a tag matching `v*` (e.g., `v1.72.7`).
- Jobs:
  - Checkout repository.
  - Install Python 3.11 and pip requirements.
  - Build one-file executable with PyInstaller (same flags as `-OneFile`).
  - Rename artifact to `SilverEstimate-<tag>.exe` and zip as `SilverEstimate-<tag>-win64.zip`.
  - Publish the zip to the GitHub Release using `softprops/action-gh-release`.

### Release Checklist
1. Update `APP_VERSION` in `silverestimate/infrastructure/app_constants.py`.
2. Update `CHANGELOG.md` and relevant docs.
3. Commit changes and push to the main branch.
4. Create and push annotated tag `git tag v<version>` followed by `git push origin v<version>`.
5. Confirm the GitHub Actions build attaches the new zip to the release entry.

## Dependency Management
- Runtime dependencies are tracked in `requirements.txt` (PyQt5, cryptography, passlib/argon2, argon2_cffi, pyinstaller, hypothesis).
- For local builds the helper script upgrades pip before installing requirements.
- Add dev/test-only libraries to a `requirements-dev.txt` (not currently present) or install manually in the virtual environment.

## Testing Before Packaging
- Run `pytest` from the repo root (requires developer dependencies such as `pytest`, `pytest-qt`, `pytest-mock`).
- Ensure the application starts with `python main.py` before freezing.
- Verify encrypted database handling by launching the packaged build, creating a password, saving a sample estimate, closing, and reopening.

## Common Troubleshooting
- **Missing DLLs:** Ensure the host machine has the Microsoft Visual C++ redistributables. PyInstaller bundles the interpreter but relies on system runtimes.
- **Antivirus false positives:** Sign the executable when distributing to customers; CI output is unsigned. Consider submitting the binary to Microsoft Defender for pre-approval.
- **Stale virtual environment:** Delete `.venv/` if the build script reports inconsistent package versions.
- **Spec updates ignored:** Remove `build/` and `dist/` folders to force PyInstaller to regenerate caches after editing the spec.

## Future Enhancements
- Automate icon/resource inclusion inside the spec once assets are finalized.
- Capture build metadata (git commit, build time) and embed it into the executable via a version resource.
- Extend CI to produce non-onefile archives for faster startup if customer feedback prefers unpacked builds.
