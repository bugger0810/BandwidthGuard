"""Builds the list of programs shown on the left side of the main window."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Dict, List, Optional

import psutil


@dataclass
class ProcessGroup:
    """All running processes that share the same executable name (e.g. every chrome.exe)."""

    name: str
    instances: int = 0
    connections: int = 0
    exe: Optional[str] = None   # full path of one instance, used to look up the icon


def list_process_groups() -> List[ProcessGroup]:
    """Return one entry per executable name, with instance and connection counts."""
    # One system-wide call is much faster than asking every process separately.
    connections_per_pid: Counter = Counter()
    try:
        for conn in psutil.net_connections(kind="inet"):
            if conn.pid:
                connections_per_pid[conn.pid] += 1
    except (psutil.AccessDenied, OSError):
        pass

    groups: Dict[str, ProcessGroup] = {}
    for proc in psutil.process_iter(["pid", "name", "exe"]):
        name = proc.info.get("name")
        if not name:
            continue
        group = groups.setdefault(name, ProcessGroup(name=name))
        group.instances += 1
        group.connections += connections_per_pid.get(proc.info["pid"], 0)
        if not group.exe:
            group.exe = proc.info.get("exe")
    return list(groups.values())
