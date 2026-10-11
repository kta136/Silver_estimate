#!/usr/bin/env python
import faulthandler
import os
import platform
import sys
import time
import traceback
from pathlib import Path
from typing import Any, TextIO

_STARTUP_LOG_PATH: Path | None = None
_FAULT_LOG_STREAM: TextIO | None = None


def _is_frozen_runtime() -> bool:
    """Return whether the process is running from a frozen/compiled artifact."""
    if getattr(sys, "frozen", False):
        return True
    return getattr(globals().get("__compiled__"), "containing_dir", None) is not None


def _runtime_root() -> Path:
    """Resolve the stable directory containing the source or frozen executable."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    containing_dir = getattr(globals().get("__compiled__"), "containing_dir", None)
    if containing_dir:
        return Path(containing_dir).resolve()
    return Path(__file__).resolve().parent


def _startup_log_candidates() -> tuple[Path, ...]:
    """Return diagnostic directories ordered from most to least discoverable."""
    candidates = [_runtime_root() / "logs"]
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        candidates.append(Path(local_app_data) / "SilverEstimate" / "logs")
    temp_dir = os.environ.get("TEMP") or os.environ.get("TMP")
    if temp_dir:
        candidates.append(Path(temp_dir) / "SilverEstimate" / "logs")

    unique: list[Path] = []
    for candidate in candidates:
        if candidate not in unique:
            unique.append(candidate)
    return tuple(unique)


def _select_startup_log() -> Path | None:
    """Select a writable startup log, falling back outside the EXE directory."""
    global _STARTUP_LOG_PATH
    if _STARTUP_LOG_PATH is not None:
        return _STARTUP_LOG_PATH

    for directory in _startup_log_candidates():
        try:
            directory.mkdir(parents=True, exist_ok=True)
            path = directory / "SilverEstimate-startup.log"
            with path.open("a", encoding="utf-8"):
                pass
        except OSError:
            continue
        _STARTUP_LOG_PATH = path
        return path
    return None


def _write_startup_event(event: str, exc: BaseException | None = None) -> Path | None:
    """Append an early-startup milestone without relying on application logging."""
    path = _select_startup_log()
    if path is None:
        return None
    try:
        with path.open("a", encoding="utf-8") as stream:
            timestamp = time.strftime("%Y-%m-%dT%H:%M:%S%z")
            stream.write(f"{timestamp} pid={os.getpid()} {event}\n")
            if exc is not None:
                stream.writelines(traceback.format_exception(exc))
            stream.flush()
    except OSError:
        return None
    return path


def _enable_native_fault_log() -> None:
    """Send Python/native fault dumps to the durable startup diagnostic log."""
    global _FAULT_LOG_STREAM
    path = _select_startup_log()
    if path is None:
        return
    try:
        _FAULT_LOG_STREAM = path.open("a", encoding="utf-8")
        faulthandler.enable(file=_FAULT_LOG_STREAM, all_threads=True)
    except OSError, RuntimeError:
        _FAULT_LOG_STREAM = None


def _show_early_error(exc: BaseException, log_path: Path | None) -> None:
    """Display an error without importing Qt, which may be the failed dependency."""
    diagnostic_location = (
        str(log_path) if log_path is not None else "No writable log location was found."
    )
    message = (
        "Silver Estimate could not start.\n\n"
        f"{type(exc).__name__}: {exc}\n\n"
        f"Startup diagnostics:\n{diagnostic_location}\n\n"
        "The application requires 64-bit Windows 10 or Windows 11. "
        "If it is in a protected folder, copy it to a writable folder and try again."
    )
    try:
        import ctypes

        windll = getattr(ctypes, "windll", None)
        user32 = getattr(windll, "user32", None)
        if user32 is not None:
            user32.MessageBoxW(None, message, "Silver Estimate Startup Error", 0x10)
            return
    except Exception:
        pass

    if sys.stderr is not None:
        print(message, file=sys.stderr)


# Fix streams for GUI launches that do not have an attached console.
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w")  # noqa: SIM115 - process-lifetime stream
if sys.stdout is None:
    sys.stdout = open(os.devnull, "w")  # noqa: SIM115 - process-lifetime stream


def _restore_frozen_qapplication(qt_widgets: Any | None = None) -> type:
    """Bypass Nuitka's unsafe Windows icon wrapper around QApplication."""
    if qt_widgets is None:
        from PySide6 import QtWidgets

        qt_widgets = QtWidgets

    application_type = qt_widgets.QApplication
    original_type = getattr(application_type, "__base__", None)
    if (
        _is_frozen_runtime()
        and original_type is not None
        and getattr(application_type, "__name__", "") == "QApplication"
        and getattr(original_type, "__name__", "") == "QApplication"
        and getattr(application_type, "__module__", "")
        == getattr(original_type, "__module__", "")
    ):
        qt_widgets.QApplication = original_type
        return original_type
    return application_type


def main() -> int:
    """Start the SilverEstimate application and return the exit code."""
    _write_startup_event(
        "main-enter "
        f"frozen={_is_frozen_runtime()} "
        f"platform={platform.platform()} "
        f"executable={sys.executable!r} "
        f"cwd={os.getcwd()!r}"
    )
    if (
        os.name == "nt"
        and not _is_frozen_runtime()
        and os.environ.get("SILVER_SHOW_CONSOLE") != "1"
    ):
        from silverestimate.infrastructure.windows_integration import (
            hide_console_window,
        )

        hide_console_window()

    if _is_frozen_runtime():
        _restore_frozen_qapplication()

    from silverestimate.infrastructure.application import ApplicationBuilder
    from silverestimate.infrastructure.main_window_runtime import (
        create_main_window,
        preload_post_auth_runtime,
    )

    builder = ApplicationBuilder(
        main_window_factory=create_main_window,
        startup_preloader=preload_post_auth_runtime,
    )
    return builder.run()


def _run_entrypoint() -> int:
    """Run the application with diagnostics that precede all non-stdlib imports."""
    log_path = _write_startup_event("process-start")
    _enable_native_fault_log()
    try:
        exit_code = main()
    except Exception as exc:
        log_path = _write_startup_event("unhandled-startup-exception", exc) or log_path
        _show_early_error(exc, log_path)
        return 1
    _write_startup_event(f"process-exit exit_code={exit_code}")
    return exit_code


__all__ = ["main"]


if __name__ == "__main__":
    sys.exit(_run_entrypoint())
