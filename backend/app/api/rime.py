"""API endpoints for Rime TTS integration and preflight validation."""

import logging

from fastapi import APIRouter, HTTPException, Response, status
from pydantic import BaseModel, Field

from app.services.rime import (
    RimeError,
    RimePreflightReport,
    rime_service,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/rime", tags=["Rime TTS"])


class RimeTestRequest(BaseModel):
    """Payload for testing Rime speech synthesis."""

    text: str = Field(default="Hello from MedSpeak.", min_length=1, max_length=1000)
    speed: float | None = Field(default=1.0, ge=0.4, le=2.5)


@router.post("/preflight", response_model=RimePreflightReport)
async def rime_preflight() -> RimePreflightReport:
    """Run full Rime API preflight validation checks.

    Verifies API credentials, endpoint connectivity, model & speaker validity,
    audio format correctness, and executes a live synthesis test.
    """
    logger.info("Executing Rime preflight validation suite...")
    report = await rime_service.preflight()
    return report


@router.post("/test")
async def rime_test_synthesis(payload: RimeTestRequest) -> Response:
    """Perform real Rime TTS synthesis and return raw playable audio.

    Returns the synthesized audio file stream with the appropriate MIME type
    (e.g., audio/mpeg for MP3).
    """
    try:
        result = await rime_service.synthesize(
            text=payload.text,
            speed=payload.speed or 1.0,
        )

        return Response(
            content=result.audio_bytes,
            media_type=result.content_type,
            headers={
                "Content-Disposition": f'inline; filename="medspeak_test.{result.audio_format}"',
                "X-Rime-Latency-Ms": str(result.latency_ms),
                "X-Rime-Model": result.model_id,
                "X-Rime-Speaker": result.speaker,
                "X-Rime-Audio-Format": result.audio_format,
            },
        )

    except RimeError as exc:
        status_code = exc.status_code or status.HTTP_500_INTERNAL_SERVER_ERROR
        logger.error("Rime test synthesis failed: %s (status %d)", exc.message, status_code)
        raise HTTPException(
            status_code=status_code,
            detail=exc.message,
        ) from exc
