"""Speech-to-Text (STT) service for MedSpeak using faster-whisper.

Provides modular speech recognition converting browser microphone audio
into accurate medical transcription text.
"""

import logging
import os
import tempfile
import threading

from faster_whisper import WhisperModel

from app.core.config import settings

logger = logging.getLogger(__name__)

# Clinical vocabulary hint to prime the language model for accurate medical terminology
CLINICAL_PROMPT_HINT = (
    "hydroxychloroquine, omeprazole, tachycardia, amoxicillin, acetaminophen, "
    "ibuprofen, azithromycin, metformin, clopidogrel, dexamethasone, levothyroxine, "
    "sternocleidomastoid, epiglottis, esophagus, electroencephalography, echocardiography, "
    "pronounce, pronunciation, break down, syllables"
)


class STTError(Exception):
    """Base exception for Speech-to-Text processing failures."""

    def __init__(self, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class STTService:
    """Modular Speech-to-Text service powered by faster-whisper."""

    def __init__(
        self,
        model_size: str | None = None,
        device: str | None = None,
        compute_type: str | None = None,
    ) -> None:
        self.model_size = model_size or settings.STT_MODEL_SIZE
        self.device = device or settings.STT_DEVICE
        self.compute_type = compute_type or settings.STT_COMPUTE_TYPE
        self._model: WhisperModel | None = None
        self._lock = threading.Lock()

    def _get_model(self) -> WhisperModel:
        """Lazily initialize and cache the WhisperModel instance."""
        if self._model is None:
            with self._lock:
                if self._model is None:
                    snapshot_dir = os.path.expanduser(
                        r"~/.cache/huggingface/hub/models--Systran--faster-whisper-tiny.en/snapshots/0d3d19a32d3338f10357c0889762bd8d64bbdeba"
                    )
                    model_source = (
                        snapshot_dir
                        if os.path.isfile(os.path.join(snapshot_dir, "model.bin"))
                        else self.model_size
                    )
                    logger.info(
                        "Loading faster-whisper model from '%s' (device=%s, compute_type=%s)...",
                        model_source,
                        self.device,
                        self.compute_type,
                    )
                    self._model = WhisperModel(
                        model_source,
                        device=self.device,
                        compute_type=self.compute_type,
                    )
        return self._model

    async def transcribe(
        self,
        audio_bytes: bytes,
        filename_hint: str = "audio.webm",
        initial_prompt: str = CLINICAL_PROMPT_HINT,
    ) -> str:
        """Transcribe raw audio bytes into text.

        Args:
            audio_bytes: Raw binary audio payload (webm, mp4, wav, etc.).
            filename_hint: Filename or extension hint to determine audio container format.
            initial_prompt: Contextual priming prompt for medical vocabulary.

        Returns:
            The transcribed text string.

        Raises:
            STTError: If the audio is empty, silence, corrupted, or cannot be transcribed.
        """
        if not audio_bytes or len(audio_bytes) < 32:
            logger.warning(
                "STT received empty or truncated audio bytes (%d bytes)", len(audio_bytes)
            )
            raise STTError("Empty audio recording received", status_code=400)

        ext = os.path.splitext(filename_hint)[1] or ".webm"
        temp_path: str | None = None

        try:
            # Write audio bytes to temporary file for PyAV/ffmpeg container decoding
            with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as temp_file:
                temp_file.write(audio_bytes)
                temp_path = temp_file.name

            model = self._get_model()

            # Execute transcription with language set to English
            segments, info = model.transcribe(
                temp_path,
                language="en",
                initial_prompt=initial_prompt,
                beam_size=5,
                vad_filter=True,
                vad_parameters={"min_silence_duration_ms": 500},
            )

            # Consume the segments generator
            transcribed_parts = [segment.text.strip() for segment in segments]
            transcript = " ".join(transcribed_parts).strip()

            logger.info(
                "STT completed: '%s' (duration=%.2fs, lang_prob=%.2f)",
                transcript,
                getattr(info, "duration", 0.0),
                getattr(info, "language_probability", 1.0),
            )

            if not transcript:
                raise STTError("Couldn't hear that. Try again.", status_code=422)

            return transcript

        except STTError:
            raise
        except Exception as exc:
            logger.error("Failed to transcribe audio with faster-whisper: %s", exc, exc_info=True)
            raise STTError(f"STT transcription failed: {str(exc)}", status_code=500) from exc
        finally:
            if temp_path and os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except OSError as err:
                    logger.warning("Could not remove temp audio file %s: %s", temp_path, err)


# Singleton STT service instance
stt_service = STTService()
