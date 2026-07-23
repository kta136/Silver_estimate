#!/usr/bin/env python
import faulthandler
import os
import platform
import sys
import time
import traceback
from pathlib import Path
from typing import TextIO

PROCESS_START_PERF = time.perf_counter()
PROCESS_START_UNIX = time.time()
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


def _run_artifact_smoke() -> int:
    import json
    import tempfile
    from pathlib import Path

    from PySide6.QtGui import QIcon, QImageReader, QTextDocument
    from PySide6.QtPrintSupport import QPrinter
    from PySide6.QtWidgets import QApplication

    from silverestimate.infrastructure.app_constants import APP_VERSION
    from silverestimate.infrastructure.paths import (
        get_asset_path,
        get_runtime_root,
    )
    from silverestimate.persistence.database_driver import (
        SqlCipherConnectionBroker,
    )
    from silverestimate.security import credential_store
    from silverestimate.security.password_service import PasswordHashService

    os.environ.setdefault(
        "QT_QPA_PLATFORM", "windows" if os.name == "nt" else "offscreen"
    )
    app = QApplication.instance() or QApplication([])
    icon_path = get_asset_path("assets", "icons", "silverestimate.ico")
    icon_available = icon_path.is_file() and not QIcon(str(icon_path)).isNull()
    image_formats = {
        bytes(image_format).decode("ascii").lower()
        for image_format in QImageReader.supportedImageFormats()
    }
    credential_status = credential_store.get_backend_status()
    password_service = PasswordHashService()
    synthetic_password = "silverestimate-artifact-smoke-password"
    synthetic_password_hash = password_service.hash_password(synthetic_password)
    password_verification = password_service.verify_password(
        synthetic_password_hash,
        synthetic_password,
    )
    password_hashing = password_verification.verified
    if not password_hashing:
        raise RuntimeError("Frozen artifact failed Argon2id password verification")

    with tempfile.TemporaryDirectory(prefix="silverestimate-artifact-smoke-") as tmp:
        temp_root = Path(tmp)
        database = temp_root / "artifact-smoke.db"
        broker = SqlCipherConnectionBroker(database, os.urandom(32))
        connection, identity = broker.open_writer(create=True)
        connection.execute("CREATE TABLE smoke(value TEXT NOT NULL)")
        connection.execute("INSERT INTO smoke VALUES ('encrypted-runtime-ok')")
        connection.commit()
        connection.close()
        plaintext_header = database.read_bytes().startswith(b"SQLite format 3\x00")
        if plaintext_header:
            raise RuntimeError("Frozen artifact created a plaintext SQLite database")

        pdf_path = temp_root / "artifact-smoke.pdf"
        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
        printer.setOutputFileName(str(pdf_path))
        document = QTextDocument()
        document.setHtml("<h1>SilverEstimate artifact smoke</h1>")
        document.print_(printer)
        pdf_bytes = pdf_path.stat().st_size
        if pdf_bytes < 1_000:
            raise RuntimeError("Frozen artifact failed to render a PDF")

    app.processEvents()
    print(
        json.dumps(
            {
                "app_version": APP_VERSION,
                "artifact_startup": "ok",
                "cipher_version": identity.sqlcipher_version,
                "credential_kinds": list(credential_store.SUPPORTED_CREDENTIAL_KINDS),
                "crypto_provider": identity.crypto_provider,
                "icon_available": icon_available,
                "keyring_available": credential_status.available,
                "keyring_backend": credential_status.backend_name,
                "password_hashing": password_hashing,
                "pdf_bytes": pdf_bytes,
                "qt_platform": app.platformName(),
                "runtime_root": str(get_runtime_root()),
                "sqlite_version": identity.sqlite_version,
                "svg_image_format": "svg" in image_formats,
            },
            sort_keys=True,
        )
    )
    return 0


def main() -> int:
    """Start the SilverEstimate application and return the exit code."""
    _write_startup_event(
        "main-enter "
        f"frozen={_is_frozen_runtime()} "
        f"platform={platform.platform()} "
        f"executable={sys.executable!r} "
        f"cwd={os.getcwd()!r}"
    )
    if "--artifact-smoke" in sys.argv:
        return _run_artifact_smoke()
    if (
        os.name == "nt"
        and not _is_frozen_runtime()
        and os.environ.get("SILVER_SHOW_CONSOLE") != "1"
    ):
        from silverestimate.infrastructure.windows_integration import (
            hide_console_window,
        )

        hide_console_window()

    from silverestimate.infrastructure.application import ApplicationBuilder
    from silverestimate.infrastructure.main_window_runtime import (
        create_main_window,
        preload_post_auth_runtime,
    )

    builder = ApplicationBuilder(
        main_window_factory=create_main_window,
        startup_t0_perf=PROCESS_START_PERF,
        startup_t0_unix=PROCESS_START_UNIX,
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
