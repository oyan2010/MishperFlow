import threading
from enum import Enum

class AppState(Enum):
    IDLE = 1
    RECORDING = 2
    PROCESSING = 3

class StateManager:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._state = AppState.IDLE
                    cls._instance._state_lock = threading.Lock()
        return cls._instance

    def get_state(self) -> AppState:
        with self._state_lock:
            return self._state

    def transition(self, new_state: AppState) -> bool:
        """Attempt to transition to new_state. Returns True if successful."""
        with self._state_lock:
            current = self._state
            # Allowed transitions: IDLE->RECORDING, RECORDING->PROCESSING, PROCESSING->IDLE
            if (current == AppState.IDLE and new_state == AppState.RECORDING) or \
               (current == AppState.RECORDING and new_state == AppState.PROCESSING) or \
               (current == AppState.PROCESSING and new_state == AppState.IDLE):
                self._state = new_state
                return True
            return False