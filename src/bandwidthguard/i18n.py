"""Tiny translation layer.

Translations live in ``locales/<code>.json`` (flat ``"key": "text"`` objects).
English is the reference: ``tools/check_locales.py`` makes sure every other
language has exactly the same keys.

Usage::

    from bandwidthguard.i18n import t, set_language
    set_language("auto")            # or "de", "fr", ...
    label.setText(t("ctl.start"))
    t("tray.active", count=2, down="1 Mbit/s", up="0 Mbit/s")
"""

from __future__ import annotations

import json
from typing import Dict

from .paths import LOCALES_DIR

# code -> name of the language written in that language (shown in the UI)
LANGUAGES: Dict[str, str] = {
    "de": "Deutsch",
    "en": "English",
    "es": "Español",
    "fr": "Français",
    "it": "Italiano",
    "nl": "Nederlands",
    "pl": "Polski",
    "pt": "Português",
    "ru": "Русский",
    "tr": "Türkçe",
}

DEFAULT_LANGUAGE = "en"

# Windows "primary language id" (low 10 bits of a LANGID) -> our language code.
_PRIMARY_LANG_IDS = {
    0x07: "de", 0x09: "en", 0x0A: "es", 0x0C: "fr", 0x10: "it",
    0x13: "nl", 0x15: "pl", 0x16: "pt", 0x19: "ru", 0x1F: "tr",
}

_current: Dict[str, str] = {}
_fallback: Dict[str, str] = {}
_current_code = DEFAULT_LANGUAGE


def _load(code: str) -> Dict[str, str]:
    """Read one locale file. Returns an empty dict if it is missing or broken."""
    try:
        with open(LOCALES_DIR / f"{code}.json", encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return {}


def detect_system_language() -> str:
    """Return the language code that matches the Windows display language."""
    try:
        import ctypes

        lang_id = ctypes.windll.kernel32.GetUserDefaultUILanguage()
        code = _PRIMARY_LANG_IDS.get(lang_id & 0x3FF)
        if code:
            return code
    except Exception:  # not on Windows, or the call failed
        pass
    return DEFAULT_LANGUAGE


def set_language(code: str) -> str:
    """Activate a language ("auto" = follow Windows). Returns the resolved code."""
    global _current, _fallback, _current_code
    if code == "auto" or code not in LANGUAGES:
        code = detect_system_language()
    _fallback = _load(DEFAULT_LANGUAGE)
    _current = _fallback if code == DEFAULT_LANGUAGE else _load(code)
    _current_code = code
    return code


def current_language() -> str:
    return _current_code


def t(key: str, **kwargs) -> str:
    """Translate ``key``; falls back to English, then to the key itself."""
    if not _fallback:  # set_language() has not been called yet
        set_language("auto")
    text = _current.get(key) or _fallback.get(key) or key
    if kwargs:
        try:
            return text.format(**kwargs)
        except (KeyError, IndexError, ValueError):
            return text
    return text
