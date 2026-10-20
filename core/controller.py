import os
import shutil
import tempfile
import wave
import threading
import time
import logging
from PySide6.QtCore import QObject, Signal

from .state import StateManager, AppState
from .audio_recorder import AudioRecorder
from .transcriber import WhisperTranscriber
from .clipboard import ClipboardManager
from .history import HistoryManager

logger = logging.getLogger(__name__)

class Controller(QObject):
    # Signals for UI updates
    state_changed = Signal(AppState)
    notification = Signal(str, str)  # title, message

    def __init__(self, base_dir: str):
        super().__init__()
        self.base_dir = base_dir
        self.recordings_dir = os.path.join(base_dir, "recordings")
        self.state_mgr = StateManager()
        self.recorder = None
        self.transcriber = WhisperTranscriber.get_instance()
        self.clipboard = ClipboardManager()
        self.history = HistoryManager()

        # For temp file handling
        self.temp_audio_path = None

        # State change callback for tray
        self._update_ui_state()

    def _update_ui_state(self):
        state = self.state_mgr.get_state()
        self.state_changed.emit(state)

    def start_recording(self):
        """Called when user triggers record (IDLE -> RECORDING)."""
        if self.state_mgr.transition(AppState.RECORDING):
            self._update_ui_state()
            # Create temp file
            fd, self.temp_audio_path = tempfile.mkstemp(suffix='.wav', prefix='whisperflow_')
            os.close(fd)  # we'll write using wave module later
            # Start recorder
            self.recorder = AudioRecorder(self.temp_audio_path)
            self.recorder.finished.connect(self._on_recording_finished)
            self.recorder.error.connect(self._on_recording_error)
            self.recorder.start()
            logger.info("Recording started")
        else:
            logger.warning("Cannot start recording: invalid state")

    def stop_recording_and_transcribe(self):
        """Called when user stops recording (RECORDING -> PROCESSING)."""
        if self.state_mgr.get_state() != AppState.RECORDING:
            logger.warning("Cannot stop: not recording")
            return
        if self.recorder and self.recorder.isRunning():
            self.recorder.stop_recording()
            # The finished signal will handle transition to PROCESSING and transcription
        else:
            # If recorder is not running, force transition to IDLE
            self._abort_recording()

    def _on_recording_finished(self, file_path: str, duration: float):
        """Recorder finished successfully."""
        logger.info(f"Recording finished: {file_path}, duration {duration:.2f}s")
        # Transition to PROCESSING
        if self.state_mgr.transition(AppState.PROCESSING):
            self._update_ui_state()
            # Check duration
            if duration < 0.5:
                self.notification.emit("Recording too short", "Ignored (less than 0.5 seconds)")
                self._reset_to_idle(delete_temp=True)
                return
            # Start transcription in a separate thread to avoid blocking GUI
            threading.Thread(target=self._transcribe_worker, args=(file_path, duration), daemon=True).start()
        else:
            logger.error("Failed to transition to PROCESSING")
            self._reset_to_idle(delete_temp=True)

    def _on_recording_error(self, error_msg: str):
        logger.error(f"Recording error: {error_msg}")
        self.notification.emit("Recording Error", error_msg)
        self._reset_to_idle(delete_temp=True)

    def _transcribe_worker(self, audio_path: str, duration: float):
        try:
            transcript = self.transcriber.transcribe(audio_path)
            if transcript is None:
                self.notification.emit("Transcription failed", "Model returned empty result")
                self._reset_to_idle(delete_temp=True)
                return
            # Success: now handle paste, save history, move file
            self._handle_transcription_success(audio_path, transcript, duration)
        except Exception as e:
            logger.exception("Transcription error")
            self.notification.emit("Transcription Error", str(e))
            self._reset_to_idle(delete_temp=True)

    def _handle_transcription_success(self, temp_path: str, transcript: str, duration: float):
        # Generate permanent file name
        timestamp = time.strftime("%Y-%m-%d_%H-%M-%S")
        perm_filename = f"{timestamp}.wav"
        perm_path = os.path.join(self.recordings_dir, perm_filename)
        try:
            # os.rename fails across drives (temp is on C:, recordings on F:),
            # so use shutil.move which handles cross-device moves.
            shutil.move(temp_path, perm_path)
        except OSError as e:
            logger.error(f"Failed to move temp file: {e}")
            self.notification.emit("File Error", "Could not save recording")
            self._reset_to_idle(delete_temp=True)
            return

        # Save to history
        try:
            self.history.add_record(perm_path, transcript, duration)
        except Exception as e:
            logger.error(f"Failed to save history: {e}")
            # We still paste and continue

        # Clipboard and paste
        try:
            self.clipboard.save_and_set(transcript)
            # Simulate paste
            self.clipboard.paste()
            # Restore original clipboard after a short delay
            import sys
            # Use QTimer for cross-platform compatibility
            from PySide6.QtCore import QTimer
            QTimer.singleShot(200, self.clipboard.restore)
        except Exception as e:
            logger.error(f"Clipboard/paste error: {e}")
            self.notification.emit("Paste Error", "Transcript copied to clipboard, but paste simulation failed. Please paste manually.")

        # Show success notification
        self.notification.emit("Transcription complete", f"'{transcript[:50]}...' pasted")

        # Transition back to IDLE
        self._reset_to_idle(delete_temp=False)  # temp already moved

    def _reset_to_idle(self, delete_temp: bool = True):
        """Force state to IDLE, clean up temp file."""
        if delete_temp and self.temp_audio_path and os.path.exists(self.temp_audio_path):
            try:
                os.remove(self.temp_audio_path)
            except OSError:
                pass
        self.temp_audio_path = None
        self.recorder = None
        if self.state_mgr.transition(AppState.IDLE):
            self._update_ui_state()
        else:
            # Force set
            with self.state_mgr._state_lock:
                self.state_mgr._state = AppState.IDLE
            self._update_ui_state()

    def _abort_recording(self):
        """Emergency abort if recorder fails."""
        if self.recorder:
            self.recorder.stop_recording()
            self.recorder = None
        self._reset_to_idle(delete_temp=True)

    def toggle_recording(self):
        """Public method called by hotkey/tray."""
        state = self.state_mgr.get_state()
        if state == AppState.IDLE:
            self.start_recording()
        elif state == AppState.RECORDING:
            self.stop_recording_and_transcribe()
        else:
            # PROCESSING: ignore
            logger.info("Already processing, ignoring trigger")

    def cleanup(self):
        """Cleanup resources."""
        if self.recorder and self.recorder.isRunning():
            self.recorder.stop_recording()
            self.recorder.wait(2000)  # timeout so shutdown can never hang
        self._reset_to_idle(delete_temp=True)