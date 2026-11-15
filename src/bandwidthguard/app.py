"""Program entry point: command-line handling, start-up checks and the Qt event loop.

Command-line switches
---------------------
--minimized          start hidden in the tray (used by the autostart task)
--lang <code>        override the language for this run (e.g. ``--lang de``)
--enable-autostart   create the autostart task and exit   (used by the installer)
--disable-autostart  remove the autostart task and exit   (used by the uninstaller)
"""

from __future__ import annotations

import sys
from typing import List

from . import autostart, i18n, theme, winutil
from .settings import Settings, installer_language


def _option_value(args: List[str], name: str) -> str:
    """Return the value that follows ``name`` in ``args`` ("" if absent)."""
    if name in args:
        index = args.index(name)
        if index + 1 < len(args):
            return args[index + 1]
    return ""


def main() -> int:
    args = sys.argv[1:]

    if sys.platform != "win32":
        print("BandwidthGuard only runs on Windows.")
        return 1

    # -- maintenance commands used by the installer (no window) ---------------
    if "--enable-autostart" in args:
        return 0 if autostart.enable() else 1
    if "--disable-autostart" in args:
        return 0 if autostart.disable() else 1

    # -- packet filtering needs administrator rights ---------------------------
    # (The packaged .exe already requests them via its manifest; this branch is
    #  for running from source.)
    if not winutil.is_admin():
        winutil.relaunch_as_admin(args)
        return 0

    # Qt is imported late so the maintenance commands above start instantly.
    from PySide6.QtGui import QFont
    from PySide6.QtWidgets import QApplication, QMessageBox

    from .main_window import MainWindow

    # -- settings and language --------------------------------------------------
    settings = Settings.load()
    if settings.first_run and settings.language == "auto":
        chosen_in_setup = installer_language()
        if chosen_in_setup:
            settings.language = chosen_in_setup
    override = _option_value(args, "--lang")
    i18n.set_language(override or settings.language)

    # -- Qt application -----------------------------------------------------------
    winutil.set_app_user_model_id()
    app = QApplication(sys.argv)
    app.setApplicationName("BandwidthGuard")
    app.setStyle("Fusion")                    # consistent base style; theme.py does the rest
    app.setFont(QFont("Segoe UI", 10))
    app.setQuitOnLastWindowClosed(False)      # closing the window hides it to the tray
    theme.apply_theme(app, settings.theme)

    if not winutil.acquire_single_instance():
        QMessageBox.information(None, "BandwidthGuard", i18n.t("err.already"))
        return 0

    window = MainWindow(settings)
    app.aboutToQuit.connect(window.shutdown_engine)

    start_hidden = ("--minimized" in args or settings.start_minimized) and window.tray_available
    if not start_hidden:
        window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
