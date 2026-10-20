import threading
import logging
import keyboard
from PySide6.QtWidgets import QApplication

from .config import Config

logger = logging.getLogger(__name__)


class HotkeyManager:
    """Registers global hotkeys from config.json:
    - toggle_recording : start/stop recording (default Ctrl+Shift+Space)
    - quit             : close the app           (default Ctrl+Shift+Q)
    """

    def __init__(self, controller):
        self.controller = controller
        self.config = Config.get()
        self._running = False
        self._thread = None
        self._registered = []

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._listen, daemon=True)
        self._thread.start()

    def _listen(self):
        try:
            toggle = self.config.hotkey_toggle
            quit_key = self.config.hotkey_quit

            if toggle:
                keyboard.add_hotkey(toggle, self.controller.toggle_recording)
                self._registered.append(toggle)
                logger.info(f"Hotkey registered: {toggle} (toggle recording)")
            if quit_key and quit_key != toggle:
                keyboard.add_hotkey(quit_key, self._quit)
                self._registered.append(quit_key)
                logger.info(f"Hotkey registered: {quit_key} (quit)")
            # Keep thread alive
            while self._running:
                keyboard.wait('', suppress=False, trigger_on_release=False)
        except Exception as e:
            logger.error(f"Hotkey listener error: {e}")
            # Notify via controller
            self.controller.notification.emit("Hotkey Error", "Failed to register global hotkey. Check permissions.")

    def _quit(self):
        """Quit the app. QCoreApplication.quit/exit is documented as thread-safe."""
        app = QApplication.instance()
        if app is not None:
            app.quit()

    def stop(self):
        self._running = False
        try:
            keyboard.unhook_all()
        except Exception:
            pass
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1)
