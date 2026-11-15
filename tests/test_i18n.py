"""Tests for the translation layer and the locale files."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from bandwidthguard import i18n  # noqa: E402


def test_every_language_has_a_complete_file():
    reference = set(json.loads((i18n.LOCALES_DIR / "en.json").read_text(encoding="utf-8")))
    for code in i18n.LANGUAGES:
        data = json.loads((i18n.LOCALES_DIR / f"{code}.json").read_text(encoding="utf-8"))
        assert set(data) == reference, code


def test_translation_and_formatting():
    i18n.set_language("de")
    assert i18n.t("ctl.start") == "Start"
    assert "13 Mbit/s" in i18n.t("stat.limited", name="x.exe", limit="13 Mbit/s")


def test_unknown_key_returns_key():
    i18n.set_language("en")
    assert i18n.t("does.not.exist") == "does.not.exist"


def test_unknown_language_falls_back_to_system_or_english():
    code = i18n.set_language("xx")
    assert code in i18n.LANGUAGES
