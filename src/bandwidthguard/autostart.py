"""Start BandwidthGuard automatically when the user signs in to Windows.

Why a scheduled task and not the classic "Run" registry key?
BandwidthGuard needs administrator rights (packet filtering). Windows does not
start elevated programs from the Run key without showing a UAC prompt or
skipping them. A scheduled task with the "run with highest privileges" flag is
the standard, prompt-free way to start an elevated app at logon.

Creating or removing the task requires administrator rights, which the app
(and the installer) always have.
"""

from __future__ import annotations

import subprocess
import sys

from .paths import is_frozen

TASK_NAME = "BandwidthGuard"
_NO_WINDOW = 0x08000000  # CREATE_NO_WINDOW – do not flash a console window

# PowerShell script that registers the task. "{EXE}" is replaced with the real path.
_REGISTER_SCRIPT = """
$exe = '{EXE}'
$user = "$env:USERDOMAIN\\$env:USERNAME"
$action = New-ScheduledTaskAction -Execute $exe -Argument '--minimized' -WorkingDirectory (Split-Path $exe)
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $user
$principal = New-ScheduledTaskPrincipal -UserId $user -LogonType Interactive -RunLevel Highest
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit ([TimeSpan]::Zero)
Register-ScheduledTask -TaskName '{TASK}' -Action $action -Trigger $trigger -Principal $principal -Settings $settings -Force | Out-Null
"""


def _run(args: list[str]) -> int:
    """Run a command silently and return its exit code (1 on any failure)."""
    try:
        return subprocess.run(
            args, capture_output=True, creationflags=_NO_WINDOW, timeout=60
        ).returncode
    except Exception:
        return 1


def is_enabled() -> bool:
    """True if the autostart task exists."""
    return _run(["schtasks", "/Query", "/TN", TASK_NAME]) == 0


def enable() -> bool:
    """Create the autostart task. Only works for the installed/packaged .exe."""
    if not is_frozen():
        return False  # from source there is no stable executable to start
    exe = sys.executable.replace("'", "''")  # escape single quotes for PowerShell
    script = _REGISTER_SCRIPT.replace("{EXE}", exe).replace("{TASK}", TASK_NAME)
    code = _run(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", script]
    )
    return code == 0


def disable() -> bool:
    """Remove the autostart task (succeeds if it does not exist)."""
    if not is_enabled():
        return True
    return _run(["schtasks", "/Delete", "/TN", TASK_NAME, "/F"]) == 0
