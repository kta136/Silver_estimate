"""Enforce the locked dependency, advisory, license, and notice policy."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import date
from pathlib import Path
from typing import Any

POLICY_KEYS = {
    "advisory_ignores",
    "allowed_licenses",
    "audit_skip_allowlist",
    "lock_review",
    "native_provenance",
    "required_attributions",
    "required_native_components",
    "schema_version",
}
IGNORE_KEYS = {"advisory_id", "expires", "owner", "rationale"}
SKIP_KEYS = {"control", "expires", "owner", "package", "rationale"}
LOCK_REVIEW_KEYS = {"rationale", "reviewed_by", "reviewed_on", "sha256"}
ATTRIBUTION_KEYS = {"component", "path", "required_text"}
NATIVE_COMPONENT_KEYS = {"license", "name"}
NATIVE_PROVENANCE_KEYS = {"path", "required_sources"}
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
PACKAGE_SEPARATOR_PATTERN = re.compile(r"[-_.]+")


class DependencyPolicyError(ValueError):
    """Raised when dependency policy data or evidence violates the contract."""


def normalize_package_name(value: str) -> str:
    """Return the PEP 503-normalized form used to compare package names."""
    return PACKAGE_SEPARATOR_PATTERN.sub("-", value).lower()


def _require_mapping(value: object, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise DependencyPolicyError(f"{label} must be an object")
    return value


def _require_list(value: object, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise DependencyPolicyError(f"{label} must be a list")
    return value


def _require_text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise DependencyPolicyError(f"{label} must be a non-empty string")
    return value.strip()


def _require_exact_keys(
    value: dict[str, Any],
    expected: set[str],
    label: str,
) -> None:
    missing = sorted(expected.difference(value))
    extra = sorted(set(value).difference(expected))
    if missing or extra:
        raise DependencyPolicyError(
            f"{label} has invalid fields; missing={missing}, extra={extra}"
        )


def _policy_date(value: object, label: str) -> date:
    text = _require_text(value, label)
    try:
        return date.fromisoformat(text)
    except ValueError as exc:
        raise DependencyPolicyError(f"{label} must use YYYY-MM-DD") from exc


def _ensure_not_expired(record: dict[str, Any], label: str, today: date) -> None:
    expires = _policy_date(record["expires"], f"{label}.expires")
    if expires < today:
        raise DependencyPolicyError(f"{label} expired on {expires.isoformat()}")


def _validate_allowed_licenses(policy: dict[str, Any]) -> list[str]:
    raw_licenses = _require_list(policy["allowed_licenses"], "policy.allowed_licenses")
    licenses = [
        _require_text(value, f"policy.allowed_licenses[{index}]")
        for index, value in enumerate(raw_licenses)
    ]
    if not licenses or len(licenses) != len(set(licenses)):
        raise DependencyPolicyError(
            "policy.allowed_licenses must be non-empty and unique"
        )
    return licenses


def _validate_advisory_ignores(policy: dict[str, Any], today: date) -> None:
    advisory_ids: set[str] = set()
    for index, raw_ignore in enumerate(
        _require_list(policy["advisory_ignores"], "policy.advisory_ignores")
    ):
        label = f"policy.advisory_ignores[{index}]"
        ignore = _require_mapping(raw_ignore, label)
        _require_exact_keys(ignore, IGNORE_KEYS, label)
        advisory_id = _require_text(
            ignore["advisory_id"], f"{label}.advisory_id"
        ).upper()
        if advisory_id in advisory_ids:
            raise DependencyPolicyError(f"duplicate advisory ignore: {advisory_id}")
        advisory_ids.add(advisory_id)
        _require_text(ignore["rationale"], f"{label}.rationale")
        _require_text(ignore["owner"], f"{label}.owner")
        _ensure_not_expired(ignore, label, today)


def _validate_audit_skips(policy: dict[str, Any], today: date) -> None:
    skipped_packages: set[str] = set()
    for index, raw_skip in enumerate(
        _require_list(policy["audit_skip_allowlist"], "policy.audit_skip_allowlist")
    ):
        label = f"policy.audit_skip_allowlist[{index}]"
        skip = _require_mapping(raw_skip, label)
        _require_exact_keys(skip, SKIP_KEYS, label)
        package = normalize_package_name(
            _require_text(skip["package"], f"{label}.package")
        )
        if package in skipped_packages:
            raise DependencyPolicyError(f"duplicate audit skip: {package}")
        skipped_packages.add(package)
        _require_text(skip["rationale"], f"{label}.rationale")
        _require_text(skip["owner"], f"{label}.owner")
        _require_text(skip["control"], f"{label}.control")
        _ensure_not_expired(skip, label, today)


def _validate_lock_review_record(policy: dict[str, Any], today: date) -> None:
    lock_review = _require_mapping(policy["lock_review"], "policy.lock_review")
    _require_exact_keys(lock_review, LOCK_REVIEW_KEYS, "policy.lock_review")
    sha256 = _require_text(lock_review["sha256"], "policy.lock_review.sha256")
    if not SHA256_PATTERN.fullmatch(sha256):
        raise DependencyPolicyError(
            "policy.lock_review.sha256 must be a lowercase SHA-256 digest"
        )
    reviewed_on = _policy_date(
        lock_review["reviewed_on"], "policy.lock_review.reviewed_on"
    )
    if reviewed_on > today:
        raise DependencyPolicyError("policy.lock_review.reviewed_on is in the future")
    _require_text(lock_review["reviewed_by"], "policy.lock_review.reviewed_by")
    _require_text(lock_review["rationale"], "policy.lock_review.rationale")


def _validate_attribution_records(policy: dict[str, Any]) -> None:
    attributions = _require_list(
        policy["required_attributions"], "policy.required_attributions"
    )
    if not attributions:
        raise DependencyPolicyError("policy.required_attributions must be non-empty")
    for index, raw_attribution in enumerate(attributions):
        label = f"policy.required_attributions[{index}]"
        attribution = _require_mapping(raw_attribution, label)
        _require_exact_keys(attribution, ATTRIBUTION_KEYS, label)
        for key in ATTRIBUTION_KEYS:
            _require_text(attribution[key], f"{label}.{key}")


def _validate_native_component_records(
    policy: dict[str, Any],
    allowed_licenses: list[str],
) -> None:
    native_names: set[str] = set()
    native_components = _require_list(
        policy["required_native_components"],
        "policy.required_native_components",
    )
    if not native_components:
        raise DependencyPolicyError(
            "policy.required_native_components must be non-empty"
        )
    for index, raw_component in enumerate(native_components):
        label = f"policy.required_native_components[{index}]"
        component = _require_mapping(raw_component, label)
        _require_exact_keys(component, NATIVE_COMPONENT_KEYS, label)
        name = normalize_package_name(_require_text(component["name"], f"{label}.name"))
        if name in native_names:
            raise DependencyPolicyError(f"duplicate native component: {name}")
        native_names.add(name)
        license_value = _require_text(component["license"], f"{label}.license")
        if license_value not in allowed_licenses:
            raise DependencyPolicyError(
                f"{label}.license is absent from allowed_licenses: {license_value}"
            )


def _validate_native_provenance_record(policy: dict[str, Any]) -> None:
    native_provenance = _require_mapping(
        policy["native_provenance"], "policy.native_provenance"
    )
    _require_exact_keys(
        native_provenance,
        NATIVE_PROVENANCE_KEYS,
        "policy.native_provenance",
    )
    _require_text(native_provenance["path"], "policy.native_provenance.path")
    required_sources = [
        _require_text(value, f"policy.native_provenance.required_sources[{index}]")
        for index, value in enumerate(
            _require_list(
                native_provenance["required_sources"],
                "policy.native_provenance.required_sources",
            )
        )
    ]
    if not required_sources or len(required_sources) != len(set(required_sources)):
        raise DependencyPolicyError(
            "policy.native_provenance.required_sources must be non-empty and unique"
        )


def validate_policy(policy: dict[str, Any], *, today: date | None = None) -> None:
    """Validate the strict policy schema and time-bounded exceptions."""
    current_date = today or date.today()
    _require_exact_keys(policy, POLICY_KEYS, "policy")
    if policy["schema_version"] != 1:
        raise DependencyPolicyError("policy.schema_version must be 1")
    allowed_licenses = _validate_allowed_licenses(policy)
    _validate_advisory_ignores(policy, current_date)
    _validate_audit_skips(policy, current_date)
    _validate_lock_review_record(policy, current_date)
    _validate_attribution_records(policy)
    _validate_native_component_records(policy, allowed_licenses)
    _validate_native_provenance_record(policy)


def _load_json(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise DependencyPolicyError(f"cannot read {label} at {path}: {exc}") from exc
    return _require_mapping(value, label)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_lock_review(
    policy: dict[str, Any],
    lockfile: Path,
) -> None:
    """Require the current lockfile bytes to match the reviewed digest."""
    expected = str(policy["lock_review"]["sha256"])
    actual = _sha256(lockfile)
    if actual != expected:
        raise DependencyPolicyError(
            "uv.lock changed without an accompanying dependency review: "
            f"expected {expected}, got {actual}"
        )


def _repository_path(repo_root: Path, relative_path: object, label: str) -> Path:
    relative = Path(_require_text(relative_path, label))
    candidate = (repo_root / relative).resolve()
    if not candidate.is_relative_to(repo_root):
        raise DependencyPolicyError(f"{label} escapes the repository: {relative}")
    return candidate


def validate_attributions(
    policy: dict[str, Any],
    repo_root: Path,
) -> None:
    """Require every configured release attribution marker."""
    for index, raw_attribution in enumerate(policy["required_attributions"]):
        attribution = _require_mapping(
            raw_attribution, f"policy.required_attributions[{index}]"
        )
        path = _repository_path(
            repo_root,
            attribution["path"],
            f"policy.required_attributions[{index}].path",
        )
        try:
            content = path.read_text(encoding="utf-8")
        except OSError as exc:
            raise DependencyPolicyError(
                f"required attribution file is unavailable: {path}"
            ) from exc
        required_text = str(attribution["required_text"])
        if required_text not in content:
            raise DependencyPolicyError(
                f"{attribution['component']} attribution is missing from {path}"
            )


def validate_native_provenance(
    policy: dict[str, Any],
    repo_root: Path,
) -> None:
    """Require controlled native sources, licenses, and binary inventory."""
    configuration = policy["native_provenance"]
    path = _repository_path(
        repo_root,
        configuration["path"],
        "policy.native_provenance.path",
    )
    provenance = _load_json(path, "native provenance")
    sources = _require_mapping(provenance.get("sources"), "native provenance.sources")
    allowed_licenses = set(policy["allowed_licenses"])
    for source_name in configuration["required_sources"]:
        source = _require_mapping(
            sources.get(source_name),
            f"native provenance.sources.{source_name}",
        )
        license_value = _require_text(
            source.get("license"),
            f"native provenance.sources.{source_name}.license",
        )
        if license_value not in allowed_licenses:
            raise DependencyPolicyError(
                f"native source {source_name} has disallowed license {license_value}"
            )
        _require_text(
            source.get("version"),
            f"native provenance.sources.{source_name}.version",
        )
        _require_text(
            source.get("revision"),
            f"native provenance.sources.{source_name}.revision",
        )
    build = _require_mapping(provenance.get("build"), "native provenance.build")
    inventory = _require_list(
        build.get("native_inventory"), "native provenance.build.native_inventory"
    )
    if not inventory:
        raise DependencyPolicyError("native provenance has no binary inventory")


def validate_audit_report(
    policy: dict[str, Any],
    report: dict[str, Any],
) -> dict[str, int]:
    """Reject unresolved advisories and unapproved audit skips."""
    ignores = {
        str(entry["advisory_id"]).upper(): entry for entry in policy["advisory_ignores"]
    }
    allowed_skips = {
        normalize_package_name(str(entry["package"])): entry
        for entry in policy["audit_skip_allowlist"]
    }
    dependencies = _require_list(report.get("dependencies"), "audit.dependencies")
    if not dependencies:
        raise DependencyPolicyError("audit.dependencies must be non-empty")
    vulnerabilities = 0
    ignored = 0
    skipped = 0
    unresolved: list[str] = []

    for index, raw_dependency in enumerate(dependencies):
        dependency = _require_mapping(raw_dependency, f"audit.dependencies[{index}]")
        package = normalize_package_name(
            _require_text(dependency.get("name"), f"audit.dependencies[{index}].name")
        )
        skip_reason = dependency.get("skip_reason")
        if skip_reason:
            _require_text(skip_reason, f"audit.dependencies[{index}].skip_reason")
            if package not in allowed_skips:
                unresolved.append(f"{package}: unapproved audit skip")
            skipped += 1
            continue

        version = _require_text(
            dependency.get("version"), f"audit.dependencies[{index}].version"
        )
        for vulnerability_index, raw_vulnerability in enumerate(
            _require_list(
                dependency.get("vulns"),
                f"audit.dependencies[{index}].vulns",
            )
        ):
            vulnerability = _require_mapping(
                raw_vulnerability,
                (f"audit.dependencies[{index}].vulns[{vulnerability_index}]"),
            )
            advisory_id = _require_text(
                vulnerability.get("id"),
                (f"audit.dependencies[{index}].vulns[{vulnerability_index}].id"),
            ).upper()
            aliases = {
                _require_text(
                    alias,
                    (
                        f"audit.dependencies[{index}]"
                        f".vulns[{vulnerability_index}].aliases"
                    ),
                ).upper()
                for alias in _require_list(
                    vulnerability.get("aliases", []),
                    (
                        f"audit.dependencies[{index}]"
                        f".vulns[{vulnerability_index}].aliases"
                    ),
                )
            }
            vulnerabilities += 1
            if {advisory_id, *aliases}.intersection(ignores):
                ignored += 1
            else:
                unresolved.append(f"{package}=={version}: {advisory_id}")

    if unresolved:
        raise DependencyPolicyError(
            "dependency audit policy failed: " + "; ".join(sorted(unresolved))
        )
    return {
        "dependencies": len(dependencies),
        "ignored_vulnerabilities": ignored,
        "skipped_dependencies": skipped,
        "vulnerabilities": vulnerabilities,
    }


def _component_license_values(component: dict[str, Any]) -> set[str]:
    values: set[str] = set()
    for raw_license in _require_list(
        component.get("licenses", []),
        f"SBOM component {component.get('name', '<unknown>')} licenses",
    ):
        license_entry = _require_mapping(raw_license, "SBOM license")
        expression = license_entry.get("expression")
        if isinstance(expression, str) and expression.strip():
            values.add(expression.strip())
        declared = license_entry.get("license")
        if isinstance(declared, dict):
            identifier = declared.get("id") or declared.get("name")
            if isinstance(identifier, str) and identifier.strip():
                values.add(identifier.strip())
    return values


def validate_sbom(
    policy: dict[str, Any],
    report: dict[str, Any],
    sbom: dict[str, Any],
) -> dict[str, int]:
    """Require licenses for audited runtime and controlled native components."""
    if sbom.get("bomFormat") != "CycloneDX":
        raise DependencyPolicyError("release SBOM is not CycloneDX")
    application = _require_mapping(
        _require_mapping(sbom.get("metadata"), "SBOM metadata").get("component"),
        "SBOM metadata.component",
    )
    if application.get("name") != "Silver Estimate":
        raise DependencyPolicyError(
            "release SBOM metadata.component must identify Silver Estimate"
        )

    components = [
        _require_mapping(component, f"SBOM components[{index}]")
        for index, component in enumerate(
            _require_list(sbom.get("components"), "SBOM components")
        )
    ]
    components_by_name: dict[str, dict[str, Any]] = {}
    for component in components:
        name = normalize_package_name(
            _require_text(component.get("name"), "SBOM component.name")
        )
        if name in components_by_name:
            raise DependencyPolicyError(f"duplicate SBOM component name: {name}")
        components_by_name[name] = component

    runtime_names = {
        normalize_package_name(
            _require_text(dependency.get("name"), "audit dependency.name")
        )
        for dependency in (
            _require_mapping(item, "audit dependency")
            for item in _require_list(report.get("dependencies"), "audit.dependencies")
        )
    }
    required_native = {
        normalize_package_name(str(component["name"])): str(component["license"])
        for component in policy["required_native_components"]
    }
    required_names = runtime_names | set(required_native)
    allowed_licenses = set(policy["allowed_licenses"])

    for name in sorted(required_names):
        required_component = components_by_name.get(name)
        if required_component is None:
            raise DependencyPolicyError(
                f"release SBOM is missing required component {name}"
            )
        licenses = _component_license_values(required_component)
        if not licenses:
            raise DependencyPolicyError(
                f"release SBOM component {name} has no declared license"
            )
        disallowed = sorted(licenses.difference(allowed_licenses))
        if disallowed:
            raise DependencyPolicyError(
                f"release SBOM component {name} has disallowed licenses {disallowed}"
            )
        expected_native_license = required_native.get(name)
        if expected_native_license and expected_native_license not in licenses:
            raise DependencyPolicyError(
                f"release SBOM component {name} does not declare "
                f"{expected_native_license}"
            )

    return {
        "licensed_runtime_components": len(runtime_names),
        "native_components": len(required_native),
        "sbom_components": len(components),
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate Silver Estimate dependency-policy evidence."
    )
    parser.add_argument(
        "--policy",
        type=Path,
        default=Path("config/dependency-policy.json"),
    )
    parser.add_argument("--audit-report", type=Path, required=True)
    parser.add_argument("--lockfile", type=Path, default=Path("uv.lock"))
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--sbom", type=Path)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    try:
        repo_root = args.repo_root.resolve()
        policy = _load_json(args.policy.resolve(), "dependency policy")
        report = _load_json(args.audit_report.resolve(), "pip-audit report")
        validate_policy(policy)
        validate_lock_review(policy, args.lockfile.resolve())
        validate_attributions(policy, repo_root)
        validate_native_provenance(policy, repo_root)
        summary = validate_audit_report(policy, report)
        if args.sbom:
            summary.update(
                validate_sbom(
                    policy,
                    report,
                    _load_json(args.sbom.resolve(), "release SBOM"),
                )
            )
    except (DependencyPolicyError, OSError) as exc:
        print(f"dependency policy failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
