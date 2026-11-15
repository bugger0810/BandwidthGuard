"""Packet engine: measures and throttles the traffic of one program.

How it works
------------
* WinDivert (via the ``pydivert`` package) lets us intercept network packets
  before Windows delivers them.
* A background thread keeps a list of the local ports that the chosen program
  currently uses (``psutil`` maps processes to ports).
* Every intercepted packet is matched against that port list:
    - not ours            -> re-injected immediately, untouched
    - ours, upload        -> counted, re-injected immediately
    - ours, download      -> counted and (optionally) delayed so that the
                             configured rate is never exceeded
* Delayed packets wait in a queue. If the queue is full the packet is dropped;
  TCP then slows the sender down by itself, which is exactly the effect we want.

The engine has no GUI code. The GUI just polls :meth:`BandwidthEngine.snapshot`.
"""

from __future__ import annotations

import ctypes
import queue
import threading
import time
from typing import Optional, Set, Tuple

import psutil

# Only look at TCP/UDP that leaves the machine (loopback is irrelevant).
PACKET_FILTER = "!loopback and (tcp or udp)"

MAX_QUEUE_BYTES = 512 * 1024   # waiting room for delayed packets
BURST_SECONDS = 0.03           # how far the pacer may "catch up" after a late wake-up
PORT_REFRESH_SECONDS = 0.5     # how often we re-read the program's ports


def _begin_timer_resolution() -> None:
    """Ask Windows for 1 ms timers; the default 15.6 ms is too coarse for pacing."""
    try:
        ctypes.windll.winmm.timeBeginPeriod(1)
    except Exception:
        pass


def _end_timer_resolution() -> None:
    try:
        ctypes.windll.winmm.timeEndPeriod(1)
    except Exception:
        pass


def scan_ports(process_name: str) -> Set[int]:
    """Return every local port currently used by processes called ``process_name``."""
    wanted = process_name.lower()
    ports: Set[int] = set()
    for proc in psutil.process_iter(["name"]):
        try:
            if (proc.info["name"] or "").lower() != wanted:
                continue
            # psutil >= 6 renamed connections() to net_connections().
            getter = getattr(proc, "net_connections", None) or proc.connections
            for conn in getter(kind="inet"):
                if conn.laddr:
                    ports.add(conn.laddr.port)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return ports


class BandwidthEngine:
    """Measures (and optionally throttles) the traffic of a single program."""

    def __init__(self) -> None:
        self.running: bool = False
        self.error: Optional[str] = None   # set if the filter dies unexpectedly

        self._handle = None
        self._stop = threading.Event()
        self._threads: list[threading.Thread] = []

        self._ports: Set[int] = set()
        self._ports_lock = threading.Lock()

        self._queue: "queue.Queue" = queue.Queue()
        self._queued_bytes = 0
        self._queue_lock = threading.Lock()

        self._in_bytes = 0
        self._out_bytes = 0
        self._count_lock = threading.Lock()

        self._process_name = ""
        self._rate = 1.0          # bytes per second
        self._throttle = False

    # ------------------------------------------------------------------ API
    def start(self, process_name: str, limit_mbit: float, throttle: bool) -> None:
        """Start filtering. Raises an exception if WinDivert cannot be opened
        (typically: no administrator rights, or an antivirus blocks the driver)."""
        if self.running:
            return

        import pydivert  # imported lazily so the GUI can start (and show an error) without it

        self._process_name = process_name
        self._rate = max(limit_mbit, 0.01) * 1_000_000 / 8
        self._throttle = throttle
        self.error = None
        self._in_bytes = self._out_bytes = 0
        self._queued_bytes = 0
        self._queue = queue.Queue()
        self._stop = threading.Event()

        with self._ports_lock:
            self._ports = scan_ports(process_name)   # so the first packets are matched too

        self._handle = pydivert.WinDivert(PACKET_FILTER)
        self._handle.open()
        _begin_timer_resolution()
        self.running = True

        self._threads = [
            threading.Thread(target=self._port_refresher, name="bg-ports", daemon=True),
            threading.Thread(target=self._sender, name="bg-sender", daemon=True),
            threading.Thread(target=self._receiver, name="bg-receiver", daemon=True),
        ]
        for thread in self._threads:
            thread.start()

    def stop(self) -> None:
        """Stop filtering. Packets still waiting in the queue are released first."""
        if self._handle is None:
            self.running = False
            return
        self._stop.set()
        for thread in self._threads:
            if thread.name == "bg-sender":
                thread.join(timeout=1.5)         # lets the sender flush the queue
        self.running = False
        try:
            self._handle.close()                  # also unblocks the receiver thread
        except Exception:
            pass
        self._handle = None
        _end_timer_resolution()

    def snapshot(self) -> Tuple[int, int]:
        """Total ``(downloaded, uploaded)`` bytes of the program since start."""
        with self._count_lock:
            return self._in_bytes, self._out_bytes

    # ------------------------------------------------------------- internals
    def _count(self, inbound: bool, size: int) -> None:
        with self._count_lock:
            if inbound:
                self._in_bytes += size
            else:
                self._out_bytes += size

    def _port_refresher(self) -> None:
        """Keep the set of the program's ports up to date (new connections appear all the time)."""
        while not self._stop.is_set():
            ports = scan_ports(self._process_name)
            with self._ports_lock:
                self._ports = ports
            self._stop.wait(PORT_REFRESH_SECONDS)

    def _receiver(self) -> None:
        """Main loop: take every packet from WinDivert and decide what to do with it."""
        try:
            for packet in self._handle:
                inbound = packet.is_inbound
                # The program's own port is the destination of incoming packets
                # and the source of outgoing ones.
                port = packet.dst_port if inbound else packet.src_port
                with self._ports_lock:
                    ours = port in self._ports

                if not ours:
                    self._handle.send(packet)
                    continue

                size = len(packet.raw)
                if inbound and self._throttle:
                    with self._queue_lock:
                        if self._queued_bytes + size > MAX_QUEUE_BYTES:
                            continue                      # drop -> TCP slows down
                        self._queued_bytes += size
                    self._queue.put(packet)               # the sender thread paces it
                else:
                    self._handle.send(packet)
                    self._count(inbound, size)
        except Exception as exc:
            # Closing the handle in stop() raises here – that is expected.
            if not self._stop.is_set():
                self.error = str(exc)
                self.running = False

    def _sender(self) -> None:
        """Release delayed download packets at the configured rate (token-bucket style)."""
        next_free = time.perf_counter()
        while True:
            try:
                packet = self._queue.get(timeout=0.1)
            except queue.Empty:
                if self._stop.is_set():
                    return
                continue

            size = len(packet.raw)
            if not self._stop.is_set():                   # while stopping: flush without delay
                now = time.perf_counter()
                # Each packet "occupies" size/rate seconds on the line. Allow a short
                # burst so a late wake-up does not permanently lose throughput.
                next_free = max(next_free, now - BURST_SECONDS) + size / self._rate
                wait = next_free - now
                if wait > 0.002:
                    time.sleep(wait)

            try:
                self._handle.send(packet)
                self._count(True, size)
            except Exception:
                pass
            with self._queue_lock:
                self._queued_bytes -= size
