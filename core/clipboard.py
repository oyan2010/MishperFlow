import pyperclip
import keyboard
import platform
import logging
import time

logger = logging.getLogger(__name__)

class ClipboardManager:
    _backup = None

    @classmethod
    def save_and_set(cls, text: str):
        """Backup current clipboard and set new text."""
        try:
            cls._backup = pyperclip.paste()
        except Exception:
            cls._backup = ""
        try:
            pyperclip.copy(text)
        except Exception as e:
            logger.error(f"Failed to set clipboard: {e}")
            raise

    @classmethod
    def restore(cls):
        """Restore original clipboard content."""
        if cls._backup is not None:
            try:
                pyperclip.copy(cls._backup)
                cls._backup = None
            except Exception as e:
                logger.error(f"Failed to restore clipboard: {e}")

    @classmethod
    def paste(cls):
        """Simulate Ctrl+V / Cmd+V."""
        try:
            if platform.system() == "Darwin":
                keyboard.press_and_release('command+v')
            else:
                keyboard.press_and_release('ctrl+v')
        except Exception as e:
            logger.error(f"Failed to simulate paste: {e}")
            raise