"""Tests for the pacing logic used to throttle downloads."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from bandwidthguard.pacing import Pacer  # noqa: E402


def test_average_rate_matches_limit():
    """100 packets of 1000 bytes at 10,000 B/s must take about 10 seconds."""
    pacer = Pacer(10_000)
    now = 0.0
    for _ in range(100):
        now += pacer.delay(1000, now)
    assert 9.9 <= now <= 10.1


def test_small_packet_on_fast_line_is_not_delayed():
    pacer = Pacer(1_625_000)           # 13 Mbit/s
    assert pacer.delay(1500, 100.0) == 0.0


def test_two_limiters_are_independent():
    slow, fast = Pacer(1_000), Pacer(1_000_000)
    assert slow.delay(5_000, 100.0) > 1.0
    assert fast.delay(5_000, 100.0) == 0.0


def test_idle_time_does_not_build_up_unlimited_credit():
    """After a long pause the next packets must still be paced, not released as one huge burst."""
    pacer = Pacer(10_000)
    pacer.delay(100, 0.0)
    now = 1_000.0                      # long idle period
    total_delay = sum(pacer.delay(1000, now) for _ in range(10))
    assert total_delay > 0.5
