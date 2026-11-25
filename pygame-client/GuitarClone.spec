# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

hiddenimports = []
hiddenimports += collect_submodules('pygame')
hiddenimports += collect_submodules('librosa')
hiddenimports += collect_submodules('sklearn')
hiddenimports += collect_submodules('scipy')
hiddenimports += collect_submodules('soundfile')
hiddenimports += collect_submodules('numba')
hiddenimports += collect_submodules('lazy_loader')

datas = []
datas += collect_data_files('librosa')
datas += collect_data_files('sklearn')
datas += collect_data_files('soundfile')

a = Analysis(
    ['main.py'],
    pathex=['.'],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports + ['analysis'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter.test', 'unittest', 'email.test', 'test'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='GuitarClone',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='GuitarClone',
)
