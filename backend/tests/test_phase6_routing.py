"""Tests for Phase 6: Pronunciation routing, clinical database, fallback, and latency optimizations.

Covers the 14 mandatory test cases:
1. "How do I pronounce tachycardia?"
2. "How do I pronounce clinical terms?"
3. "How do I pronounce medical words?"
4. "What clinical terms can you help me pronounce?"
5. "How do I pronounce hydroxychloroquine?"
6. "Say it slower."
7. "Repeat that."
8. "How do I pronounce acetaminophen?"
9. "a set of amino phen" (misrecognized STT)
10. "How do I pronounce bronchoscopy?" (unsupported term -> gemini fallback)
11. "How do I pronounce amlodipine?" (unsupported term -> gemini fallback)
12. "Hello"
13. "What can you do?"
14. "Can you teach me medical pronunciation?"
"""

from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.services.rime import RimeSynthesisResult


@pytest.fixture
def mock_rime():
    """Mock Rime synthesis service to avoid external API calls during unit tests."""
    with patch("app.api.chat.rime_service.synthesize") as mock_synth:
        mock_synth.return_value = RimeSynthesisResult(
            audio_bytes=b"dummy_mp3_audio_data",
            audio_format="mp3",
            content_type="audio/mpeg",
            sampling_rate=24000,
            latency_ms=120.0,
            speaker="astra",
            model_id="coda",
            text_length=20,
        )
        yield mock_synth


# 1. "How do I pronounce tachycardia?"
@pytest.mark.asyncio
async def test_case_1_pronounce_tachycardia(mock_rime) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.post("/api/chat", json={"message": "How do I pronounce tachycardia?"})
        assert res.status_code == 200
        data = res.json()
        assert data["intent"] in ["pronounce", "ask_pronunciation"]
        assert data["term"] == "tachycardia"
        assert data["pronunciation_source"] == "verified_database"
        assert "TAK-i-KAR-dee-uh" in data["reply"]
        assert "timing" in data
        assert data["timing"]["total_response_ms"] > 0


# 2. "How do I pronounce clinical terms?"
@pytest.mark.asyncio
async def test_case_2_generic_clinical_terms(mock_rime) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.post("/api/chat", json={"message": "How do I pronounce clinical terms?"})
        assert res.status_code == 200
        data = res.json()
        # Must NOT classify "clinical terms" as a medical term
        assert data["term"] != "clinical terms"
        assert "I detected the term clinical terms" not in data["reply"]
        assert (
            "pronounce specific medical terms" in data["reply"].lower()
            or "tachycardia" in data["reply"].lower()
        )


# 3. "How do I pronounce medical words?"
@pytest.mark.asyncio
async def test_case_3_generic_medical_words(mock_rime) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.post("/api/chat", json={"message": "How do I pronounce medical words?"})
        assert res.status_code == 200
        data = res.json()
        # Must NOT classify "medical words" as a medical term
        assert data["term"] != "medical words"
        assert "I detected the term medical words" not in data["reply"]
        assert (
            "pronounce specific medical terms" in data["reply"].lower()
            or "tachycardia" in data["reply"].lower()
        )


# 4. "What clinical terms can you help me pronounce?"
@pytest.mark.asyncio
async def test_case_4_what_clinical_terms(mock_rime) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.post(
            "/api/chat", json={"message": "What clinical terms can you help me pronounce?"}
        )
        assert res.status_code == 200
        data = res.json()
        assert data["term"] is None
        assert "clinical" in data["reply"].lower() or "pronounce" in data["reply"].lower()


# 5. "How do I pronounce hydroxychloroquine?"
@pytest.mark.asyncio
async def test_case_5_pronounce_hydroxychloroquine(mock_rime) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.post(
            "/api/chat", json={"message": "How do I pronounce hydroxychloroquine?"}
        )
        assert res.status_code == 200
        data = res.json()
        assert data["intent"] in ["pronounce", "ask_pronunciation"]
        assert data["term"] == "hydroxychloroquine"
        assert data["pronunciation_source"] == "verified_database"
        assert "hy-DROK-see-KLOR-oh-kwin" in data["reply"]


