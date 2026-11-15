"""Dark / light colour palettes and the Qt stylesheet built from them.

All colours of the UI come from the :class:`Palette` dataclass. To tweak the
look of the app, change the values below – no other file needs to be touched.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from string import Template

from .paths import ASSETS_DIR


@dataclass(frozen=True)
class Palette:
    is_dark: bool
    bg: str            # window background
    card: str          # cards / panels
    border: str
    text: str
    muted: str         # secondary text
    accent: str
    accent_hover: str
    accent_pressed: str
    danger: str        # the "Stop" button
    danger_hover: str
    field: str         # input fields, neutral buttons
    row_hover: str
    selection: str     # selected table row
    down: str          # download colour (tile + graph)
    up: str            # upload colour (tile + graph)
    grid: str          # graph grid lines
    graph_bg: str      # graph / tile background
    switch_off: str    # toggle switch, switched off
    chevron: str       # file name of the combo-box arrow image


DARK = Palette(
    is_dark=True, bg="#0f1115", card="#171a21", border="#262b36", text="#e6e8ee",
    muted="#8b93a7", accent="#3b82f6", accent_hover="#5b9bff", accent_pressed="#2f6fe0",
    danger="#ef4444", danger_hover="#f26363", field="#0f1218", row_hover="#1d222c",
    selection="#1e3a6e", down="#4c9aff", up="#ffa14a", grid="#252b37",
    graph_bg="#12151b", switch_off="#3a4152", chevron="chevron_dark.png",
)

LIGHT = Palette(
    is_dark=False, bg="#f3f5f9", card="#ffffff", border="#e1e5ed", text="#1b1f2a",
    muted="#6b7385", accent="#2563eb", accent_hover="#3b78f2", accent_pressed="#1d4fc4",
    danger="#dc2626", danger_hover="#e53e3e", field="#f6f8fb", row_hover="#f1f4fa",
    selection="#dbe8ff", down="#2563eb", up="#ea7a12", grid="#e7ebf2",
    graph_bg="#f9fafc", switch_off="#c3cad8", chevron="chevron_light.png",
)

_current: Palette = DARK


def current() -> Palette:
    """The palette that is active right now (custom-painted widgets read this)."""
    return _current


def detect_system_theme() -> str:
    """Return "dark" or "light" according to the Windows app-theme setting."""
    try:
        import winreg

        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize",
        )
        value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
        return "light" if value else "dark"
    except Exception:
        return "dark"


def resolve(name: str) -> Palette:
    """Map a setting value ("auto" / "dark" / "light") to a palette."""
    if name == "auto":
        name = detect_system_theme()
    return LIGHT if name == "light" else DARK


# Qt stylesheet. "$name" placeholders are filled from the Palette.
_QSS = Template(r"""
* { font-family: "Segoe UI Variable Text", "Segoe UI", sans-serif; }
QMainWindow, QDialog, QMessageBox { background: $bg; }
QWidget { color: $text; font-size: 13px; }
QLabel { background: transparent; }
QToolTip { background: $card; color: $text; border: 1px solid $border; padding: 4px 6px; }

/* ---- cards and tiles ------------------------------------------------- */
QFrame#card { background: $card; border: 1px solid $border; border-radius: 14px; }
QFrame#ruleCard { background: $graph_bg; border: 1px solid $border; border-radius: 12px; }
QScrollArea { background: transparent; border: none; }
QScrollArea > QWidget > QWidget { background: transparent; }

/* ---- text styles ------------------------------------------------------ */
QLabel#h1 { font-size: 22px; font-weight: 700; }
QLabel#h2 { font-size: 15px; font-weight: 600; }
QLabel#muted { color: $muted; }
QLabel#selectedName { font-size: 15px; font-weight: 600; }
QLabel#rate { font-size: 16px; font-weight: 700; }
QLabel#chip { background: $field; border: 1px solid $border; border-radius: 8px; padding: 4px 10px; color: $accent; font-weight: 600; }

