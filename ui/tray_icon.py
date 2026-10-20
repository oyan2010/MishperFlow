import os
from PySide6.QtWidgets import QSystemTrayIcon, QMenu, QApplication
from PySide6.QtGui import QIcon, QPixmap, QPainter, QColor, QAction
from PySide6.QtCore import QTimer, QSize
from core.state import AppState
from core.config import Config

class SystemTrayIcon(QSystemTrayIcon):
    def __init__(self, controller):
        super().__init__()
        self.controller = controller
        self.config = Config.get()
        self.setIcon(self._create_icon(AppState.IDLE))
        self.setToolTip("WhisperFlow")
        self.setContextMenu(self._create_menu())

        # Connect signals
        self.activated.connect(self._on_activated)
        self.controller.state_changed.connect(self._on_state_changed)
        self.controller.notification.connect(self._show_notification)

        # Ensure proper exit
        self.quit_action = None

    def _create_icon(self, state: AppState) -> QIcon:
        """Generate colored circle icon."""
        size = 64
        pixmap = QPixmap(QSize(size, size))
        pixmap.fill(QColor("transparent"))
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)

        if state == AppState.IDLE:
            color = QColor("green")
        elif state == AppState.RECORDING:
            color = QColor("red")
        else:  # PROCESSING
            color = QColor("orange")

        painter.setBrush(color)
        painter.setPen(QColor("black"))
        painter.drawEllipse(4, 4, size-8, size-8)
        painter.end()
        return QIcon(pixmap)

    def _create_menu(self):
        menu = QMenu()
        record_action = QAction(f"Record ({self.config.hotkey_toggle})", self)
        record_action.triggered.connect(self.controller.toggle_recording)
        menu.addAction(record_action)

        stop_action = QAction("Stop Recording", self)
        stop_action.triggered.connect(self.controller.stop_recording_and_transcribe)
        menu.addAction(stop_action)

        menu.addSeparator()
        exit_action = QAction(f"Exit ({self.config.hotkey_quit})", self)
        exit_action.triggered.connect(self._exit_app)
        menu.addAction(exit_action)

        self.record_action = record_action
        self.stop_action = stop_action
        self.exit_action = exit_action
        return menu

    def _on_activated(self, reason):
        if reason == QSystemTrayIcon.Trigger:  # left click
            self.controller.toggle_recording()

    def _on_state_changed(self, state: AppState):
        self.setIcon(self._create_icon(state))
        # Update menu visibility
        if state == AppState.IDLE:
            self.record_action.setEnabled(True)
            self.stop_action.setEnabled(False)
        elif state == AppState.RECORDING:
            self.record_action.setEnabled(False)
            self.stop_action.setEnabled(True)
        else:  # PROCESSING
            self.record_action.setEnabled(False)
            self.stop_action.setEnabled(False)

    def _show_notification(self, title: str, message: str):
        self.showMessage(title, message, QSystemTrayIcon.Information, 3000)

    def _exit_app(self):
        QApplication.quit()