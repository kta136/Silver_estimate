from __future__ import annotations

import copy
import hashlib
import json
from datetime import date
from pathlib import Path
from typing import Any

import pytest

from scripts.check_dependency_policy import (
    DependencyPolicyError,
    validate_attributions,
    validate_audit_report,
    validate_lock_review,
    validate_native_provenance,
    validate_policy,
    validate_sbom,
)

TODAY = date(2026, 7, 30)


def _write_repository(tmp_path: Path) -> tuple[Path, Path]:
    lockfile = tmp_path / "uv.lock"
    lockfile.write_text("version = 1\n", encoding="utf-8")
    notices = tmp_path / "THIRD_PARTY_NOTICES.md"
    notices.write_text("Controlled component notice\n", encoding="utf-8")
    provenance_dir = tmp_path / "vendor" / "sqlcipher"
    provenance_dir.mkdir(parents=True)
    provenance = provenance_dir / "PROVENANCE.json"
    provenance.write_text(
        json.dumps(
            {
                "build": {
                    "native_inventory": [
                        {
                            "path": "sqlcipher3/_sqlite3.pyd",
                            "sha256": "a" * 64,
                            "size": 1,
                        }
                    ]
                },
                "sources": {
                    "sqlcipher": {
                        "license": "BSD-3-Clause",
                        "revision": "revision",
                        "version": "4.17.0",
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    return lockfile, notices


def _policy(lockfile: Path) -> dict[str, Any]:
    return {
        "advisory_ignores": [],
        "allowed_licenses": ["BSD-3-Clause", "MIT", "PSF-2.0"],
        "audit_skip_allowlist": [
            {
                "control": "Controlled native artifact verification.",
                "expires": "2027-07-30",
                "owner": "release maintainer",
                "package": "sqlcipher3",
                "rationale": "Private wheel.",
            }
        ],
        "lock_review": {
            "rationale": "Reviewed dependency change.",
            "reviewed_by": "project maintainer",
            "reviewed_on": "2026-07-30",
            "sha256": hashlib.sha256(lockfile.read_bytes()).hexdigest(),
        },
        "native_provenance": {
            "path": "vendor/sqlcipher/PROVENANCE.json",
            "required_sources": ["sqlcipher"],
        },
        "required_attributions": [
            {
                "component": "Controlled component",
                "path": "THIRD_PARTY_NOTICES.md",
                "required_text": "Controlled component notice",
            }
        ],
        "required_native_components": [{"license": "PSF-2.0", "name": "CPython"}],
        "schema_version": 1,
    }


def _audit_report() -> dict[str, Any]:
    return {
        "dependencies": [
            {"name": "argon2-cffi", "version": "25.1.0", "vulns": []},
            {
                "name": "sqlcipher3",
                "skip_reason": "Dependency is not available on PyPI.",
            },
        ],
        "fixes": [],
    }


def _sbom() -> dict[str, Any]:
    return {
        "bomFormat": "CycloneDX",
        "components": [
            {
                "name": "argon2-cffi",
                "version": "25.1.0",
                "licenses": [{"license": {"id": "MIT"}}],
            },
            {
                "name": "sqlcipher3",
                "version": "0.6.2",
                "licenses": [{"license": {"id": "MIT"}}],
            },
            {
                "name": "CPython",
                "version": "3.14.4",
                "licenses": [{"license": {"id": "PSF-2.0"}}],
            },
        ],
        "metadata": {"component": {"name": "Silver Estimate", "version": "3.12"}},
    }


def test_dependency_policy_accepts_complete_evidence(tmp_path: Path) -> None:
    lockfile, _notices = _write_repository(tmp_path)
    policy = _policy(lockfile)
    report = _audit_report()

    validate_policy(policy, today=TODAY)
    validate_lock_review(policy, lockfile)
    validate_attributions(policy, tmp_path)
    validate_native_provenance(policy, tmp_path)
    audit_summary = validate_audit_report(policy, report)
    sbom_summary = validate_sbom(policy, report, _sbom())

    assert audit_summary == {
        "dependencies": 2,
        "ignored_vulnerabilities": 0,
        "skipped_dependencies": 1,
        "vulnerabilities": 0,
    }
    assert sbom_summary["licensed_runtime_components"] == 2
    assert sbom_summary["native_components"] == 1


def test_policy_rejects_expired_advisory_ignore(tmp_path: Path) -> None:
    lockfile, _notices = _write_repository(tmp_path)
    policy = _policy(lockfile)
    policy["advisory_ignores"] = [
        {
            "advisory_id": "CVE-2026-0001",
            "expires": "2026-07-29",
            "owner": "security owner",
            "rationale": "Temporary exception.",
        }
    ]

    with pytest.raises(DependencyPolicyError, match="expired"):
        validate_policy(policy, today=TODAY)


def test_audit_rejects_unresolved_vulnerability(tmp_path: Path) -> None:
    lockfile, _notices = _write_repository(tmp_path)
    policy = _policy(lockfile)
    report = _audit_report()
    report["dependencies"][0]["vulns"] = [
        {
            "aliases": ["GHSA-test-test-test"],
            "id": "CVE-2026-0001",
        }
    ]

    with pytest.raises(DependencyPolicyError, match="CVE-2026-0001"):
        validate_audit_report(policy, report)


def test_audit_accepts_documented_advisory_alias(tmp_path: Path) -> None:
    lockfile, _notices = _write_repository(tmp_path)
    policy = _policy(lockfile)
    policy["advisory_ignores"] = [
        {
            "advisory_id": "GHSA-TEST-TEST-TEST",
            "expires": "2026-08-30",
            "owner": "security owner",
            "rationale": "Not reachable in the desktop application.",
        }
    ]
    report = _audit_report()
    report["dependencies"][0]["vulns"] = [
        {
            "aliases": ["GHSA-test-test-test"],
            "id": "CVE-2026-0001",
        }
    ]

    validate_policy(policy, today=TODAY)
    summary = validate_audit_report(policy, report)

    assert summary["ignored_vulnerabilities"] == 1


def test_audit_rejects_unapproved_skip(tmp_path: Path) -> None:
    lockfile, _notices = _write_repository(tmp_path)
    policy = _policy(lockfile)
    report = _audit_report()
    report["dependencies"][1]["name"] = "unknown-private-wheel"

    with pytest.raises(DependencyPolicyError, match="unapproved audit skip"):
        validate_audit_report(policy, report)


def test_lock_review_rejects_changed_lockfile(tmp_path: Path) -> None:
    lockfile, _notices = _write_repository(tmp_path)
    policy = _policy(lockfile)
    lockfile.write_text("version = 2\n", encoding="utf-8")

    with pytest.raises(DependencyPolicyError, match="without an accompanying"):
        validate_lock_review(policy, lockfile)


def test_attribution_rejects_missing_notice(tmp_path: Path) -> None:
    lockfile, notices = _write_repository(tmp_path)
    policy = _policy(lockfile)
    notices.write_text("Incomplete notices\n", encoding="utf-8")

    with pytest.raises(DependencyPolicyError, match="attribution is missing"):
        validate_attributions(policy, tmp_path)


def test_native_provenance_rejects_empty_inventory(tmp_path: Path) -> None:
    lockfile, _notices = _write_repository(tmp_path)
    policy = _policy(lockfile)
    provenance_path = tmp_path / "vendor" / "sqlcipher" / "PROVENANCE.json"
    provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
    provenance["build"]["native_inventory"] = []
    provenance_path.write_text(json.dumps(provenance), encoding="utf-8")

    with pytest.raises(DependencyPolicyError, match="no binary inventory"):
        validate_native_provenance(policy, tmp_path)


def test_sbom_rejects_unknown_runtime_license(tmp_path: Path) -> None:
    lockfile, _notices = _write_repository(tmp_path)
    policy = _policy(lockfile)
    sbom = copy.deepcopy(_sbom())
    sbom["components"][0].pop("licenses")

    with pytest.raises(DependencyPolicyError, match="has no declared license"):
        validate_sbom(policy, _audit_report(), sbom)
