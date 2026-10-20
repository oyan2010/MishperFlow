import pyaudio
import wave
import threading
import time
import logging
from PySide6.QtCore import QThread, Signal

from .config import Config

logger = logging.getLogger(__name__)

# Audio parameters
CHANNELS = 1
FORMAT = pyaudio.paInt16
CHUNK = 1024


def _list_input_devices(p):
    """Return [(index, name), ...] for every device with input channels."""
    out = []
    for i in range(p.get_device_count()):
        try:
            info = p.get_device_info_by_index(i)
            if info["maxInputChannels"] > 0:
                out.append((i, info["name"]))
        except Exception:
            continue
    return out


def _select_input_device_index(p, configured):
    """Resolve the input device index from config (or auto-detect)."""
    if configured is not None:
        if isinstance(configured, int):
            try:
                info = p.get_device_info_by_index(configured)
                if info["maxInputChannels"] > 0:
                    return configured
                logger.warning(f"Configured device index {configured} has no input channels")
            except Exception as e:
                logger.warning(f"Configured device index {configured} invalid: {e}")
        elif isinstance(configured, str):
            name = configured.lower()
            for idx, dev_name in _list_input_devices(p):
                if name in dev_name.lower():
                    return idx
            logger.warning(f"No input device matching '{configured}'")
    # Fall back: default input device
    try:
        info = p.get_default_input_device_info()
        return info["index"]
    except Exception:
        pass
    # Fall back: first device with input channels
    devices = _list_input_devices(p)
    if devices:
        return devices[0][0]
    return None


def _open_stream(p, preferred_index, rate):
    """Open the first working input device, trying preferred first.

    The old code relied on PortAudio's implicit default device, which can
    fail with `[Errno -9996] Invalid input device` right after app start.
    We now try the configured/default device, then every other input device
    in order until one opens successfully.
    """
    candidates = []
    if preferred_index is not None:
        candidates.append(preferred_index)
    for idx, _name in _list_input_devices(p):
        if idx not in candidates:
            candidates.append(idx)

    last_err = None
    for idx in candidates:
        try:
            stream = p.open(
                format=FORMAT,
                channels=CHANNELS,
                rate=rate,
                input=True,
                frames_per_buffer=CHUNK,
                input_device_index=idx,
            )
            try:
                name = p.get_device_info_by_index(idx)["name"]
            except Exception:
                name = str(idx)
            logger.info(f"Opened input device [{idx}] {name}")
            return stream
        except Exception as e:
            last_err = e
            logger.warning(f"Input device [{idx}] failed to open: {e}")
    raise last_err or RuntimeError("No usable input device found")


class AudioRecorder(QThread):
    finished = Signal(str, float)  # file_path, duration
    error = Signal(str)

    def __init__(self, output_path: str):
        super().__init__()
        self.output_path = output_path
        self._stop_event = threading.Event()
        self._recording = False
        self._p = None
        self._stream = None

    def stop_recording(self):
        self._stop_event.set()

    def run(self):
        try:
            cfg = Config.get()
            rate = int(cfg.get_value("recorder", {}).get("sample_rate", 16000))
            configured = cfg.get_value("recorder", {}).get("input_device")

            self._p = pyaudio.PyAudio()
            preferred = _select_input_device_index(self._p, configured)
            if preferred is None:
                raise RuntimeError("No audio input device found on this system")
            self._stream = _open_stream(self._p, preferred, rate)

            frames = []
            self._recording = True
            start_time = time.time()

            while not self._stop_event.is_set():
                data = self._stream.read(CHUNK, exception_on_overflow=False)
                frames.append(data)

            duration = time.time() - start_time

            # Stop stream
            self._stream.stop_stream()
            self._stream.close()
            self._p.terminate()

            # Write to WAV file
            with wave.open(self.output_path, 'wb') as wf:
                wf.setnchannels(CHANNELS)
                wf.setsampwidth(self._p.get_sample_size(FORMAT))
                wf.setframerate(rate)
                wf.writeframes(b''.join(frames))

            self.finished.emit(self.output_path, duration)

        except Exception as e:
            logger.exception("Audio recording failed")
            self.error.emit(str(e))
        finally:
            self._recording = False
            if self._stream:
                try:
                    self._stream.close()
                except Exception:
                    pass
            if self._p:
                self._p.terminate()
