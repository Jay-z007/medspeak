import json
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Base directory paths
# backend/app/core/config.py -> parents[2] is backend directory, parents[3] is project root
BACKEND_DIR = Path(__file__).resolve().parents[2]
PROJECT_ROOT = Path(__file__).resolve().parents[3]

# Candidate .env files in discovery order:
# 1. backend/.env (canonical backend env file)
# 2. project root .env (if root .env exists)
# 3. current working directory .env / backend/.env
_CANDIDATE_ENV_FILES: list[Path] = [
    BACKEND_DIR / ".env",
    PROJECT_ROOT / ".env",
    Path(".env").resolve(),
    Path("backend/.env").resolve(),
]

# Deduplicate discovered .env files that exist on disk
_seen_paths: set[Path] = set()
ENV_FILES: list[Path] = []
for _candidate in _CANDIDATE_ENV_FILES:
    if _candidate.is_file():
        _resolved = _candidate.resolve()
        if _resolved not in _seen_paths:
            _seen_paths.add(_resolved)
            ENV_FILES.append(_resolved)

# Eagerly load environment variables into os.environ for non-pydantic consumers
for _env_path in ENV_FILES:
    load_dotenv(dotenv_path=_env_path, override=False)


class Settings(BaseSettings):
    """Application settings loaded from environment variables and .env file."""

    model_config = SettingsConfigDict(
        env_file=tuple(ENV_FILES) if ENV_FILES else ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Application Configuration
    APP_NAME: str = "MedSpeak API"
    APP_VERSION: str = "0.1.0"
    APP_ENV: str = Field(
        default="development",
        description="Environment: development, test, production",
    )
    DEBUG: bool = Field(default=True, description="Debug mode")
    HOST: str = Field(default="0.0.0.0", description="Bind host")
    PORT: int = Field(default=8000, description="Bind port")
    CORS_ORIGINS: list[str] | str = Field(
        default=["http://localhost:3000", "http://127.0.0.1:3000"],
        description="Allowed CORS origins",
    )

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Any) -> list[str]:
        """Allow CORS_ORIGINS to be supplied as a comma-separated string or JSON array."""
        if isinstance(v, str):
            v_stripped = v.strip()
            if v_stripped.startswith("[") and v_stripped.endswith("]"):
                try:
                    parsed = json.loads(v_stripped)
                    if isinstance(parsed, list):
                        return [str(item).strip() for item in parsed if str(item).strip()]
                except Exception:
                    pass
            return [item.strip() for item in v_stripped.split(",") if item.strip()]
        if isinstance(v, list):
            return [str(item).strip() for item in v if str(item).strip()]
        return ["http://localhost:3000", "http://127.0.0.1:3000"]

    # Rime TTS Configuration (Server-Side Only - NEVER expose to frontend)
    RIME_API_KEY: str = Field(default="", description="Rime API secret key")
    RIME_API_URL: str = Field(
        default="https://users.rime.ai/v1/rime-tts",
        description="Rime synthesis endpoint",
    )
    RIME_MODEL_ID: str = Field(default="coda", description="Rime model ID")
    RIME_SPEAKER: str = Field(default="astra", description="Rime speaker identifier")
    RIME_LANGUAGE: str = Field(default="en", description="Rime language code")
    RIME_AUDIO_FORMAT: str = Field(default="mp3", description="Rime audio format (mp3, wav, etc.)")
    RIME_SAMPLING_RATE: int = Field(default=24000, description="Sampling rate in Hz")

    # Fallback TTS Configuration (Optional)
    FALLBACK_TTS_ENABLED: bool = Field(default=False, description="Whether fallback TTS is enabled")
    FALLBACK_TTS_PROVIDER: str = Field(default="edge_tts", description="Fallback TTS provider")

    # Speech-to-Text Configuration
    STT_PROVIDER: str = Field(default="faster_whisper", description="STT provider")
    STT_MODEL_SIZE: str = Field(default="tiny.en", description="STT model size")
    STT_DEVICE: str = Field(default="cpu", description="STT compute device")
    STT_COMPUTE_TYPE: str = Field(default="int8", description="STT quantization type")

    # Gemini API Configuration (Server-Side Only - NEVER expose to frontend)
    GEMINI_API_KEY: str = Field(default="", description="Gemini API secret key")
    GEMINI_MODEL: str = Field(
        default="gemini-3.8-flash",
        description="Gemini model ID (e.g. gemini-3.8-flash, gemini-2.5-flash)",
    )
    GEMINI_TIMEOUT_SECONDS: float = Field(
        default=10.0,
        description="Timeout in seconds for Gemini API generation requests",
    )

    # Storage & Database
    DATABASE_URL: str = Field(
        default="sqlite:///./data/medspeak.db",
        description="Database connection URL",
    )


settings = Settings()
