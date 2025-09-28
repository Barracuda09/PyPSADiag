# -*- mode: python ; coding: utf-8 -*-

import os
import platform

# general
program_name = "PyPSADiag"
root_dir = os.path.abspath(os.getcwd())
platform_name = platform.system().lower()
extras_dir = os.path.join(root_dir, "extras")


if platform_name == "darwin":
    icon_path = os.path.join(extras_dir, "macos", "icon.icns")
    program_file = f"{program_name}.app"
    console_mode = False   # macOS GUI apps should not show a terminal
elif platform_name == "linux":
    icon_path = os.path.join(extras_dir, "linux", "icon.png")
    program_file = program_name
    console_mode = True    # keep console for debug on Linux
elif platform_name == "windows":
    icon_path = os.path.join(extras_dir, "windows", "icon.ico")
    program_file = f"{program_name}.exe"
    console_mode = True    # keep console for debug on Windows
else:
    icon_path = None
    program_file = program_name
    console_mode = True

# resource files
added_files = [
    ('csv/*.csv', 'csv'),
    ('data/*.json', 'data'),
    ('json/*', 'json'),
    ('simu/*', 'simu'),
    ('i18n/flags/*', 'i18n/flags'),
    ('i18n/translations/*', 'i18n/translations'),
]

# PyInstaller build pipeline
a = Analysis(
    ['main.py'],
    pathex=[root_dir],
    binaries=[],
    datas=added_files,
    hiddenimports=[
        # list extra imports PyInstaller sometimes misses
        "PySide6.QtCore",
        "PySide6.QtGui",
        "PySide6.QtWidgets",
        "PySide6.QtNetwork",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=1,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name=program_name,
    debug=False,
    bootloader_ignore_signals=False,
    strip=True,             # strip symbols to reduce size
    upx=True,               # compress with UPX if available
    console=console_mode,   # depends on platform
    disable_windowed_traceback=False,
    argv_emulation=False,   # set to True if you need drag&drop args on macOS
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=icon_path,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=True,
    upx=True,
    upx_exclude=[],
    name=program_name,
)

# bundle step for macos
if platform_name == "darwin":
    app = BUNDLE(
        coll,
        name=f"{program_name}.app",
        icon=icon_path,
        bundle_identifier="Barracuda09.PyPSADiag.py",
        info_plist={
            "NSHighResolutionCapable": "True",
            "CFBundleShortVersionString": "0.1.0",
            "CFBundleVersion": "0.1.0",
            "CFBundleName": program_name,
            "CFBundleDisplayName": program_name,
        }
    )
