#!/usr/bin/env python
import faulthandler
import os
import sys
from contextlib import suppress

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
        from silverestimate.infrastructure.app_constants import APP_VERSION

        print(f"SilverEstimate {APP_VERSION} artifact startup OK")
        return 0
    if os.name == "nt" and os.environ.get("SILVER_SHOW_CONSOLE") != "1":
        from silverestimate.infrastructure.windows_integration import (
            hide_console_window,
        )

        hide_console_window()

    from silverestimate.infrastructure.application import ApplicationBuilder

    builder = ApplicationBuilder(main_window_factory=create_main_window)
    return builder.run()


__all__ = ["main"]


if __name__ == "__main__":
    sys.exit(main())
