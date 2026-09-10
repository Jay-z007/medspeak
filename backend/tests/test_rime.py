"""Automated unit and integration tests for Rime TTS service and API routes."""

import httpx
import pytest
from httpx import ASGITransport, AsyncClient

from app.core.config import Settings
from app.main import app
from app.services.rime import (
    RimeAuthenticationError,
    RimeConfigurationError,
    RimeMalformedAudioError,
    RimeRateLimitError,
    RimeServerError,
    RimeService,
    RimeTimeoutError,
    is_valid_audio_bytes,
    redact_secret,
    sanitize_headers,
)

# Minimal valid MP3 header bytes for testing
VALID_MP3_BYTES = b"\xff\xf3\xe4\xc4" + b"\x00" * 64


@pytest.fixture
def valid_settings() -> Settings:
    return Settings(
        RIME_API_KEY="test_mock_secret_key_1234567890",
        RIME_API_URL="https://users.rime.ai/v1/rime-tts",
        RIME_MODEL_ID="coda",
        RIME_SPEAKER="astra",
        RIME_LANGUAGE="en",
        RIME_AUDIO_FORMAT="mp3",
        RIME_SAMPLING_RATE=24000,
    )


# 1. Missing Configuration
def test_missing_api_key_configuration(valid_settings: Settings) -> None:
    valid_settings.RIME_API_KEY = ""
    service = RimeService(settings=valid_settings)
    checks = service.validate_configuration()

    api_key_check = next((c for c in checks if c.name == "api_key_exists"), None)
    assert api_key_check is not None
    assert api_key_check.passed is False


@pytest.mark.asyncio
async def test_missing_api_key_raises_during_synthesis(valid_settings: Settings) -> None:
    valid_settings.RIME_API_KEY = ""
    service = RimeService(settings=valid_settings)

    with pytest.raises(RimeConfigurationError, match="API key is missing"):
        await service.synthesize("Test phrase")


# 2. Invalid Configuration
def test_invalid_model_configuration(valid_settings: Settings) -> None:
    valid_settings.RIME_MODEL_ID = "invalid_nonexistent_model"
    service = RimeService(settings=valid_settings)
    checks = service.validate_configuration()

    model_check = next((c for c in checks if c.name == "model_valid"), None)
    assert model_check is not None
    assert model_check.passed is False


def test_invalid_audio_format_configuration(valid_settings: Settings) -> None:
    valid_settings.RIME_AUDIO_FORMAT = "flac"  # Unsupported
    service = RimeService(settings=valid_settings)
    checks = service.validate_configuration()

    fmt_check = next((c for c in checks if c.name == "audio_format_valid"), None)
    assert fmt_check is not None
    assert fmt_check.passed is False


# 3. Successful Synthesis (Mocked)
@pytest.mark.asyncio
async def test_successful_synthesis(valid_settings: Settings) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["authorization"] == f"Bearer {valid_settings.RIME_API_KEY}"
        assert request.headers["accept"] == "audio/mpeg"
        return httpx.Response(200, content=VALID_MP3_BYTES)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        service = RimeService(settings=valid_settings, client=client)
        result = await service.synthesize("Hello from MedSpeak.")

    assert result.audio_bytes == VALID_MP3_BYTES
    assert result.content_type == "audio/mpeg"
    assert result.model_id == "coda"
    assert result.speaker == "astra"
    assert result.latency_ms >= 0


# 4. Authentication Failure (401 / 403)
@pytest.mark.asyncio
async def test_authentication_failure(valid_settings: Settings) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": "Invalid API key"})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        service = RimeService(settings=valid_settings, client=client)
        with pytest.raises(RimeAuthenticationError) as exc_info:
            await service.synthesize("Hello")

    assert exc_info.value.status_code == 401
    assert "authentication failed" in exc_info.value.message.lower()


# 5. Timeout Handling
@pytest.mark.asyncio
async def test_timeout_handling(valid_settings: Settings) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("Request timed out", request=request)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        service = RimeService(settings=valid_settings, client=client)
        with pytest.raises(RimeTimeoutError) as exc_info:
            await service.synthesize("Hello", timeout=1.0)

    assert exc_info.value.status_code == 504
    assert "timed out" in exc_info.value.message.lower()


# 6. Rate Limit Handling (429)
@pytest.mark.asyncio
async def test_rate_limit_handling(valid_settings: Settings) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, json={"error": "Too Many Requests"})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        service = RimeService(settings=valid_settings, client=client)
        with pytest.raises(RimeRateLimitError) as exc_info:
            await service.synthesize("Hello")

    assert exc_info.value.status_code == 429
    assert "rate limit" in exc_info.value.message.lower()


# 7. Server Error Handling (500)
@pytest.mark.asyncio
async def test_server_error_handling(valid_settings: Settings) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="Internal Server Error")

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        service = RimeService(settings=valid_settings, client=client)
        with pytest.raises(RimeServerError) as exc_info:
            await service.synthesize("Hello")

    assert exc_info.value.status_code == 500
    assert "server error" in exc_info.value.message.lower()


# 8. Empty / Malformed Audio
@pytest.mark.asyncio
async def test_empty_audio_raises_malformed_error(valid_settings: Settings) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"")

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        service = RimeService(settings=valid_settings, client=client)
        with pytest.raises(RimeMalformedAudioError, match="empty audio content"):
            await service.synthesize("Hello")


@pytest.mark.asyncio
async def test_corrupt_audio_raises_malformed_error(valid_settings: Settings) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        # 100 bytes of plain text or corrupt header
        return httpx.Response(200, content=b"corrupt_non_audio_payload_bytes_here" * 3)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        service = RimeService(settings=valid_settings, client=client)
        with pytest.raises(RimeMalformedAudioError, match="malformed audio"):
            await service.synthesize("Hello")


# 9. Secret Redaction
def test_secret_redaction_utilities() -> None:
    raw_key = "test_super_secret_api_key_9999"
    redacted = redact_secret(raw_key)

    # Must not contain the full key
    assert raw_key not in redacted
    assert "REDACTED" in redacted
    assert redact_secret("") == "<EMPTY>"

    # Header sanitization
    headers = {
        "Authorization": f"Bearer {raw_key}",
        "Content-Type": "application/json",
    }
    sanitized = sanitize_headers(headers)
    assert raw_key not in sanitized["Authorization"]
    assert sanitized["Authorization"] == "Bearer ***REDACTED***"
    assert sanitized["Content-Type"] == "application/json"


# 10. Preflight Verification Logic (Mocked)
@pytest.mark.asyncio
async def test_preflight_success(valid_settings: Settings) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=VALID_MP3_BYTES)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        service = RimeService(settings=valid_settings, client=client)
        report = await service.preflight()

    assert report.status == "ok"
    assert report.model_id == "coda"
    assert report.speaker == "astra"
    assert report.audio_bytes == len(VALID_MP3_BYTES)
    assert report.error is None
    assert all(c.passed for c in report.checks)


# 11. API Endpoints
@pytest.mark.asyncio
async def test_api_preflight_endpoint() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/api/rime/preflight")

    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "checks" in data
    assert data["model_id"] == "coda"
    assert data["speaker"] == "astra"


@pytest.mark.asyncio
async def test_api_test_endpoint() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/rime/test",
            json={"text": "Hello from MedSpeak."},
        )

    # Should succeed with real Rime credentials
    assert response.status_code == 200
    assert response.headers["content-type"] == "audio/mpeg"
    assert "filename=" in response.headers["content-disposition"]
    assert len(response.content) > 1000
    assert is_valid_audio_bytes(response.content, "mp3") is True
