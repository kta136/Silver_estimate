# Dependency and Release-Inventory Policy

This policy covers the Python runtime dependency graph, dependency advisories,
redistributed licenses and notices, and controlled native components shipped in
the Windows release. The machine-readable policy is
[`config/dependency-policy.json`](../config/dependency-policy.json); the
enforcement entry point is
[`scripts/check_dependency_policy.py`](../scripts/check_dependency_policy.py).

## Required local and CI gate

Run:

```powershell
uv run nox -s dependency_policy
```

The session exports only the locked runtime graph from `uv.lock`, audits the
fully pinned export with `pip-audit`, writes deterministic JSON evidence under
`artifacts/dependency-policy/`, and applies the repository policy. PR, main,
and release workflows treat the result as blocking.

Safety is retired. Bandit remains a separate source-analysis gate, while Ruff,
mypy, pytest/pytest-qt, coverage, Hypothesis, Nox, pre-commit, frozen-artifact
smokes, and performance budgets retain their existing responsibilities.

## Advisory exceptions

Known vulnerabilities are blocking unless `advisory_ignores` contains a
matching advisory ID or alias. Every exception must record:

- the exact advisory ID;
- a reachability and impact rationale;
- an accountable owner;
- an ISO `YYYY-MM-DD` expiry.

Expired or malformed exceptions fail before the audit result is accepted.
Remove an exception when the dependency is upgraded or the advisory no longer
applies.

`pip-audit` may report that a dependency cannot be audited. Such a skip is also
blocking unless `audit_skip_allowlist` records the package, rationale, owner,
expiry, and compensating control. The only current exception is the controlled
`sqlcipher3` wheel: it is intentionally not published to PyPI and is instead
verified against the committed hash, source provenance, native-extension
inventory, and live SQLCipher identity.

## Lockfile review

`lock_review.sha256` binds the policy to the exact committed `uv.lock` bytes.
Any dependency update must:

1. update `pyproject.toml` deliberately and run `uv lock`;
2. inspect the complete direct and transitive lock diff;
3. run the dependency, test, and relevant artifact gates;
4. update the SHA-256, review date, reviewer, and rationale in the policy.

A lockfile-only change fails CI because its digest no longer matches the
reviewed value.

## License, notice, and native-component gates

The release workflow retains `cyclonedx-bom`. A comparison showed that
`pip-audit`'s CycloneDX output for the locked runtime did not include the Silver
Estimate application root or component license metadata, so it is not an
equivalent replacement.

The release SBOM begins with the frozen build environment and is augmented with
the application, CPython, native Qt, SQLCipher, and OpenSSL identities. The
policy then checks every audited runtime component and required native
component for a known, allowed license. Unknown or disallowed licenses stop the
release.

`THIRD_PARTY_NOTICES.md` markers are enforced for SQLCipher, `sqlcipher3`,
OpenSSL, and Qt for Python. The committed SQLCipher provenance must list every
controlled source and at least one native binary with its hash and size.
Standalone artifact inspection additionally rejects unintended standard
SQLite binaries, PyQt, unused Qt/QML/media components, and unapproved plugins.

When a new runtime or native dependency is introduced, update the license
allowlist only after compatibility review, add the required attribution, add
native inventory where applicable, regenerate and review `uv.lock`, and verify
the complete release SBOM.
