"""Chat and voice conversation API endpoints for MedSpeak interactive pronunciation tutor."""

import base64
import logging
import time

from fastapi import APIRouter, File, Form, HTTPException, Response, UploadFile, status
from pydantic import BaseModel, Field

from app.services.gemini import gemini_service
from app.services.rime import rime_service
from app.services.safety import check_medical_safety
from app.services.stt import STTError, stt_service
from app.services.terminology import (
    extract_potential_term,
    is_generic_category,
    resolve_term,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/chat", tags=["Chat & Voice"])


class TimingMetrics(BaseModel):
    """Detailed timing metrics for request processing in milliseconds."""

    stt_final_ms: float = 0.0
    gemini_ms: float = 0.0
    routing_ms: float = 0.0
    pronunciation_ms: float = 0.0
    rime_ms: float = 0.0
    total_response_ms: float = 0.0


class ChatRequest(BaseModel):
    """Chat message request from the user."""

    message: str = Field(..., min_length=1, max_length=2000, description="User message text")
    synthesize_audio: bool = Field(
        default=True, description="Whether to generate Rime spoken audio for the response"
    )
    speed: float = Field(default=1.0, ge=0.4, le=2.5, description="Speaking rate multiplier")
    context_term: str | None = Field(
        default=None, description="Active medical term from previous conversation turn"
    )


class ChatResponse(BaseModel):
    """Structured response from the MedSpeak tutor."""

    reply: str
    intent: str
    term: str | None = None
    provider: str = "rime"
    pronunciation_source: str | None = None  # "verified_database" | "gemini_fallback" | None
    speech_text: str | None = None
    audio_base64: str | None = None
    audio_format: str = "mp3"
    timing: TimingMetrics = Field(default_factory=TimingMetrics)


class VoiceChatResponse(ChatResponse):
    """Structured response from the MedSpeak tutor with transcribed user speech."""

    transcript: str


class SynthesizeRequest(BaseModel):
    """Request payload to synthesize speech audio for replay or speed variation."""

    text: str = Field(..., min_length=1, max_length=2000, description="Text to speak")
    speed: float = Field(default=1.0, ge=0.4, le=2.5, description="Speech rate (e.g. 0.7 for slow)")


async def _synthesize_audio_base64(text: str, speed: float = 1.0) -> tuple[str | None, float]:
    """Synthesize Rime speech audio and return base64 string and latency in ms."""
    try:
        start_t = time.perf_counter()
        result = await rime_service.synthesize(text=text, speed=speed)
        elapsed_ms = round((time.perf_counter() - start_t) * 1000, 2)
        b64 = base64.b64encode(result.audio_bytes).decode("utf-8")
        return b64, result.latency_ms or elapsed_ms
    except Exception as exc:
        logger.error("Failed to synthesize Rime audio for chat response: %s", exc)
        return None, 0.0


async def _process_message(
    user_message: str,
    context_term: str | None = None,
    requested_speed: float = 1.0,
) -> tuple[str, str, str, str | None, str | None, float, float, float, float]:
    """Process message using fast-path routing, Gemini API, or authoritative terminology services.

    Returns:
        tuple containing:
        (reply_text, speech_text, intent, canonical_or_term, pronunciation_source,
         effective_speed, gemini_ms, routing_ms, pronunciation_ms)
    """
    overall_route_start = time.perf_counter()
    msg_clean = user_message.lower().strip().rstrip(".?!")

    # 1. Immediate zero-trust medical safety check (< 1ms)
    is_violation, safety_reply = check_medical_safety(user_message)
    if is_violation:
        logger.warning("Safety boundary triggered for prompt: %s", user_message)
        routing_ms = round((time.perf_counter() - overall_route_start) * 1000, 2)
        return (
            safety_reply,
            safety_reply,
            "safety_boundary",
            None,
            None,
            requested_speed,
            0.0,
            routing_ms,
            0.0,
        )

    # 2. FAST-PATH: Follow-up contextual commands ("say it slower", "repeat that", "again")
    # If there is an active context_term, bypass Gemini entirely (< 1ms)
    is_slow_cmd = any(w in msg_clean for w in ["slower", "slow down", "say it slower"])
    is_repeat_cmd = any(w in msg_clean for w in ["again", "repeat", "say it again", "once more"])
    is_syllables_cmd = any(w in msg_clean for w in ["break it down", "syllables", "syllable"])

    if context_term and (is_slow_cmd or is_repeat_cmd or is_syllables_cmd):
        logger.info("Fast-path triggered for follow-up command on term: '%s'", context_term)
        pron_start = time.perf_counter()
        active_term = resolve_term(context_term)

        if active_term:
            canonical = active_term.canonical_name
            title_term = canonical.capitalize()
            if is_slow_cmd:
                effective_speed = 0.7
                reply_text = (
                    f"**{title_term}** pronounced slower (0.7x speed):\n\n"
                    f"- **Syllables:** **{active_term.syllables}**\n"
                    f"- **IPA:** {active_term.ipa}\n"
                    f"- **Category:** {active_term.category}"
                )
                speech_text = f"Here is {canonical} pronounced slower: {active_term.syllables}."
                intent = "slow"
            elif is_repeat_cmd:
                effective_speed = 1.0
                reply_text = (
                    f"Repeating **{title_term}**:\n\n"
                    f"- **Pronunciation:** **{active_term.syllables}**\n"
                    f"- **IPA:** {active_term.ipa}\n"
                    f"- **Definition:** {active_term.definition}"
                )
                speech_text = f"Repeating {canonical}: {active_term.syllables}."
                intent = "repeat"
            else:
                effective_speed = 1.0
                reply_text = (
                    f"Syllable breakdown for **{title_term}**:\n\n"
                    f"**{active_term.syllables}**\n\n"
                    f"- **IPA:** {active_term.ipa}"
                )
                speech_text = f"The syllable breakdown for {canonical} is {active_term.syllables}."
                intent = "syllables"

            pron_ms = round((time.perf_counter() - pron_start) * 1000, 2)
            routing_ms = round((time.perf_counter() - overall_route_start) * 1000, 2)
            return (
                reply_text,
                speech_text,
                intent,
                canonical,
                "verified_database",
                effective_speed,
                0.0,
                routing_ms,
                pron_ms,
            )
        else:
            # context_term from fallback source
            title_term = context_term.capitalize()
            if is_slow_cmd:
                effective_speed = 0.7
                reply_text = f"**{title_term}** pronounced slower (0.7x speed)."
                speech_text = f"Here is {context_term} pronounced slower: {context_term}."
                intent = "slow"
            elif is_repeat_cmd:
                effective_speed = 1.0
                reply_text = f"Repeating **{title_term}**."
                speech_text = f"Repeating {context_term}."
                intent = "repeat"
            else:
                effective_speed = 1.0
                reply_text = f"Syllables for **{title_term}**."
                speech_text = f"Syllables for {context_term}."
                intent = "syllables"

            pron_ms = round((time.perf_counter() - pron_start) * 1000, 2)
            routing_ms = round((time.perf_counter() - overall_route_start) * 1000, 2)
            return (
                reply_text,
                speech_text,
                intent,
                context_term,
                "gemini_fallback",
                effective_speed,
                0.0,
                routing_ms,
                pron_ms,
            )

    # 3. Query Gemini conversational brain (with in-memory static cache check)
    gemini_turn = await gemini_service.generate_chat_turn(
        message=user_message,
        context_term=context_term,
    )
    gemini_ms = gemini_turn.elapsed_ms

    intent = gemini_turn.intent
    target_term = gemini_turn.target_term
    effective_speed = requested_speed

    # 4. If safety boundary classified by Gemini
    if intent == "safety_boundary":
        routing_ms = round((time.perf_counter() - overall_route_start) * 1000, 2)
        return (
            gemini_turn.response,
            gemini_turn.response,
            "safety_boundary",
            None,
            None,
            requested_speed,
            gemini_ms,
            routing_ms,
            0.0,
        )

    # 5. Handle Generic Category / Capability Inquiries (e.g. "How do I pronounce clinical terms?")
    if (
        intent == "pronunciation_general"
        or is_generic_category(msg_clean)
        or (target_term and is_generic_category(target_term))
    ):
        generic_reply = (
            "You can ask me how to pronounce specific medical terms like tachycardia, "
            "acetaminophen, or hydroxychloroquine. Just say the term or ask 'How do I "
            "pronounce...' followed by any clinical word."
        )
        routing_ms = round((time.perf_counter() - overall_route_start) * 1000, 2)
        return (
            generic_reply,
            generic_reply,
            "pronunciation_general",
            None,
            None,
            requested_speed,
            gemini_ms,
            routing_ms,
            0.0,
        )

    # 6. Handle follow-up commands without prior fast-path
    if intent in ["slow", "repeat", "syllables"]:
        active_term = resolve_term(target_term or context_term)
        term_label = active_term.canonical_name if active_term else target_term or context_term
        if intent == "slow":
            effective_speed = 0.7
        routing_ms = round((time.perf_counter() - overall_route_start) * 1000, 2)
        return (
            gemini_turn.response,
            gemini_turn.response,
            intent,
            term_label,
            "verified_database" if active_term else "gemini_fallback",
            effective_speed,
            gemini_ms,
            routing_ms,
            0.0,
        )

    # 7. Handle Pronunciation or Definition Requests
    if (
        intent in ("pronounce", "definition")
        or gemini_turn.needs_pronunciation
        or gemini_turn.needs_pronunciation_service
    ):
        pron_start = time.perf_counter()

        # Check local authoritative dictionary (exact match, aliases, STT misrecognitions)
        term_obj = resolve_term(target_term or user_message)
        if not term_obj and target_term:
            term_obj = resolve_term(target_term)
        if not term_obj:
            candidate = extract_potential_term(user_message)
            if candidate and not is_generic_category(candidate):
                term_obj = resolve_term(candidate)

        # Case A: Authoritative database term match
        if term_obj:
            canonical = term_obj.canonical_name
            title_term = canonical.capitalize()

            # Note recognized misrecognition cleanly if user message was an alias
            stt_garble_note = ""
            if msg_clean != canonical and msg_clean in [a.lower() for a in term_obj.aliases]:
                stt_garble_note = f' (recognized from "{user_message.strip()}")'

            if intent == "definition":
                reply_text = (
                    f"**{title_term}**{stt_garble_note} is classified under "
                    f"*{term_obj.category}*.\n\n"
                    f"**Definition:** {term_obj.definition}\n\n"
                    f"**Pronunciation:** {term_obj.syllables} (IPA: {term_obj.ipa})"
                )
                speech_text = (
                    f"{title_term} is classified under {term_obj.category}. {term_obj.definition}"
                )
            else:
                reply_text = (
                    f"**{title_term}**{stt_garble_note} is pronounced **{term_obj.syllables}** "
                    f"(IPA: {term_obj.ipa}).\n\n"
                    f"- **Category:** {term_obj.category}\n"
                    f"- **Definition:** {term_obj.definition}"
                )
                if stt_garble_note:
                    speech_text = f"Pronouncing {canonical}: {term_obj.syllables}."
                else:
                    speech_text = (
                        f"{title_term} is pronounced {term_obj.syllables}. "
                        f"It is defined as: {term_obj.definition}"
                    )

            pron_ms = round((time.perf_counter() - pron_start) * 1000, 2)
            routing_ms = round((time.perf_counter() - overall_route_start) * 1000, 2)
            return (
                reply_text,
                speech_text,
                intent,
                canonical,
                "verified_database",
                effective_speed,
                gemini_ms,
                routing_ms,
                pron_ms,
            )

        # Case B: Arbitrary / Unknown term - Gemini Fallback Engine
        arbitrary_term = target_term or extract_potential_term(user_message)
        if arbitrary_term and not is_generic_category(arbitrary_term):
            title_term = arbitrary_term.capitalize()
            syllables = gemini_turn.fallback_syllables or title_term
            ipa_str = f" (IPA: {gemini_turn.fallback_ipa})" if gemini_turn.fallback_ipa else ""

            reply_text = (
                f"**{title_term}** is pronounced **{syllables}**{ipa_str}.\n\n"
                "*Note: Pronunciation provided via AI clinical assistant.*"
            )
            speech_text = f"{title_term} is pronounced {syllables}."

            pron_ms = round((time.perf_counter() - pron_start) * 1000, 2)
            routing_ms = round((time.perf_counter() - overall_route_start) * 1000, 2)
            return (
                reply_text,
                speech_text,
                "pronounce",
                arbitrary_term.lower(),
                "gemini_fallback",
                effective_speed,
                gemini_ms,
                routing_ms,
                pron_ms,
            )

    # 8. General conversational reply
    routing_ms = round((time.perf_counter() - overall_route_start) * 1000, 2)
    return (
        gemini_turn.response,
        gemini_turn.response,
        "general",
        None,
        None,
        effective_speed,
        gemini_ms,
        routing_ms,
        0.0,
    )


@router.post("", response_model=ChatResponse, status_code=status.HTTP_200_OK)
async def handle_chat(payload: ChatRequest) -> ChatResponse:
    """Process user message, enforce safety boundaries, and optionally return Rime spoken audio."""
    request_start = time.perf_counter()
    user_message = payload.message.strip()
    logger.info("Chat message received: %s (context_term=%s)", user_message, payload.context_term)

    (
        reply_text,
        speech_text,
        intent,
        canonical,
        pron_source,
        effective_speed,
        gemini_ms,
        routing_ms,
        pron_ms,
    ) = await _process_message(
        user_message,
        context_term=payload.context_term,
        requested_speed=payload.speed,
    )

    audio_base64: str | None = None
    rime_ms = 0.0
    if payload.synthesize_audio:
        audio_base64, rime_ms = await _synthesize_audio_base64(speech_text, speed=effective_speed)

    total_ms = round((time.perf_counter() - request_start) * 1000, 2)

    logger.info(
        "Chat response ready: intent=%s, term=%s, source=%s, "
        "timing=(gemini=%.1fms, route=%.1fms, rime=%.1fms, total=%.1fms)",
        intent,
        canonical,
        pron_source,
        gemini_ms,
        routing_ms,
        rime_ms,
        total_ms,
    )

    return ChatResponse(
        reply=reply_text,
        intent=intent,
        term=canonical,
        provider="rime",
        pronunciation_source=pron_source,
        speech_text=speech_text,
        audio_base64=audio_base64,
        audio_format="mp3",
        timing=TimingMetrics(
            stt_final_ms=0.0,
            gemini_ms=gemini_ms,
            routing_ms=routing_ms,
            pronunciation_ms=pron_ms,
            rime_ms=rime_ms,
            total_response_ms=total_ms,
        ),
    )


@router.post("/voice", response_model=VoiceChatResponse, status_code=status.HTTP_200_OK)
async def handle_voice(
    audio: UploadFile = File(..., description="Recorded microphone audio stream"),  # noqa: B008
    speed: float = Form(default=1.0, ge=0.4, le=2.5, description="Speaking rate"),  # noqa: B008
    context_term: str | None = Form(default=None, description="Prior turn term"),  # noqa: B008
) -> VoiceChatResponse:
    """Process microphone audio with STT, resolve medical query, and synthesize Rime speech."""
    request_start = time.perf_counter()
    logger.info(
        "Received voice audio upload: filename=%s, content_type=%s, context_term=%s",
        audio.filename,
        audio.content_type,
        context_term,
    )

    try:
        audio_bytes = await audio.read()
    except Exception as exc:
        logger.error("Failed to read audio file upload: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to read uploaded audio file",
        ) from exc

    # Transcribe user speech via modular STT service
    stt_start = time.perf_counter()
    try:
        transcript = await stt_service.transcribe(
            audio_bytes,
            filename_hint=audio.filename or "audio.webm",
        )
        stt_ms = round((time.perf_counter() - stt_start) * 1000, 2)
    except STTError as err:
        stt_ms = round((time.perf_counter() - stt_start) * 1000, 2)
        logger.warning("STT transcription unsuccessful: %s", err.message)
        fallback_reply = "Couldn't hear that. Try again."
        fallback_audio, rime_ms = await _synthesize_audio_base64(fallback_reply, speed=speed)
        total_ms = round((time.perf_counter() - request_start) * 1000, 2)
        return VoiceChatResponse(
            transcript="",
            reply=fallback_reply,
            intent="stt_failure",
            term=context_term,
            provider="rime",
            pronunciation_source=None,
            speech_text=fallback_reply,
            audio_base64=fallback_audio,
            audio_format="mp3",
            timing=TimingMetrics(
                stt_final_ms=stt_ms,
                gemini_ms=0.0,
                routing_ms=0.0,
                pronunciation_ms=0.0,
                rime_ms=rime_ms,
                total_response_ms=total_ms,
            ),
        )

    logger.info("Voice transcription result: '%s' (stt_ms=%.1f)", transcript, stt_ms)

    # Process transcribed text through terminology & safety engine
    (
        reply_text,
        speech_text,
        intent,
        canonical,
        pron_source,
        effective_speed,
        gemini_ms,
        routing_ms,
        pron_ms,
    ) = await _process_message(
        transcript,
        context_term=context_term,
        requested_speed=speed,
    )

    # Synthesize response using real Rime TTS
    audio_base64, rime_ms = await _synthesize_audio_base64(speech_text, speed=effective_speed)
    total_ms = round((time.perf_counter() - request_start) * 1000, 2)

    logger.info(
        "Voice turn complete: transcript='%s', term=%s, source=%s, "
        "timing=(stt=%.1fms, gemini=%.1fms, rime=%.1fms, total=%.1fms)",
        transcript,
        canonical,
        pron_source,
        stt_ms,
        gemini_ms,
        rime_ms,
        total_ms,
    )

    return VoiceChatResponse(
        transcript=transcript,
        reply=reply_text,
        intent=intent,
        term=canonical,
        provider="rime",
        pronunciation_source=pron_source,
        speech_text=speech_text,
        audio_base64=audio_base64,
        audio_format="mp3",
        timing=TimingMetrics(
            stt_final_ms=stt_ms,
            gemini_ms=gemini_ms,
            routing_ms=routing_ms,
            pronunciation_ms=pron_ms,
            rime_ms=rime_ms,
            total_response_ms=total_ms,
        ),
    )


@router.post("/synthesize")
async def handle_synthesize(payload: SynthesizeRequest) -> Response:
    """Synthesize speech audio for replay, slow pronunciation, or repeated review."""
    logger.info(
        "Synthesizing speech: length=%d chars, speed=%.2f",
        len(payload.text),
        payload.speed,
    )
    try:
        result = await rime_service.synthesize(text=payload.text, speed=payload.speed)
        return Response(
            content=result.audio_bytes,
            media_type=result.content_type,
            headers={
                "Content-Disposition": f'inline; filename="medspeak_speech.{result.audio_format}"',
                "X-Rime-Latency-Ms": str(result.latency_ms),
                "X-Rime-Speed": str(payload.speed),
            },
        )
    except Exception as exc:
        logger.error("Synthesis failed in /api/chat/synthesize: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Speech synthesis failed: {str(exc)}",
        ) from exc
