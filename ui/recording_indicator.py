import time
import math
import random
import logging

from PySide6.QtCore import Qt, QTimer, QRectF
from PySide6.QtGui import QPainter, QColor
from PySide6.QtWidgets import QWidget

from core.state import AppState

logger = logging.getLogger(__name__)

BAR_COUNT = 9

_STATE_STYLE = {
    AppState.RECORDING: (QColor(220, 50, 47), "REC"),   # red
    AppState.PROCESSING: (QColor(255, 165, 0), "Transcribing…"),  # orange
}


class RecordingIndicator(QWidget):
    """Small always-on-top indicator that appears while recording/transcribing.

    Shows animated waveform bars + elapsed time so the user can see the app
    is actually capturing audio. It follows the floating icon if dragged and
    never takes keyboard focus (so pasting still lands in the target window).
    """

    def __init__(self, controller, icon):
        super().__init__(None, Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint
                         | Qt.Tool | Qt.WindowDoesNotAcceptFocus)
        self.controller = controller
        self.icon = icon
        self.state = AppState.IDLE
        self._rec_start = None
        self._t = 0.0
        self._phases = [random.uniform(0, 2 * math.pi) for _ in range(BAR_COUNT)]

        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedSize(120, 58)
        self.hide()

        # ~30 fps animation loop; only paints when visible
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._on_tick)
        self._timer.start(33)

        self.controller.state_changed.connect(self._on_state_changed)

    # ------------------------------------------------------------ state --
    def _on_state_changed(self, state: AppState):
        self.state = state
        if state == AppState.RECORDING:
            self._rec_start = time.monotonic()
            self._show_near_icon()
        elif state == AppState.PROCESSING:
            self._show_near_icon()
        else:
            self.hide()
        self.update()

    def _show_near_icon(self):
        self.align_to_icon()
        self.show()
        self.raise_()

    def align_to_icon(self):
        """Place the indicator just below the floating icon."""
        if self.icon is None or not self.icon.isVisible():
            return
        g = self.icon.frameGeometry()
        self.move(g.left() + (g.width() - self.width()) // 2, g.bottom() + 8)

    def _on_tick(self):
        if self.state in (AppState.RECORDING, AppState.PROCESSING):
            self._t += 1
            # follow the icon if the user drags it while recording
            self.align_to_icon()
            self.update()

    # ------------------------------------------------------------ paint --
    def paintEvent(self, event):
        style = _STATE_STYLE.get(self.state)
        if style is None:
            return
        color, label = style

        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()

        # dark pill background
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(18, 18, 26, 210))
        p.drawRoundedRect(QRectF(1, 1, w - 2, h - 2), 14, 14)

        # animated waveform bars (layered sines => pseudo-random wave)
        bar_w = 5.0
        gap = (w - 24 - BAR_COUNT * bar_w) / (BAR_COUNT - 1)
        t = self._t * 0.35
        bottom = h - 12
        for i in range(BAR_COUNT):
            v = (math.sin(t + self._phases[i]) +
                 math.sin(t * 1.7 + self._phases[i] * 2)) / 2.0  # [-1, 1]
            frac = 0.22 + 0.78 * abs(v)
            bar_h = max(6.0, (bottom - 16) * frac)
            x = 12 + i * (bar_w + gap)
            p.setBrush(color)
            p.drawRoundedRect(QRectF(x, bottom - bar_h, bar_w, bar_h), 2, 2)

        # label / elapsed time
        if self.state == AppState.RECORDING and self._rec_start is not None:
            secs = int(time.monotonic() - self._rec_start)
            text = f"{label}  {secs // 60:02d}:{secs % 60:02d}"
        else:
            text = label
        font = p.font()
        font.setPointSize(8)
        font.setBold(True)
        p.setFont(font)
        p.setPen(QColor(255, 255, 255))
        p.drawText(QRectF(6, 2, w - 12, 13), Qt.AlignCenter, text)

        p.end()

    # ------------------------------------------------------------ mouse --
    def mousePressEvent(self, event):
        # Big visible target while recording: a click stops recording.
        if event.button() == Qt.LeftButton and self.state == AppState.RECORDING:
            self.controller.toggle_recording()
