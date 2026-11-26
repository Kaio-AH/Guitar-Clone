# -*- mode: python ; coding: utf-8 -*-

import os
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
hiddenimports += collect_submodules('spotipy')
hiddenimports += collect_submodules('yt_dlp')

datas = []
datas += collect_data_files('librosa')
datas += collect_data_files('sklearn')
datas += collect_data_files('soundfile')
datas += collect_data_files('certifi')

binaries = []
# Bundle ffmpeg if present (set FFMPEG_BIN env or place ffmpeg.exe in PATH)
ffmpeg_bin = os.environ.get('FFMPEG_BIN') or r'C:\ffmpeg\ffmpeg-2025-10-30-git-00c23bafb0-essentials_build\bin\ffmpeg.exe'
if os.path.isfile(ffmpeg_bin):
    binaries.append((ffmpeg_bin, 'ffmpeg'))

a = Analysis(
    ['main.py'],
    pathex=['.'],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports + ['analysis', 'online_service'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter.test', 'email.test'],
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
