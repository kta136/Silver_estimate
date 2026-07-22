#!/usr/bin/env python
import faulthandler
import os
import sys
import time
from contextlib import suppress

PROCESS_START_PERF = time.perf_counter()
PROCESS_START_UNIX = time.time()

# Proactively hide the console as early as possible on Windows when not explicitly requested.
if os.name == "nt" and os.environ.get("SILVER_SHOW_CONSOLE") != "1":
    try:
        import ctypes

        windll = getattr(ctypes, "windll", None)
        if windll is not None:
            hwnd = windll.kernel32.GetConsoleWindow()
            if hwnd:
                windll.user32.ShowWindow(hwnd, 0)  # SW_HIDE
            windll.kernel32.FreeConsole()
    except Exception:
        pass

from silverestimate.infrastructure.main_window_runtime import create_main_window

# Fix sys.stdout and sys.stderr for GUI mode (Windows without console)
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w")  # noqa: SIM115 - process-lifetime stream
if sys.stdout is None:
    sys.stdout = open(os.devnull, "w")  # noqa: SIM115 - process-lifetime stream

# Enable Python-level crash dumps for segmentation faults (only if stderr is available)
with suppress(Exception):
    faulthandler.enable()


def main() -> int:
    """Start the SilverEstimate application and return the exit code."""
    if "--artifact-smoke" in sys.argv:
        import json
        import tempfile
        from pathlib import Path

        from silverestimate.infrastructure.app_constants import APP_VERSION
        from silverestimate.persistence.database_driver import (
            SqlCipherConnectionBroker,
        )
        from silverestimate.security import credential_store

        credential_kinds = credential_store.SUPPORTED_CREDENTIAL_KINDS
        for kind in credential_kinds:
            credential_store._get_secure_id(kind)  # noqa: SLF001

        with tempfile.TemporaryDirectory(
            prefix="silverestimate-artifact-smoke-"
        ) as tmp:
            database = Path(tmp) / "artifact-smoke.db"
            broker = SqlCipherConnectionBroker(database, os.urandom(32))
            connection, identity = broker.open_writer(create=True)
            connection.execute("CREATE TABLE smoke(value TEXT NOT NULL)")
            connection.execute("INSERT INTO smoke VALUES ('encrypted-runtime-ok')")
            connection.commit()
            connection.close()
            plaintext_header = database.read_bytes().startswith(b"SQLite format 3\x00")
            if plaintext_header:
                raise RuntimeError(
                    "Frozen artifact created a plaintext SQLite database"
                )

        print(
            json.dumps(
                {
                    "app_version": APP_VERSION,
                    "artifact_startup": "ok",
                    "cipher_version": identity.sqlcipher_version,
                    "credential_kinds": list(credential_kinds),
                    "crypto_provider": identity.crypto_provider,
                    "sqlite_version": identity.sqlite_version,
                },
                sort_keys=True,
            )
        )
        return 0
    if os.name == "nt" and os.environ.get("SILVER_SHOW_CONSOLE") != "1":
        from silverestimate.infrastructure.windows_integration import (
            hide_console_window,
        )

        hide_console_window()

    from silverestimate.infrastructure.application import ApplicationBuilder

    builder = ApplicationBuilder(
        main_window_factory=create_main_window,
        startup_t0_perf=PROCESS_START_PERF,
        startup_t0_unix=PROCESS_START_UNIX,
    )
    return builder.run()


__all__ = ["main"]


if __name__ == "__main__":
    sys.exit(main())
