# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller recipe for SubLoom.

CPU build (default):
    pyinstaller packaging/subloom.spec --noconfirm

GPU build on Windows (after ``pip install -e ".[gpu]"``):
    $env:SUBLOOM_BUNDLE_CUDA = "1"
    pyinstaller packaging/subloom.spec --noconfirm

Models are never bundled.  They are downloaded on first use into the user's
data directory.
"""

from __future__ import annotations

import os
import site
import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_all

ROOT = Path(SPECPATH).resolve()  # noqa: F821
if ROOT.suffix == ".spec":
    ROOT = ROOT.parent
ROOT = ROOT.parent
SRC = ROOT / "src"
ASSETS = SRC / "subloom" / "assets"

datas = [(str(ASSETS), "subloom/assets")]
binaries = []
hiddenimports = [
    "webrtcvad",
    "soxr",
    "subloom.ui.main_window",
    "subloom.ui.settings_dialog",
]
if sys.platform == "win32":
    hiddenimports += ["keyring.backends.Windows", "soundcard"]
elif sys.platform == "darwin":
    hiddenimports += ["keyring.backends.macOS"]

for package in (
    "faster_whisper",
    "ctranslate2",
    "av",
    "soundcard",
    "webrtcvad",
    "soxr",
    "sentencepiece",
    "keyring",
    "huggingface_hub",
    "tokenizers",
    "onnxruntime",
    "platformdirs",
):
    try:
        package_datas, package_binaries, package_hidden = collect_all(package)
        datas += package_datas
        binaries += package_binaries
        hiddenimports += package_hidden
    except Exception as exc:
        print(f"[subloom] collect_all({package}) skipped: {exc}")

# Optional CUDA runtime wheels (1.2+ GB).  Only included when requested.
if os.environ.get("SUBLOOM_BUNDLE_CUDA") == "1" and sys.platform == "win32":
    for site_dir in site.getsitepackages():
        nvidia = Path(site_dir) / "nvidia"
        if not nvidia.is_dir():
            continue
        for package_dir in nvidia.iterdir():
            bin_dir = package_dir / "bin"
            if not bin_dir.is_dir():
                continue
            for dll in bin_dir.glob("*.dll"):
                binaries.append((str(dll), f"nvidia/{package_dir.name}/bin"))
    print("[subloom] CUDA runtime DLLs included")

icon = str(ASSETS / "icon.ico") if sys.platform == "win32" else None

a = Analysis(
    [str(ROOT / "packaging" / "launcher.py")],
    pathex=[str(SRC)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[str(ROOT / "packaging" / "hooks")],
    runtime_hooks=[],
    excludes=["tkinter", "pytest", "matplotlib", "scipy", "IPython"],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="SubLoom",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=icon,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="SubLoom",
)

if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name="SubLoom.app",
        icon=icon,
        bundle_identifier="app.subloom.captions",
        info_plist={
            "NSMicrophoneUsageDescription": "SubLoom needs microphone access to generate live subtitles.",
            "NSScreenCaptureUsageDescription": "SubLoom may capture system audio to generate live subtitles.",
            "LSMinimumSystemVersion": "13.0",
        },
    )
