# -*- mode: python ; coding: utf-8 -*-

import os

from PyInstaller.utils.hooks import collect_data_files

qtawesome_datas = sorted(collect_data_files("qtawesome"))


def _normalized_path(path):
    return path.replace("\\", "/")


def _path_matches_prefix(filename, prefixes):
    return any(filename.startswith(prefix) for prefix in prefixes)


def _native_platform_plugins():
    if os.name == "nt":
        return ("qwindows",)
    return ("libqxcb", "libqcocoa")


def _keep_qt_plugin(bundle_path):
    normalized = _normalized_path(bundle_path)
    plugin_prefix = "PyQt5/Qt5/plugins/"
    if not normalized.startswith(plugin_prefix):
        return True

    relative_path = normalized[len(plugin_prefix) :]
    plugin_dir, _, filename = relative_path.partition("/")

    if plugin_dir == "platforms":
        return _path_matches_prefix(filename, _native_platform_plugins())
    if plugin_dir == "imageformats":
        return _path_matches_prefix(
            filename,
            ("qgif", "qico", "qjpeg", "qpng", "qsvg", "libqgif", "libqico", "libqjpeg", "libqpng", "libqsvg"),
        )
    if plugin_dir == "iconengines":
        return _path_matches_prefix(filename, ("qsvgicon", "libqsvgicon"))
    if plugin_dir == "printsupport":
        return True
    return False


_EXCLUDED_QT_MODULES = (
    "Qt5Quick",
    "Qt5Qml",
    "Qt5QmlModels",
    "Qt5WebSockets",
    "Qt5Designer",
    "Qt5Location",
    "Qt5Multimedia",
    "Qt5Bluetooth",
    "Qt5Nfc",
    "Qt5Positioning",
    "Qt5RemoteObjects",
    "Qt5XmlPatterns",
    "Qt5Wayland",
    "Qt5EglFS",
)


def _is_excluded_qt_binary(bundle_path):
    normalized = _normalized_path(bundle_path)
    filename = normalized.rsplit("/", 1)[-1]
    if filename.endswith(".dll"):
        module_name = filename[:-4]
        return module_name.startswith(_EXCLUDED_QT_MODULES)
    if filename.endswith((".so", ".dylib")):
        return filename.startswith(tuple(f"lib{name}" for name in _EXCLUDED_QT_MODULES))
    return False


def _is_excluded_qt_path(bundle_path):
    normalized = _normalized_path(bundle_path)

    if normalized.startswith("PyQt5/Qt5/translations/"):
        return True
    if normalized.startswith("PyQt5/Qt5/qml/"):
        return True
    if normalized.startswith("PyQt5/Qt5/qsci/"):
        return True
    if normalized.startswith("PyQt5/Qt5/plugins/"):
        return not _keep_qt_plugin(normalized)
    if normalized.startswith(("PyQt5/Qt5/lib/", "PyQt5/Qt5/bin/")):
        return _is_excluded_qt_binary(normalized)
    return False


def _filter_frozen_entries(entries):
    filtered_entries = []
    for entry in entries:
        dest_name, src_name, typecode = entry
        if _is_excluded_qt_path(dest_name) or _is_excluded_qt_path(src_name):
            continue
        filtered_entries.append(entry)
    return filtered_entries

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=qtawesome_datas,
    hiddenimports=[
        "passlib.handlers.argon2",
        "passlib.handlers.bcrypt",
        "keyring.backends.Windows",
        "keyring.backends.fail",
        "keyring.backends.null",
        "qtawesome",
        "qtawesome.iconic_font",
    ],
    hookspath=["pyinstaller_hooks"],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "qtawesome.icon_browser",
        "qtpy.tests",
    ],
    noarchive=False,
    optimize=0,
)
a.binaries = _filter_frozen_entries(a.binaries)
a.datas = _filter_frozen_entries(a.datas)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="SilverEstimate",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
