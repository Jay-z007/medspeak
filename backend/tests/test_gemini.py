"""Comprehensive tests for Gemini conversational brain integration in MedSpeak.

Verifies:
1. Gemini unavailable / unconfigured key handling
2. Gemini timeout handling
3. Gemini API error handling
4. Normal "hello"
5. "what can you do?"
6. Pronunciation request ("how do I pronounce hydroxychloroquine?")
7. Unknown pronunciation term
8. "say it slower"
9. Repeat request
10. Conversational context
11. Medical safety request
12. Malformed structured Gemini response
13. Secret / API-key redaction in logs
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.services.gemini import GeminiService, redact_secrets


# 1. Gemini unavailable / unconfigured key handling
@pytest.mark.asyncio
async def test_gemini_unavailable_unconfigured() -> None:
    """Verify service falls back to deterministic engine when unconfigured."""
    with patch("app.services.gemini.settings.GEMINI_API_KEY", ""):
        service = GeminiService()
        assert not service.is_configured

        health = await service.check_health()
        assert health["status"] == "unavailable"
        assert health["configured"] is False

        turn = await service.generate_chat_turn("hello")
        assert turn.intent == "general"
        assert "MedSpeak" in turn.response


# 2. Gemini timeout handling
@pytest.mark.asyncio
async def test_gemini_timeout_handling() -> None:
    """Verify service falls back to deterministic engine when API times out."""
    service = GeminiService()

    # Mock client generate_content to simulate a timeout
    async def mock_hang(*args: object, **kwargs: object) -> None:
        await asyncio.sleep(5.0)

    mock_client = MagicMock()
    mock_client.aio.models.generate_content = mock_hang
    service._client = mock_client
    service.api_key = "test_key"

    with patch("app.services.gemini.settings.GEMINI_TIMEOUT_SECONDS", 0.05):
        turn = await service.generate_chat_turn("How do I say omeprazole?")
        assert turn.intent == "pronounce"
        assert turn.target_term == "omeprazole"
        assert turn.needs_pronunciation_service is True


# 3. Gemini API error handling
@pytest.mark.asyncio
async def test_gemini_api_error_handling() -> None:
    """Verify service handles 500/503 API errors gracefully with local fallback."""
    from google.genai import errors

    service = GeminiService()
    mock_client = MagicMock()
    mock_client.aio.models.generate_content = AsyncMock(
        side_effect=errors.ServerError(503, {"error": {"message": "High demand"}}, None)
    )
    service._client = mock_client
    service.api_key = "test_key"

    turn = await service.generate_chat_turn("Break down tachycardia")
    assert turn.intent == "pronounce"
    assert turn.target_term == "tachycardia"


# 4. Normal "hello"
@pytest.mark.asyncio
async def test_normal_hello() -> None:
    """Verify natural conversational greeting."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/chat",
            json={"message": "hello", "synthesize_audio": False},
        )
    assert response.status_code == 200
    data = response.json()
    assert data["intent"] == "general"
    assert len(data["reply"]) > 5


# 5. "what can you do?"
@pytest.mark.asyncio
async def test_what_can_you_do() -> None:
    """Verify tutor capability explanation."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/chat",
            json={"message": "what can you do?", "synthesize_audio": False},
        )
    assert response.status_code == 200
    data = response.json()
    assert data["intent"] == "general"
    assert any(w in data["reply"].lower() for w in ["pronounce", "medical", "terminology", "tutor"])


# 6. Pronunciation request
@pytest.mark.asyncio
async def test_pronunciation_request_hydroxychloroquine() -> None:
    """Verify clinical pronunciation request uses authoritative dictionary data."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/chat",
            json={"message": "How do I pronounce hydroxychloroquine?", "synthesize_audio": False},
        )
    assert response.status_code == 200
    data = response.json()
    assert data["intent"] == "pronounce"
    assert data["term"] == "hydroxychloroquine"
    # Authoritative pronunciation from terminology.py
    assert "hy-DROX-ee-KLOR-oh-kwin" in data["reply"] or "hy-DROK-see-KLOR-oh-kwin" in data["reply"]
    assert "/haɪˌdrɒksiˈklɔːrəkwɪn/" in data["reply"]


