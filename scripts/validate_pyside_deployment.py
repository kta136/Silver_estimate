"""Validate the required contents of a pyside6-deploy standalone artifact."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

REQUIRED_FILES = (
    "main.exe",
    "assets/icons/silverestimate.ico",
    "license",
    "third_party_notices.md",
    "vendor/sqlcipher/provenance.json",
    "sqlcipher3/_sqlite3.pyd",
    "pyside6.abi3.dll",
    "shiboken6.abi3.dll",
    "qt6core.dll",
    "qt6gui.dll",
    "qt6printsupport.dll",
    "qt6svg.dll",
    "qt6widgets.dll",
    "pyside6/qt-plugins/iconengines/qsvgicon.dll",
    "pyside6/qt-plugins/imageformats/qgif.dll",
    "pyside6/qt-plugins/imageformats/qico.dll",
    "pyside6/qt-plugins/imageformats/qjpeg.dll",
    "pyside6/qt-plugins/imageformats/qsvg.dll",
    "pyside6/qt-plugins/platforms/qwindows.dll",
    "pyside6/qt-plugins/styles/qmodernwindowsstyle.dll",
)

FORBIDDEN_PATH_FRAGMENTS = (
    "/passlib/",
    "pyqt6",
    "/qml/",
    "qt6bluetooth",
    "qt6multimedia",
    "qt6qml",
    "qt6quick",
    "qt6webengine",
    "/qcertonlybackend.dll",
    "/qdirect2d.dll",
    "/qicns.dll",
    "/qminimal.dll",
    "/qoffscreen.dll",
    "/qopensslbackend.dll",
    "/qpdf.dll",
    "/qschannelbackend.dll",
    "/qtga.dll",
    "/qtiff.dll",
    "/qwbmp.dll",
    "/qwebp.dll",
)

REQUIRED_REPORT_MODULES = (
    "argon2._password_hasher",
    "keyring.backends.Windows",
    "keyring.backends.fail",
    "keyring.backends.null",
    "sqlcipher3._sqlite3",
    "sqlcipher3.dbapi2",
)

FORBIDDEN_REPORT_MODULE_PREFIXES = (
    "PyQt6",
    "passlib",
)


def deployment_inventory(root: Path) -> dict[str, Path]:
    """Return a case-insensitive relative-path inventory for ``root``."""
    return {
        path.relative_to(root).as_posix().lower(): path
        for path in root.rglob("*")
        if path.is_file()
    }


def validate_deployment(root: Path, report: Path) -> dict[str, int]:
    """Validate deployment contents and return summary metrics."""
    if not root.is_dir():
        raise ValueError(f"Standalone deployment directory is missing: {root}")
    if not report.is_file():
        raise ValueError(f"Nuitka compilation report is missing: {report}")

    inventory = deployment_inventory(root)
    missing = sorted(set(REQUIRED_FILES).difference(inventory))
    if missing:
        raise ValueError(f"Required deployment files are missing: {missing}")

    forbidden = sorted(
        relative_path
        for relative_path in inventory
        if any(fragment in f"/{relative_path}" for fragment in FORBIDDEN_PATH_FRAGMENTS)
    )
    if forbidden:
        raise ValueError(f"Forbidden deployment files are present: {forbidden}")

    report_text = report.read_text(encoding="utf-8")
    missing_modules = [
        module
        for module in REQUIRED_REPORT_MODULES
        if f'name="{module}"' not in report_text
    ]
    if missing_modules:
        raise ValueError(
            f"Required modules are absent from the Nuitka report: {missing_modules}"
        )
    forbidden_modules = [
        prefix
        for prefix in FORBIDDEN_REPORT_MODULE_PREFIXES
        if f'name="{prefix}' in report_text
    ]
    if forbidden_modules:
        raise ValueError(
            "The Nuitka report unexpectedly contains forbidden modules: "
            f"{forbidden_modules}"
        )

    return {
        "file_count": len(inventory),
        "total_bytes": sum(path.stat().st_size for path in inventory.values()),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--standalone-dir", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()

    summary = validate_deployment(
        args.standalone_dir.resolve(),
        args.report.resolve(),
    )
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
