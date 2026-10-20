import sys
import os
import signal
import threading
import logging
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer

# Ensure data directories exist
from core import history, transcriber
from core.config import Config
from core.controller import Controller
from ui.tray_icon import SystemTrayIcon
from ui.floating_icon import FloatingIcon

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Exit handling
# ---------------------------------------------------------------------------
# Ctrl+C in a console does NOT interrupt a running Qt event loop by default
# (the KeyboardInterrupt is deferred until app.exec() returns, which never
# happens), so the app silently keeps running in the background eating RAM.
# We install signal handlers that set this flag; the Qt event loop polls it
# and quits cleanly.
_exit_requested = False


def _request_exit(signum=None, frame=None):
    global _exit_requested
    _exit_requested = True
    logger.info(f"Exit signal received ({signum}), shutting down...")


def _maybe_quit(app):
    if _exit_requested:
        app.quit()


def _install_exit_handlers(app):
    """Make Ctrl+C / Ctrl+Break / SIGTERM actually quit the app."""
    for sig_name in ("SIGINT", "SIGBREAK", "SIGTERM"):
        if hasattr(signal, sig_name):
            try:
                signal.signal(getattr(signal, sig_name), _request_exit)
            except Exception:
                pass

    # Qt's event loop calls this Python slot every 200ms; that is when the
    # interpreter runs, so the pending signal handler executes and the flag
    # is observed -> app.quit() -> clean shutdown.
    poller = QTimer()
    poller.timeout.connect(lambda: _maybe_quit(app))
    poller.start(200)
    return poller


class _SingleInstance:
    """Prevents two app instances running at once (and zombie stacking).

    Uses an OS-level file lock: if another instance holds it, this one exits.
    The lock is released automatically by the OS if the process dies, even
    after a crash.
    """

    def __init__(self, lock_path):
        self._lock_path = lock_path
        self._file = None

    def acquire(self):
        try:
            import msvcrt
            self._file = open(self._lock_path, "w")
            self._file.write("x")
            self._file.flush()
            self._file.seek(0)
            msvcrt.locking(self._file.fileno(), msvcrt.LK_NBLCK, 1)
            return True
        except (OSError, ImportError):
            if self._file:
                self._file.close()
                self._file = None
            return False

    def release(self):
        if self._file:
            try:
                import msvcrt
                self._file.seek(0)
                msvcrt.locking(self._file.fileno(), msvcrt.LK_UNLCK, 1)
            except Exception:
                pass
            self._file.close()
            self._file = None


def _notify_already_running():
    msg = "WhisperFlow is already running in the background.\n"
    msg += "Look for its icon in the system tray (or the floating mic icon)."
    logger.warning(msg)
    try:
        import ctypes
        ctypes.windll.user32.MessageBoxW(0, msg, "WhisperFlow", 0x40)  # MB_ICONINFORMATION
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    # Load (or create) config.json in the current working directory
    config = Config.get()

    # Use the current working directory for all app data (recordings, DB),
    # NOT the user's Documents folder. Override via WHISPERFLOW_DATA_DIR if needed.
    base_dir = os.getenv("WHISPERFLOW_DATA_DIR", os.getcwd())
    recordings_dir = os.path.join(base_dir, "recordings")
    os.makedirs(recordings_dir, exist_ok=True)
    logger.info(f"Data directory: {base_dir}")

    # Single-instance guard
    lock = _SingleInstance(os.path.join(base_dir, "whisperflow.lock"))
    if not lock.acquire():
        _notify_already_running()
        return 1

    # Exit handling: Ctrl+C / Ctrl+Break / SIGTERM quit cleanly
    exit_poller = _install_exit_handlers(app)

    # Initialize history DB
    history.HistoryManager.init_db(base_dir)

    # Initialize transcriber (loads model)
    try:
        transcriber.WhisperTranscriber.get_instance()
    except Exception as e:
        logger.error(f"Failed to load model: {e}")
        # Show critical notification? Tray not created yet; we'll handle later.
        # We'll exit gracefully after showing message box? But no GUI yet.
        # We can still create tray and show notification.
        pass

    # Create controller (will manage state, hotkeys, recorder)
    controller = Controller(base_dir)

    # Create tray icon (notifications + menu)
    tray = SystemTrayIcon(controller)
    tray.show()

    # Create floating icon (click-to-record, draggable, configurable image)
    floating = FloatingIcon(controller)
    floating.show()

    # Start hotkey listener in a separate thread (non-blocking for Qt)
    from core.hotkey import HotkeyManager
    hotkey_mgr = HotkeyManager(controller)
    hotkey_mgr.start()

    # Ensure application exits cleanly and NEVER leaves a zombie behind
    def on_exit():
        logger.info("Shutting down...")
        # Safety net: if any thread blocks shutdown, force-exit after 6s
        watchdog = threading.Timer(6.0, lambda: os._exit(0))
        watchdog.daemon = True
        watchdog.start()
        try:
            config.save()
            controller.cleanup()
            hotkey_mgr.stop()
            lock.release()
        finally:
            watchdog.cancel()

    app.aboutToQuit.connect(on_exit)

    code = app.exec()
    exit_poller.stop()
    return code


if __name__ == "__main__":
    sys.exit(main())
