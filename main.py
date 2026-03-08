#!/usr/bin/env python
import faulthandler
import os
import sys

# Proactively hide the console as early as possible on Windows when not explicitly requested.
if os.name == "nt" and os.environ.get("SILVER_SHOW_CONSOLE") != "1":
    try:
        import ctypes

        hwnd = ctypes.windll.kernel32.GetConsoleWindow()
        if hwnd:
            ctypes.windll.user32.ShowWindow(hwnd, 0)  # SW_HIDE
        ctypes.windll.kernel32.FreeConsole()
    except Exception:
        pass

from silverestimate.infrastructure.main_window_runtime import create_main_window

# Fix sys.stdout and sys.stderr for GUI mode (Windows without console)
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w")
if sys.stdout is None:
    sys.stdout = open(os.devnull, "w")

# Enable Python-level crash dumps for segmentation faults (only if stderr is available)
try:
    faulthandler.enable()
except Exception:
    pass


def main() -> int:
    """Start the SilverEstimate application and return the exit code."""
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
