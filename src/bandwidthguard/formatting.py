"""Small, dependency-free helpers for numbers and units.

Everything in here is a pure function so it can be unit-tested without Qt or
Windows. Network speeds follow the usual convention: 1 Mbit/s = 1,000,000 bit/s
and 1 MB/s = 1,000,000 byte/s = 8 Mbit/s.
"""

from __future__ import annotations

from typing import Optional

UNIT_MBIT = "mbit"    # megabit per second
UNIT_MBYTE = "mbyte"  # megabyte per second


def bytes_per_s_to_mbit(bytes_per_second: float) -> float:
    """Convert a byte rate into megabit per second."""
    return bytes_per_second * 8 / 1_000_000


def bytes_per_s_to_mbyte(bytes_per_second: float) -> float:
    """Convert a byte rate into megabyte per second."""
    return bytes_per_second / 1_000_000


def to_mbit(value: float, unit: str) -> float:
    """Convert a user-entered limit (in ``unit``) to megabit per second."""
    return value * 8 if unit == UNIT_MBYTE else value


def parse_number(text: str) -> Optional[float]:
    """Parse a user-typed number. Accepts both ``13.5`` and ``13,5``.

    Returns ``None`` when the text is not a number.
    """
    cleaned = text.strip().replace(",", ".")
    if not cleaned:
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def format_bytes(count: float) -> str:
    """Human readable data amount, e.g. ``1.5 MB`` or ``2.31 GB`` (decimal units)."""
    if count < 1_000:
        return f"{int(count)} B"
    if count < 1_000_000:
        return f"{count / 1_000:.1f} KB"
    if count < 1_000_000_000:
        return f"{count / 1_000_000:.1f} MB"
    return f"{count / 1_000_000_000:.2f} GB"


def format_limit(value: float, unit: str) -> str:
    """Text such as ``13 Mbit/s`` or ``1.6 MB/s`` for status messages."""
    label = "MB/s" if unit == UNIT_MBYTE else "Mbit/s"
    return f"{value:g} {label}"