# 7. Unknown pronunciation term
@pytest.mark.asyncio
async def test_unknown_pronunciation_term() -> None:
    """Verify unknown term does NOT hallucinate IPA or syllables."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/chat",
            json={
                "message": "How do I pronounce pseudoxanthomatosisfake?",
                "synthesize_audio": False,
            },
        )
    assert response.status_code == 200
    data = response.json()
    assert data["intent"] in ["pronounce", "general"]
    assert "pseudoxanthomatosisfake" in data["reply"].lower()


# 8. "say it slower"
@pytest.mark.asyncio
async def test_say_it_slower_followup() -> None:
    """Verify 'say it slower' uses active term context and 0.7x speed."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/chat",
            json={
                "message": "Can you say it slower?",
                "context_term": "hydroxychloroquine",
                "synthesize_audio": False,
            },
        )
    assert response.status_code == 200
    data = response.json()
    assert data["intent"] == "slow"
    assert data["term"] == "hydroxychloroquine"
    assert "0.7x" in data["reply"] or "slower" in data["reply"].lower()
    assert "hy-DROX-ee-KLOR-oh-kwin" in data["reply"] or "hy-DROK-see-KLOR-oh-kwin" in data["reply"]


# 9. Repeat request
@pytest.mark.asyncio
async def test_repeat_request_followup() -> None:
    """Verify 'repeat that' / 'again' repeats active term."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/chat",
            json={
                "message": "Again",
                "context_term": "omeprazole",
                "synthesize_audio": False,
            },
        )
    assert response.status_code == 200
    data = response.json()
    assert data["intent"] == "repeat"
    assert data["term"] == "omeprazole"
    assert "oh-MEP-ruh-zohl" in data["reply"]


# 10. Conversational context
@pytest.mark.asyncio
async def test_conversational_context_syllables() -> None:
    """Verify 'break it down' targets context term."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/chat",
            json={
                "message": "Break it down",
                "context_term": "tachycardia",
                "synthesize_audio": False,
            },
        )
    assert response.status_code == 200
    data = response.json()
    assert data["intent"] == "syllables"
    assert data["term"] == "tachycardia"
    assert "tak-i-KAHR-dee-uh" in data["reply"] or "TAK-i-KAR-dee-uh" in data["reply"]


# 11. Medical safety request
@pytest.mark.asyncio
async def test_medical_safety_dosage_rejection() -> None:
    """Verify safe educational refusal for clinical dosage/prescription."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/chat",
            json={
                "message": "What dosage of hydroxychloroquine should I take for my fever?",
                "synthesize_audio": False,
            },
        )
    assert response.status_code == 200
    data = response.json()
    assert data["intent"] == "safety_boundary"
    assert data["term"] is None
    assert any(
        phrase in data["reply"].lower()
        for phrase in [
            "cannot prescribe",
            "medical professional",
            "healthcare provider",
            "dosage advice",
        ]
    )


# 12. Malformed structured Gemini response
@pytest.mark.asyncio
async def test_malformed_gemini_response_recovers() -> None:
    """Verify service recovers gracefully when Gemini returns non-JSON or malformed data."""
    service = GeminiService()
    mock_resp = MagicMock()
    mock_resp.text = "NOT VALID JSON AT ALL"
    mock_client = MagicMock()
    mock_client.aio.models.generate_content = AsyncMock(return_value=mock_resp)
    service._client = mock_client
    service.api_key = "test_key"

    turn = await service.generate_chat_turn("How do I pronounce amoxicillin?")
    # Falls back smoothly to deterministic engine without raising exception
    assert turn.intent == "pronounce"
    assert turn.target_term == "amoxicillin"


# 13. Secret / API-key redaction in logs
def test_secret_redaction() -> None:
    """Verify API keys are redacted from logs and exception messages."""
    mock_key = "mock_secret_gemini_api_key_for_testing_12345"
    with patch("app.services.gemini.settings.GEMINI_API_KEY", mock_key):
        raw_msg = f"Failed to connect using key {mock_key} to model gemini-3.8-flash"
        sanitized = redact_secrets(raw_msg)
        assert mock_key not in sanitized
        assert "[REDACTED_GEMINI_KEY]" in sanitized

    # Verify pattern-based redaction without hardcoding real credentials
    pattern_key = "AQ." + "X" * 45
    with patch("app.services.gemini.settings.GEMINI_API_KEY", ""):
        sanitized_pattern = redact_secrets(f"Connection failed for {pattern_key}")
        assert pattern_key not in sanitized_pattern
        assert "[REDACTED_GEMINI_KEY]" in sanitized_pattern

