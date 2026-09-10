"""Unit tests for the modular Speech-to-Text (STT) service."""

from unittest.mock import MagicMock, patch

import pytest

from app.services.stt import CLINICAL_PROMPT_HINT, STTError, STTService


@pytest.mark.asyncio
async def test_stt_empty_audio_raises_error() -> None:
    """Verify that empty or truncated audio bytes immediately raise STTError."""
    service = STTService(model_size="tiny.en")
    with pytest.raises(STTError) as exc_info:
        await service.transcribe(b"")

    assert "empty" in exc_info.value.message.lower()
    assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_stt_short_audio_raises_error() -> None:
    """Verify audio under minimum threshold raises STTError."""
    service = STTService(model_size="tiny.en")
    with pytest.raises(STTError) as exc_info:
        await service.transcribe(b"too_short")

    assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_stt_successful_transcription_with_mock_model() -> None:
    """Verify transcription pipeline when WhisperModel returns segment text."""
    service = STTService(model_size="tiny.en")

    mock_segment_1 = MagicMock()
    mock_segment_1.text = "How do I pronounce"
    mock_segment_2 = MagicMock()
    mock_segment_2.text = "hydroxychloroquine"

    mock_info = MagicMock()
    mock_info.duration = 2.5
    mock_info.language_probability = 0.98

    mock_model = MagicMock()
    mock_model.transcribe.return_value = ([mock_segment_1, mock_segment_2], mock_info)

    # Supply sufficient dummy bytes to pass header length check
    dummy_audio = b"\x1aE\xdf\xa3" + b"\x00" * 64

    with patch.object(service, "_get_model", return_value=mock_model):
        transcript = await service.transcribe(dummy_audio, filename_hint="audio.webm")

    assert transcript == "How do I pronounce hydroxychloroquine"
    mock_model.transcribe.assert_called_once()
    call_kwargs = mock_model.transcribe.call_args[1]
    assert call_kwargs["language"] == "en"
    assert call_kwargs["initial_prompt"] == CLINICAL_PROMPT_HINT


@pytest.mark.asyncio
async def test_stt_silence_raises_try_again_error() -> None:
    """Verify that an empty transcription (silence) raises the required friendly error."""
    service = STTService(model_size="tiny.en")

    mock_info = MagicMock()
    mock_model = MagicMock()
    mock_model.transcribe.return_value = ([], mock_info)

    dummy_audio = b"\x1aE\xdf\xa3" + b"\x00" * 64

    with patch.object(service, "_get_model", return_value=mock_model):
        with pytest.raises(STTError) as exc_info:
            await service.transcribe(dummy_audio, filename_hint="audio.webm")

    assert exc_info.value.message == "Couldn't hear that. Try again."
    assert exc_info.value.status_code == 422
