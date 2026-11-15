"""The main window: program list, limit controls, live traffic and tray icon."""

from __future__ import annotations

import time
from typing import Dict, Optional

from PySide6.QtCore import QFileInfo, QRegularExpression, QSize, Qt, QTimer
from PySide6.QtGui import QAction, QIcon, QPixmap, QRegularExpressionValidator
from PySide6.QtWidgets import (
    QAbstractItemView, QApplication, QButtonGroup, QFileIconProvider, QHBoxLayout, QHeaderView,
    QLabel, QLineEdit, QMainWindow, QMenu, QMessageBox, QPushButton, QSystemTrayIcon,
    QTableWidget, QTableWidgetItem, QToolButton, QVBoxLayout, QWidget,
)

from . import autostart, i18n, theme
from .dialogs import AboutDialog, SettingsDialog
from .engine import BandwidthEngine
from .formatting import (
    UNIT_MBIT, UNIT_MBYTE, bytes_per_s_to_mbit, bytes_per_s_to_mbyte, format_bytes, format_limit,
    parse_number, to_mbit,
)
from .i18n import t
from .paths import ASSETS_DIR
from .processes import list_process_groups
from .settings import Settings
from .widgets import Card, Switch, Tile, TrafficGraph
from .winutil import set_dark_titlebar

TICK_MS = 500             # how often the traffic display updates
PROCESS_REFRESH_MS = 4000  # how often the program list refreshes


def app_icon() -> QIcon:
    return QIcon(str(ASSETS_DIR / "icon.png"))


def repolish(widget: QWidget) -> None:
    """Re-apply the stylesheet after a dynamic property (e.g. ``running``) changed."""
    widget.style().unpolish(widget)
    widget.style().polish(widget)
    widget.update()


class StatTile(Tile):
    """One statistics box: coloured title, big Mbit/s value, MB/s and running total."""

    def __init__(self) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(2)

        head = QHBoxLayout()
        head.setSpacing(6)
        self.dot = QLabel("●")
        self.title = QLabel()
        self.title.setObjectName("muted")
        head.addWidget(self.dot)
        head.addWidget(self.title)
        head.addStretch(1)
        layout.addLayout(head)

        value_row = QHBoxLayout()
        value_row.setSpacing(6)
        self.value = QLabel("0.00")
        self.value.setObjectName("statValue")
        unit = QLabel("Mbit/s")
        unit.setObjectName("statUnit")
        value_row.addWidget(self.value, 0, Qt.AlignmentFlag.AlignBottom)
        value_row.addWidget(unit, 0, Qt.AlignmentFlag.AlignBottom)
        value_row.addStretch(1)
        layout.addLayout(value_row)

        self.sub = QLabel("0.00 MB/s")
        self.sub.setObjectName("statSub")
        self.total = QLabel()
        self.total.setObjectName("statSub")
        layout.addWidget(self.sub)
        layout.addWidget(self.total)

    def set_color(self, color: str) -> None:
        self.dot.setStyleSheet(f"color: {color}; font-size: 11px;")


