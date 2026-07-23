"""Add application and native-runtime identity to a CycloneDX environment SBOM."""

from __future__ import annotations

import argparse
import json
import platform
from pathlib import Path
from typing import Any

from PySide6.QtCore import qVersion

from silverestimate.infrastructure.app_constants import APP_VERSION

QT_WHEEL_COMPONENTS = (
    "PySide6",
    "PySide6_Addons",
    "PySide6_Essentials",
    "shiboken6",
)
QT_RUNTIME_MODULES = ("Core", "Gui", "PrintSupport", "Svg", "Widgets")


def _require_component_version(
    components: list[dict[str, Any]],
    name: str,
    expected_version: str,
) -> None:
    component = next(
        (item for item in components if item.get("name") == name),
        None,
    )
    if component is None:
        raise ValueError(f"SBOM is missing required component {name}")
    actual_version = str(component.get("version", ""))
    if actual_version != expected_version:
        raise ValueError(
            f"SBOM component {name} is {actual_version}, expected {expected_version}"
        )


def _replace_dependency_ref(
    dependencies: list[dict[str, Any]],
    old_ref: str,
    new_ref: str,
) -> None:
    for dependency in dependencies:
        if dependency.get("ref") == old_ref:
            dependency["ref"] = new_ref
        dependency["dependsOn"] = [
            new_ref if item == old_ref else item
            for item in dependency.get("dependsOn", [])
        ]


def _extract_application_component(
    document: dict[str, Any],
    app_version: str,
) -> tuple[dict[str, Any], str, str]:
    components = document["components"]
    application = next(
        (
            component
            for component in components
            if str(component.get("name", "")).lower() == "silverestimate"
        ),
        None,
    )
    if application is None:
        raise ValueError("SBOM is missing the silverestimate project component")

    components.remove(application)
    old_ref = str(application.get("bom-ref", "silverestimate"))
    new_ref = f"pkg:generic/silverestimate@{app_version}"
    application.update(
        {
            "bom-ref": new_ref,
            "name": "Silver Estimate",
            "purl": new_ref,
            "type": "application",
            "version": app_version,
        }
    )
    application["properties"] = [
        {
            "name": "silverestimate:artifact-scope",
            "value": "Windows one-file application",
        },
        {
            "name": "silverestimate:qt-binding",
            "value": "PySide6",
        },
    ]
    return application, old_ref, new_ref


def _remove_local_distribution_references(
    components: list[dict[str, Any]],
) -> None:
    for component in components:
        component["externalReferences"] = [
            reference
            for reference in component.get("externalReferences", [])
            if not (
                reference.get("type") == "distribution"
                and str(reference.get("url", "")).startswith("file:")
            )
        ]
        if not component["externalReferences"]:
            component.pop("externalReferences")


