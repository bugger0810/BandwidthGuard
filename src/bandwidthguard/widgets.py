"""Custom-painted widgets: toggle switch, card container and the live traffic graph."""

from __future__ import annotations

from collections import deque
from typing import Deque, Optional

from PySide6.QtCore import QPointF, QRectF, QSize, Qt
from PySide6.QtGui import QColor, QFont, QLinearGradient, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QAbstractButton, QFrame, QWidget

from . import theme

GRAPH_SAMPLES = 120   # 120 samples x 0.5 s = the last 60 seconds


class Card(QFrame):
    """A rounded container. The look comes from the ``#card`` rule in theme.py."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("card")


class Tile(QFrame):
    """A smaller, inset container used for the download / upload statistics."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("tile")


class Switch(QAbstractButton):
    """A modern on/off toggle (replaces the old-fashioned check box)."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(44, 24)

    def sizeHint(self) -> QSize:
        return QSize(44, 24)

    def paintEvent(self, _event) -> None:  # noqa: N802 (Qt naming)
        palette = theme.current()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        track_color = QColor(palette.accent if self.isChecked() else palette.switch_off)
        if not self.isEnabled():
            track_color.setAlpha(110)

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(track_color)
        height = self.height()
        painter.drawRoundedRect(QRectF(0.5, 0.5, self.width() - 1, height - 1), height / 2, height / 2)

        diameter, margin = 18, 3
        x = self.width() - margin - diameter if self.isChecked() else margin
        painter.setBrush(QColor("#ffffff"))
        painter.drawEllipse(QRectF(x, (height - diameter) / 2, diameter, diameter))


class TrafficGraph(QWidget):
    """Line graph of the last 60 seconds of download and upload speed (in Mbit/s)."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setMinimumHeight(150)
        self._down: Deque[float] = deque([0.0] * GRAPH_SAMPLES, maxlen=GRAPH_SAMPLES)
        self._up: Deque[float] = deque([0.0] * GRAPH_SAMPLES, maxlen=GRAPH_SAMPLES)
        self._limit: Optional[float] = None
        self._limit_text = ""

    # -- data ---------------------------------------------------------------
    def push(self, down_mbit: float, up_mbit: float) -> None:
        """Append one sample and redraw."""
        self._down.append(down_mbit)
        self._up.append(up_mbit)
        self.update()

    def clear(self) -> None:
        self._down.extend([0.0] * GRAPH_SAMPLES)
        self._up.extend([0.0] * GRAPH_SAMPLES)
        self.update()

    def set_limit(self, mbit: Optional[float], label: str = "") -> None:
        """Show a dashed red line at the throttle limit (``None`` hides it)."""
        self._limit = mbit
        self._limit_text = label
        self.update()

    # -- painting -----------------------------------------------------------
    def paintEvent(self, _event) -> None:  # noqa: N802 (Qt naming)
        palette = theme.current()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        width, height = self.width(), self.height()
        painter.setPen(QPen(QColor(palette.border), 1))
        painter.setBrush(QColor(palette.graph_bg))
        painter.drawRoundedRect(QRectF(0.5, 0.5, width - 1, height - 1), 12, 12)

        pad_left, pad_right, pad_top, pad_bottom = 12, 12, 22, 12
        plot = QRectF(pad_left, pad_top, width - pad_left - pad_right, height - pad_top - pad_bottom)
        if plot.width() < 10 or plot.height() < 10:
            return

        peak = max(max(self._down), max(self._up), self._limit or 0.0, 1.0) * 1.15

        def y_of(value: float) -> float:
            return plot.bottom() - (value / peak) * plot.height()

        # horizontal grid lines + scale label
        painter.setPen(QPen(QColor(palette.grid), 1))
        for fraction in (0.0, 0.25, 0.5, 0.75, 1.0):
            gy = plot.top() + plot.height() * fraction
            painter.drawLine(QPointF(plot.left(), gy), QPointF(plot.right(), gy))
        small = QFont(self.font())
        small.setPointSizeF(8)
        painter.setFont(small)
        painter.setPen(QColor(palette.muted))
        painter.drawText(QPointF(pad_left, 14), f"{peak:.1f} Mbit/s")

        # the two data series (upload first so download is drawn on top)
        step = plot.width() / (GRAPH_SAMPLES - 1)
        for series, color in ((self._up, palette.up), (self._down, palette.down)):
            line = QPainterPath()
            for index, value in enumerate(series):
                point = QPointF(plot.left() + index * step, y_of(value))
                if index == 0:
                    line.moveTo(point)
                else:
                    line.lineTo(point)

            # soft gradient under the line
            area = QPainterPath(line)
            area.lineTo(QPointF(plot.right(), plot.bottom()))
            area.lineTo(QPointF(plot.left(), plot.bottom()))
            area.closeSubpath()
            fill = QLinearGradient(0, plot.top(), 0, plot.bottom())
            top_color = QColor(color)
            top_color.setAlpha(70)
            bottom_color = QColor(color)
            bottom_color.setAlpha(0)
            fill.setColorAt(0.0, top_color)
            fill.setColorAt(1.0, bottom_color)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(fill)
            painter.drawPath(area)

            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(QColor(color), 2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
            painter.drawPath(line)

        # dashed throttle limit line
        if self._limit:
            ly = y_of(self._limit)
            pen = QPen(QColor(palette.danger), 1.5, Qt.PenStyle.DashLine)
            painter.setPen(pen)
            painter.drawLine(QPointF(plot.left(), ly), QPointF(plot.right(), ly))
            painter.setPen(QColor(palette.danger))
            text_width = painter.fontMetrics().horizontalAdvance(self._limit_text)
            painter.drawText(QPointF(plot.right() - text_width - 2, ly - 4), self._limit_text)
