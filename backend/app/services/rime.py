"""Rime Text-to-Speech (TTS) integration service for MedSpeak.

This service connects directly to the official Rime API (https://users.rime.ai/v1/rime-tts),
enforces server-side credentials, validates configuration, performs audio synthesis,
and provides preflight diagnostic validation.
"""

import logging
import time
from collections.abc import AsyncGenerator
from dataclasses import dataclass
from typing import Any

import httpx
from pydantic import BaseModel

from app.core.config import Settings
from app.core.config import settings as default_settings

logger = logging.getLogger(__name__)

# Official recognized Rime models and audio formats
SUPPORTED_MODELS = {"coda", "mistv3", "mistv2", "mist", "arcana"}
SUPPORTED_FORMATS = {"mp3", "wav", "pcm", "mulaw"}
DEFAULT_TIMEOUT_SECONDS = 15.0


class RimeError(Exception):
    """Base exception for all Rime TTS errors."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class RimeConfigurationError(RimeError):
    """Raised when Rime configuration is missing or invalid."""

    pass


class RimeAuthenticationError(RimeError):
    """Raised when Rime rejects credentials (HTTP 401/403)."""

    pass


class RimeRateLimitError(RimeError):
    """Raised when Rime rate limit is exceeded (HTTP 429)."""

    pass


class RimeTimeoutError(RimeError):
    """Raised when request to Rime API times out."""

    pass


class RimeServerError(RimeError):
    """Raised when Rime returns a 5xx server error."""

    pass


class RimeMalformedAudioError(RimeError):
    """Raised when Rime returns empty or unrecognized audio bytes."""

    pass


class RimeProviderError(RimeError):
    """Raised for unexpected 4xx provider errors."""

    pass


def redact_secret(secret: str) -> str:
    """Mask sensitive credentials so they are never leaked in logs or error messages."""
    if not secret:
        return "<EMPTY>"
    if len(secret) <= 8:
        return "***REDACTED***"
    return f"{secret[:4]}...***REDACTED***...{secret[-4:]}"


def sanitize_headers(headers: dict[str, str]) -> dict[str, str]:
    """Return a copy of request headers with sensitive tokens redacted."""
    sanitized: dict[str, str] = {}
    for key, val in headers.items():
        if key.lower() == "authorization":
            sanitized[key] = "Bearer ***REDACTED***"
        else:
            sanitized[key] = val
    return sanitized


def is_valid_audio_bytes(audio_bytes: bytes, audio_format: str) -> bool:
    """Validate whether the returned byte payload contains valid audio headers."""
    if not audio_bytes or len(audio_bytes) < 8:
        return False

    fmt = audio_format.lower()
    if fmt == "mp3":
        # ID3 tag header check ('ID3') or MPEG syncword (11 bits set: 0xFF followed by 0xE0 mask)
        if audio_bytes.startswith(b"ID3"):
            return True
        if len(audio_bytes) >= 2 and audio_bytes[0] == 0xFF and (audio_bytes[1] & 0xE0) == 0xE0:
            return True
        return False
    elif fmt == "wav":
        # RIFF header with WAVE format marker
        return audio_bytes.startswith(b"RIFF") and b"WAVE" in audio_bytes[:16]
    elif fmt in {"pcm", "mulaw"}:
        # Raw formats don't have magic bytes; ensure non-empty buffer
        return len(audio_bytes) > 0

    return True


@dataclass
class RimeSynthesisResult:
    """Container for successful synthesis audio output and latency telemetry."""

    audio_bytes: bytes
    content_type: str
    audio_format: str
    sampling_rate: int
    latency_ms: float
    model_id: str
    speaker: str
    text_length: int


class RimePreflightCheckResult(BaseModel):
    """Status of an individual preflight check step."""

    name: str
    passed: bool
    detail: str


class RimePreflightReport(BaseModel):
    """Comprehensive preflight validation report."""

    status: str  # "ok" or "failed"
    model_id: str
    speaker: str
    language: str
    audio_format: str
    sampling_rate: int
    endpoint: str
    latency_ms: float
    audio_bytes: int
    checks: list[RimePreflightCheckResult]
    error: str | None = None


class RimeService:
    """Production service for interacting with Rime Text-to-Speech API."""

    def __init__(
        self,
        settings: Settings | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.settings: Settings = settings or default_settings
        self._external_client: httpx.AsyncClient | None = client

    @property
    def api_key(self) -> str:
        return self.settings.RIME_API_KEY.strip()

    @property
    def api_url(self) -> str:
        return self.settings.RIME_API_URL.strip()

    @property
    def model_id(self) -> str:
        return self.settings.RIME_MODEL_ID.strip() or "coda"

    @property
    def speaker(self) -> str:
        return self.settings.RIME_SPEAKER.strip() or "astra"

    @property
    def language(self) -> str:
        return self.settings.RIME_LANGUAGE.strip() or "en"

    @property
    def audio_format(self) -> str:
        return self.settings.RIME_AUDIO_FORMAT.strip() or "mp3"

    @property
    def sampling_rate(self) -> int:
        return self.settings.RIME_SAMPLING_RATE or 24000

    def get_mime_type(self) -> str:
        """Return the appropriate HTTP MIME type for the configured audio format."""
        fmt = self.audio_format.lower()
        if fmt == "mp3":
            return "audio/mpeg"
        elif fmt == "wav":
            return "audio/wav"
        elif fmt == "pcm":
            return "audio/pcm"
        elif fmt == "mulaw":
            return "audio/basic"
        return f"audio/{fmt}"

    def validate_configuration(self) -> list[RimePreflightCheckResult]:
        """Validate that all required Rime configuration fields are present and valid."""
        checks: list[RimePreflightCheckResult] = []

        # 1. API Key Check
        if not self.api_key:
            checks.append(
                RimePreflightCheckResult(
                    name="api_key_exists",
                    passed=False,
                    detail="RIME_API_KEY is not set or empty in environment.",
                )
            )
        else:
            checks.append(
                RimePreflightCheckResult(
                    name="api_key_exists",
                    passed=True,
                    detail=f"API key configured ({redact_secret(self.api_key)}).",
                )
            )

        # 2. Endpoint URL Check
        if not self.api_url or not (
            self.api_url.startswith("https://") or self.api_url.startswith("http://")
        ):
            checks.append(
                RimePreflightCheckResult(
                    name="endpoint_valid",
                    passed=False,
                    detail=f"Invalid RIME_API_URL: '{self.api_url}'. Must begin with http:// or https://",
                )
            )
        else:
            checks.append(
                RimePreflightCheckResult(
                    name="endpoint_valid",
                    passed=True,
                    detail=f"Valid endpoint configured: {self.api_url}",
                )
            )

        # 3. Model ID Check
        if not self.model_id or self.model_id.lower() not in SUPPORTED_MODELS:
            supported_str = ", ".join(sorted(SUPPORTED_MODELS))
            checks.append(
                RimePreflightCheckResult(
                    name="model_valid",
                    passed=False,
                    detail=f"Unsupported modelId '{self.model_id}'. Supported: {supported_str}",
                )
            )
        else:
            checks.append(
                RimePreflightCheckResult(
                    name="model_valid",
                    passed=True,
                    detail=f"Valid model ID: {self.model_id}",
                )
            )

        # 4. Speaker Check
        if not self.speaker:
            checks.append(
                RimePreflightCheckResult(
                    name="speaker_valid",
                    passed=False,
                    detail="RIME_SPEAKER is empty.",
                )
            )
        else:
            checks.append(
                RimePreflightCheckResult(
                    name="speaker_valid",
                    passed=True,
                    detail=f"Valid speaker identifier: {self.speaker}",
                )
            )

        # 5. Audio Format Check
        if not self.audio_format or self.audio_format.lower() not in SUPPORTED_FORMATS:
            supported_fmt = ", ".join(sorted(SUPPORTED_FORMATS))
            checks.append(
                RimePreflightCheckResult(
                    name="audio_format_valid",
                    passed=False,
                    detail=f"Unsupported format '{self.audio_format}'. Supported: {supported_fmt}",
                )
            )
        else:
            checks.append(
                RimePreflightCheckResult(
                    name="audio_format_valid",
                    passed=True,
                    detail=f"Valid audio format: {self.audio_format}",
                )
            )

        # 6. Sampling Rate Check
        if self.sampling_rate <= 0 or self.sampling_rate > 96000:
            checks.append(
                RimePreflightCheckResult(
                    name="sampling_rate_valid",
                    passed=False,
                    detail=f"Invalid sampling rate: {self.sampling_rate}. Must be 8000-96000 Hz.",
                )
            )
        else:
            checks.append(
                RimePreflightCheckResult(
                    name="sampling_rate_valid",
                    passed=True,
                    detail=f"Valid sampling rate: {self.sampling_rate} Hz",
                )
            )

        return checks

    async def synthesize(
        self,
        text: str,
        speed: float = 1.0,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
        client: httpx.AsyncClient | None = None,
    ) -> RimeSynthesisResult:
        """Synthesize text into speech audio via Rime API.

        Args:
            text: Text to speak (1 to 1000 characters).
            speed: Speed scaling factor (0.4 to 2.5, default 1.0).
            timeout: Network timeout in seconds.
            client: Optional httpx.AsyncClient override.

        Returns:
            RimeSynthesisResult containing audio bytes and timing information.
        """
        if not text or not text.strip():
            raise RimeConfigurationError("Text to synthesize cannot be empty.")

        clean_text = text.strip()
        if len(clean_text) > 1000:
            raise RimeConfigurationError("Text length exceeds Rime 1000 character limit.")

        # Configuration sanity checks
        if not self.api_key:
            raise RimeConfigurationError(
                "Rime API key is missing. Set RIME_API_KEY in environment or backend/.env."
            )

        mime_type = self.get_mime_type()
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": mime_type,
        }

        payload: dict[str, Any] = {
            "speaker": self.speaker,
            "text": clean_text,
            "modelId": self.model_id,
            "lang": self.language,
            "audioFormat": self.audio_format,
            "samplingRate": self.sampling_rate,
        }

        # Speed scaling factor (timeScaleFactor in official Rime API)
        if speed != 1.0:
            clamped_speed = max(0.4, min(2.5, round(speed, 2)))
            payload["timeScaleFactor"] = clamped_speed

        start_time = time.perf_counter()
        active_client = client or self._external_client

        try:
            if active_client is not None:
                response = await active_client.post(
                    self.api_url,
                    headers=headers,
                    json=payload,
                    timeout=timeout,
                )
            else:
                async with httpx.AsyncClient() as new_client:
                    response = await new_client.post(
                        self.api_url,
                        headers=headers,
                        json=payload,
                        timeout=timeout,
                    )

            latency_ms = round((time.perf_counter() - start_time) * 1000, 2)

        except httpx.TimeoutException as exc:
            duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
            logger.error(
                "Rime synthesis timed out after %.2fms at %s",
                duration_ms,
                self.api_url,
            )
            raise RimeTimeoutError(
                f"Rime API request timed out after {timeout} seconds.",
                status_code=504,
            ) from exc

        except httpx.RequestError as exc:
            duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
            logger.error(
                "Rime network request error after %.2fms: %s",
                duration_ms,
                str(exc),
            )
            raise RimeProviderError(
                f"Network error communicating with Rime API: {str(exc)}",
                status_code=502,
            ) from exc

        # Handle HTTP status codes
        status_code = response.status_code

        if status_code in (401, 403):
            logger.error("Rime authentication failed (HTTP %d)", status_code)
            raise RimeAuthenticationError(
                f"Rime authentication failed (HTTP {status_code}). Verify RIME_API_KEY.",
                status_code=status_code,
            )

        if status_code == 429:
            logger.warning("Rime rate limit exceeded (HTTP 429)")
            raise RimeRateLimitError(
                "Rime API rate limit exceeded. Please retry shortly.",
                status_code=429,
            )

        if status_code >= 500:
            logger.error("Rime server error (HTTP %d): %s", status_code, response.text[:200])
            raise RimeServerError(
                f"Rime upstream server error (HTTP {status_code}).",
                status_code=status_code,
            )

        if status_code != 200:
            error_msg = response.text[:250]
            logger.error("Rime provider error (HTTP %d): %s", status_code, error_msg)
            raise RimeProviderError(
                f"Rime synthesis failed with HTTP {status_code}: {error_msg}",
                status_code=status_code,
            )

        audio_bytes = response.content

        # Validate returned audio payload
        if not audio_bytes or len(audio_bytes) == 0:
            raise RimeMalformedAudioError(
                "Rime API returned empty audio content (0 bytes).",
                status_code=502,
            )

        if not is_valid_audio_bytes(audio_bytes, self.audio_format):
            msg = f"Rime API returned malformed audio for format '{self.audio_format}'."
            raise RimeMalformedAudioError(msg, status_code=502)

        logger.info(
            "Rime synthesis succeeded: %d bytes, %.2fms, model=%s, speaker=%s",
            len(audio_bytes),
            latency_ms,
            self.model_id,
            self.speaker,
        )

        return RimeSynthesisResult(
            audio_bytes=audio_bytes,
            content_type=mime_type,
            audio_format=self.audio_format,
            sampling_rate=self.sampling_rate,
            latency_ms=latency_ms,
            model_id=self.model_id,
            speaker=self.speaker,
            text_length=len(clean_text),
        )

    async def stream(
        self,
        text: str,
        chunk_size: int = 4096,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
    ) -> AsyncGenerator[bytes, None]:
        """Stream audio chunks for synthesis output."""
        result = await self.synthesize(text=text, timeout=timeout)
        audio = result.audio_bytes
        for offset in range(0, len(audio), chunk_size):
            yield audio[offset : offset + chunk_size]

    async def preflight(self) -> RimePreflightReport:
        """Execute full end-to-end preflight verification suite."""
        checks = self.validate_configuration()
        failed_checks = [c for c in checks if not c.passed]

        if failed_checks:
            return RimePreflightReport(
                status="failed",
                model_id=self.model_id,
                speaker=self.speaker,
                language=self.language,
                audio_format=self.audio_format,
                sampling_rate=self.sampling_rate,
                endpoint=self.api_url,
                latency_ms=0.0,
                audio_bytes=0,
                checks=checks,
                error=f"Preflight configuration validation failed: {failed_checks[0].detail}",
            )

        # Real synthesis test
        test_phrase = "MedSpeak Rime synthesis preflight test."
        try:
            result = await self.synthesize(text=test_phrase, timeout=12.0)
            checks.append(
                RimePreflightCheckResult(
                    name="synthesis_success",
                    passed=True,
                    detail=f"Successfully synthesized audio in {result.latency_ms}ms.",
                )
            )
            checks.append(
                RimePreflightCheckResult(
                    name="audio_valid",
                    passed=True,
                    detail=f"Valid {result.audio_format} audio ({len(result.audio_bytes)} bytes).",
                )
            )

            return RimePreflightReport(
                status="ok",
                model_id=self.model_id,
                speaker=self.speaker,
                language=self.language,
                audio_format=self.audio_format,
                sampling_rate=self.sampling_rate,
                endpoint=self.api_url,
                latency_ms=result.latency_ms,
                audio_bytes=len(result.audio_bytes),
                checks=checks,
                error=None,
            )

        except RimeError as exc:
            checks.append(
                RimePreflightCheckResult(
                    name="synthesis_success",
                    passed=False,
                    detail=f"Synthesis failed: {exc.message}",
                )
            )
            return RimePreflightReport(
                status="failed",
                model_id=self.model_id,
                speaker=self.speaker,
                language=self.language,
                audio_format=self.audio_format,
                sampling_rate=self.sampling_rate,
                endpoint=self.api_url,
                latency_ms=0.0,
                audio_bytes=0,
                checks=checks,
                error=exc.message,
            )


# Default singleton instance
rime_service = RimeService()
