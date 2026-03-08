# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

qtawesome_datas = collect_data_files('qtawesome')
qtawesome_hiddenimports = collect_submodules('qtawesome') + collect_submodules('qtpy')

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=qtawesome_datas,
    hiddenimports=[
        'passlib.handlers.argon2',
        'passlib.handlers.bcrypt',
        'keyring.backends',
        'keyring.backends.Windows',
        'keyring.backends.fail',
        'keyring.backends.null',
        'qtawesome',
        'qtpy',
        *qtawesome_hiddenimports,
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='SilverEstimate',
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
