from __future__ import annotations

import shutil
from pathlib import Path

import nox  # type: ignore[import-not-found]

nox.options.sessions = ["ruff", "mypy", "tests"]

PROJECT_ROOT = Path(__file__).resolve().parent
RUFF_TARGETS = ("silverestimate", "tests", "scripts", "main.py", "noxfile.py")


def clean_artifact(path: Path) -> None:
    try:
        if path.is_dir():
            shutil.rmtree(path)
            return
        path.unlink()
    except FileNotFoundError:
        return


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
def tests(session: nox.Session) -> None:
    session.env["QT_QPA_PLATFORM"] = "offscreen"
    session.run(
        "python",
        "-m",
        "pytest",
        "tests",
        "--ignore=tests/smoke",
        *session.posargs,
    )


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
def audit(session: nox.Session) -> None:
    """List known advisories for the locked runtime packages; never blocks."""
    artifact_dir = PROJECT_ROOT / "artifacts" / "audit"
    requirements = artifact_dir / "runtime-requirements.txt"
    clean_artifact(artifact_dir)
    artifact_dir.mkdir(parents=True, exist_ok=True)

    session.run(
        "uv",
        "export",
        "--frozen",
        "--no-dev",
        "--no-emit-project",
        "--no-hashes",
        "--format",
        "requirements-txt",
        "--output-file",
        str(requirements),
        external=True,
    )
    session.run(
        "python",
        "-m",
        "pip_audit",
        "--requirement",
        str(requirements),
        "--no-deps",
        "--disable-pip",
        "--progress-spinner",
        "off",
        success_codes=[0, 1],
    )