/* ---- inputs ------------------------------------------------------------ */
QLineEdit { background: $field; border: 1px solid $border; border-radius: 8px; padding: 7px 10px;
            selection-background-color: $accent; selection-color: #ffffff; }
QLineEdit:focus { border: 1px solid $accent; }
QLineEdit:disabled { color: $muted; }

/* ---- buttons ----------------------------------------------------------- */
QPushButton { background: $field; border: 1px solid $border; border-radius: 8px; padding: 8px 14px; }
QPushButton:hover { background: $row_hover; }
QPushButton:disabled { color: $muted; }
QPushButton#primary { background: $accent; border: 1px solid $accent; color: #ffffff;
                      font-weight: 600; font-size: 14px; padding: 11px 16px; }
QPushButton#primary:hover { background: $accent_hover; border-color: $accent_hover; }
QPushButton#primary:pressed { background: $accent_pressed; }
QPushButton#primary:disabled { background: $border; border-color: $border; color: $muted; }
QPushButton#primary[running="true"] { background: $danger; border-color: $danger; }
QPushButton#primary[running="true"]:hover { background: $danger_hover; border-color: $danger_hover; }

QPushButton#dangerSmall { background: transparent; border: 1px solid $danger; color: $danger; padding: 5px 14px; }
QPushButton#dangerSmall:hover { background: $danger; color: #ffffff; }

/* segmented control (unit selector) */
QPushButton#seg { border-radius: 0px; padding: 7px 14px; }
QPushButton#seg[pos="left"] { border-top-left-radius: 8px; border-bottom-left-radius: 8px; }
QPushButton#seg[pos="right"] { border-top-right-radius: 8px; border-bottom-right-radius: 8px; border-left: none; }
QPushButton#seg:checked { background: $accent; border-color: $accent; color: #ffffff; font-weight: 600; }
QPushButton#seg:disabled:checked { background: $border; border-color: $border; color: $muted; }

QToolButton#iconBtn { background: transparent; border: 1px solid transparent; border-radius: 8px;
                      padding: 5px 9px; font-size: 18px; }
QToolButton#iconBtn:hover { background: $row_hover; border-color: $border; }

/* ---- combo box ---------------------------------------------------------- */
QComboBox { background: $field; border: 1px solid $border; border-radius: 8px; padding: 6px 10px; min-width: 170px; }
QComboBox:hover { border-color: $accent; }
QComboBox::drop-down { border: none; width: 26px; }
QComboBox::down-arrow { image: url("$chevron_url"); width: 12px; height: 12px; }
QComboBox QAbstractItemView { background: $card; border: 1px solid $border; outline: 0; padding: 4px;
                              selection-background-color: $selection; selection-color: $text; }

/* ---- process table ------------------------------------------------------- */
QTableWidget#procTable { background: transparent; border: none; outline: 0; }
QTableWidget#procTable::item { padding: 6px 8px; border: none; }
QTableWidget#procTable::item:selected { background: $selection; color: $text; }
QTableWidget#procTable::item:disabled { color: $muted; }
QHeaderView { background: transparent; }
QHeaderView::section { background: transparent; color: $muted; border: none; border-bottom: 1px solid $border;
                       padding: 8px; font-weight: 600; font-size: 12px; text-align: left; }

/* ---- scroll bars ----------------------------------------------------------- */
QScrollBar:vertical { background: transparent; width: 10px; margin: 2px; }
QScrollBar::handle:vertical { background: $border; border-radius: 4px; min-height: 30px; }
QScrollBar::handle:vertical:hover { background: $switch_off; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
QScrollBar:horizontal { height: 0px; }

/* ---- menus (tray) ------------------------------------------------------------ */
QMenu { background: $card; border: 1px solid $border; border-radius: 8px; padding: 6px; }
QMenu::item { padding: 7px 24px; border-radius: 6px; }
QMenu::item:selected { background: $selection; }
QMenu::item:disabled { color: $muted; }
QMenu::separator { height: 1px; background: $border; margin: 5px 8px; }

QMessageBox QPushButton { min-width: 84px; }
""")


def build_stylesheet(palette: Palette) -> str:
    """Fill the stylesheet template with the colours of ``palette``."""
    values = asdict(palette)
    values["chevron_url"] = (ASSETS_DIR / palette.chevron).as_posix()
    return _QSS.safe_substitute(values)


def apply_theme(app, name: str) -> Palette:
    """Activate a theme application-wide and return its palette."""
    global _current
    _current = resolve(name)
    app.setStyleSheet(build_stylesheet(_current))
    return _current