def _native_components(
    *,
    python_version: str,
    qt_version: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    python_ref = f"pkg:generic/cpython@{python_version}"
    qt_ref = f"pkg:generic/qt@{qt_version}"
    python_component: dict[str, Any] = {
        "bom-ref": python_ref,
        "externalReferences": [
            {
                "type": "distribution",
                "url": f"https://www.python.org/downloads/release/python-{python_version.replace('.', '')}/",
            },
            {
                "type": "license",
                "url": "https://docs.python.org/3/license.html",
            },
        ],
        "group": "Python Software Foundation",
        "licenses": [{"license": {"id": "PSF-2.0"}}],
        "name": "CPython",
        "properties": [
            {
                "name": "silverestimate:artifact-role",
                "value": "embedded interpreter",
            }
        ],
        "purl": python_ref,
        "type": "platform",
        "version": python_version,
    }
    qt_component: dict[str, Any] = {
        "bom-ref": qt_ref,
        "externalReferences": [
            {
                "type": "license",
                "url": "https://doc.qt.io/qtforpython-6/licenses.html",
            },
            {
                "type": "website",
                "url": "https://www.qt.io/product/qt6",
            },
        ],
        "group": "The Qt Company",
        "name": "Qt",
        "properties": [
            {
                "name": "silverestimate:artifact-role",
                "value": "native Windows runtime",
            },
            {
                "name": "silverestimate:included-modules",
                "value": ",".join(QT_RUNTIME_MODULES),
            },
        ],
        "purl": qt_ref,
        "type": "framework",
        "version": qt_version,
    }
    return python_component, qt_component


def augment_release_sbom(
    document: dict[str, Any],
    *,
    app_version: str,
    python_version: str,
    qt_version: str,
) -> dict[str, Any]:
    """Return an augmented CycloneDX document and validate selected versions."""
    if document.get("bomFormat") != "CycloneDX":
        raise ValueError("Expected a CycloneDX SBOM")
    components = document.get("components")
    dependencies = document.get("dependencies")
    if not isinstance(components, list) or not isinstance(dependencies, list):
        raise ValueError("SBOM components and dependencies must be lists")

    for package_name in QT_WHEEL_COMPONENTS:
        _require_component_version(components, package_name, qt_version)

    application, old_app_ref, app_ref = _extract_application_component(
        document,
        app_version,
    )
    _remove_local_distribution_references([application, *components])
    _replace_dependency_ref(dependencies, old_app_ref, app_ref)

    python_component, qt_component = _native_components(
        python_version=python_version,
        qt_version=qt_version,
    )
    native_refs = (python_component["bom-ref"], qt_component["bom-ref"])
    existing_names = {str(component.get("name")) for component in components}
    if "CPython" not in existing_names:
        components.append(python_component)
    if "Qt" not in existing_names:
        components.append(qt_component)

    root_dependency = next(
        (dependency for dependency in dependencies if dependency.get("ref") == app_ref),
        None,
    )
    if root_dependency is None:
        root_dependency = {"ref": app_ref, "dependsOn": []}
        dependencies.append(root_dependency)
    root_dependency["dependsOn"] = sorted(
        set(root_dependency.get("dependsOn", ())) | set(native_refs)
    )
    existing_dependency_refs = {
        str(dependency.get("ref")) for dependency in dependencies
    }
    for native_ref in native_refs:
        if native_ref not in existing_dependency_refs:
            dependencies.append({"ref": native_ref, "dependsOn": []})

    metadata = document.setdefault("metadata", {})
    metadata["component"] = application
    metadata["properties"] = [
        {
            "name": "silverestimate:sbom-scope",
            "value": "locked build environment plus declared frozen native runtime",
        }
    ]
    components.sort(key=lambda component: str(component.get("bom-ref", "")))
    dependencies.sort(key=lambda dependency: str(dependency.get("ref", "")))
    validate_release_sbom(
        document,
        app_version=app_version,
        python_version=python_version,
        qt_version=qt_version,
    )
    return document


def validate_release_sbom(
    document: dict[str, Any],
    *,
    app_version: str,
    python_version: str,
    qt_version: str,
) -> None:
    """Fail when application, Python, Qt, or Qt wheel identity is incomplete."""
    application = document.get("metadata", {}).get("component", {})
    if application.get("name") != "Silver Estimate":
        raise ValueError("SBOM metadata.component does not identify Silver Estimate")
    if application.get("version") != app_version:
        raise ValueError("SBOM application version does not match APP_VERSION")

    components = document.get("components", [])
    for package_name in QT_WHEEL_COMPONENTS:
        _require_component_version(components, package_name, qt_version)
    _require_component_version(components, "CPython", python_version)
    _require_component_version(components, "Qt", qt_version)

    component_refs = [str(component.get("bom-ref", "")) for component in components]
    if len(component_refs) != len(set(component_refs)):
        raise ValueError("SBOM contains duplicate component references")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Add Silver Estimate, CPython, and native Qt identity to an SBOM."
    )
    parser.add_argument("--sbom", required=True, type=Path)
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    source_path: Path = args.sbom.resolve()
    output_path: Path = (args.output or args.sbom).resolve()
    document = json.loads(source_path.read_text(encoding="utf-8"))
    python_version = platform.python_version()
    qt_version = qVersion()
    augment_release_sbom(
        document,
        app_version=APP_VERSION,
        python_version=python_version,
        qt_version=qt_version,
    )
    temporary_path = output_path.with_suffix(f"{output_path.suffix}.tmp")
    temporary_path.write_text(
        json.dumps(document, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary_path.replace(output_path)
    print(
        json.dumps(
            {
                "application": APP_VERSION,
                "components": len(document["components"]),
                "python": python_version,
                "qt": qt_version,
                "sbom": str(output_path),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
