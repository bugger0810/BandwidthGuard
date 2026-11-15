"""The main window: program list, limit controls, active limits and tray icon."""

from __future__ import annotations

import time
from typing import Dict, Optional

from PySide6.QtCore import QFileInfo, QRegularExpression, QSize, Qt, QTimer
from PySide6.QtGui import QAction, QColor, QIcon, QPixmap, QRegularExpressionValidator
from PySide6.QtWidgets import (
    QAbstractItemView, QApplication, QButtonGroup, QFileIconProvider, QFrame, QHBoxLayout, QHeaderView,
    QLabel, QLineEdit, QMainWindow, QMenu, QMessageBox, QPushButton, QScrollArea, QSizePolicy,
    QSystemTrayIcon, QTableWidget, QTableWidgetItem, QToolButton, QVBoxLayout, QWidget,
)

from . import autostart, i18n, theme
from .dialogs import AboutDialog, SettingsDialog
from .engine import BandwidthEngine
from .formatting import UNIT_MBIT, UNIT_MBYTE, bytes_per_s_to_mbit, format_limit, parse_number, to_mbit
from .i18n import t
from .paths import ASSETS_DIR
from .processes import list_process_groups
from .rule_card import RuleCard
from .settings import Settings
from .widgets import Card, Switch
from .winutil import set_dark_titlebar

TICK_MS = 500              # how often the traffic display updates
PROCESS_REFRESH_MS = 4000  # how often the program list refreshes


def app_icon() -> QIcon:
    return QIcon(str(ASSETS_DIR / "icon.png"))


def repolish(widget: QWidget) -> None:
    """Re-apply the stylesheet after a dynamic property changed."""
    widget.style().unpolish(widget)
    widget.style().polish(widget)
    widget.update()


