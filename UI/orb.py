from __future__ import annotations

import math
from enum import Enum

from PySide6.QtCore import QEasingCurve, QPropertyAnimation, QRect, Qt, QTimer
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QApplication, QWidget


class _StrEnum(str, Enum):
    """String enum compatible with Python versions before 3.11."""


class OrbState(_StrEnum):
    SLEEPING = "Sleeping"
    LISTENING = "Listening"
    THINKING = "Thinking"
    SPEAKING = "Speaking"
    EXECUTING = "Executing"
    ERROR = "Error"


STATE_COLORS: dict[OrbState, str] = {
    OrbState.SLEEPING: "#1f2937",
    OrbState.LISTENING: "#22c55e",
    OrbState.THINKING: "#3b82f6",
    OrbState.SPEAKING: "#a855f7",
    OrbState.EXECUTING: "#f59e0b",
    OrbState.ERROR: "#ef4444",
}


class FloatingOrb(QWidget):
    """Transparent bottom-center assistant orb with animated waveform."""

    def __init__(self, fade_ms: int = 2500) -> None:
        super().__init__()
        self.state = OrbState.SLEEPING
        self._phase = 0.0
        self._fade_ms = fade_ms
        self._state_color = QColor(STATE_COLORS[self.state])
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Tool | Qt.WindowStaysOnTopHint | Qt.WindowDoesNotAcceptFocus)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.resize(220, 160)
        self._timer = QTimer(self)
        self._timer.setInterval(33)
        self._timer.timeout.connect(self._tick)
        self._timer.start()
        self._fade = QPropertyAnimation(self, b"windowOpacity", self)
        self._fade.setDuration(self._fade_ms)
        self._fade.setEasingCurve(QEasingCurve.InOutQuad)
        self.hide()

    def set_state(self, state: OrbState) -> None:
        """Show the orb and switch waveform color/state."""
        self.state = state
        self._state_color = QColor(STATE_COLORS[state])
        self._move_bottom_center()
        self.setWindowOpacity(0.96)
        self.show()
        self.raise_()
        self.update()
        if state in {OrbState.SLEEPING}:
            self.fade_away()

    def fade_away(self) -> None:
        """Fade and hide after temporary assistant activity."""
        self._fade.stop()
        self._fade.setStartValue(self.windowOpacity())
        self._fade.setEndValue(0.0)
        self._fade.finished.connect(self.hide)
        self._fade.start()

    def _move_bottom_center(self) -> None:
        screen = QApplication.primaryScreen()
        if not screen:
            return
        geometry: QRect = screen.availableGeometry()
        x = geometry.x() + (geometry.width() - self.width()) // 2
        y = geometry.y() + geometry.height() - self.height() - 24
        self.move(x, y)

    def _tick(self) -> None:
        self._phase = (self._phase + 0.18) % (math.pi * 2)
        if self.isVisible():
            self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        center_x = self.width() / 2
        center_y = self.height() / 2
        radius = 46

        glow = QColor(self._state_color)
        glow.setAlpha(70)
        painter.setBrush(glow)
        painter.setPen(Qt.NoPen)
        pulse = 8 * (1 + math.sin(self._phase))
        painter.drawEllipse(int(center_x - radius - pulse), int(center_y - radius - pulse), int((radius + pulse) * 2), int((radius + pulse) * 2))

        core = QColor(self._state_color)
        core.setAlpha(235)
        painter.setBrush(core)
        painter.drawEllipse(int(center_x - radius), int(center_y - radius), radius * 2, radius * 2)

        pen = QPen(QColor("white"), 3)
        pen.setCapStyle(Qt.RoundCap)
        painter.setPen(pen)
        bar_count = 9
        spacing = 10
        for index in range(bar_count):
            offset = index - bar_count // 2
            height = 16 + 22 * abs(math.sin(self._phase + index * 0.55))
            x = center_x + offset * spacing
            painter.drawLine(int(x), int(center_y - height / 2), int(x), int(center_y + height / 2))
