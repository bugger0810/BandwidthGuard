"""One card per active limit: program, limit, live speed, totals and its own graph."""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QSizePolicy, QVBoxLayout

from . import theme
from .formatting import bytes_per_s_to_mbit, bytes_per_s_to_mbyte, format_bytes
from .i18n import t
from .widgets import TrafficGraph


class RuleCard(QFrame):
    """Shows and controls the limit of a single program.

    The card is created when the user starts a limit and removed when it is stopped.
    It does not talk to the engine itself: it only emits :attr:`stop_requested` and
    the main window does the rest.
    """

    stop_requested = Signal(str)   # emits the program key (lower-case name)

    def __init__(self, name: str, icon: QIcon) -> None:
        super().__init__()
        self.setObjectName("ruleCard")
        # Never let the layout squash the card: it always keeps its natural height.
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)

        self.name = name
        self.key = name.lower()
        # Values needed by the main window to refill the controls when the program is selected.
        self.value = 0.0
        self.unit = ""
        self.measure_only = False
        # Counters at the previous tick, used to calculate the current speed.
        self.last_in = 0
        self.last_out = 0
        self._limit_text = ""
        self._limit_mbit: Optional[float] = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(10)

        # --- header: icon, name, limit chip, stop button --------------------
        header = QHBoxLayout()
        header.setSpacing(10)
        icon_label = QLabel()
        icon_label.setPixmap(icon.pixmap(QSize(22, 22)))
        title = QLabel(name)
        title.setObjectName("selectedName")
        self.chip = QLabel()
        self.chip.setObjectName("chip")
        self.stop_button = QPushButton()
        self.stop_button.setObjectName("dangerSmall")
        self.stop_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.stop_button.clicked.connect(lambda: self.stop_requested.emit(self.key))
        header.addWidget(icon_label)
        header.addWidget(title)
        header.addStretch(1)
        header.addWidget(self.chip)
        header.addWidget(self.stop_button)
        layout.addLayout(header)

        # --- live numbers ---------------------------------------------------------
        numbers = QHBoxLayout()
        numbers.setSpacing(18)
        self.down_label = QLabel()
        self.down_label.setObjectName("rate")
        self.up_label = QLabel()
        self.up_label.setObjectName("rate")
        numbers.addWidget(self.down_label)
        numbers.addWidget(self.up_label)
        numbers.addStretch(1)
        layout.addLayout(numbers)

        self.total_label = QLabel()
        self.total_label.setObjectName("muted")
        layout.addWidget(self.total_label)

        self.graph = TrafficGraph()
        self.graph.setMinimumHeight(100)
        layout.addWidget(self.graph)

        self.retranslate()
        self.apply_palette()
        self.update_stats(0.0, 0.0, 0, 0)

    # ------------------------------------------------------------------ setup
    def configure(self, limit_mbit: Optional[float], limit_text: str, value: float, unit: str,
                  measure_only: bool) -> None:
        """(Re)start the card with new limit settings – used on creation and on "Update limit"."""
        self.value, self.unit, self.measure_only = value, unit, measure_only
        self._limit_text = limit_text
        self._limit_mbit = limit_mbit
        self.last_in = self.last_out = 0
        self.graph.clear()
        self.retranslate()
        self.update_stats(0.0, 0.0, 0, 0)

    def retranslate(self) -> None:
        """Texts that depend on the language."""
        self.stop_button.setText(t("ctl.stop"))
        self.chip.setText(t("rules.measuring") if self.measure_only else self._limit_text)
        # The dashed limit line in the graph carries a translated label.
        label = t("traf.limit", value=self._limit_text) if self._limit_mbit else ""
        self.graph.set_limit(self._limit_mbit, label)

    def apply_palette(self) -> None:
        """Colour the download / upload numbers with the current theme's colours."""
        palette = theme.current()
        self.down_label.setStyleSheet(f"color: {palette.down};")
        self.up_label.setStyleSheet(f"color: {palette.up};")
        self.graph.update()

    # ------------------------------------------------------------------ live data
    def update_stats(self, down_bps: float, up_bps: float, total_in: int, total_out: int) -> None:
        """Show the current speed (bytes/second) and the totals (bytes) and extend the graph."""
        down_mbit = bytes_per_s_to_mbit(down_bps)
        up_mbit = bytes_per_s_to_mbit(up_bps)
        self.down_label.setText(f"↓ {down_mbit:.2f} Mbit/s  ·  {bytes_per_s_to_mbyte(down_bps):.2f} MB/s")
        self.up_label.setText(f"↑ {up_mbit:.2f} Mbit/s")
        self.total_label.setText(
            t("traf.total", value=f"↓ {format_bytes(total_in)}   ↑ {format_bytes(total_out)}"))
        self.graph.push(down_mbit, up_mbit)
