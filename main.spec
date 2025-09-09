# -*- mode: python ; coding: utf-8 -*-

import os
import platform

# general
root_dir = os.path.abspath(os.getcwd())
platform_name = platform.system().lower()
extras_dir = os.path.join(root_dir, "extras")

# platform data
program_name = "PyPSADiag"
icon_path = None
program_file = None

if platform_name == "darwin":
    icon_path = os.path.join(extras_dir, "macos", "icon.icns")
    program_file = "{0}.app".format(program_name)
elif platform_name == "linux":
    icon_path = os.path.join(extras_dir, "linux", "icon.png")
    program_file = "{0}".format(program_name)
elif platform_name == "windows":
    icon_path = os.path.join(extras_dir, "windows", "icon.ico")
    program_file = "{0}.exe".format(program_name)

added_files = [
    ('csv/*.csv', './csv'),
    ('data/*.json', './data'),
    ('json', './json'),
    ('i18n/flags', './i18n/flags'),
    ('i18n/translations', './i18n/translations')
]

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=added_files,
    hiddenimports=[],
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
    [],
    exclude_binaries=True,
    name=program_name,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name=program_name,
)

app = BUNDLE(
    coll,
    name='PyPSADiag.app',
#    icon='icon_path/pypsadiag.icns',
    bundle_identifier="com.barracuda09.pypsadiag.py",
    info_plist={
        'CFBundleShortVersionString': '1.0.0',
        'CFBundleVersion': '1.0.0',
        'NSHighResolutionCapable': True
    }
)