from __future__ import annotations

from typing import Any

import pytest

from scripts.augment_release_sbom import augment_release_sbom


def _environment_sbom() -> dict[str, Any]:
    components = [
        {
            "bom-ref": "silverestimate==3.7",
            "externalReferences": [
                {
                    "type": "distribution",
                    "url": "file:///D:/Projects/Silver%20Estimate",
                },
                {
                    "type": "website",
                    "url": "https://example.invalid/silverestimate",
                },
            ],
            "name": "silverestimate",
            "type": "library",
            "version": "3.7",
        }
    ]
    components.extend(
        {
            "bom-ref": f"{name}==6.11.1",
            "name": name,
            "type": "library",
            "version": "6.11.1",
        }
        for name in (
            "PySide6",
            "PySide6_Addons",
            "PySide6_Essentials",
            "shiboken6",
        )
    )
    components.append(
        {
            "bom-ref": "sqlcipher3==0.6.2",
            "externalReferences": [
                {
                    "type": "distribution",
                    "url": "file:///D:/Projects/Silver%20Estimate/vendor/sqlcipher.whl",
                }
            ],
            "name": "sqlcipher3",
            "type": "library",
            "version": "0.6.2",
        }
    )
    return {
        "bomFormat": "CycloneDX",
        "components": components,
        "dependencies": [
            {
                "dependsOn": ["PySide6==6.11.1"],
                "ref": "silverestimate==3.7",
            }
        ],
        "metadata": {},
        "specVersion": "1.6",
        "version": 1,
    }


def test_augment_release_sbom_adds_application_python_and_native_qt() -> None:
    document = augment_release_sbom(
        _environment_sbom(),
        app_version="3.07",
        python_version="3.14.4",
        qt_version="6.11.1",
    )

    application = document["metadata"]["component"]
    assert application["name"] == "Silver Estimate"
    assert application["version"] == "3.07"
    assert not any(
        reference["url"].startswith("file:")
        for reference in application["externalReferences"]
    )

    versions = {
        component["name"]: component["version"] for component in document["components"]
    }
    assert versions["CPython"] == "3.14.4"
    assert versions["Qt"] == "6.11.1"
    sqlcipher = next(
        component
        for component in document["components"]
        if component["name"] == "sqlcipher3"
    )
    assert "externalReferences" not in sqlcipher
    root_dependency = next(
        dependency
        for dependency in document["dependencies"]
        if dependency["ref"] == "pkg:generic/silverestimate@3.07"
    )
    assert "pkg:generic/cpython@3.14.4" in root_dependency["dependsOn"]
    assert "pkg:generic/qt@6.11.1" in root_dependency["dependsOn"]


def test_augment_release_sbom_rejects_mismatched_qt_wheel() -> None:
    document = _environment_sbom()
    pyside = next(
        component
        for component in document["components"]
        if component["name"] == "PySide6"
    )
    pyside["version"] = "6.10.0"

    with pytest.raises(ValueError, match="expected 6.11.1"):
        augment_release_sbom(
            document,
            app_version="3.07",
            python_version="3.14.4",
            qt_version="6.11.1",
        )
