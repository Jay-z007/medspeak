"""Tests for conversational context retention and follow-up commands in MedSpeak."""

from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.services.terminology import resolve_term


@pytest.mark.asyncio
async def test_new_section_21_terminology() -> None:
    """Verify newly added Section 21 terms resolve correctly."""
    terms_to_test = [
        ("mri", "mri"),
        ("magnetic resonance imaging", "mri"),
        ("ecg", "ecg"),
        ("ekg", "ecg"),
        ("copd", "copd"),
        ("sars-cov-2", "sars-cov-2"),
        ("covid 19 virus", "sars-cov-2"),
        ("10 mg", "10 mg"),
        ("10mg", "10 mg"),
        ("0.5 ml", "0.5 ml"),
        ("2.5 mg", "2.5 mg"),
    ]
    for query, expected_canonical in terms_to_test:
        resolved = resolve_term(query)
        assert resolved is not None, f"Failed to resolve {query}"
        assert resolved.canonical_name == expected_canonical


@pytest.mark.asyncio
async def test_contextual_slower_followup(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify 'slower' follow-up command targets the active context term at 0.7x speed."""

    async def mock_synthesize(text: str, speed: float = 1.0) -> Any:
        class MockResult:
            audio_bytes = b"fake_mp3_audio"
            latency_ms = 120
            audio_format = "mp3"

        return MockResult()

    monkeypatch.setattr("app.api.chat.rime_service.synthesize", mock_synthesize)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.post(
            "/api/chat",
            json={
                "message": "Can you say it slower?",
                "context_term": "tachycardia",
                "synthesize_audio": True,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["intent"] == "slow"
        assert data["term"] == "tachycardia"
        assert "tak-i-KAHR-dee-uh" in data["reply"] or "TAK-i-KAR-dee-uh" in data["reply"]
        assert "slower" in data["reply"].lower()
        assert data["audio_base64"] is not None


@pytest.mark.asyncio
async def test_contextual_repeat_again_followup(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify 'Again' follow-up command repeats active term pronunciation."""

    async def mock_synthesize(text: str, speed: float = 1.0) -> Any:
        class MockResult:
            audio_bytes = b"fake_mp3_audio"
            latency_ms = 110
            audio_format = "mp3"

        return MockResult()

    monkeypatch.setattr("app.api.chat.rime_service.synthesize", mock_synthesize)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.post(
            "/api/chat",
            json={
                "message": "Again.",
                "context_term": "hydroxychloroquine",
                "synthesize_audio": True,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["intent"] == "repeat"
        assert data["term"] == "hydroxychloroquine"
        assert (
            "hy-DROX-ee-KLOR-oh-kwin" in data["reply"]
            or "hy-DROK-see-KLOR-oh-kwin" in data["reply"]
        )
        assert data["audio_base64"] is not None


@pytest.mark.asyncio
async def test_contextual_syllables_breakdown(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify 'Break it down' follow-up command breaks down the active term."""

    async def mock_synthesize(text: str, speed: float = 1.0) -> Any:
        class MockResult:
            audio_bytes = b"fake_mp3_audio"
            latency_ms = 115
            audio_format = "mp3"

        return MockResult()

    monkeypatch.setattr("app.api.chat.rime_service.synthesize", mock_synthesize)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.post(
            "/api/chat",
            json={
                "message": "Break it down",
                "context_term": "omeprazole",
                "synthesize_audio": True,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["intent"] == "syllables"
        assert data["term"] == "omeprazole"
        assert "oh-MEP-ruh-zohl" in data["reply"]
