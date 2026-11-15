"""Build the BandwidthGuard application folder with PyInstaller.

Result: dist/BandwidthGuard/BandwidthGuard.exe (plus its support files)

The folder ("one-dir") layout is intentional: the bundled libraries (Qt, WinDivert,
pydivert) are LGPL-licensed and stay replaceable as separate files. It also starts
faster and triggers fewer antivirus false positives than a single-file exe.

Usage:  python tools/build.py
Requires: pip install -r requirements.txt -r requirements-dev.txt
"""
import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
PKG = SRC / "bandwidthguard"


def main() -> int:
    try:
        import PyInstaller.__main__ as pyinstaller
    except ImportError:
        print("PyInstaller is not installed. Run: pip install -r requirements-dev.txt")
        return 1

    # Start from a clean slate so stale files never end up in the installer.
    for folder in ("build", "dist"):
        shutil.rmtree(ROOT / folder, ignore_errors=True)

    sep = os.pathsep  # ';' on Windows – separates source and destination in --add-data
    args = [
        str(ROOT / "run.py"),
        "--name", "BandwidthGuard",
        "--noconfirm", "--clean",
        "--windowed",                         # no console window
        "--uac-admin",                        # ask for administrator rights (needed by WinDivert)
        "--icon", str(PKG / "assets" / "icon.ico"),
        "--paths", str(SRC),
        "--collect-all", "pydivert",          # includes WinDivert64.dll / WinDivert64.sys
        "--add-data", f"{PKG / 'locales'}{sep}bandwidthguard/locales",
        "--add-data", f"{PKG / 'assets'}{sep}bandwidthguard/assets",
        "--exclude-module", "tkinter",
        "--distpath", str(ROOT / "dist"),
        "--workpath", str(ROOT / "build" / "pyinstaller"),
        "--specpath", str(ROOT / "build"),
    ]
    pyinstaller.run(args)

    exe = ROOT / "dist" / "BandwidthGuard" / "BandwidthGuard.exe"
    if not exe.exists():
        print("Build failed: BandwidthGuard.exe was not created.")
        return 1
    print(f"\nBuild OK: {exe}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
