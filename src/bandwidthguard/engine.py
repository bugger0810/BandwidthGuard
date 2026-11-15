"""Packet engine: measures and throttles the traffic of several programs independently.

How it works
------------
* WinDivert (via the ``pydivert`` package) lets us intercept network packets
  before Windows delivers them. One handle serves all programs.
* Every monitored program is a :class:`Rule` with its own limit, its own waiting
  queue, its own pacer thread and its own counters – so limits never influence
  each other (e.g. program X at 10 Mbit/s and program Y at 11 Mbit/s).
* A background thread keeps a map "local port -> rule" up to date
  (``psutil`` maps processes to ports).
* Every intercepted packet is looked up in that map:
    - no rule             -> re-injected immediately, untouched
    - rule, upload        -> counted, re-injected immediately
    - rule, download      -> counted and (unless "measure only") delayed by the
                             rule's pacer so its limit is never exceeded
* Delayed packets wait in the rule's queue. If the queue is full the packet is
  dropped; TCP then slows the sender down by itself, which is the effect we want.

The engine has no GUI code. The GUI just polls :meth:`BandwidthEngine.snapshot_all`.
"""

from __future__ import annotations

import ctypes
import queue
import threading
import time
from typing import Dict, Iterable, Optional, Set, Tuple

import psutil

from .pacing import Pacer

# Only look at TCP/UDP that leaves the machine (loopback is irrelevant).
PACKET_FILTER = "!loopback and (tcp or udp)"

MAX_QUEUE_BYTES = 512 * 1024   # waiting room per rule for delayed packets
PORT_REFRESH_SECONDS = 0.5     # how often we re-read the programs' ports


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


def scan_ports(process_names: Iterable[str]) -> Dict[str, Set[int]]:
    """Map every (lower-case) process name to the local ports its processes use right now."""
    wanted = {name.lower() for name in process_names}
    result: Dict[str, Set[int]] = {name: set() for name in wanted}
    if not wanted:
        return result
    for proc in psutil.process_iter(["name"]):
        try:
            name = (proc.info["name"] or "").lower()
            if name not in wanted:
                continue
            # psutil >= 6 renamed connections() to net_connections().
            getter = getattr(proc, "net_connections", None) or proc.connections
            for conn in getter(kind="inet"):
                if conn.laddr:
                    result[name].add(conn.laddr.port)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return result


class Rule:
    """State of one monitored program."""

    def __init__(self, name: str, limit_mbit: Optional[float]) -> None:
        self.name = name                      # as shown to the user, e.g. "chrome.exe"
        self.key = name.lower()
        self.limit_mbit = limit_mbit          # None = measure only, no throttling
        self.pacer = Pacer(limit_mbit * 1_000_000 / 8) if limit_mbit else None

        self.queue: "queue.Queue" = queue.Queue()   # delayed download packets
        self.queued_bytes = 0
        self.queue_lock = threading.Lock()

        self.in_bytes = 0                     # downloaded so far
        self.out_bytes = 0                    # uploaded so far

        self.stop = threading.Event()
        self.thread: Optional[threading.Thread] = None