class MainWindow(QMainWindow):
    """Everything the user sees. Heavy lifting is delegated to :class:`BandwidthEngine`."""

    def __init__(self, settings: Settings) -> None:
        super().__init__()
        self.settings = settings
        self.engine = BandwidthEngine()

        # --- state -----------------------------------------------------------
        self._selected: Optional[str] = settings.last_process or None
        self._cards: Dict[str, RuleCard] = {}   # lower-case program name -> card of the active limit
        self._last_time = 0.0
        self._quitting = False
        self._tray_notified = False
        self._shown_once = False
        self._unit = settings.unit if settings.unit in (UNIT_MBIT, UNIT_MBYTE) else UNIT_MBIT
        self._icon_provider = QFileIconProvider()
        self._icon_cache: Dict[str, QIcon] = {}
        self._exe_by_key: Dict[str, Optional[str]] = {}   # lower-case name -> .exe path (from the last refresh)
        self._settings_dialog: Optional[SettingsDialog] = None
        self._about_dialog: Optional[AboutDialog] = None

        self.setWindowIcon(app_icon())
        self.resize(settings.window_width, settings.window_height)

        self._build_ui()
        self._build_tray()
        self.retranslate()
        self._apply_theme_to_widgets()
        self.refresh_processes()
        self._update_min_size()

        self._tick_timer = QTimer(self)
        self._tick_timer.timeout.connect(self._tick)
        self._tick_timer.start(TICK_MS)
        self._process_timer = QTimer(self)
        self._process_timer.timeout.connect(self.refresh_processes)
        self._process_timer.start(PROCESS_REFRESH_MS)

    # ====================================================================
    # UI construction
    # ====================================================================
    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        outer = QVBoxLayout(central)
        outer.setContentsMargins(26, 22, 26, 24)
        outer.setSpacing(18)

        outer.addLayout(self._build_header())

        body = QHBoxLayout()
        body.setSpacing(18)
        body.addWidget(self._build_process_card(), 11)
        right = QVBoxLayout()
        right.setSpacing(18)
        right.addWidget(self._build_control_card())
        right.addWidget(self._build_rules_card(), 1)
        body.addLayout(right, 10)
        outer.addLayout(body, 1)

    def _build_header(self) -> QHBoxLayout:
        header = QHBoxLayout()
        header.setSpacing(14)

        logo = QLabel()
        logo.setPixmap(QPixmap(str(ASSETS_DIR / "icon.png")).scaled(
            44, 44, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        header.addWidget(logo)

        titles = QVBoxLayout()
        titles.setSpacing(0)
        name = QLabel("BandwidthGuard")
        name.setObjectName("h1")
        self.tagline = QLabel()
        self.tagline.setObjectName("muted")
        titles.addWidget(name)
        titles.addWidget(self.tagline)
        header.addLayout(titles)
        header.addStretch(1)

        self.about_button = QToolButton()
        self.about_button.setObjectName("iconBtn")
        self.about_button.setText("ⓘ")
        self.about_button.clicked.connect(self.show_about)
        self.settings_button = QToolButton()
        self.settings_button.setObjectName("iconBtn")
        self.settings_button.setText("⚙")
        self.settings_button.clicked.connect(self.show_settings)
        header.addWidget(self.about_button)
        header.addWidget(self.settings_button)
        return header

    def _build_process_card(self) -> Card:
        card = Card()
        layout = QVBoxLayout(card)
        layout.setContentsMargins(20, 18, 20, 16)
        layout.setSpacing(12)

        top = QHBoxLayout()
        self.proc_title = QLabel()
        self.proc_title.setObjectName("h2")
        self.refresh_button = QPushButton()
        self.refresh_button.clicked.connect(self.refresh_processes)
        top.addWidget(self.proc_title)
        top.addStretch(1)
        top.addWidget(self.refresh_button)
        layout.addLayout(top)

        self.search = QLineEdit()
        self.search.setClearButtonEnabled(True)
        self.search.setMinimumHeight(38)
        self.search.textChanged.connect(lambda _text: self.refresh_processes())
        layout.addWidget(self.search)

        filter_row = QHBoxLayout()
        self.only_net_switch = Switch()
        self.only_net_switch.setChecked(True)
        self.only_net_switch.toggled.connect(lambda _on: self.refresh_processes())
        self.only_net_label = QLabel()
        filter_row.addWidget(self.only_net_switch)
        filter_row.addWidget(self.only_net_label)
        filter_row.addStretch(1)
        layout.addLayout(filter_row)

        self.table = QTableWidget(0, 3)
        self.table.setObjectName("procTable")
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(38)
        self.table.setShowGrid(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.table.setIconSize(QSize(20, 20))
        self.table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        header = self.table.horizontalHeader()
        header.setHighlightSections(False)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(1, 90)
        self.table.setColumnWidth(2, 110)
        self.table.itemSelectionChanged.connect(self._on_selection_changed)
        layout.addWidget(self.table, 1)
        return card

    def _build_control_card(self) -> Card:
        card = Card()
        # The card always keeps the height its content needs. Without this, Qt squeezed
        # the widgets inside when the window was too small ("cut-off" controls).
        card.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(10)

        self.ctl_title = QLabel()
        self.ctl_title.setObjectName("h2")
        layout.addWidget(self.ctl_title)

        self.selected_caption = QLabel()
        self.selected_caption.setObjectName("muted")
        self.selected_name = QLabel()
        self.selected_name.setObjectName("selectedName")
        layout.addWidget(self.selected_caption)
        layout.addWidget(self.selected_name)
        layout.addSpacing(4)

        self.limit_caption = QLabel()
        self.limit_caption.setObjectName("muted")
        layout.addWidget(self.limit_caption)

        limit_row = QHBoxLayout()
        limit_row.setSpacing(12)
        self.limit_edit = QLineEdit(f"{self.settings.limit:g}")
        self.limit_edit.setFixedWidth(96)
        self.limit_edit.setMinimumHeight(38)
        self.limit_edit.setValidator(QRegularExpressionValidator(QRegularExpression(r"^\d{0,5}([.,]\d{0,2})?$")))
        limit_row.addWidget(self.limit_edit)

        # Segmented unit selector: [ Mbit/s | MB/s ]
        self.unit_mbit = QPushButton("Mbit/s")
        self.unit_mbyte = QPushButton("MB/s")
        self._unit_group = QButtonGroup(self)
        self._unit_group.setExclusive(True)
        for button, position, unit in ((self.unit_mbit, "left", UNIT_MBIT), (self.unit_mbyte, "right", UNIT_MBYTE)):
            button.setObjectName("seg")
            button.setProperty("pos", position)
            button.setCheckable(True)
            button.setMinimumHeight(38)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.clicked.connect(lambda _checked=False, u=unit: self._set_unit(u))
            self._unit_group.addButton(button)
            limit_row.addWidget(button)
        (self.unit_mbyte if self._unit == UNIT_MBYTE else self.unit_mbit).setChecked(True)
        limit_row.addStretch(1)
        layout.addLayout(limit_row)

        measure_row = QHBoxLayout()
        self.measure_switch = Switch()
        self.measure_switch.setChecked(self.settings.measure_only)
        self.measure_label = QLabel()
        measure_row.addWidget(self.measure_switch)
        measure_row.addWidget(self.measure_label)
        measure_row.addStretch(1)
        layout.addSpacing(2)
        layout.addLayout(measure_row)

        self.start_button = QPushButton()
        self.start_button.setObjectName("primary")
        self.start_button.setMinimumHeight(46)
        self.start_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.start_button.clicked.connect(self._start_rule)
        layout.addSpacing(6)
        layout.addWidget(self.start_button)
        return card

    def _build_rules_card(self) -> Card:
        """The list of active limits: one :class:`RuleCard` per program, scrollable."""
        card = Card()
        layout = QVBoxLayout(card)
        layout.setContentsMargins(20, 18, 14, 18)
        layout.setSpacing(12)

        self.rules_title = QLabel()
        self.rules_title.setObjectName("h2")
        layout.addWidget(self.rules_title)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setMinimumHeight(170)
        content = QWidget()
        self._rules_layout = QVBoxLayout(content)
        self._rules_layout.setContentsMargins(0, 0, 6, 0)
        self._rules_layout.setSpacing(12)

        self.empty_label = QLabel()
        self.empty_label.setObjectName("muted")
        self.empty_label.setWordWrap(True)
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)
        self.empty_label.setContentsMargins(10, 28, 10, 0)
        self._rules_layout.addWidget(self.empty_label)
        self._rules_layout.addStretch(1)       # keeps the cards at the top; cards are inserted before it

        scroll.setWidget(content)
        layout.addWidget(scroll, 1)
        return card

    def _build_tray(self) -> None:
        self.tray_available = QSystemTrayIcon.isSystemTrayAvailable()
        self.tray = QSystemTrayIcon(app_icon(), self)
        menu = QMenu()
        self.tray_open_action = QAction(self)
        self.tray_open_action.triggered.connect(self.show_window)
        self.tray_stop_action = QAction(self)
        self.tray_stop_action.triggered.connect(self._stop_all)
        self.tray_stop_action.setEnabled(False)
        self.tray_quit_action = QAction(self)
        self.tray_quit_action.triggered.connect(self.quit_app)
        menu.addAction(self.tray_open_action)
        menu.addAction(self.tray_stop_action)
        menu.addSeparator()
        menu.addAction(self.tray_quit_action)
        self._tray_menu = menu                      # keep a reference, otherwise it is garbage-collected
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self._on_tray_activated)
        if self.tray_available:
            self.tray.show()

    # ====================================================================
    # Window size safety net
    # ====================================================================
    def _update_min_size(self) -> None:
        """Never let the window become smaller than its content needs.

        This is what prevents clipped widgets: the minimum size is calculated from the
        real content (after the stylesheet has been applied) instead of a fixed guess.
        It is limited to the screen size so the window always stays reachable.
        """
        self.ensurePolished()
        central = self.centralWidget()
        central.ensurePolished()
        central.layout().activate()
        needed = central.minimumSizeHint()

        screen = self.screen()
        max_w = screen.availableGeometry().width() - 40 if screen else 10_000
        max_h = screen.availableGeometry().height() - 60 if screen else 10_000
        min_w = min(max(needed.width(), 960), max_w)
        min_h = min(max(needed.height(), 560), max_h)
        self.setMinimumSize(min_w, min_h)
        if self.width() < min_w or self.height() < min_h:
            self.resize(max(self.width(), min_w), max(self.height(), min_h))

    # ====================================================================
    # Texts and theme
    # ====================================================================
    def retranslate(self) -> None:
        """Set every visible text in the current language."""
        self.setWindowTitle("BandwidthGuard")
        self.tagline.setText(t("tagline"))
        self.about_button.setToolTip(t("btn.about"))
        self.settings_button.setToolTip(t("btn.settings"))

        self.proc_title.setText(t("proc.title"))
        self.refresh_button.setText(t("proc.refresh"))
        self.search.setPlaceholderText(t("proc.search"))
        self.only_net_label.setText(t("proc.only_net"))
        self.table.setHorizontalHeaderLabels([t("proc.col_name"), t("proc.col_inst"), t("proc.col_conn")])

        self.ctl_title.setText(t("ctl.title"))
        self.selected_caption.setText(t("ctl.selected"))
        self.limit_caption.setText(t("ctl.limit"))
        self.measure_label.setText(t("ctl.measure_only"))
        self._update_selected_label()
        self._update_start_button()

        self.rules_title.setText(t("rules.title"))
        self.empty_label.setText(t("rules.empty"))
        for card in self._cards.values():
            card.retranslate()

        self.tray_open_action.setText(t("tray.open"))
        self.tray_stop_action.setText(t("tray.stop"))
        self.tray_quit_action.setText(t("tray.quit"))
        if not self._cards:
            self.tray.setToolTip(t("tray.idle"))

        if self._settings_dialog is not None:
            self._settings_dialog.retranslate()
        if self._about_dialog is not None:
            self._about_dialog.retranslate()
        if self._shown_once:
            QTimer.singleShot(0, self._update_min_size)   # texts changed -> sizes may have changed

    def _apply_theme_to_widgets(self) -> None:
        """Update the parts that are not covered by the global stylesheet."""
        palette = theme.current()
        for switch in (self.only_net_switch, self.measure_switch):
            switch.update()
        for card in self._cards.values():
            card.apply_palette()
        set_dark_titlebar(self, palette.is_dark)

    def showEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        super().showEvent(event)
        set_dark_titlebar(self, theme.current().is_dark)
        if not self._shown_once:
            self._shown_once = True
            QTimer.singleShot(0, self._update_min_size)   # re-check once everything is really laid out

    # ====================================================================
    # Callbacks used by the dialogs
    # ====================================================================
    def set_language(self, code: str) -> None:
        self.settings.language = code
        i18n.set_language(code)
        self.retranslate()

    def set_theme(self, name: str) -> None:
        self.settings.theme = name
        theme.apply_theme(QApplication.instance(), name)
        self._apply_theme_to_widgets()
        self.refresh_processes()                      # active rows use the accent colour
        for dialog in (self._settings_dialog, self._about_dialog):
            if dialog is not None:
                dialog.refresh_titlebar()
                for switch in dialog.findChildren(Switch):
                    switch.update()

    def set_autostart(self, enabled: bool) -> bool:
        return autostart.enable() if enabled else autostart.disable()

    def show_settings(self) -> None:
        self._settings_dialog = SettingsDialog(self)
        self._settings_dialog.exec()
        self._settings_dialog = None

    def show_about(self) -> None:
        self._about_dialog = AboutDialog(self)
        self._about_dialog.exec()
        self._about_dialog = None

    # ====================================================================
    # Program list
    # ====================================================================
    def refresh_processes(self) -> None:
        """Rebuild the table while keeping the selection and scroll position."""
        needle = self.search.text().strip().lower()
        only_network = self.only_net_switch.isChecked()
        selected_key = (self._selected or "").lower()

        groups = list_process_groups()
        self._exe_by_key = {g.name.lower(): g.exe for g in groups}

        rows = []
        for group in groups:
            key = group.name.lower()
            if needle and needle not in key:
                continue
            # Programs with an active limit and the selected program always stay visible.
            if only_network and group.connections == 0 and key != selected_key and key not in self._cards:
                continue
            rows.append(group)
        rows.sort(key=lambda g: (-g.connections, g.name.lower()))

        accent = QColor(theme.current().accent)
        scroll = self.table.verticalScrollBar().value()
        self.table.setUpdatesEnabled(False)
        self.table.blockSignals(True)
        self.table.setRowCount(len(rows))
        selected_row = -1
        for row, group in enumerate(rows):
            name_item = QTableWidgetItem(group.name)
            name_item.setData(Qt.ItemDataRole.UserRole, group.name)
            name_item.setIcon(self._icon_for(group.exe))
            if group.name.lower() in self._cards:
                name_item.setForeground(accent)       # highlight programs that are being limited
            inst_item = QTableWidgetItem(str(group.instances))
            conn_item = QTableWidgetItem(str(group.connections))
            for item in (inst_item, conn_item):
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(row, 0, name_item)
            self.table.setItem(row, 1, inst_item)
            self.table.setItem(row, 2, conn_item)
            if group.name.lower() == selected_key:
                selected_row = row
        if selected_row >= 0:
            self.table.selectRow(selected_row)
        self.table.blockSignals(False)
        self.table.setUpdatesEnabled(True)
        self.table.verticalScrollBar().setValue(scroll)
        self._update_start_button()

    def _icon_for(self, exe_path: Optional[str]) -> QIcon:
        """Program icon from the .exe file (cached; falls back to a generic file icon)."""
        key = exe_path or ""
        if key not in self._icon_cache:
            if exe_path:
                icon = self._icon_provider.icon(QFileInfo(exe_path))
            else:
                icon = self._icon_provider.icon(QFileIconProvider.IconType.File)
            self._icon_cache[key] = icon
        return self._icon_cache[key]

    def _on_selection_changed(self) -> None:
        rows = self.table.selectionModel().selectedRows()
        if rows:
            item = self.table.item(rows[0].row(), 0)
            if item is not None:
                self._selected = item.data(Qt.ItemDataRole.UserRole)
                card = self._cards.get(self._selected.lower())
                if card is not None:                  # show the settings of the existing limit
                    self._load_controls(card.value, card.unit, card.measure_only)
        self._update_selected_label()
        self._update_start_button()

    def _update_selected_label(self) -> None:
        self.selected_name.setText(self._selected or t("ctl.none"))

    # ====================================================================
    # Limit controls
    # ====================================================================
    def _set_unit(self, unit: str) -> None:
        """Switch between Mbit/s and MB/s and convert the number in the field."""
        if unit == self._unit:
            return
        value = parse_number(self.limit_edit.text())
        if value is not None:
            converted = value * 8 if unit == UNIT_MBIT else value / 8
            self.limit_edit.setText(f"{round(converted, 2):g}")
        self._unit = unit

    def _load_controls(self, value: float, unit: str, measure_only: bool) -> None:
        """Fill the input controls with the settings of an existing limit (no conversion)."""
        self.limit_edit.setText(f"{value:g}")
        self._unit = unit
        (self.unit_mbyte if unit == UNIT_MBYTE else self.unit_mbit).setChecked(True)
        self.measure_switch.setChecked(measure_only)

    def _update_start_button(self) -> None:
        """"Start" for a new program, "Update limit" if the selected program is already limited."""
        already = bool(self._selected) and self._selected.lower() in self._cards
        self.start_button.setText(t("ctl.update") if already else t("ctl.start"))
        self.start_button.setEnabled(bool(self._selected))

    # ====================================================================
    # Start / stop of individual limits
    # ====================================================================
    def _start_rule(self) -> None:
        """Start (or update) the limit for the selected program."""
        if not self._selected:
            QMessageBox.information(self, t("err.title"), t("err.no_sel"))
            return
        value = parse_number(self.limit_edit.text())
        if value is None or value <= 0:
            QMessageBox.warning(self, t("err.title"), t("err.bad_limit"))
            return

        name = self._selected
        measure_only = self.measure_switch.isChecked()
        limit_mbit = None if measure_only else to_mbit(value, self._unit)
        try:
            self.engine.add_rule(name, limit_mbit)
        except Exception as exc:  # no admin rights, driver blocked, pydivert missing ...
            QMessageBox.critical(self, t("err.title"), t("err.start", error=exc))
            return

        key = name.lower()
        card = self._cards.get(key)
        if card is None:
            card = RuleCard(name, self._icon_for(self._exe_by_key.get(name.lower())))
            card.stop_requested.connect(self._stop_rule)
            self._cards[key] = card
            self._rules_layout.insertWidget(self._rules_layout.count() - 1, card)   # before the stretch
        if len(self._cards) == 1:
            self._last_time = time.perf_counter()
        card.configure(limit_mbit, format_limit(value, self._unit), value, self._unit, measure_only)
        card.apply_palette()
        self._after_rules_changed()

    def _stop_rule(self, key: str) -> None:
        """Stop the limit of one program (emitted by the card's Stop button)."""
        card = self._cards.get(key)
        if card is None:
            return
        self.engine.remove_rule(card.name)
        self._remove_card(key)
        self._after_rules_changed()

    def _stop_all(self) -> None:
        """Stop every active limit (tray menu)."""
        self.engine.stop()
        for key in list(self._cards):
            self._remove_card(key)
        self._after_rules_changed()

    def _remove_card(self, key: str) -> None:
        card = self._cards.pop(key, None)
        if card is not None:
            self._rules_layout.removeWidget(card)
            card.deleteLater()

    def _after_rules_changed(self) -> None:
        """Update everything that depends on whether/which limits are active."""
        has_rules = bool(self._cards)
        self.empty_label.setVisible(not has_rules)
        self.tray_stop_action.setEnabled(has_rules)
        if not has_rules:
            self.tray.setToolTip(t("tray.idle"))
        self._update_start_button()
        self.refresh_processes()

    def _handle_engine_crash(self) -> None:
        """The packet filter died by itself – reset the UI and tell the user."""
        error = self.engine.error or "unknown error"
        self.engine.stop()
        for key in list(self._cards):
            self._remove_card(key)
        self._after_rules_changed()
        QMessageBox.critical(self, t("err.title"), t("err.stopped", error=error))

    # ====================================================================
    # Live traffic display
    # ====================================================================
    def _tick(self) -> None:
        """Every 0.5 s: read the counters and update all cards."""
        if not self._cards:
            return
        if not self.engine.running:
            self._handle_engine_crash()
            return

        now = time.perf_counter()
        elapsed = max(now - self._last_time, 1e-3)
        self._last_time = now
        snapshots = self.engine.snapshot_all()

        total_down = total_up = 0.0
        for key, card in self._cards.items():
            downloaded, uploaded = snapshots.get(key, (card.last_in, card.last_out))
            down_rate = (downloaded - card.last_in) / elapsed     # bytes per second
            up_rate = (uploaded - card.last_out) / elapsed
            card.last_in, card.last_out = downloaded, uploaded
            card.update_stats(down_rate, up_rate, downloaded, uploaded)
            total_down += down_rate
            total_up += up_rate

        self.tray.setToolTip(t(
            "tray.active", count=len(self._cards),
            down=f"{bytes_per_s_to_mbit(total_down):.1f} Mbit/s",
            up=f"{bytes_per_s_to_mbit(total_up):.1f} Mbit/s",
        ))

    # ====================================================================
    # Tray icon, closing and quitting
    # ====================================================================
    def _on_tray_activated(self, reason) -> None:
        if reason in (QSystemTrayIcon.ActivationReason.Trigger, QSystemTrayIcon.ActivationReason.DoubleClick):
            self.show_window()

    def show_window(self) -> None:
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def closeEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        """The X button hides to the tray (if enabled) instead of quitting."""
        if not self._quitting and self.settings.minimize_to_tray_on_close and self.tray.isVisible():
            event.ignore()
            self.hide()
            if not self._tray_notified:
                self._tray_notified = True
                self.tray.showMessage(t("tray.hidden_title"), t("tray.hidden_msg"),
                                      QSystemTrayIcon.MessageIcon.Information, 4000)
            return
        self._shutdown()
        event.accept()

    def quit_app(self) -> None:
        """Real exit (tray menu → Quit)."""
        self._quitting = True
        self._shutdown()

    def shutdown_engine(self) -> None:
        """Called on application exit (also on Windows logoff) so no packets stay captured."""
        self.engine.stop()

    def _shutdown(self) -> None:
        self.engine.stop()
        self._save_settings()
        self.tray.hide()
        QApplication.quit()

    def _save_settings(self) -> None:
        s = self.settings
        value = parse_number(self.limit_edit.text())
        if value is not None and value > 0:
            s.limit = value
        s.unit = self._unit
        s.measure_only = self.measure_switch.isChecked()
        s.last_process = self._selected or ""
        s.window_width, s.window_height = self.width(), self.height()
        s.save()
