from pathlib import Path

import pytest

from scripts import validate_pyside_deployment as deployment_validator


def _write_deployment(root: Path) -> None:
    for relative_path in deployment_validator.REQUIRED_FILES:
        target = root / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"deployment-test")


def _write_report(path: Path) -> None:
    modules = "".join(
        f'<module name="{module}" />'
        for module in deployment_validator.REQUIRED_REPORT_MODULES
    )
    path.write_text(f"<report>{modules}</report>", encoding="utf-8")


def test_validate_deployment_accepts_required_inventory(tmp_path):
    root = tmp_path / "SilverEstimate.dist"
    report = tmp_path / "nuitka-report.xml"
    _write_deployment(root)
    _write_report(report)

    result = deployment_validator.validate_deployment(root, report)

    assert result["file_count"] == len(deployment_validator.REQUIRED_FILES)
    assert result["total_bytes"] > 0


def test_validate_deployment_rejects_forbidden_plugin(tmp_path):
    root = tmp_path / "SilverEstimate.dist"
    report = tmp_path / "nuitka-report.xml"
    _write_deployment(root)
    _write_report(report)
    forbidden = root / "PySide6" / "qt-plugins" / "platforms" / "qoffscreen.dll"
    forbidden.parent.mkdir(parents=True, exist_ok=True)
    forbidden.write_bytes(b"forbidden")

    with pytest.raises(ValueError, match="qoffscreen"):
        deployment_validator.validate_deployment(root, report)