class BandwidthEngine:
    """Measures (and optionally throttles) the traffic of any number of programs."""

    def __init__(self) -> None:
        self.running: bool = False
        self.error: Optional[str] = None      # set if the filter dies unexpectedly

        self._handle = None
        self._stop = threading.Event()
        self._receiver: Optional[threading.Thread] = None
        self._refresher: Optional[threading.Thread] = None

        self._rules: Dict[str, Rule] = {}     # lower-case program name -> rule
        self._rules_lock = threading.Lock()
        self._port_map: Dict[int, Rule] = {}  # replaced as a whole, never edited in place
        self._count_lock = threading.Lock()

    # ------------------------------------------------------------------ API
    def has_rule(self, name: str) -> bool:
        return name.lower() in self._rules

    def rule_count(self) -> int:
        return len(self._rules)

    def add_rule(self, name: str, limit_mbit: Optional[float]) -> None:
        """Start limiting (``limit_mbit`` > 0) or just measuring (``None``) a program.

        Calling it again for a program that already has a rule replaces that rule.
        Raises an exception if WinDivert cannot be opened (typically: no administrator
        rights, or an antivirus blocks the driver).
        """
        self._ensure_started()
        rule = Rule(name, limit_mbit)
        with self._rules_lock:
            old = self._rules.get(rule.key)
            self._rules[rule.key] = rule
        if rule.pacer is not None:
            rule.thread = threading.Thread(target=self._rule_sender, args=(rule,),
                                           name=f"bg-sender-{rule.key}", daemon=True)
            rule.thread.start()
        self._rebuild_port_map()              # so the first packets are matched right away
        if old is not None:
            self._shutdown_rule(old)

    def remove_rule(self, name: str) -> None:
        """Stop limiting one program. When the last rule is gone the filter is closed."""
        with self._rules_lock:
            rule = self._rules.pop(name.lower(), None)
        self._rebuild_port_map()
        if rule is not None:
            self._shutdown_rule(rule)
        if not self._rules:
            self.stop()

    def stop(self) -> None:
        """Remove all rules and close the packet filter."""
        if self._handle is None:
            self.running = False
            return
        self._stop.set()
        with self._rules_lock:
            rules = list(self._rules.values())
            self._rules.clear()
        self._port_map = {}
        for rule in rules:                    # flush waiting packets while the handle is still open
            self._shutdown_rule(rule)
        self.running = False
        try:
            self._handle.close()              # also unblocks the receiver thread
        except Exception:
            pass
        self._handle = None
        _end_timer_resolution()

    def snapshot_all(self) -> Dict[str, Tuple[int, int]]:
        """``{lower-case name: (downloaded_bytes, uploaded_bytes)}`` for every rule."""
        with self._rules_lock:
            rules = list(self._rules.values())
        with self._count_lock:
            return {rule.key: (rule.in_bytes, rule.out_bytes) for rule in rules}

    # ------------------------------------------------------------- internals
    def _ensure_started(self) -> None:
        """Open WinDivert and start the shared threads (only once)."""
        if self.running:
            return
        import pydivert  # imported lazily so the GUI can start (and show an error) without it

        self.error = None
        self._stop = threading.Event()
        self._handle = pydivert.WinDivert(PACKET_FILTER)
        self._handle.open()
        _begin_timer_resolution()
        self.running = True

        self._refresher = threading.Thread(target=self._port_refresher, name="bg-ports", daemon=True)
        self._receiver = threading.Thread(target=self._receive_loop, name="bg-receiver", daemon=True)
        self._refresher.start()
        self._receiver.start()

    def _shutdown_rule(self, rule: Rule) -> None:
        """Stop a rule's pacer thread; it releases its waiting packets first."""
        rule.stop.set()
        if rule.thread is not None:
            rule.thread.join(timeout=1.5)

    def _count(self, rule: Rule, inbound: bool, size: int) -> None:
        with self._count_lock:
            if inbound:
                rule.in_bytes += size
            else:
                rule.out_bytes += size

    def _rebuild_port_map(self) -> None:
        """Re-read which ports the monitored programs use and publish a fresh port -> rule map."""
        with self._rules_lock:
            rules = list(self._rules.values())
        ports = scan_ports(rule.key for rule in rules)
        new_map: Dict[int, Rule] = {}
        for rule in rules:
            for port in ports.get(rule.key, ()):
                new_map[port] = rule
        self._port_map = new_map              # atomic swap; the receiver never sees a half-built map

    def _port_refresher(self) -> None:
        """New connections appear all the time, so keep the map fresh."""
        while not self._stop.is_set():
            self._rebuild_port_map()
            self._stop.wait(PORT_REFRESH_SECONDS)

    def _receive_loop(self) -> None:
        """Main loop: take every packet from WinDivert and decide what to do with it."""
        handle = self._handle
        try:
            for packet in handle:
                inbound = packet.is_inbound
                # The program's own port is the destination of incoming packets
                # and the source of outgoing ones.
                port = packet.dst_port if inbound else packet.src_port
                rule = self._port_map.get(port)

                if rule is None:
                    handle.send(packet)           # not one of ours
                    continue

                size = len(packet.raw)
                if inbound and rule.pacer is not None:
                    with rule.queue_lock:
                        if rule.queued_bytes + size > MAX_QUEUE_BYTES:
                            continue              # drop -> TCP slows down
                        rule.queued_bytes += size
                    rule.queue.put(packet)        # the rule's pacer thread releases it
                else:
                    handle.send(packet)
                    self._count(rule, inbound, size)
        except Exception as exc:
            # Closing the handle in stop() raises here – that is expected.
            if not self._stop.is_set():
                self.error = str(exc)
                self.running = False

    def _rule_sender(self, rule: Rule) -> None:
        """Release one rule's delayed download packets at its configured rate."""
        while True:
            try:
                packet = rule.queue.get(timeout=0.1)
            except queue.Empty:
                if rule.stop.is_set():
                    return
                continue

            size = len(packet.raw)
            if not rule.stop.is_set():            # while stopping: flush without delay
                wait = rule.pacer.delay(size, time.perf_counter())
                if wait > 0.002:
                    time.sleep(wait)

            try:
                self._handle.send(packet)
                self._count(rule, True, size)
            except Exception:
                pass
            with rule.queue_lock:
                rule.queued_bytes -= size