class MainWindow(QMainWindow):
    """Everything the user sees. Heavy lifting is delegated to :class:`BandwidthEngine`."""

    def __init__(self, settings: Settings) -> None:
        super().__init__()
        self.settings = settings
        self.engine = BandwidthEngine()

        # --- state -----------------------------------------------------------
        self._selected: Optional[str] = settings.last_process or None
        self._ui_running = False          # True between Start and Stop
        self._state = "ready"             # "ready" | "limited" | "measuring" | "stopped"
        self._run_name = ""
        self._run_limit_text = ""
        self._quitting = False
        self._tray_notified = False
        self._last_snapshot = (0, 0)
        self._last_time = 0.0
        self._unit = settings.unit if settings.unit in (UNIT_MBIT, UNIT_MBYTE) else UNIT_MBIT
        self._icon_provider = QFileIconProvider()
        self._icon_cache: Dict[str, QIcon] = {}
        self._settings_dialog: Optional[SettingsDialog] = None
        self._about_dialog: Optional[AboutDialog] = None

        self.setWindowIcon(app_icon())
        self.setMinimumSize(960, 640)
        self.resize(settings.window_width, settings.window_height)

        self._build_ui()
        self._build_tray()
        self.retranslate()
        self._apply_theme_to_widgets()
        self.refresh_processes()

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
        right.addWidget(self._build_traffic_card(), 1)
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
        self.limit_edit.setValidator(QRegularExpressionValidator(QRegularExpression(r"^\d{0,5}([.,]\d{0,2})?$")))
        limit_row.addWidget(self.limit_edit)

        # Segmented unit selector: [ Mbit/s | MB/s ]
        self.unit_mbit = QPushButton("Mbit/s")
        self.unit_mbyte = QPushButton("MB/s")
        group = QButtonGroup(self)
        group.setExclusive(True)
        for button, position, unit in ((self.unit_mbit, "left", UNIT_MBIT), (self.unit_mbyte, "right", UNIT_MBYTE)):
            button.setObjectName("seg")
            button.setProperty("pos", position)
            button.setCheckable(True)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.clicked.connect(lambda _checked=False, u=unit: self._set_unit(u))
            group.addButton(button)
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
        self.start_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.start_button.clicked.connect(self.toggle)
        layout.addSpacing(6)
        layout.addWidget(self.start_button)

        self.status_pill = QLabel()
        self.status_pill.setObjectName("pill")
        self.status_pill.setProperty("state", "idle")
        layout.addWidget(self.status_pill)
        return card

    def _build_traffic_card(self) -> Card:
        card = Card()
        layout = QVBoxLayout(card)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(12)

        self.traffic_title = QLabel()
        self.traffic_title.setObjectName("h2")
        layout.addWidget(self.traffic_title)

        tiles = QHBoxLayout()
        tiles.setSpacing(12)
        self.down_tile = StatTile()
        self.up_tile = StatTile()
        tiles.addWidget(self.down_tile)
        tiles.addWidget(self.up_tile)
        layout.addLayout(tiles)

        self.graph = TrafficGraph()
        layout.addWidget(self.graph, 1)
        return card

    def _build_tray(self) -> None:
        self.tray_available = QSystemTrayIcon.isSystemTrayAvailable()
        self.tray = QSystemTrayIcon(app_icon(), self)
        menu = QMenu()
        self.tray_open_action = QAction(self)
        self.tray_open_action.triggered.connect(self.show_window)
        self.tray_stop_action = QAction(self)
        self.tray_stop_action.triggered.connect(self._stop)
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
        self._update_status()

        self.traffic_title.setText(t("traf.title"))
        self.down_tile.title.setText(t("traf.down"))
        self.up_tile.title.setText(t("traf.up"))
        totals = self.engine.snapshot() if self._ui_running else self._last_snapshot
        self._update_totals(*totals)

        self.tray_open_action.setText(t("tray.open"))
        self.tray_stop_action.setText(t("tray.stop"))
        self.tray_quit_action.setText(t("tray.quit"))
        self.tray.setToolTip(t("tray.idle"))

        if self._settings_dialog is not None:
            self._settings_dialog.retranslate()
        if self._about_dialog is not None:
            self._about_dialog.retranslate()

    def _apply_theme_to_widgets(self) -> None:
        """Update the parts that are not covered by the global stylesheet."""
        palette = theme.current()
        self.down_tile.set_color(palette.down)
        self.up_tile.set_color(palette.up)
        for switch in (self.only_net_switch, self.measure_switch):
            switch.update()
        self.graph.update()
        set_dark_titlebar(self, palette.is_dark)

    def showEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        super().showEvent(event)
        set_dark_titlebar(self, theme.current().is_dark)

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

        rows = []
        for group in list_process_groups():
            if needle and needle not in group.name.lower():
                continue
            if only_network and group.connections == 0 and group.name != self._selected:
                continue
            rows.append(group)
        rows.sort(key=lambda g: (-g.connections, g.name.lower()))

        scroll = self.table.verticalScrollBar().value()
        self.table.setUpdatesEnabled(False)
        self.table.blockSignals(True)
        self.table.setRowCount(len(rows))
        selected_row = -1
        for row, group in enumerate(rows):
            name_item = QTableWidgetItem(group.name)
            name_item.setData(Qt.ItemDataRole.UserRole, group.name)
            name_item.setIcon(self._icon_for(group.exe))
            inst_item = QTableWidgetItem(str(group.instances))
            conn_item = QTableWidgetItem(str(group.connections))
            for item in (inst_item, conn_item):
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(row, 0, name_item)
            self.table.setItem(row, 1, inst_item)
            self.table.setItem(row, 2, conn_item)
            if group.name == self._selected:
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

    def _update_start_button(self) -> None:
        self.start_button.setText(t("ctl.stop") if self._ui_running else t("ctl.start"))
        self.start_button.setProperty("running", self._ui_running)
        self.start_button.setEnabled(self._ui_running or bool(self._selected))
        repolish(self.start_button)

    def _update_status(self) -> None:
        if self._state == "limited":
            text = t("stat.limited", name=self._run_name, limit=self._run_limit_text)
        elif self._state == "measuring":
            text = t("stat.measuring", name=self._run_name)
        elif self._state == "stopped":
            text = t("stat.stopped")
        else:
            text = t("stat.ready")
        self.status_pill.setText(text)
        self.status_pill.setProperty("state", "running" if self._ui_running else "idle")
        repolish(self.status_pill)

    # ====================================================================
    # Start / stop
    # ====================================================================
    def toggle(self) -> None:
        if self._ui_running:
            self._stop()
        else:
            self._start()

    def _start(self) -> None:
        if not self._selected:
            QMessageBox.information(self, t("err.title"), t("err.no_sel"))
            return
        value = parse_number(self.limit_edit.text())
        if value is None or value <= 0:
            QMessageBox.warning(self, t("err.title"), t("err.bad_limit"))
            return

        mbit = to_mbit(value, self._unit)
        throttle = not self.measure_switch.isChecked()
        try:
            self.engine.start(self._selected, mbit, throttle)
        except Exception as exc:  # no admin rights, driver blocked, pydivert missing ...
            QMessageBox.critical(self, t("err.title"), t("err.start", error=exc))
            return

        self._run_name = self._selected
        self._run_limit_text = format_limit(value, self._unit)
        self._state = "limited" if throttle else "measuring"
        self._last_snapshot = (0, 0)
        self._last_time = time.perf_counter()
        self.graph.clear()
        self.graph.set_limit(mbit if throttle else None, t("traf.limit", value=self._run_limit_text))
        self._set_running_ui(True)

    def _stop(self) -> None:
        self.engine.stop()
        self._state = "stopped"
        self._set_running_ui(False)
        self._show_rates(0.0, 0.0)
        self.graph.set_limit(None)
        self.tray.setToolTip(t("tray.idle"))

    def _set_running_ui(self, running: bool) -> None:
        """Enable/disable the controls that must not change while the engine runs."""
        self._ui_running = running
        for widget in (self.table, self.search, self.only_net_switch, self.limit_edit,
                       self.unit_mbit, self.unit_mbyte, self.measure_switch):
            widget.setEnabled(not running)
        self.tray_stop_action.setEnabled(running)
        self._update_start_button()
        self._update_status()

    def _handle_engine_crash(self) -> None:
        """The packet filter died by itself – reset the UI and tell the user."""
        error = self.engine.error or "unknown error"
        self.engine.stop()
        self._state = "ready"
        self._set_running_ui(False)
        self._show_rates(0.0, 0.0)
        self.graph.set_limit(None)
        QMessageBox.critical(self, t("err.title"), t("err.stopped", error=error))

    # ====================================================================
    # Live traffic display
    # ====================================================================
    def _tick(self) -> None:
        if not self._ui_running:
            return
        if not self.engine.running:
            self._handle_engine_crash()
            return

        now = time.perf_counter()
        downloaded, uploaded = self.engine.snapshot()
        elapsed = max(now - self._last_time, 1e-3)
        down_rate = (downloaded - self._last_snapshot[0]) / elapsed   # bytes per second
        up_rate = (uploaded - self._last_snapshot[1]) / elapsed
        self._last_snapshot = (downloaded, uploaded)
        self._last_time = now

        self._show_rates(down_rate, up_rate)
        self._update_totals(downloaded, uploaded)
        self.graph.push(bytes_per_s_to_mbit(down_rate), bytes_per_s_to_mbit(up_rate))
        self.tray.setToolTip(t(
            "tray.running", name=self._run_name,
            down=f"{bytes_per_s_to_mbit(down_rate):.1f} Mbit/s",
            up=f"{bytes_per_s_to_mbit(up_rate):.1f} Mbit/s",
        ))

    def _show_rates(self, down_bps: float, up_bps: float) -> None:
        for tile, rate in ((self.down_tile, down_bps), (self.up_tile, up_bps)):
            tile.value.setText(f"{bytes_per_s_to_mbit(rate):.2f}")
            tile.sub.setText(f"{bytes_per_s_to_mbyte(rate):.2f} MB/s")

    def _update_totals(self, downloaded: int, uploaded: int) -> None:
        self.down_tile.total.setText(t("traf.total", value=format_bytes(downloaded)))
        self.up_tile.total.setText(t("traf.total", value=format_bytes(uploaded)))

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
