"""Integration test of the multi-program engine with a fake WinDivert (no Windows needed).

Program A is throttled to 8 Mbit/s (= 1,000,000 bytes/s), program B is only measured.
We feed fake packets through the engine and check that
  * A's download is delayed to its limit,
  * B and unrelated traffic are not delayed at all,
  * counters are kept separately per program,
  * the packet filter is closed when the last rule is removed.
"""
import queue
import sys
import time
import types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

try:
    import psutil  # noqa: F401
except ImportError:  # the engine only needs the name to import; ports are faked below
    stub = types.ModuleType("psutil")
    stub.NoSuchProcess = stub.AccessDenied = Exception
    stub.process_iter = lambda *a, **k: []
    sys.modules["psutil"] = stub


class FakePacket:
    def __init__(self, inbound, port, size):
        self.is_inbound = inbound
        self.dst_port = port if inbound else 9999
        self.src_port = 9999 if inbound else port
        self.raw = b"x" * size


class FakeWinDivert:
    """Stands in for pydivert.WinDivert: yields queued packets, records what is sent."""

    last = None

    def __init__(self, _filter):
        self.incoming = queue.Queue()
        self.sent = []
        self.closed = False
        FakeWinDivert.last = self

    def open(self):
        pass

    def close(self):
        self.closed = True
        self.incoming.put(None)

    def send(self, packet):
        self.sent.append((packet, time.perf_counter()))

    def __iter__(self):
        while True:
            packet = self.incoming.get()
            if packet is None:
                raise OSError("handle closed")   # like the real library after close()
            yield packet


def _wait_until(condition, timeout=5.0):
    end = time.perf_counter() + timeout
    while time.perf_counter() < end:
        if condition():
            return True
        time.sleep(0.01)
    return False


def test_rules_work_independently():
    fake_module = types.ModuleType("pydivert")
    fake_module.WinDivert = FakeWinDivert
    saved_module = sys.modules.get("pydivert")
    sys.modules["pydivert"] = fake_module

    from bandwidthguard import engine as eng
    saved_scan = eng.scan_ports
    ports = {"a.exe": {1111}, "b.exe": {2222}}
    eng.scan_ports = lambda names: {n.lower(): set(ports.get(n.lower(), ())) for n in names}

    try:
        engine = eng.BandwidthEngine()
        engine.add_rule("A.exe", 8.0)       # 1,000,000 bytes/s
        engine.add_rule("B.exe", None)      # measure only
        assert engine.rule_count() == 2 and engine.has_rule("a.EXE")
        handle = FakeWinDivert.last

        start = time.perf_counter()
        for _ in range(200):
            handle.incoming.put(FakePacket(True, 1111, 1000))     # A download  -> must be paced
        for _ in range(200):
            handle.incoming.put(FakePacket(True, 2222, 1000))     # B download  -> immediately
        for _ in range(50):
            handle.incoming.put(FakePacket(True, 3333, 1000))     # unrelated   -> immediately
        for _ in range(50):
            handle.incoming.put(FakePacket(False, 1111, 1000))    # A upload    -> immediately

        assert _wait_until(lambda: len(handle.sent) == 500), "not all packets were forwarded"
        finished = max(t for _, t in handle.sent) - start

        # A's 200,000 bytes at 1,000,000 bytes/s need ~0.2 s (minus a 30 ms burst allowance).
        assert finished >= 0.12, finished

        # Everything that is not A's download must have been forwarded long before that.
        fast = [t for p, t in handle.sent if not (p.is_inbound and p.dst_port == 1111)]
        assert max(fast) - start < 0.1

        snapshot = engine.snapshot_all()
        assert snapshot["a.exe"] == (200_000, 50_000)
        assert snapshot["b.exe"] == (200_000, 0)

        # Removing one rule keeps the filter alive for the other one ...
        engine.remove_rule("A.exe")
        assert engine.running and engine.rule_count() == 1 and not handle.closed
        # ... removing the last rule closes it.
        engine.remove_rule("B.exe")
        assert not engine.running and handle.closed
    finally:
        eng.scan_ports = saved_scan
        if saved_module is None:
            sys.modules.pop("pydivert", None)
        else:
            sys.modules["pydivert"] = saved_module
