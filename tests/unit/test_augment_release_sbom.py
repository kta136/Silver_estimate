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


def _provenance() -> dict[str, Any]:
    return {
        "sources": {
            "openssl": {
                "license": "Apache-2.0",
                "revision": "openssl-revision",
                "version": "3.6.0",
            },
            "sqlcipher": {
                "license": "BSD-3-Clause",
                "revision": "sqlcipher-revision",
                "version": "4.17.0",
            },
        }
    }


def test_augment_release_sbom_adds_application_python_and_native_qt() -> None:
    document = augment_release_sbom(
        _environment_sbom(),
        app_version="3.07",
        python_version="3.14.4",
        qt_version="6.11.1",
        provenance=_provenance(),
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
    assert versions["SQLCipher"] == "4.17.0"
    assert versions["OpenSSL"] == "3.6.0"
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
    sqlcipher_dependency = next(
        dependency
        for dependency in document["dependencies"]
        if dependency["ref"] == "sqlcipher3==0.6.2"
    )
    assert sqlcipher_dependency["dependsOn"] == [
        "pkg:generic/openssl@3.6.0",
        "pkg:generic/sqlcipher@4.17.0",
    ]

    qt = next(
        component for component in document["components"] if component["name"] == "Qt"
    )
    assert qt["licenses"] == [
        {"expression": "LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only"}
    ]


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
            provenance=_provenance(),
        )
