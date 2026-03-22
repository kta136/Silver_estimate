from __future__ import annotations

import os
import shutil
from pathlib import Path

import nox  # type: ignore[import-not-found]

nox.options.sessions = ["pr"]

PROJECT_ROOT = Path(__file__).resolve().parent
RUFF_TARGETS = ("silverestimate", "tests", "main.py", "noxfile.py")
PYINSTALLER_SPEC = PROJECT_ROOT / "SilverEstimate.spec"


def clean_artifact(path: Path) -> None:
    try:
        if path.is_dir():
            shutil.rmtree(path)
            return
        path.unlink()
    except FileNotFoundError:
        return


def run_pyinstaller_build(session: nox.Session, *, clean: bool = False) -> Path:
    artifact = (
        PROJECT_ROOT
        / "dist"
        / ("SilverEstimate.exe" if os.name == "nt" else "SilverEstimate")
    )
    clean_artifact(artifact)

    session.run("python", "-m", "PyInstaller", "--version")
    pyinstaller_args = [
        "python",
        "-m",
        "PyInstaller",
        "--noconfirm",
    ]
    if clean:
        pyinstaller_args.append("--clean")
    pyinstaller_args.append(str(PYINSTALLER_SPEC))
    session.run(*pyinstaller_args)
    return artifact


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
    coverage_xml = PROJECT_ROOT / "coverage.xml"
    clean_artifact(perf_log)
    clean_artifact(coverage_xml)

    session.run(
        "python",
        "-m",
        "pytest",
        "-W",
        "error",
        "-W",
        "ignore:'crypt' is deprecated and slated for removal in Python 3.13:DeprecationWarning",
        "-m",
        "unit or integration or slow",
        "--cov=silverestimate",
        "--cov-report=xml",
        "--cov-report=term-missing",
        "--cov-fail-under=70",
        "-v",
    )
    session.run(
        "python",
        "-m",
        "pytest",
        "tests/ui/test_estimate_entry_widget.py",
        "tests/ui/test_item_master.py",
        "tests/integration/test_repositories.py",
        "-q",
        "--log-file",
        str(perf_log),
        "--log-file-level",
        "DEBUG",
    )
    session.run("python", "scripts/check_perf_budgets.py", "--log-file", str(perf_log))


@nox.session(python=False)
def bandit(session: nox.Session) -> None:
    session.run(
        "python", "-m", "bandit", "-c", "pyproject.toml", "-r", "silverestimate"
    )


@nox.session(python=False)
def safety(session: nox.Session) -> None:
    session.run("python", "-m", "safety", "check", "--json")


@nox.session(python=False)
def build(session: nox.Session) -> None:
    artifact = run_pyinstaller_build(session)
    if not artifact.exists():
        session.error(f"Build artifact was not created: {artifact}")
    session.log(f"Build artifact created at {artifact}")


@nox.session(python=False, name="build_clean")
def build_clean(session: nox.Session) -> None:
    artifact = run_pyinstaller_build(session, clean=True)
    if not artifact.exists():
        session.error(f"Build artifact was not created: {artifact}")
    session.log(f"Build artifact created at {artifact}")


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
