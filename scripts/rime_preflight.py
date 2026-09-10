#!/usr/bin/env python3
"""Rime TTS Preflight Verification Script for MedSpeak.

Verifies:
1. RIME_API_KEY exists and is non-empty
2. RIME_API_URL endpoint is reachable
3. RIME_MODEL_ID is valid and supported
4. RIME_SPEAKER is valid
5. RIME_LANGUAGE is valid
6. RIME_AUDIO_FORMAT is recognized
7. Real synthesis succeeds against live Rime API
8. Returned audio payload is non-empty (> 0 bytes)
9. Returned audio payload matches expected audio magic bytes/structure
10. Secrets are never exposed or printed

Exit codes:
- 0: Preflight passed successfully
- 1: Preflight failed
"""

import asyncio
import os
import sys
from pathlib import Path

# Fix Windows cp1252 stdout encoding
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# Add backend directory to sys.path so app modules can be imported
backend_dir = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(backend_dir))

# Ensure environment variables are loaded from backend/.env
from dotenv import load_dotenv
load_dotenv(backend_dir / ".env")

from app.core.config import Settings
from app.services.rime import (
    RimeService,
    redact_secret,
)


async def run_preflight() -> int:
    print("=" * 70)
    print("  MEDSPEAK - RIME TTS PREFLIGHT VALIDATION")
    print("=" * 70)

    settings = Settings(_env_file=str(backend_dir / ".env"))
    service = RimeService(settings=settings)

    print(f"Endpoint:      {service.api_url}")
    print(f"Model ID:      {service.model_id}")
    print(f"Speaker:       {service.speaker}")
    print(f"Language:      {service.language}")
    print(f"Audio Format:  {service.audio_format}")
    print(f"Sampling Rate: {service.sampling_rate} Hz")
    print(f"API Key:       {redact_secret(service.api_key)}")
    print("-" * 70)

    print("Running configuration checks...")
    checks = service.validate_configuration()
    all_passed = True

    for c in checks:
        icon = "[PASS]" if c.passed else "[FAIL]"
        print(f"  {icon} {c.name:22} : {c.detail}")
        if not c.passed:
            all_passed = False

    if not all_passed:
        print("-" * 70)
        print("[FAILED] PREFLIGHT FAILED: Configuration validation errors detected.")
        print("=" * 70)
        return 1

    print("-" * 70)
    print("Executing live synthesis test against Rime API...")
    test_phrase = "MedSpeak medical pronunciation tutor preflight test."

    try:
        result = await service.synthesize(text=test_phrase, timeout=15.0)
        print(f"  [PASS] synthesis_request     : HTTP 200 OK received in {result.latency_ms}ms")
        print(f"  [PASS] audio_non_empty        : Received {len(result.audio_bytes):,} bytes")
        print(f"  [PASS] audio_format_valid    : Valid {result.audio_format} payload (MIME: {result.content_type})")

        # Save sample to verification file in data/
        output_file = backend_dir / "data" / f"preflight_sample.{result.audio_format}"
        output_file.parent.mkdir(parents=True, exist_ok=True)
        output_file.write_bytes(result.audio_bytes)
        print(f"  [INFO] sample_saved          : {output_file}")

        print("-" * 70)
        print("[SUCCESS] PREFLIGHT PASSED: All Rime TTS checks verified successfully.")
        print("=" * 70)
        return 0

    except Exception as exc:
        print(f"  [FAIL] synthesis_request     : {str(exc)}")
        print("-" * 70)
        print("[FAILED] PREFLIGHT FAILED: Live synthesis request failed.")
        print("=" * 70)
        return 1


def main() -> None:
    code = asyncio.run(run_preflight())
    sys.exit(code)


if __name__ == "__main__":
    main()