# 6. "Say it slower." (Fast-path bypass)
@pytest.mark.asyncio
async def test_case_6_say_it_slower_fast_path(mock_rime) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.post(
            "/api/chat",
            json={"message": "Say it slower.", "context_term": "hydroxychloroquine"},
        )
        assert res.status_code == 200
        data = res.json()
        assert data["intent"] == "slow"
        assert data["term"] == "hydroxychloroquine"
        assert data["pronunciation_source"] == "verified_database"
        assert "0.7x speed" in data["reply"]
        # Fast path should bypass Gemini (gemini_ms = 0.0)
        assert data["timing"]["gemini_ms"] == 0.0


# 7. "Repeat that." (Fast-path bypass)
@pytest.mark.asyncio
async def test_case_7_repeat_that_fast_path(mock_rime) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.post(
            "/api/chat",
            json={"message": "Repeat that.", "context_term": "hydroxychloroquine"},
        )
        assert res.status_code == 200
        data = res.json()
        assert data["intent"] == "repeat"
        assert data["term"] == "hydroxychloroquine"
        assert data["pronunciation_source"] == "verified_database"
        assert "Repeating" in data["reply"]
        # Fast path should bypass Gemini
        assert data["timing"]["gemini_ms"] == 0.0


# 8. "How do I pronounce acetaminophen?"
@pytest.mark.asyncio
async def test_case_8_pronounce_acetaminophen(mock_rime) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.post("/api/chat", json={"message": "How do I pronounce acetaminophen?"})
        assert res.status_code == 200
        data = res.json()
        assert data["term"] == "acetaminophen"
        assert data["pronunciation_source"] == "verified_database"
        assert "uh-SEE-tuh-MIN-oh-fen" in data["reply"]


# 9. "a set of amino phen" (STT misrecognition recovery)
@pytest.mark.asyncio
async def test_case_9_stt_misrecognition_recovery(mock_rime) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.post("/api/chat", json={"message": "a set of amino phen"})
        assert res.status_code == 200
        data = res.json()
        assert data["term"] == "acetaminophen"
        assert data["pronunciation_source"] == "verified_database"
        assert "uh-SEE-tuh-MIN-oh-fen" in data["reply"]


# 10. "How do I pronounce bronchoscopy?" (Gemini fallback engine)
@pytest.mark.asyncio
async def test_case_10_gemini_fallback_bronchoscopy(mock_rime) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.post("/api/chat", json={"message": "How do I pronounce bronchoscopy?"})
        assert res.status_code == 200
        data = res.json()
        assert data["intent"] in ["pronounce", "ask_pronunciation"]
        assert data["term"] == "bronchoscopy"
        # Must NOT be marked verified database
        assert data["pronunciation_source"] == "gemini_fallback"
        # Must pronounce it, NOT reject it
        assert "not yet in my verified clinical pronunciation database" not in data["reply"]
        assert "Bronchoscopy" in data["reply"] or "bronchoscopy" in data["reply"]


# 11. "How do I pronounce amlodipine?" (Gemini fallback engine)
@pytest.mark.asyncio
async def test_case_11_gemini_fallback_amlodipine(mock_rime) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.post("/api/chat", json={"message": "How do I pronounce amlodipine?"})
        assert res.status_code == 200
        data = res.json()
        assert data["term"] == "amlodipine"
        assert data["pronunciation_source"] == "gemini_fallback"
        assert "not yet in my verified clinical pronunciation database" not in data["reply"]


# 12. "Hello" (In-memory static cache)
@pytest.mark.asyncio
async def test_case_12_static_cache_hello(mock_rime) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.post("/api/chat", json={"message": "Hello"})
        assert res.status_code == 200
        data = res.json()
        assert data["intent"] == "general"
        assert "MedSpeak" in data["reply"]
        # Static cache hit should bypass network call to Gemini (< 1ms routing)
        assert data["timing"]["gemini_ms"] < 10.0


# 13. "What can you do?" (In-memory static cache)
@pytest.mark.asyncio
async def test_case_13_static_cache_what_can_you_do(mock_rime) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.post("/api/chat", json={"message": "What can you do?"})
        assert res.status_code == 200
        data = res.json()
        assert data["intent"] == "general"
        assert "MedSpeak" in data["reply"]
        assert data["timing"]["gemini_ms"] < 10.0


# 14. "Can you teach me medical pronunciation?"
@pytest.mark.asyncio
async def test_case_14_can_you_teach_me(mock_rime) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.post(
            "/api/chat", json={"message": "Can you teach me medical pronunciation?"}
        )
        assert res.status_code == 200
        data = res.json()
        assert data["term"] is None
        assert "pronounce" in data["reply"].lower() or "tachycardia" in data["reply"].lower()
