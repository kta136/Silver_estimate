"""Probe the controlled SQLCipher runtime and optionally a wheel artifact."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
import subprocess
import tempfile
import venv
import zipfile
from pathlib import Path
from typing import Any


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--candidate",
        action="store_true",
        help="probe a newly built candidate without requiring the recorded artifact hash",
    )
    parser.add_argument("--wheel", type=Path)
    parser.add_argument("--provenance", type=Path, required=True)
    return parser.parse_args()


def _native_inventory(wheel: Path) -> list[dict[str, object]]:
    with zipfile.ZipFile(wheel) as archive:
        native = sorted(
            name for name in archive.namelist() if name.endswith((".pyd", ".dll"))
        )
        inventory = [
            {
                "path": name,
                "sha256": hashlib.sha256(archive.read(name)).hexdigest(),
                "size": archive.getinfo(name).file_size,
            }
            for name in native
        ]
    if not inventory:
        raise SystemExit("wheel has no native extension")
    return inventory


def _probe_wheel(
    wheel: Path,
    provenance_path: Path,
    provenance: dict[str, Any],
    *,
    candidate: bool,
) -> None:
    wheel = wheel.resolve()
    build = provenance["build"]
    if wheel.name != build["wheel"]:
        raise SystemExit(f"unexpected wheel name: {wheel.name}")
    actual_hash = _sha256(wheel)
    inventory = _native_inventory(wheel)
    expected_inventory = [
        {"path": item["path"], "sha256": item["sha256"], "size": item["size"]}
        for item in build.get("native_inventory", [])
    ]
    if not candidate:
        if wheel.stat().st_size != build["wheel_size"]:
            raise SystemExit(f"wheel size mismatch: {wheel.stat().st_size}")
        if actual_hash != build["wheel_sha256"]:
            raise SystemExit(f"wheel hash mismatch: {actual_hash}")
        if inventory != expected_inventory:
            raise SystemExit(f"native inventory mismatch: {inventory}")
    print(
        json.dumps(
            {"wheel_sha256": actual_hash, "native_inventory": inventory},
            sort_keys=True,
        )
    )

    # Probe the supplied artifact, never an unrelated installed package.
    with tempfile.TemporaryDirectory() as directory:
        environment = Path(directory) / "wheel-probe"
        venv.EnvBuilder(with_pip=True, clear=True).create(environment)
        probe_python = environment / "Scripts" / "python.exe"
        subprocess.run(
            [
                str(probe_python),
                "-m",
                "pip",
                "install",
                "--disable-pip-version-check",
                "--no-deps",
                str(wheel),
            ],
            check=True,
        )
        subprocess.run(
            [
                str(probe_python),
                str(Path(__file__).resolve()),
                "--provenance",
                str(provenance_path.resolve()),
            ],
            check=True,
        )


def _probe_installed_runtime(provenance: dict[str, Any]) -> None:

    from sqlcipher3 import dbapi2

    package_version = importlib.metadata.version("sqlcipher3")
    expected_version = provenance["sources"]["sqlcipher3"]["version"]
    if package_version != expected_version:
        raise SystemExit(
            f"controlled sqlcipher3 {expected_version} required: {package_version}"
        )

    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "probe.db"
        connection = dbapi2.connect(path)
        connection.execute(f"PRAGMA key = \"x'{os.urandom(32).hex()}'\"")
        connection.execute("CREATE TABLE canary(value TEXT)")
        connection.execute(
            "INSERT INTO canary VALUES ('SILVERESTIMATE_PLAINTEXT_CANARY')"
        )
        connection.commit()
        values = {
            "binding_version": package_version,
            "cipher_version": connection.execute("PRAGMA cipher_version").fetchone()[0],
            "cipher_status": connection.execute("PRAGMA cipher_status").fetchone()[0],
            "cipher_provider": connection.execute("PRAGMA cipher_provider").fetchone()[
                0
            ],
            "sqlite_version": connection.execute("SELECT sqlite_version()").fetchone()[
                0
            ],
            "compile_options": sorted(
                row[0] for row in connection.execute("PRAGMA compile_options")
            ),
        }
        connection.execute("PRAGMA journal_mode=WAL").fetchone()
        connection.close()
        if b"SILVERESTIMATE_PLAINTEXT_CANARY" in path.read_bytes():
            raise SystemExit("plaintext canary found in encrypted database")
    if not str(values["cipher_version"]).startswith("4.17."):
        raise SystemExit(f"SQLCipher 4.17.x required: {values['cipher_version']}")
    for name, expected in provenance.get("runtime", {}).items():
        if values.get(name) != expected:
            raise SystemExit(
                f"runtime {name} mismatch: expected {expected}, got {values.get(name)}"
            )
    for option in ("TEMP_STORE=2", "THREADSAFE=1", "HAS_CODEC"):
        if not any(option in value for value in values["compile_options"]):
            raise SystemExit(f"missing compile option: {option}")
    print(json.dumps(values, sort_keys=True))


def main() -> int:
    args = _parse_args()
    provenance = json.loads(args.provenance.read_text(encoding="utf-8"))
    if args.wheel:
        _probe_wheel(
            args.wheel,
            args.provenance,
            provenance,
            candidate=args.candidate,
        )
    else:
        _probe_installed_runtime(provenance)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
