import os
import logging
import sys
from faster_whisper import WhisperModel

logger = logging.getLogger(__name__)

# Download models into a local folder next to the app (current working directory),
# instead of the user's global ~/.cache/huggingface folder.
MODEL_DIR = os.path.join(os.getcwd(), "models")

class WhisperTranscriber:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._model = None
            cls._instance._load_model()
        return cls._instance

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def _load_model(self):
        """Load the Whisper model with fallback."""
        os.makedirs(MODEL_DIR, exist_ok=True)
        model_size = os.getenv("WHISPERFLOW_MODEL", "base")  # can be made configurable
        device = "cuda" if self._cuda_available() else "cpu"
        compute_type = "int8"
        try:
            self._model = WhisperModel(model_size, device=device, compute_type=compute_type, download_root=MODEL_DIR)
            logger.info(f"Loaded Whisper model {model_size} on {device} with {compute_type} (models dir: {MODEL_DIR})")
        except Exception as e:
            logger.error(f"Failed to load model with {compute_type} on {device}: {e}")
            # Try fallback: CPU, float32
            try:
                self._model = WhisperModel(model_size, device="cpu", compute_type="float32", download_root=MODEL_DIR)
                logger.warning(f"Fell back to CPU with float32")
            except Exception as e2:
                logger.critical(f"Could not load Whisper model at all: {e2}")
                raise RuntimeError("Failed to load transcription model") from e2

    def _cuda_available(self):
        try:
            import torch
            return torch.cuda.is_available()
        except ImportError:
            return False

    def transcribe(self, audio_path: str) -> str:
        """Transcribe audio file. Returns text or None on failure."""
        if self._model is None:
            logger.error("Model not loaded")
            return None
        try:
            segments, info = self._model.transcribe(audio_path, beam_size=5, language="en")
            # Concatenate all segments
            full_text = " ".join(seg.text for seg in segments)
            if not full_text.strip():
                logger.warning("Empty transcription result")
                return None
            return full_text.strip()
        except Exception as e:
            logger.exception("Transcription failed")
            return None