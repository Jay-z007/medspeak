"""Integration tests for voice endpoints, audio synthesis, and STT pipeline."""

from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.services.rime import RimeSynthesisResult
from app.services.stt import STTError


def _create_mock_synthesis(
    audio_bytes: bytes = b"\xff\xfb\x90\x00medspeak_mock_audio",
    latency_ms: float = 150.0,
) -> RimeSynthesisResult:
    """Helper to instantiate valid RimeSynthesisResult fixtures."""
    return RimeSynthesisResult(
        audio_bytes=audio_bytes,
        content_type="audio/mpeg",
        audio_format="mp3",
        sampling_rate=24000,
        latency_ms=latency_ms,
        model_id="coda",
        speaker="astra",
        text_length=30,
    )


@pytest.mark.asyncio
async def test_chat_endpoint_includes_synthesized_audio() -> None:
    """Verify that POST /api/chat synthesizes Rime audio when synthesize_audio=True."""
    mock_synthesis = _create_mock_synthesis()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        with patch("app.api.chat.rime_service.synthesize", new_callable=AsyncMock) as mock_synth:
            mock_synth.return_value = mock_synthesis
            response = await client.post(
                "/api/chat",
                json={"message": "How do I pronounce omeprazole?", "synthesize_audio": True},
            )

    assert response.status_code == 200
    data = response.json()
    assert data["intent"] == "pronounce"
    assert data["term"] == "omeprazole"
    assert data["audio_base64"] is not None
    assert data["audio_format"] == "mp3"
    assert data["speech_text"] is not None
    assert "Omeprazole is pronounced oh-MEP-ruh-zohl" in data["speech_text"]


@pytest.mark.asyncio
async def test_voice_endpoint_successful_transcription_and_synthesis() -> None:
    """Verify full voice pipeline: audio upload -> STT -> conversation engine -> Rime synthesis."""
    mock_synthesis = _create_mock_synthesis()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        with (
            patch(
                "app.api.chat.stt_service.transcribe",
                new_callable=AsyncMock,
                return_value="How do I pronounce hydroxychloroquine?",
            ),
            patch("app.api.chat.rime_service.synthesize", new_callable=AsyncMock) as mock_synth,
        ):
            mock_synth.return_value = mock_synthesis

            files = {"audio": ("test.webm", b"\x1aE\xdf\xa3" + b"\x00" * 64, "audio/webm")}
            response = await client.post("/api/chat/voice", files=files, data={"speed": "1.0"})

    assert response.status_code == 200
    data = response.json()
    assert data["transcript"] == "How do I pronounce hydroxychloroquine?"
    assert data["intent"] == "pronounce"
    assert data["term"] == "hydroxychloroquine"
    assert "hy-DROX-ee-KLOR-oh-kwin" in data["reply"] or "hy-DROK-see-KLOR-oh-kwin" in data["reply"]
    assert data["audio_base64"] is not None


@pytest.mark.asyncio
async def test_voice_endpoint_handles_stt_failure_gracefully() -> None:
    """Verify STT failure returns 'Couldn't hear that. Try again.' with fallback audio."""
    mock_synthesis = _create_mock_synthesis(audio_bytes=b"\xff\xfb\x90\x00fallback_audio")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        with (
            patch(
                "app.api.chat.stt_service.transcribe",
                new_callable=AsyncMock,
                side_effect=STTError("Couldn't hear that. Try again.", status_code=422),
            ),
            patch("app.api.chat.rime_service.synthesize", new_callable=AsyncMock) as mock_synth,
        ):
            mock_synth.return_value = mock_synthesis

            files = {"audio": ("silent.webm", b"\x1aE\xdf\xa3" + b"\x00" * 64, "audio/webm")}
            response = await client.post("/api/chat/voice", files=files)

    assert response.status_code == 200
    data = response.json()
    assert data["transcript"] == ""
    assert data["intent"] == "stt_failure"
    assert data["reply"] == "Couldn't hear that. Try again."
    assert data["audio_base64"] is not None


@pytest.mark.asyncio
async def test_chat_synthesize_endpoint() -> None:
    """Verify POST /api/chat/synthesize returns audio stream with appropriate headers."""
    mock_synthesis = _create_mock_synthesis(audio_bytes=b"\xff\xfb\x90\x00synthesized_audio")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        with patch("app.api.chat.rime_service.synthesize", new_callable=AsyncMock) as mock_synth:
            mock_synth.return_value = mock_synthesis
            response = await client.post(
                "/api/chat/synthesize",
                json={"text": "Omeprazole is pronounced oh-MEP-ruh-zohl.", "speed": 0.7},
            )

    assert response.status_code == 200
    assert response.headers["content-type"] == "audio/mpeg"
    assert response.headers["x-rime-speed"] == "0.7"
    assert response.content == b"\xff\xfb\x90\x00synthesized_audio"
