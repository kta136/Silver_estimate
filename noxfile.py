from __future__ import annotations

import configparser
import os
import shutil
import zipfile
from pathlib import Path

import nox  # type: ignore[import-not-found]

from silverestimate.infrastructure.app_constants import APP_VERSION

nox.options.sessions = ["pr"]

PROJECT_ROOT = Path(__file__).resolve().parent
RUFF_TARGETS = ("silverestimate", "tests", "main.py", "noxfile.py")
PYSIDE_DEPLOY_CONFIG = PROJECT_ROOT / "pysidedeploy.spec"
NUITKA_VERSION = "4.1.3"
LEGAL_ARTIFACTS = (
    PROJECT_ROOT / "LICENSE",
    PROJECT_ROOT / "THIRD_PARTY_NOTICES.md",
    PROJECT_ROOT / "vendor" / "sqlcipher" / "PROVENANCE.json",
)


def clean_artifact(path: Path) -> None:
    try:
        if path.is_dir():
            shutil.rmtree(path)
            return
        path.unlink()
    except FileNotFoundError:
        return


def _artifact_extension() -> str:
    return ".exe" if os.name == "nt" else ""


def _local_build_label() -> str:
    return "win64" if os.name == "nt" else "linux64"


def _versioned_artifact_path() -> Path:
    return (
        PROJECT_ROOT / "dist" / f"SilverEstimate-v{APP_VERSION}{_artifact_extension()}"
    )


def _versioned_archive_path() -> Path:
    return (
        PROJECT_ROOT
        / "dist"
        / f"SilverEstimate-v{APP_VERSION}-{_local_build_label()}.zip"
    )


def package_local_artifact(base_artifact: Path) -> tuple[Path, Path]:
    versioned_artifact = _versioned_artifact_path()
    versioned_archive = _versioned_archive_path()
    clean_artifact(versioned_artifact)
    clean_artifact(versioned_archive)

    shutil.copy2(base_artifact, versioned_artifact)
    with zipfile.ZipFile(
        versioned_archive,
        mode="w",
        compression=zipfile.ZIP_DEFLATED,
    ) as archive:
        archive.write(versioned_artifact, arcname=versioned_artifact.name)
        for legal_artifact in LEGAL_ARTIFACTS:
            archive.write(
                legal_artifact,
                arcname=legal_artifact.relative_to(PROJECT_ROOT).as_posix(),
            )
    return versioned_artifact, versioned_archive


def run_pyside_deploy_build(
    session: nox.Session,
    *,
    mode: str = "onefile",
    clean: bool = False,
) -> Path:
    deployment_dir = PROJECT_ROOT / "deployment"
    report_dir = PROJECT_ROOT / "artifacts" / "pyside6-deploy"
    temporary_config = PROJECT_ROOT / f".pysidedeploy-{mode}.spec"
    if mode == "onefile":
        artifact = (
            PROJECT_ROOT
            / "dist"
            / ("SilverEstimate.exe" if os.name == "nt" else "SilverEstimate.bin")
        )
    else:
        artifact = (
            PROJECT_ROOT
            / "dist"
            / "SilverEstimate.dist"
            / ("main.exe" if os.name == "nt" else "main.bin")
        )

    if clean:
        clean_artifact(deployment_dir)
        clean_artifact(artifact.parent if mode == "standalone" else artifact)
        if mode == "onefile":
            clean_artifact(_versioned_artifact_path())
            clean_artifact(_versioned_archive_path())
    else:
        clean_artifact(artifact)
    report_dir.mkdir(parents=True, exist_ok=True)

    parser = configparser.ConfigParser(interpolation=None)
    parser.read(PYSIDE_DEPLOY_CONFIG, encoding="utf-8")
    parser.set("nuitka", "mode", mode)
    with temporary_config.open("w", encoding="utf-8") as stream:
        parser.write(stream)

    session.run("python", "-m", "nuitka", "--version")
    try:
        session.run(
            "pyside6-deploy",
            "--config-file",
            str(temporary_config),
            "--force",
            "--mode",
            mode,
            "--nuitka-version",
            NUITKA_VERSION,
        )
    finally:
        clean_artifact(temporary_config)
    if not artifact.exists():
        session.error(
            f"pyside6-deploy did not create the expected artifact: {artifact}"
        )
    if mode == "standalone":
        return artifact
    versioned_artifact, versioned_archive = package_local_artifact(artifact)
    session.log(f"Versioned artifact created at {versioned_artifact}")
    session.log(f"Packaged archive created at {versioned_archive}")
    return versioned_artifact


@nox.session(python=False)
def ruff(session: nox.Session) -> None:
    session.run("python", "-m", "ruff", "check", *RUFF_TARGETS)
    session.run("python", "-m", "ruff", "format", "--check", *RUFF_TARGETS)


@nox.session(python=False)
def mypy(session: nox.Session) -> None:
    session.run(
        "python", "-m", "mypy", "silverestimate", "--config-file=pyproject.toml"
    )


@nox.session(python=False)
def tests_fast(session: nox.Session) -> None:
    session.run(
        "python",
        "-m",
        "pytest",
        "-m",
        "(unit and not slow) or integration",
        "-v",
    )


