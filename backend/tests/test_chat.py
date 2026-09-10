"""Automated tests for the MedSpeak Chat API and clinical safety boundaries."""

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.mark.asyncio
async def test_chat_pronounce_hydroxychloroquine() -> None:
    """Verify pronunciation breakdown for hydroxychloroquine (Suggested Prompt 1)."""
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
    assert data["provider"] == "rime"
    assert "hy-DROX-ee-KLOR-oh-kwin" in data["reply"] or "hy-DROK-see-KLOR-oh-kwin" in data["reply"]
    assert "/haɪˌdrɒksiˈklɔːrəkwɪn/" in data["reply"]


@pytest.mark.asyncio
async def test_chat_break_down_tachycardia() -> None:
    """Verify syllable breakdown for tachycardia (Suggested Prompt 2)."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/chat",
            json={"message": "Break down tachycardia", "synthesize_audio": False},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["intent"] in ["pronounce", "syllables"]
    assert data["term"] == "tachycardia"

    assert data["provider"] == "rime"
    assert "tak-i-KAHR-dee-uh" in data["reply"] or "TAK-i-KAR-dee-uh" in data["reply"]


@pytest.mark.asyncio
async def test_chat_how_do_i_say_omeprazole() -> None:
    """Verify pronunciation for omeprazole (Suggested Prompt 3)."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/chat",
            json={"message": "How do I say omeprazole?", "synthesize_audio": False},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["intent"] == "pronounce"
    assert data["term"] == "omeprazole"
    assert data["provider"] == "rime"
    assert "oh-MEP-ruh-zohl" in data["reply"]


@pytest.mark.asyncio
async def test_chat_safety_boundary_dosage() -> None:
    """Verify that dosage inquiries trigger medical safety boundaries."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/chat",
            json={"message": "What dose of amoxicillin should I take?", "synthesize_audio": False},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["intent"] == "safety_boundary"
    assert data["term"] is None
    expected_msg = (
        "I can help explain or pronounce medical terminology, but I can't provide "
        "diagnosis, treatment, or dosage advice."
    )
    assert expected_msg in data["reply"]


@pytest.mark.asyncio
async def test_chat_safety_boundary_diagnosis() -> None:
    """Verify that diagnosis inquiries trigger medical safety boundaries."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/chat",
            json={
                "message": "Can you diagnose me? My heart is beating fast",
                "synthesize_audio": False,
            },
        )

    assert response.status_code == 200
    data = response.json()
    assert data["intent"] == "safety_boundary"
    assert "diagnosis, treatment, or dosage advice" in data["reply"]


@pytest.mark.asyncio
async def test_chat_safety_boundary_treatment() -> None:
    """Verify that treatment inquiries trigger medical safety boundaries."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/chat",
            json={"message": "How to cure bacterial pneumonia?", "synthesize_audio": False},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["intent"] == "safety_boundary"


@pytest.mark.asyncio
async def test_chat_definition_query() -> None:
    """Verify definition lookup for clinical terms."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/chat",
            json={"message": "What is acetaminophen?", "synthesize_audio": False},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["intent"] == "definition"
    assert data["term"] == "acetaminophen"
    assert "Analgesic / Antipyretic" in data["reply"]


@pytest.mark.asyncio
async def test_chat_general_greeting() -> None:
    """Verify general greeting response."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/chat",
            json={"message": "Hello!", "synthesize_audio": False},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["intent"] == "general"
    assert "MedSpeak" in data["reply"]


@pytest.mark.asyncio
async def test_chat_unknown_term_fallback() -> None:
    """Verify graceful handling of clinical terms not yet in verified dictionary."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/chat",
            json={"message": "How do I pronounce cefepime?", "synthesize_audio": False},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["intent"] in ["pronounce", "general"]
    assert "cefepime" in data["reply"].lower()
