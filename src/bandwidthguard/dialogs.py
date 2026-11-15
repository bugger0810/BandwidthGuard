"""Settings and About dialogs.

The dialogs apply changes immediately (no OK/Cancel). They talk to the main
window through a few small methods: ``set_language``, ``set_theme`` and
``set_autostart`` – see main_window.py.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices, QPixmap
from PySide6.QtWidgets import (
    QComboBox, QDialog, QHBoxLayout, QLabel, QMessageBox, QPushButton, QVBoxLayout, QWidget,
)

from . import __version__, GITHUB_URL, autostart, theme
from .i18n import LANGUAGES, t
from .paths import ASSETS_DIR
from .widgets import Switch
from .winutil import set_dark_titlebar


class _BaseDialog(QDialog):
    """Common behaviour: dark title bar that follows the current theme."""

    def showEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        super().showEvent(event)
        set_dark_titlebar(self, theme.current().is_dark)

    def refresh_titlebar(self) -> None:
        set_dark_titlebar(self, theme.current().is_dark)


class SettingsDialog(_BaseDialog):
    """Language, appearance and start-up behaviour."""

    def __init__(self, window) -> None:
        super().__init__(window)
        self._window = window
        self.setModal(True)
        self.setMinimumWidth(480)

        root = QVBoxLayout(self)
        root.setContentsMargins(26, 24, 26, 22)
        root.setSpacing(16)

        self._title = QLabel()
        self._title.setObjectName("h1")
        root.addWidget(self._title)

        # -- language and theme drop-downs
        self._language_label = QLabel()
        self._language_box = QComboBox()
        self._theme_label = QLabel()
        self._theme_box = QComboBox()
        root.addLayout(self._row(self._language_label, self._language_box))
        root.addLayout(self._row(self._theme_label, self._theme_box))

        # -- toggles
        self._autostart = Switch()
        self._tray_close = Switch()
        self._start_min = Switch()
        self._autostart_label, self._autostart_tip = QLabel(), QLabel()
        self._autostart_tip.setObjectName("muted")
        self._tray_label, self._min_label = QLabel(), QLabel()
        root.addLayout(self._toggle_row(self._autostart_label, self._autostart, self._autostart_tip))
        root.addLayout(self._toggle_row(self._tray_label, self._tray_close))
        root.addLayout(self._toggle_row(self._min_label, self._start_min))

        # -- close button
        self._close = QPushButton()
        self._close.clicked.connect(self.accept)
        footer = QHBoxLayout()
        footer.addStretch(1)
        footer.addWidget(self._close)
        root.addLayout(footer)

        self._load_state()
        self.retranslate()

        # Connect signals only after the initial state is loaded.
        self._language_box.currentIndexChanged.connect(self._on_language)
        self._theme_box.currentIndexChanged.connect(self._on_theme)
        self._autostart.toggled.connect(self._on_autostart)
        self._tray_close.toggled.connect(lambda on: setattr(window.settings, "minimize_to_tray_on_close", on))
        self._start_min.toggled.connect(lambda on: setattr(window.settings, "start_minimized", on))

    # -- layout helpers ------------------------------------------------------
    @staticmethod
    def _row(label: QLabel, widget: QWidget) -> QHBoxLayout:
        row = QHBoxLayout()
        row.addWidget(label, 1)
        row.addWidget(widget)
        return row

    @staticmethod
    def _toggle_row(label: QLabel, switch: Switch, tip: QLabel | None = None) -> QHBoxLayout:
        row = QHBoxLayout()
        text = QVBoxLayout()
        text.setSpacing(2)
        text.addWidget(label)
        if tip is not None:
            text.addWidget(tip)
        row.addLayout(text, 1)
        row.addWidget(switch, 0, Qt.AlignmentFlag.AlignVCenter)
        return row

    # -- state ---------------------------------------------------------------
    def _load_state(self) -> None:
        """Fill the controls from the current settings (without firing change events)."""
        settings = self._window.settings
        for widget in (self._language_box, self._theme_box, self._autostart, self._tray_close, self._start_min):
            widget.blockSignals(True)

        self._language_box.clear()
        self._language_box.addItem("", "auto")
        for code, name in LANGUAGES.items():
            self._language_box.addItem(name, code)
        self._language_box.setCurrentIndex(max(0, self._language_box.findData(settings.language)))

        self._theme_box.clear()
        for value in ("auto", "dark", "light"):
            self._theme_box.addItem("", value)
        self._theme_box.setCurrentIndex(max(0, self._theme_box.findData(settings.theme)))

        self._autostart.setChecked(autostart.is_enabled())
        self._tray_close.setChecked(settings.minimize_to_tray_on_close)
        self._start_min.setChecked(settings.start_minimized)

        for widget in (self._language_box, self._theme_box, self._autostart, self._tray_close, self._start_min):
            widget.blockSignals(False)

    def retranslate(self) -> None:
        """(Re)apply all texts – called again when the language changes."""
        self.setWindowTitle(t("set.title"))
        self._title.setText(t("set.title"))
        self._language_label.setText(t("set.language"))
        self._theme_label.setText(t("set.theme"))
        self._language_box.setItemText(0, t("set.language_auto"))
        for index, key in enumerate(("set.theme_auto", "set.theme_dark", "set.theme_light")):
            self._theme_box.setItemText(index, t(key))
        self._autostart_label.setText(t("set.autostart"))
        self._autostart_tip.setText(t("set.autostart_tip"))
        self._tray_label.setText(t("set.tray_close"))
        self._min_label.setText(t("set.start_min"))
        self._close.setText(t("btn.close"))

    # -- change handlers -------------------------------------------------------
    def _on_language(self) -> None:
        self._window.set_language(self._language_box.currentData())

    def _on_theme(self) -> None:
        self._window.set_theme(self._theme_box.currentData())

    def _on_autostart(self, enabled: bool) -> None:
        if not self._window.set_autostart(enabled):
            # Revert the switch and tell the user.
            self._autostart.blockSignals(True)
            self._autostart.setChecked(not enabled)
            self._autostart.blockSignals(False)
            QMessageBox.warning(self, t("err.title"), t("err.autostart"))


class AboutDialog(_BaseDialog):
    """Version, license and the vibe-coding note."""

    def __init__(self, window) -> None:
        super().__init__(window)
        self.setModal(True)
        self.setMinimumWidth(420)

        root = QVBoxLayout(self)
        root.setContentsMargins(30, 28, 30, 24)
        root.setSpacing(8)
        center = Qt.AlignmentFlag.AlignHCenter

        logo = QLabel()
        pixmap = QPixmap(str(ASSETS_DIR / "icon.png"))
        logo.setPixmap(pixmap.scaled(84, 84, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        root.addWidget(logo, 0, center)

        name = QLabel("BandwidthGuard")
        name.setObjectName("h1")
        root.addWidget(name, 0, center)

        self._version = QLabel()
        self._version.setObjectName("muted")
        root.addWidget(self._version, 0, center)
        root.addSpacing(8)

        self._text, self._vibe, self._license = QLabel(), QLabel(), QLabel()
        for label in (self._text, self._vibe, self._license):
            label.setWordWrap(True)
            label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
            root.addWidget(label)
        self._vibe.setObjectName("muted")
        self._license.setObjectName("muted")
        root.addSpacing(10)

        self._github = QPushButton()
        self._github.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(GITHUB_URL)))
        self._close = QPushButton()
        self._close.clicked.connect(self.accept)
        buttons = QHBoxLayout()
        buttons.addStretch(1)
        buttons.addWidget(self._github)
        buttons.addWidget(self._close)
        buttons.addStretch(1)
        root.addLayout(buttons)

        self.retranslate()

    def retranslate(self) -> None:
        self.setWindowTitle(t("about.title"))
        self._version.setText(t("about.version", version=__version__))
        self._text.setText(t("about.text"))
        self._vibe.setText(t("about.vibe"))
        self._license.setText(t("about.license"))
        self._github.setText(t("about.github"))
        self._close.setText(t("btn.close"))
