"""Persistent user settings (stored as JSON in %APPDATA%\\BandwidthGuard)."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, fields

from .formatting import UNIT_MBIT
from .i18n import LANGUAGES
from .paths import config_dir, install_dir, settings_file


@dataclass
class Settings:
    """All values the app remembers between runs."""

    language: str = "auto"                # "auto" or a code from i18n.LANGUAGES
    theme: str = "auto"                   # "auto" | "dark" | "light"
    limit: float = 13.0                   # number as typed by the user
    unit: str = UNIT_MBIT                 # unit of ``limit`` (see formatting.py)
    measure_only: bool = False
    last_process: str = ""                # e.g. "chrome.exe"
    minimize_to_tray_on_close: bool = True
    start_minimized: bool = False
    window_width: int = 1060
    window_height: int = 700

    # Not stored: True when no settings file existed yet (very first start).
    first_run: bool = False

    @classmethod
    def load(cls) -> "Settings":
        """Read the settings file; fall back to defaults if it is missing/corrupt."""
        path = settings_file()
        if not path.exists():
            return cls(first_run=True)
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return cls()
        known = {f.name for f in fields(cls)} - {"first_run"}
        return cls(**{k: v for k, v in raw.items() if k in known})

    def save(self) -> None:
        """Write the settings file (errors are ignored – settings are not critical)."""
        try:
            config_dir().mkdir(parents=True, exist_ok=True)
            data = asdict(self)
            data.pop("first_run", None)
            settings_file().write_text(json.dumps(data, indent=2), encoding="utf-8")
        except OSError:
            pass


def installer_language() -> str:
    """Language chosen in the setup wizard, or "" if unavailable.

    The installer writes the wizard language code into ``install_lang.txt``
    next to the executable. We only use it on the very first start.
    """
    try:
        code = (install_dir() / "install_lang.txt").read_text(encoding="utf-8").strip().lower()
    except OSError:
        return ""
    return code if code in LANGUAGES else ""
