"""Central place for every file-system location the app uses."""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Folder of the Python package. This also works inside a PyInstaller bundle,
# because the build script copies "locales" and "assets" to the same relative
# location (see tools/build.py).
PACKAGE_DIR = Path(__file__).resolve().parent
LOCALES_DIR = PACKAGE_DIR / "locales"
ASSETS_DIR = PACKAGE_DIR / "assets"


def is_frozen() -> bool:
    """True when running as the packaged .exe (PyInstaller), False from source."""
    return bool(getattr(sys, "frozen", False))


def install_dir() -> Path:
    """Folder that contains the executable (the installation folder when installed)."""
    if is_frozen():
        return Path(sys.executable).resolve().parent
    return PACKAGE_DIR.parent.parent  # repository root when running from source


def config_dir() -> Path:
    """Per-user settings folder: %APPDATA%\\BandwidthGuard."""
    base = os.environ.get("APPDATA")
    root = Path(base) if base else Path.home()
    return root / "BandwidthGuard"


def settings_file() -> Path:
    return config_dir() / "settings.json"
