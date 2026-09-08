# Dependency update review — 8 September 2026

The project now pins CPython **3.14.7** and builds against PySide6/Qt **6.11.2** and Nuitka **4.2.1**. The existing Windows `.cmd` launcher remains the local build entry point. It now reads the exact interpreter version from `.python-version`, lets uv find or download it, and rejects a synchronized environment with a different patch version. The native-wheel CI workflow also reads that file.

Checked every public-registry package in the lockfile against non-yanked stable PyPI releases, plus upstream CPython, SQLCipher and OpenSSL releases. Prereleases were excluded. The before column below is the resolved version actually used by the project; old minimum requirements such as pytest >=7.4 did not mean pytest 7 was installed. `uv.lock` provides exact package versions; compatible requirement ranges remain in `pyproject.toml`.

## Applied and checked

Python **3.14.4 → 3.14.7** is a maintenance update. Nuitka 4.2 officially supports Python 3.14; the old experimental-support warning no longer appears in the new compiler preflight. Sources: [Python release](https://www.python.org/downloads/release/python-3147/), [Nuitka 4.2 release notes](https://nuitka.net/posts/nuitka-release-42.html).

| Package | Previous lock | Updated lock | Change |
|---|---|---|---|
| [cyclonedx-bom](https://pypi.org/project/cyclonedx-bom/7.3.1/) | 7.3.0 | 7.3.1 | patch |
| [diff-cover](https://pypi.org/project/diff-cover/10.5.1/) | 10.4.0 | 10.5.1 | minor |
| [hypothesis](https://pypi.org/project/hypothesis/6.167.1/) | 6.160.0 | 6.167.1 | minor |
| [mypy](https://pypi.org/project/mypy/2.3.1/) | 2.3.0 | 2.3.1 | patch |
| [nox](https://pypi.org/project/nox/2026.8.17/) | 2026.7.11 | 2026.8.17 | minor |
| [nuitka](https://pypi.org/project/nuitka/4.2.1/) | 4.1.3 | 4.2.1 | minor |
| [pre-commit](https://pypi.org/project/pre-commit/4.6.2/) | 4.6.1 | 4.6.2 | patch |
| [pyside6](https://pypi.org/project/pyside6/6.11.2/) | 6.11.1 | 6.11.2 | patch |
| [ruff](https://pypi.org/project/ruff/0.16.6/) | 0.15.22 | 0.16.6 | minor |

The Qt Addons, Essentials and Shiboken packages also move together from 6.11.1 to 6.11.2. That makes **12 package version changes**, with no added/removed packages. Nox additionally declares two dependencies already present in the lock: platformdirs and python-discovery. Hashes and the complete direct/transitive diff were reviewed; the dependency policy records the new lock digest. Qt attribution text and the Ruff/mypy hook revisions were aligned.

PySide6 6.11.2 requires Python below 3.15, and the controlled SQLCipher wheel targets CPython 3.14. Python 3.15 is therefore not an upgrade target for this batch. [Qt release notes](https://doc.qt.io/qtforpython-6/release_notes/pyside6_release_notes.html), [PySide6 package requirements](https://pypi.org/project/PySide6/6.11.2/).

Ruff 0.16 expands default lint rules and adds Markdown formatting. This project already selects its lint rules explicitly; the existing source passes the new lint/format checks without application-code changes. [Ruff 0.16 migration notes](https://github.com/astral-sh/ruff/releases/tag/0.16.0).

## Remaining major and native upgrades, in recommended order

1. **Rebuild the controlled SQLCipher/OpenSSL wheel.** SQLCipher **4.17.0 → 4.18.0** is a minor update that advances its SQLite baseline from 3.53.3 to 3.53.4 and fixes a Windows crash under particular logging/memory-security settings. The embedded OpenSSL **3.6.0 → 3.6.4** patch update is also available. OpenSSL 3.6 reaches end of support on **1 November 2026**; evaluate a supported longer-lived branch as part of that work. OpenSSL **4.0.2** is a major alternative requiring a separate compatibility assessment. Rebuild with the existing wheel script, verify source hashes/native inventory, update provenance and notices, and run encrypted open/migration/backup/restore/rekey plus packaged-runtime checks. A plain PyPI sqlcipher3 update must not replace the controlled wheel. [SQLCipher 4.18 release](https://github.com/sqlcipher/sqlcipher/releases/tag/v4.18.0), [OpenSSL releases and lifecycle](https://openssl-library.org/source/).

2. **argon2-cffi-bindings 25.1.0 → 26.1.0.** This is a release-year version increment in the native password-hashing dependency, not evidence by itself of a breaking API change. A Windows x64 ABI3 wheel compatible with Python 3.14 is available. Test old password hashes and deterministic database-key derivation in both directions, wrong-password rejection, pending-credential recovery, password change/rekey and frozen packaging before adopting it. The public high-level argon2-cffi package remains current at 25.1.0. [Bindings release](https://pypi.org/project/argon2-cffi-bindings/26.1.0/).

3. **cryptography 49.0.0 → 50.0.1.** It is present in the cross-platform lock through SecretStorage, but is not installed in this Windows development environment or required by the Windows application runtime. The existing mypy hook separately lists it as an extra dependency. Version 50 includes a PKCS7 decryption security fix and its latest wheels embed OpenSSL 4.0.2. Updating this package would not update OpenSSL embedded in SQLCipher. Validate the Linux keyring path if supported, and review whether the mypy-only extra is still needed. This review does not establish exploitability of the upstream advisory in this application. [Cryptography changelog](https://cryptography.io/en/latest/changelog/).

4. **chardet 5.2.0 → 7.6.0: blocked by the current SBOM dependency.** cyclonedx-bom 7.3.1 declares `chardet>=5.1,<6.0`, so forcing 7.x would make the environment inconsistent. Retain 5.2.0 until upstream relaxes that bound or a separately validated SBOM-tool migration is chosen. Both CycloneDX and diff-cover consume it. [CycloneDX metadata](https://pypi.org/pypi/cyclonedx-bom/7.3.1/json), [chardet release](https://pypi.org/project/chardet/7.6.0/).

## Other available transitive minor updates

These versions are available but were deliberately left out of the direct-package batch. Update them in coherent tool groups and rerun their consumers: mypy cache/runtime, coverage and diff reporting, Nox environment discovery, SBOM validation, and audit HTTP handling. Availability is verified; compatibility of these unselected versions has not been tested here.

| Transitive package | Current lock | Available stable |
|---|---|---|
| [ast-serialize](https://pypi.org/project/ast-serialize/0.10.0/) | 0.6.0 | 0.10.0 |
| [charset-normalizer](https://pypi.org/project/charset-normalizer/3.5.1/) | 3.4.9 | 3.5.1 |
| [colorlog](https://pypi.org/project/colorlog/6.12.0/) | 6.11.0 | 6.12.0 |
| [coverage](https://pypi.org/project/coverage/7.16.0/) | 7.15.2 | 7.16.0 |
| [cyclonedx-python-lib](https://pypi.org/project/cyclonedx-python-lib/11.12.0/) | 11.11.0 | 11.12.0 |
| [idna](https://pypi.org/project/idna/3.19/) | 3.18 | 3.19 |
| [librt](https://pypi.org/project/librt/0.15.0/) | 0.13.0 | 0.15.0 |
| [packaging](https://pypi.org/project/packaging/26.3/) | 26.2 | 26.3 |
| [pygments](https://pypi.org/project/pygments/2.21.0/) | 2.20.0 | 2.21.0 |
| [python-discovery](https://pypi.org/project/python-discovery/1.6.0/) | 1.5.0 | 1.6.0 |

Additional patch releases are listed in the [complete machine-readable inventory](../artifacts/project-review/dependencies-20260908/available-updates.json), including cffi, argcomplete, filelock, lxml, msgpack, platformdirs, virtualenv and pip. The installed external uv tool can move from **0.12.3 to 0.12.10**; no machine-wide tooling was changed in this batch. [uv release](https://pypi.org/project/uv/0.12.10/).

Build-system requirements (`setuptools>=77.0.3`, unpinned wheel) are resolved in an isolated build environment, not recorded as installed application dependencies. Their latest stable releases are setuptools 84.0.0 and wheel 0.48.0; a future reproducibility pass can record exact build-backend versions. These are available versions, not claimed upgrades from measured prior installed versions. [setuptools](https://pypi.org/project/setuptools/84.0.0/), [wheel](https://pypi.org/project/wheel/0.48.0/).

## Already current direct packages

| Package | Resolved stable version |
|---|---|
| [argon2-cffi](https://pypi.org/project/argon2-cffi/25.1.0/) | 25.1.0 |
| [bandit](https://pypi.org/project/bandit/1.9.4/) | 1.9.4 |
| [keyring](https://pypi.org/project/keyring/25.7.0/) | 25.7.0 |
| [pip-audit](https://pypi.org/project/pip-audit/2.10.1/) | 2.10.1 |
| [pytest](https://pypi.org/project/pytest/9.1.1/) | 9.1.1 |
| [pytest-cov](https://pypi.org/project/pytest-cov/7.1.0/) | 7.1.0 |
| [pytest-qt](https://pypi.org/project/pytest-qt/4.5.0/) | 4.5.0 |
| [zstandard](https://pypi.org/project/zstandard/0.25.0/) | 0.25.0 |

The upstream sqlcipher3 binding is also still 0.6.2; the project uses its controlled local build `0.6.2+silverestimate.4.17.0.1`. Its SQLCipher/OpenSSL payload needs the separate native update described above. [Upstream binding](https://pypi.org/project/sqlcipher3/0.6.2/).

## Validation

- **1,004 tests passed**: 1,001 non-smoke and three full-startup smoke tests. Coverage remains **85.87%**.
- Ruff lint/format, mypy across 155 application source files, configured Bandit, and all seven performance budgets passed.
- New build-script regressions check exact Python patch acceptance/rejection and consistent Nuitka versions across manifest, deployment config and both build entry points.
- The controlled SQLCipher runtime passes identity checks on Python 3.14.7.
- The reviewed lock and release SBOM pass policy: 15 runtime dependencies, 103 SBOM components, four required native identities/licenses, zero reported Python-runtime vulnerabilities and zero ignored advisories. The local SQLCipher wheel remains explicitly excluded from PyPI advisory lookup and covered by its separate provenance/runtime controls; this is not a native OpenSSL vulnerability audit.
- Both standalone and single-file builds passed packaged-runtime checks: Windows keyring availability, Argon2, encrypted SQLCipher, icon/SVG loading and PDF generation. The final executable was built through the existing `scripts/build_windows_local.cmd` launcher. Five startup samples measured **2.24-second p95**, within the three-second budget. The ZIP contents, release SBOM and all SHA-256 sidecars were refreshed and verified. These measurements are local checks, not proof of a startup improvement over the earlier build.

Evidence: [source gates](../artifacts/project-review/dependencies-20260908/validation.log), [lock diff](../artifacts/project-review/dependencies-20260908/lock-diff.json), [SQLCipher runtime](../artifacts/project-review/dependencies-20260908/sqlcipher-runtime.log), [SBOM policy](../artifacts/project-review/dependencies-20260908/sbom.log), [local CMD build](../artifacts/project-review/dependencies-20260908/build-local-cmd.log), [startup budget](../artifacts/project-review/dependencies-20260908/startup-budget.log), [artifact hashes and inventory](../artifacts/project-review/dependencies-20260908/build-artifacts.json).

No production database or credentials were used for these dependency tests. The previous executable is preserved under `artifacts/project-review/dependencies-20260908/before/`. Existing interactive acceptance testing was interrupted and remains incomplete; updated artifacts need a new interactive pass. No signing, publishing or commit was performed.
