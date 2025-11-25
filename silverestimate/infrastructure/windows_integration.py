"""
Windows-specific helpers for taskbar behaviour and AppUserModelID management.

These functions are safe to import on any platform; they simply no-op when
executed outside of Windows.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

if sys.platform == "win32":  # pragma: no cover - platform specific
    import ctypes
    from ctypes import wintypes


def set_app_user_model_id(app_id: str, logger=None) -> None:
    """
    Set the Windows AppUserModelID for the current process.

    Having a stable ID ensures taskbar grouping works and allows custom icons
    to appear even when the application is launched via python.exe.
    """
    if sys.platform != "win32":
        return

    try:  # pragma: no cover - Windows API
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(app_id)
    except Exception as exc:  # pragma: no cover - defensive logging only
        if logger:
            logger.debug("Failed to set AppUserModelID: %s", exc)


def apply_taskbar_icon(hwnd: Optional[int], icon_path: Path, logger=None) -> Optional[int]:
    """
    Force the Windows taskbar to use a specific icon for the given window.

    Returns:
        Optional[int]: An HICON handle if the icon was applied, otherwise None.
    """
    if sys.platform != "win32":
        return None

    if not icon_path.exists():
        if logger:
            logger.debug("Taskbar icon path does not exist: %s", icon_path)
        return None

    if not hwnd:
        if logger:
            logger.debug("Invalid window handle for taskbar icon update.")
        return None

    try:  # pragma: no cover - Windows API
        load_flags = 0x00000010 | 0x00000040  # LR_LOADFROMFILE | LR_DEFAULTSIZE
        hicon = ctypes.windll.user32.LoadImageW(
            None,
            str(icon_path),
            1,  # IMAGE_ICON
            0,
            0,
            load_flags,
        )
        if not hicon:
            if logger:
                logger.debug("Failed to load icon for taskbar from %s", icon_path)
            return None

        WM_SETICON = 0x0080
        ICON_SMALL = 0
        ICON_BIG = 1

        ctypes.windll.user32.SendMessageW(hwnd, WM_SETICON, ICON_BIG, hicon)
        ctypes.windll.user32.SendMessageW(hwnd, WM_SETICON, ICON_SMALL, hicon)

        return hicon
    except Exception as exc:  # pragma: no cover - defensive logging only
        if logger:
            logger.debug("Failed to apply Windows taskbar icon: %s", exc)
        return None


def destroy_icon_handle(handle: Optional[int], logger=None) -> None:
    """
    Release a previously loaded icon handle to avoid GDI leaks.
    """
    if sys.platform != "win32" or not handle:
        return

    try:  # pragma: no cover - Windows API
        ctypes.windll.user32.DestroyIcon(handle)
    except Exception as exc:  # pragma: no cover - defensive logging only
        if logger:
            logger.debug("Failed to destroy icon handle: %s", exc)


def hide_console_window(logger=None) -> None:
    """
    Hide the attached Windows console window if the app was launched via python.exe.

    Many users double-click the script or shortcut, which opens an extra console window
    titled "python". Hiding it prevents the phantom window while still allowing developers
    to opt in by setting SILVER_SHOW_CONSOLE=1.
    """
    if sys.platform != "win32":
        return

    try:  # pragma: no cover - Windows API
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        SW_HIDE = 0

        hwnd = kernel32.GetConsoleWindow()
        if not hwnd:
            # Fall back to finding by class name if no console handle is attached.
            hwnd = user32.FindWindowW("ConsoleWindowClass", None)

        if hwnd:
            try:
                user32.ShowWindow(hwnd, SW_HIDE)
                user32.UpdateWindow(hwnd)
            except Exception:
                pass

        # Detach so the phantom window does not reappear when stdout/stderr flush.
        try:
            kernel32.FreeConsole()
        except Exception:
            pass
    except Exception as exc:
        if logger:
            logger.debug("Failed to hide console window: %s", exc)


__all__ = [
    "set_app_user_model_id",
    "apply_taskbar_icon",
    "destroy_icon_handle",
    "hide_console_window",
]
