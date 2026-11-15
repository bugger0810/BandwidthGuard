"""Small Windows-specific helpers (admin rights, single instance, dark title bar).

Every function is wrapped so that it fails quietly: none of these helpers is
important enough to crash the app.
"""

from __future__ import annotations

import ctypes
import sys
from typing import List

from .paths import is_frozen

MUTEX_NAME = "BandwidthGuardMutex"          # must match AppMutex in installer/BandwidthGuard.iss
APP_USER_MODEL_ID = "bugger0810.BandwidthGuard"
ERROR_ALREADY_EXISTS = 183

_mutex_handle = None  # kept alive for the whole process lifetime


def is_admin() -> bool:
    """True if the process runs with administrator rights."""
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def relaunch_as_admin(args: List[str]) -> bool:
    """Start this program again with a UAC prompt. Returns True if Windows accepted it.

    The packaged .exe already asks for elevation through its manifest, so this
    is mainly used when running from source (``python run.py``).
    """
    try:
        if is_frozen():
            exe, params = sys.executable, args
        else:
            exe, params = sys.executable, [sys.argv[0], *args]
        param_text = " ".join(f'"{p}"' for p in params)
        result = ctypes.windll.shell32.ShellExecuteW(None, "runas", exe, param_text, None, 1)
        return result > 32
    except Exception:
        return False


def acquire_single_instance() -> bool:
    """Create a named mutex. Returns False if another instance already owns it."""
    global _mutex_handle
    try:
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.CreateMutexW.restype = ctypes.c_void_p
        _mutex_handle = kernel32.CreateMutexW(None, False, MUTEX_NAME)
        return ctypes.get_last_error() != ERROR_ALREADY_EXISTS
    except Exception:
        return True  # if the check itself fails, do not block the start


def set_app_user_model_id() -> None:
    """Gives the app its own taskbar identity (so the taskbar shows our icon, not Python's)."""
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_USER_MODEL_ID)
    except Exception:
        pass


def set_dark_titlebar(widget, dark: bool) -> None:
    """Switch the native Windows title bar between dark and light (Windows 10 1809+ / 11)."""
    if sys.platform != "win32":
        return
    try:
        hwnd = ctypes.c_void_p(int(widget.winId()))
        value = ctypes.c_int(1 if dark else 0)
        # Attribute 20 is the documented value; 19 was used before Windows 10 20H1.
        for attribute in (20, 19):
            if ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd, attribute, ctypes.byref(value), ctypes.sizeof(value)
            ) == 0:
                break
    except Exception:
        pass
