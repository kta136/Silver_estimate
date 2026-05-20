"""Qt bootstrap helpers that must run before creating QApplication."""

from __future__ import annotations

import os
import sys
from collections.abc import MutableMapping
from typing import Any

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QGuiApplication

QT_QPA_PLATFORM = "QT_QPA_PLATFORM"
WINDOWS_QPA_PLATFORM = "windows"
WINDOWS_LIGHT_MODE_QPA_PLATFORM = "windows:darkmode=0"

APPLICATION_ATTRIBUTE_NAMES = (
    "AA_EnableHighDpiScaling",
    "AA_UseHighDpiPixmaps",
    "AA_DontUseNativeDialogs",
)


def windows_platform_without_dark_mode(platform: str) -> str:
    """Return a Windows QPA platform string with Qt dark mode disabled."""
    plugin, separator, options = platform.partition(":")
    if plugin.lower() != WINDOWS_QPA_PLATFORM:
        return platform

    option_parts = [
        option
        for raw_option in options.split(",")
        if (option := raw_option.strip()) and not option.lower().startswith("darkmode=")
    ]
    option_parts.append("darkmode=0")
    return f"{plugin}{separator or ':'}{','.join(option_parts)}"


def disable_windows_dark_mode(
    *,
    environ: MutableMapping[str, str] | None = None,
    platform: str | None = None,
) -> None:
    """Disable Qt's Windows dark-mode integration without changing other plugins."""
    current_platform = sys.platform if platform is None else platform
    if current_platform != "win32":
        return

    target_environ = os.environ if environ is None else environ
    configured_platform = target_environ.get(QT_QPA_PLATFORM)
    if not configured_platform:
        target_environ[QT_QPA_PLATFORM] = WINDOWS_LIGHT_MODE_QPA_PLATFORM
        return

    target_environ[QT_QPA_PLATFORM] = windows_platform_without_dark_mode(
        configured_platform
    )


def set_pass_through_high_dpi_rounding_policy(
    *,
    qgui_application: Any | None = None,
    qt: Any | None = None,
) -> bool:
    """Set Qt's high-DPI rounding policy to PassThrough when the runtime has it."""
    qgui_application = QGuiApplication if qgui_application is None else qgui_application
    qt = Qt if qt is None else qt

    policy_enum = getattr(qt, "HighDpiScaleFactorRoundingPolicy", None)
    pass_through = getattr(policy_enum, "PassThrough", None)
    setter = getattr(
        qgui_application,
        "setHighDpiScaleFactorRoundingPolicy",
        None,
    )
    if pass_through is None or setter is None:
        return False

    setter(pass_through)
    return True


def available_application_attributes(
    *names: str,
    qt: Any | None = None,
) -> tuple[Any, ...]:
    """Return Qt application attributes that exist on the active Qt runtime."""
    qt = Qt if qt is None else qt
    attribute_enum = getattr(qt, "ApplicationAttribute", None)
    if attribute_enum is None:
        return ()

    requested_names = names or APPLICATION_ATTRIBUTE_NAMES
    attrs: list[Any] = []
    for name in requested_names:
        attr = getattr(attribute_enum, name, None)
        if attr is not None:
            attrs.append(attr)
    return tuple(attrs)


def configure_qt_before_application(
    *,
    environ: MutableMapping[str, str] | None = None,
    platform: str | None = None,
    qgui_application: Any | None = None,
    qt: Any | None = None,
) -> bool:
    """Run pre-QApplication Qt bootstrap tweaks and report high-DPI policy support."""
    disable_windows_dark_mode(environ=environ, platform=platform)
    return set_pass_through_high_dpi_rounding_policy(
        qgui_application=qgui_application,
        qt=qt,
    )
