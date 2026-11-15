"""Tests for loading and saving settings."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from bandwidthguard import settings as settings_module  # noqa: E402
from bandwidthguard.settings import Settings  # noqa: E402


def test_first_run_flag_and_roundtrip(tmp_path, monkeypatch):
    target = tmp_path / "BandwidthGuard"
    monkeypatch.setattr(settings_module, "config_dir", lambda: target)
    monkeypatch.setattr(settings_module, "settings_file", lambda: target / "settings.json")

    first = Settings.load()
    assert first.first_run is True

    first.limit = 7.5
    first.language = "fr"
    first.save()

    again = Settings.load()
    assert again.first_run is False
    assert again.limit == 7.5
    assert again.language == "fr"


def test_corrupt_file_falls_back_to_defaults(tmp_path, monkeypatch):
    target = tmp_path / "BandwidthGuard"
    target.mkdir()
    (target / "settings.json").write_text("{ not json", encoding="utf-8")
    monkeypatch.setattr(settings_module, "settings_file", lambda: target / "settings.json")
    assert Settings.load().limit == 13.0
