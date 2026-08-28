# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller build recipe for the Windows desktop distribution."""

from __future__ import annotations

import os
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files


project_root = Path(SPECPATH).parent
source_root = project_root / "src"
runtime_root = Path(os.environ.get("SIEGFRIDI_FLUIDSYNTH_DIR", "C:/tools/fluidsynth/bin"))

pack_root = project_root / "assets" / "packs"
datas = []
# Only top-level runtime packs and their provenance are distributable inputs.
# Source libraries under assets/packs/sources are kept for authoring and must
# not be pulled into the application bundle accidentally.
for pattern in ("*.sf2", "*.sf3", "*.json", "*.COPYING", "*.CC0.txt", "*.SOURCE.txt", "README.md"):
    datas.extend((str(path), "assets/packs") for path in pack_root.glob(pattern))
datas.append((str(project_root / "assets" / "presets"), "assets/presets"))

# pyFluidSynth loads its implementation with ctypes, so PyInstaller cannot
# discover the native files from Python imports alone.
binaries = []
if runtime_root.is_dir():
    for filename in ("fluidsynth.exe", "libfluidsynth-3.dll", "SDL3.dll", "sndfile.dll"):
        path = runtime_root / filename
        if path.is_file():
            binaries.append((str(path), "."))

hiddenimports = [
    "fluidsynth",
    "basic_pitch",
    "basic_pitch.inference",
    "basic_pitch.predict",
]
datas += collect_data_files("basic_pitch", include_py_files=False)

analysis = Analysis(
    [str(project_root / "packaging" / "entrypoint.py")],
    pathex=[str(source_root)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[str(project_root / "packaging" / "rthooks" / "native_runtime.py")],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(analysis.pure)
exe = EXE(
    pyz,
    analysis.scripts,
    [],
    exclude_binaries=True,
    name="Siegfridi",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
)
coll = COLLECT(
    exe,
    analysis.binaries,
    analysis.datas,
    strip=False,
    upx=False,
    name="Siegfridi",
)
