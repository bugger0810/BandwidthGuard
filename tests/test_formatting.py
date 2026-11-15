"""Unit tests for the pure helper functions (no Qt / Windows needed)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from bandwidthguard.formatting import (  # noqa: E402
    UNIT_MBIT, UNIT_MBYTE, bytes_per_s_to_mbit, bytes_per_s_to_mbyte,
    format_bytes, format_limit, parse_number, to_mbit,
)


def test_13_mbit_is_1_625_mbyte():
    assert bytes_per_s_to_mbyte(13 * 1_000_000 / 8) == 1.625


def test_byte_rate_to_mbit():
    assert bytes_per_s_to_mbit(1_250_000) == 10.0


def test_to_mbit_converts_units():
    assert to_mbit(13, UNIT_MBIT) == 13
    assert to_mbit(2, UNIT_MBYTE) == 16


def test_parse_number_accepts_comma_and_dot():
    assert parse_number("13,5") == 13.5
    assert parse_number(" 13.5 ") == 13.5
    assert parse_number("") is None
    assert parse_number("abc") is None


def test_format_bytes():
    assert format_bytes(512) == "512 B"
    assert format_bytes(1_500) == "1.5 KB"
    assert format_bytes(2_500_000) == "2.5 MB"
    assert format_bytes(3_210_000_000) == "3.21 GB"


def test_format_limit():
    assert format_limit(13.0, UNIT_MBIT) == "13 Mbit/s"
    assert format_limit(1.6, UNIT_MBYTE) == "1.6 MB/s"
