# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path

project_dir = Path(SPECPATH)

datas = [
    (str(project_dir / 'dist'), 'dist'),
    (str(project_dir / 'vendor' / 'SESAMI_web'), 'vendor/SESAMI_web'),
    (str(project_dir / 'vendor' / 'zeopp-lsmo' / 'zeo++'), 'vendor/zeopp-lsmo/zeo++'),
]

hiddenimports = [
    'matplotlib.backends.backend_agg',
]

block_cipher = None

a = Analysis(
    ['desktop_launcher.py'],
    pathex=[str(project_dir)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={'matplotlib': {'backends': ['Agg']}},
    runtime_hooks=[],
    excludes=[],
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
    name='ChemEx',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    icon=str(project_dir / 'public' / 'favicon.ico'),
)
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='ChemEx',
)
