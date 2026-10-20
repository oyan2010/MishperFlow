import json
import os
import logging

logger = logging.getLogger(__name__)

DEFAULT_CONFIG = {
    "hotkeys": {
        # Keys follow the `keyboard` library syntax: https://github.com/boppreh/keyboard
        "toggle_recording": "ctrl+alt+r",
        "quit": "ctrl+shift+q",
    },
    "icon": {
        # Path to a custom image (png/svg/ico) for the floating icon.
        # Leave empty ("") to auto-pick a random one from the assets/ folder.
        "path": "",
        "random": True,
        "size": 56,
        "position": None,  # [x, y] saved automatically when you drag the icon
    },
    "recorder": {
        # None = auto-detect. Or use an int device index (e.g. 6),
        # or a string matched against the device name (e.g. "USB Audio").
        "input_device": None,
        "sample_rate": 16000,
    },
}


def _deep_merge(base, override):
    """Merge user config over defaults (recursively for dicts)."""
    out = dict(base)
    for k, v in (override or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


class Config:
    """Loads config.json from the current working directory.

    A default config.json is written to disk on first run so the user can
    edit hotkeys / icon image / input device without touching code.
    """
    _instance = None

    def __init__(self, path=None):
        self.path = path or os.path.join(os.getcwd(), "config.json")
        self.data = self._load()
        if not os.path.exists(self.path):
            self.save()

    @classmethod
    def get(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def _load(self):
        if os.path.exists(self.path):
            try:
                with open(self.path, "r", encoding="utf-8") as f:
                    user = json.load(f)
                return _deep_merge(DEFAULT_CONFIG, user)
            except Exception as e:
                logger.error(f"Failed to read config {self.path}: {e}")
        return json.loads(json.dumps(DEFAULT_CONFIG))

    def save(self):
        try:
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=2, ensure_ascii=False)
            logger.info(f"Config saved to {self.path}")
        except Exception as e:
            logger.error(f"Failed to save config {self.path}: {e}")

    # --- typed accessors -------------------------------------------------
    def get_value(self, key, default=None):
        return self.data.get(key, default)

    @property
    def hotkey_toggle(self):
        return self.data.get("hotkeys", {}).get("toggle_recording", "ctrl+shift+space")

    @property
    def hotkey_quit(self):
        return self.data.get("hotkeys", {}).get("quit", "ctrl+shift+q")
