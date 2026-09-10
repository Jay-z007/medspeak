"""Health check endpoints for MedSpeak API."""

from typing import Any

from fastapi import APIRouter

from app.core.config import settings

router = APIRouter(tags=["Health"])


@router.get("/health", response_model=dict[str, Any])
async def health_check() -> dict[str, Any]:
    """Basic health check endpoint reporting service status and configuration flags."""
    return {
        "status": "ok",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "environment": settings.APP_ENV,
        "primary_tts_provider": "rime",
        "fallback_tts_enabled": settings.FALLBACK_TTS_ENABLED,
        "conversational_brain": "gemini",
        "gemini_model": settings.GEMINI_MODEL,
        "gemini_configured": bool(settings.GEMINI_API_KEY),
        "phase_1_status": "ready",
    }
