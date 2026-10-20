import os
import math
import random
import logging

from PySide6.QtCore import Qt, QPoint, QRectF, QSize, QTimer
from PySide6.QtGui import QPixmap, QPainter, QColor, QAction, QIcon
from PySide6.QtWidgets import QWidget, QMenu, QApplication
from PySide6.QtSvg import QSvgRenderer

from core.state import AppState
from core.config import Config
from ui.recording_indicator import RecordingIndicator

logger = logging.getLogger(__name__)

# assets/ lives next to the ui/ package (one level up from this file)
ASSETS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets")

_STATE_COLORS = {
    AppState.IDLE: QColor(70, 130, 180),       # steel blue ring
    AppState.RECORDING: QColor(220, 50, 47),   # red ring while recording
    AppState.PROCESSING: QColor(255, 165, 0),  # orange ring while transcribing
}

_STATE_LABELS = {
    AppState.IDLE: "Idle",
    AppState.RECORDING: "Recording...",
    AppState.PROCESSING: "Transcribing...",
}


class FloatingIcon(QWidget):
    """Always-on-top, draggable round icon.

    - Left click   : start / stop recording
    - Right click  : menu (record / quit)
    - Drag         : move it; position is saved to config.json
    - Icon image   : config['icon']['path'], or a random one from assets/
    """

    def __init__(self, controller):
        # WindowDoesNotAcceptFocus: clicking the icon must NOT steal keyboard
        # focus from the user's text field, otherwise the simulated Ctrl+V
        # paste lands in this window instead of the target app.
        super().__init__(None, Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint
                         | Qt.Tool | Qt.WindowDoesNotAcceptFocus)
        self.controller = controller
        self.config = Config.get()
        self.state = AppState.IDLE
        self._pulse_t = 0.0

        icon_cfg = self.config.get_value("icon", {})
        self._size = int(icon_cfg.get("size", 56))
        self._icon_pixmap = self._load_icon_pixmap()

        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedSize(self._size, self._size)
        self.setWindowTitle("WhisperFlow")

        # Restore last position (saved on drag), else top-right of the screen
        pos = icon_cfg.get("position")
        if pos and len(pos) == 2:
            self.move(int(pos[0]), int(pos[1]))
        else:
            screen = QApplication.primaryScreen().availableGeometry()
            self.move(screen.right() - self._size - 60, 60)

        self._drag_offset = None
        self._moved = False

        # Recording/transcribing indicator (wave animation) — follows this icon
        self.indicator = RecordingIndicator(controller, self)

        # Pulse animation while recording (drives the ring + this widget)
        self._anim_timer = QTimer(self)
        self._anim_timer.timeout.connect(self._on_anim_tick)
        self._anim_timer.start(33)

        self.controller.state_changed.connect(self._on_state_changed)
        self._update_tooltip()

    def _on_anim_tick(self):
        if self.state == AppState.RECORDING:
            self._pulse_t += 1
            self.update()
        elif self.state == AppState.PROCESSING:
            self.update()

    # ------------------------------------------------------------- icon --
    def _load_icon_pixmap(self):
        icon_cfg = self.config.get_value("icon", {})
        custom_path = icon_cfg.get("path") or ""
        use_random = bool(icon_cfg.get("random", True))

        chosen = None
        if custom_path and os.path.exists(custom_path):
            chosen = custom_path
            logger.info(f"Using custom icon: {custom_path}")
        elif use_random:
            svgs = []
            if os.path.isdir(ASSETS_DIR):
                svgs = [os.path.join(ASSETS_DIR, f) for f in sorted(os.listdir(ASSETS_DIR))
                        if f.lower().endswith((".svg", ".png", ".ico", ".jpg"))]
            if svgs:
                chosen = random.choice(svgs)
                logger.info(f"Using random icon: {chosen}")

        if chosen:
            pm = QPixmap(self._size, self._size)
            pm.fill(Qt.transparent)
            if chosen.lower().endswith(".svg"):
                try:
                    renderer = QSvgRenderer(chosen)
                    painter = QPainter(pm)
                    renderer.render(painter, QRectF(0, 0, self._size, self._size))
                    painter.end()
                except Exception as e:
                    logger.error(f"Failed to render SVG {chosen}: {e}")
                    pm = QPixmap()
            else:
                loaded = QPixmap(chosen)
                if not loaded.isNull():
                    pm = loaded.scaled(self._size, self._size, Qt.KeepAspectRatio,
                                       Qt.SmoothTransformation)
            if not pm.isNull():
                return pm

        logger.warning("No icon image available, drawing fallback microphone")
        return self._draw_mic_icon()

    def _draw_mic_icon(self):
        pm = QPixmap(self._size, self._size)
        pm.fill(Qt.transparent)
        p = QPainter(pm)
        p.setRenderHint(QPainter.Antialiasing)
        s = self._size
        # background circle
        p.setBrush(QColor(31, 111, 235))
        p.setPen(Qt.NoPen)
        p.drawEllipse(2, 2, s - 4, s - 4)
        # microphone body
        p.setBrush(QColor("white"))
        w = s * 0.28
        p.drawRoundedRect(QRectF(s / 2 - w / 2, s * 0.22, w, s * 0.38), w / 2, w / 2)
        # arc
        pen_w = max(2.0, s * 0.06)
        p.setBrush(Qt.NoBrush)
        pen = p.pen()
        pen.setWidthF(pen_w)
        pen.setColor(QColor("white"))
        pen.setCapStyle(Qt.RoundCap)
        p.setPen(pen)
        p.drawArc(QRectF(s * 0.25, s * 0.34, s * 0.5, s * 0.5), 200 * 16, 140 * 16)
        # stem
        p.setBrush(QColor("white"))
        p.setPen(Qt.NoPen)
        p.drawRoundedRect(QRectF(s / 2 - w * 0.2, s * 0.66, w * 0.4, s * 0.16), 2, 2)
        p.end()
        return pm

    # -------------------------------------------------------------- paint --
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # state ring — pulses while recording
        ring = _STATE_COLORS.get(self.state, _STATE_COLORS[AppState.IDLE])
        inset = max(1.0, self._size * 0.04)
        pen_w = max(2.5, self._size * 0.05)
        if self.state == AppState.RECORDING:
            # oscillate the ring inward/outward for a "live" feel
            pulse = math.sin(self._pulse_t * 0.35) * self._size * 0.045
            inset = max(0.5, inset - pulse)
            pen_w = max(2.0, pen_w + abs(pulse) * 0.6)
        painter.setBrush(Qt.NoBrush)
        pen = painter.pen()
        pen.setColor(ring)
        pen.setWidthF(pen_w)
        painter.setPen(pen)
        painter.drawEllipse(QRectF(inset, inset, self._size - 2 * inset, self._size - 2 * inset))

        # icon image
        painter.drawPixmap(0, 0, self._icon_pixmap)
        painter.end()

    # ------------------------------------------------------------- mouse --
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_offset = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            self._moved = False
        elif event.button() == Qt.RightButton:
            self._show_menu(event.globalPosition().toPoint())

    def mouseMoveEvent(self, event):
        if self._drag_offset is not None and event.buttons() & Qt.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_offset)
            self._moved = True
            # keep the recording indicator glued to the icon
            self.indicator.align_to_icon()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self._drag_offset is not None:
            was_drag = self._moved
            self._drag_offset = None
            if not was_drag:
                self.controller.toggle_recording()
            else:
                self._save_position()

    def _save_position(self):
        pos = self.pos()
        self.config.get_value("icon", {})["position"] = [pos.x(), pos.y()]
        self.config.save()

    def _show_menu(self, global_pos):
        menu = QMenu(self)
        cfg = self.config
        if self.state == AppState.IDLE:
            record_label = f"Start Recording ({cfg.hotkey_toggle})"
        else:
            record_label = "Stop & Transcribe"
        rec_action = QAction(record_label, self)
        rec_action.triggered.connect(self.controller.toggle_recording)
        menu.addAction(rec_action)
        menu.addSeparator()
        quit_action = QAction(f"Quit ({cfg.hotkey_quit})", self)
        quit_action.triggered.connect(self._quit_app)
        menu.addAction(quit_action)
        menu.exec(global_pos)

    def _quit_app(self):
        app = QApplication.instance()
        if app is not None:
            app.quit()

    # ------------------------------------------------------------ state --
    def _on_state_changed(self, state: AppState):
        self.state = state
        self._update_tooltip()
        self.update()
    def _update_tooltip(self):
        cfg = self.config
        self.setToolTip(
            f"WhisperFlow — {_STATE_LABELS.get(self.state, '')}\n"
            f"Left-click: start/stop recording\n"
            f"Record: {cfg.hotkey_toggle}   Quit: {cfg.hotkey_quit}"
        )