@nox.session(python=False)
def tests_full(session: nox.Session) -> None:
    perf_log = PROJECT_ROOT / "perf-metrics.log"
    coverage_data = PROJECT_ROOT / ".coverage"
    coverage_xml = PROJECT_ROOT / "coverage.xml"
    clean_artifact(perf_log)
    clean_artifact(coverage_data)
    clean_artifact(coverage_xml)
    session.env["QT_QPA_PLATFORM"] = "offscreen"

    session.run(
        "python",
        "-m",
        "pytest",
        "-W",
        "error",
        "-W",
        "ignore:'crypt' is deprecated and slated for removal in Python 3.13:DeprecationWarning",
        "tests",
        "--ignore=tests/smoke",
        "--cov=silverestimate",
        "--cov-report=",
        "-v",
    )
    session.run(
        "python",
        "-m",
        "pytest",
        "tests/smoke",
        "--run-smoke",
        "--cov=silverestimate",
        "--cov-append",
        "--cov-report=",
        "-v",
    )
    session.run(
        "python",
        "-m",
        "coverage",
        "run",
        "--append",
        "scripts/run_performance_gate.py",
        "--output",
        str(perf_log),
    )
    session.run("python", "scripts/check_perf_budgets.py", "--log-file", str(perf_log))
    session.run(
        "python", "-m", "coverage", "report", "--show-missing", "--fail-under=75"
    )
    session.run("python", "-m", "coverage", "xml", "-o", str(coverage_xml))


@nox.session(python=False)
def smoke_ui(session: nox.Session) -> None:
    artifact_dir = PROJECT_ROOT / "artifacts" / "smoke-ui"
    clean_artifact(artifact_dir)
    artifact_dir.mkdir(parents=True, exist_ok=True)

    session.env["QT_QPA_PLATFORM"] = "offscreen"
    session.run(
        "python",
        "-m",
        "pytest",
        "tests/smoke",
        "--run-smoke",
        "--smoke-screenshots",
        "--smoke-artifact-dir",
        str(artifact_dir),
        "-v",
    )


@nox.session(python=False)
def bandit(session: nox.Session) -> None:
    session.run(
        "python",
        "-m",
        "bandit",
        "-c",
        "pyproject.toml",
        "-r",
        "silverestimate",
        "-ll",
        "-ii",
    )


@nox.session(python=False)
def safety(session: nox.Session) -> None:
    session.run("python", "-m", "safety", "check", "--json")


@nox.session(python=False)
def build(session: nox.Session) -> None:
    artifact = run_pyside_deploy_build(session)
    if not artifact.exists():
        session.error(f"Build artifact was not created: {artifact}")
    session.log(f"Build artifact created at {artifact}")


@nox.session(python=False, name="build_clean")
def build_clean(session: nox.Session) -> None:
    artifact = run_pyside_deploy_build(session, clean=True)
    if not artifact.exists():
        session.error(f"Build artifact was not created: {artifact}")
    session.log(f"Build artifact created at {artifact}")


@nox.session(python=False, name="build_standalone")
def build_standalone(session: nox.Session) -> None:
    artifact = run_pyside_deploy_build(session, mode="standalone", clean=True)
    if not artifact.exists():
        session.error(f"Standalone artifact was not created: {artifact}")
    session.log(f"Standalone artifact created at {artifact}")


@nox.session(python=False, name="artifact_smoke")
def artifact_smoke(session: nox.Session) -> None:
    artifact = _versioned_artifact_path()
    if not artifact.exists():
        session.error(f"Versioned artifact is unavailable: {artifact}")
    session.run(
        "python",
        "scripts/validate_frozen_artifact.py",
        "--artifact",
        str(artifact),
    )


@nox.session(python=False, name="standalone_artifact_smoke")
def standalone_artifact_smoke(session: nox.Session) -> None:
    standalone_dir = PROJECT_ROOT / "dist" / "SilverEstimate.dist"
    artifact = standalone_dir / ("main.exe" if os.name == "nt" else "main.bin")
    if not artifact.exists():
        session.error(f"Standalone artifact is unavailable: {artifact}")
    session.run(
        "python",
        "scripts/validate_frozen_artifact.py",
        "--artifact",
        str(artifact),
    )
    session.run(
        "python",
        "scripts/validate_pyside_deployment.py",
        "--standalone-dir",
        str(standalone_dir),
        "--report",
        str(PROJECT_ROOT / "artifacts" / "pyside6-deploy" / "nuitka-report.xml"),
    )


@nox.session(python=False, name="pr")
def pr(session: nox.Session) -> None:
    for session_name in ("ruff", "mypy", "tests_fast"):
        session.notify(session_name)


@nox.session(python=False, name="ci")
def ci(session: nox.Session) -> None:
    for session_name in ("ruff", "mypy", "tests_full", "build_clean"):
        session.notify(session_name)


@nox.session(python=False, name="advisory")
def advisory(session: nox.Session) -> None:
    for session_name in ("bandit", "safety"):
        session.notify(session_name)
