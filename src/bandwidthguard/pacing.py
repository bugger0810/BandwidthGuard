"""Pure rate-pacing logic (no Windows, no threads – easy to unit-test).

Idea: every packet "occupies" the line for ``size / rate`` seconds. We keep track of
the moment the line becomes free again (``_next_free``). A packet that arrives while
the line is still busy has to wait until then; a packet that arrives later than that
goes straight through.

A short burst allowance lets the pacer "catch up" after a late wake-up (Windows
timers are not perfectly precise) so the average speed still matches the limit.
"""

from __future__ import annotations


class Pacer:
    """Computes how long each packet must be delayed to stay below a byte rate."""

    def __init__(self, rate_bytes_per_s: float, burst_seconds: float = 0.03) -> None:
        self.rate = max(rate_bytes_per_s, 1.0)
        self.burst = burst_seconds
        self._next_free = 0.0

    def delay(self, size: int, now: float) -> float:
        """Seconds to wait before releasing a packet of ``size`` bytes at time ``now``."""
        self._next_free = max(self._next_free, now - self.burst) + size / self.rate
        return max(0.0, self._next_free - now)
