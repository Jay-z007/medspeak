"""Automated tests for health check endpoint."""

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.config import settings
from app.main import app


@pytest.mark.asyncio
async def test_health_endpoint_returns_ok() -> None:
    """Verify that GET /health returns 200 OK and expected structure."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["app"] == settings.APP_NAME
    assert data["version"] == settings.APP_VERSION
    assert data["primary_tts_provider"] == "rime"
    assert data["phase_1_status"] == "ready"
    assert "environment" in data
    assert "fallback_tts_enabled" in data


@pytest.mark.asyncio
async def test_health_endpoint_rime_is_default_provider() -> None:
    """Verify Rime is strictly designated as primary TTS provider in health status."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")

    assert response.status_code == 200
    data = response.json()
    assert data["primary_tts_provider"] == "rime"
