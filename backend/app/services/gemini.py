"""Gemini API conversational brain service for MedSpeak pronunciation tutor.

Integrates the official Google GenAI SDK (google-genai) to provide natural conversational
intelligence, structured intent detection, and medical term extraction while maintaining
authoritative clinical terminology boundaries and low-latency performance.
"""

import asyncio
import logging
import re
import time
from typing import Any

from google import genai
from google.genai import errors, types
from pydantic import BaseModel, Field

from app.core.config import settings
from app.services.safety import check_medical_safety
from app.services.terminology import (
    extract_potential_term,
    is_generic_category,
    resolve_term,
)

logger = logging.getLogger(__name__)

SYSTEM_INSTRUCTION = """You are the conversational brain of MedSpeak, an educational tutor
for medical terminology and pronunciation.

Your responsibilities:
1. Greet users naturally, explain MedSpeak capabilities, and handle conversational
   pleasantries ("hello", "what can you do?", "thanks").
2. CRITICAL DISTINCTION: Generic Category Questions vs Specific Medical Term:
   - If user asks about generic categories like:
     - "How do I pronounce clinical terms?"
     - "How do I pronounce medical words?"
     - "What clinical terms can you help me pronounce?"
     - "Can you teach me medical pronunciation?"
     These are general educational inquiries.
     Set intent = "pronunciation_general", target_term = null, is_specific_term = false,
     needs_pronunciation = false.
     Explain that the user can ask for specific terms like tachycardia, acetaminophen,
     or hydroxychloroquine.
     NEVER treat "clinical terms", "medical words", or similar as a medical term!
3. Specific Medical Term Pronunciation Requests:
   - When user asks how to pronounce, break down, or define a specific clinical word
     (e.g. "tachycardia", "acetaminophen", "bronchoscopy", "amlodipine"):
     Set intent = "pronounce" (or "definition"), target_term = <extracted lowercase term>,
     is_specific_term = true, needs_pronunciation = true.
     Provide accurate fallback_syllables with stressed syllables capitalized
     (e.g. "TAK-i-KAR-dee-uh", "uh-SEE-tuh-MIN-oh-fen", "brong-KOS-kuh-pee", "am-LOH-dih-peen")
     and fallback_ipa (e.g. "/ˌtæk.ɪˈkɑːr.di.ə/", "/brɒŋˈkɒs.kə.pi/").
     In response, give a concise conversational reply.
4. STT Phonetic Misrecognition Recovery:
   - When user speech is phonetically garbled (e.g. "a set of amino phen" -> "acetaminophen",
     "tacky cardia" -> "tachycardia", "hydro chloroquine" -> "hydroxychloroquine"):
     Recover the intended clinical term in target_term (e.g. "acetaminophen"),
     set is_specific_term = true, needs_pronunciation = true, and provide syllables.
5. Follow-up and Contextual Commands:
   - "say it slower", "slow down": intent = "slow"
   - "repeat that", "again", "once more": intent = "repeat"
   - "break it down", "syllables": intent = "syllables"
6. MEDICAL SAFETY BOUNDARIES (CRITICAL):
   - MedSpeak is strictly an educational pronunciation tutor.
   - NEVER diagnose conditions, prescribe medications, recommend dosages, or give advice.
   - If asked: set intent = "safety_boundary", target_term = null, is_specific_term = false,
     needs_pronunciation = false, and politely redirect to a licensed healthcare provider.
7. Return structured JSON conforming strictly to the schema.
"""


class GeminiChatOutput(BaseModel):
    """Structured output from Gemini conversational brain."""

    intent: str = Field(
        ...,
        description=(
            "Classified intent: 'pronounce', 'definition', 'slow', 'repeat', 'syllables', "
            "'pronunciation_general', 'safety_boundary', or 'general'"
        ),
    )
    target_term: str | None = Field(
        default=None,
        description="Extracted clinical term (e.g. 'hydroxychloroquine'). None if generic.",
    )
    is_specific_term: bool = Field(
        default=False,
        description="True for specific medical term; False for generic categories.",
    )
    response: str = Field(
        ...,
        description="Conversational reply text for the user.",
    )
    needs_pronunciation: bool = Field(
        default=False,
        description="True if the request requires medical pronunciation breakdown.",
    )
    needs_pronunciation_service: bool = Field(
        default=False,
        description="Alias for backward compatibility.",
    )
    needs_rime: bool = Field(
        default=True,
        description="True if MedSpeak should synthesize spoken audio response via Rime TTS.",
    )
    fallback_syllables: str | None = Field(
        default=None,
        description=(
            "Phonetic syllables with stressed syllables capitalized (e.g. 'TAK-i-KAR-dee-uh')."
        ),
    )
    fallback_ipa: str | None = Field(
        default=None,
        description="International Phonetic Alphabet transcription (e.g. '/ˌtæk.ɪˈkɑːr.di.ə/').",
    )
    elapsed_ms: float = Field(
        default=0.0,
        description="Latency for Gemini generation in milliseconds.",
    )


# Fast in-memory responses for common static queries to bypass Gemini API calls (< 1ms)
STATIC_CACHE: dict[str, dict[str, Any]] = {
    "hello": {
        "intent": "general",
        "target_term": None,
        "is_specific_term": False,
        "response": (
            "Hello! I am MedSpeak, your medical pronunciation tutor. Ask me how to pronounce "
            "clinical terms like tachycardia, acetaminophen, or hydroxychloroquine."
        ),
        "needs_pronunciation": False,
        "needs_rime": True,
    },
    "hi": {
        "intent": "general",
        "target_term": None,
        "is_specific_term": False,
        "response": (
            "Hi there! I am MedSpeak. How can I help with your medical pronunciation today?"
        ),
        "needs_pronunciation": False,
        "needs_rime": True,
    },
    "hey": {
        "intent": "general",
        "target_term": None,
        "is_specific_term": False,
        "response": (
            "Hey! Ready to practice clinical terminology. Which medical term would you like "
            "to pronounce?"
        ),
        "needs_pronunciation": False,
        "needs_rime": True,
    },
    "what can you do": {
        "intent": "general",
        "target_term": None,
        "is_specific_term": False,
        "response": (
            "I am MedSpeak, an educational medical terminology pronunciation tutor. I help you "
            "master difficult clinical words, break down syllables, learn standard IPA "
            "transcriptions, and practice speaking with high-accuracy TTS audio."
        ),
        "needs_pronunciation": False,
        "needs_rime": True,
    },
    "help": {
        "intent": "general",
        "target_term": None,
        "is_specific_term": False,
        "response": (
            "You can ask me how to pronounce any clinical term, such as 'How do I pronounce "
            "omeprazole?' or 'Say it slower'. You can also ask for syllable breakdowns "
            "or definitions."
        ),
        "needs_pronunciation": False,
        "needs_rime": True,
    },
    "thanks": {
        "intent": "general",
        "target_term": None,
        "is_specific_term": False,
        "response": (
            "You're welcome! Let me know if you would like to practice any other medical terms."
        ),
        "needs_pronunciation": False,
        "needs_rime": True,
    },
    "thank you": {
        "intent": "general",
        "target_term": None,
        "is_specific_term": False,
        "response": (
            "You're welcome! Let me know if you would like to practice any other medical terms."
        ),
        "needs_pronunciation": False,
        "needs_rime": True,
    },
    "how do i pronounce clinical terms": {
        "intent": "pronunciation_general",
        "target_term": None,
        "is_specific_term": False,
        "response": (
            "You can ask me how to pronounce specific medical terms like tachycardia, "
            "acetaminophen, or hydroxychloroquine. Just say the term or ask 'How do I "
            "pronounce...' followed by any clinical word."
        ),
        "needs_pronunciation": False,
        "needs_rime": True,
    },
    "how do i pronounce medical words": {
        "intent": "pronunciation_general",
        "target_term": None,
        "is_specific_term": False,
        "response": (
            "You can ask me how to pronounce specific medical terms like tachycardia, "
            "acetaminophen, or hydroxychloroquine. Just say the term or ask 'How do I "
            "pronounce...' followed by any clinical word."
        ),
        "needs_pronunciation": False,
        "needs_rime": True,
    },
    "what clinical terms can you help me pronounce": {
        "intent": "pronunciation_general",
        "target_term": None,
        "is_specific_term": False,
        "response": (
            "I can help you pronounce any medical term! My verified clinical database includes "
            "terms like hydroxychloroquine, tachycardia, omeprazole, amoxicillin, acetaminophen, "
            "and many more. You can also ask about any other clinical term."
        ),
        "needs_pronunciation": False,
        "needs_rime": True,
    },
    "can you teach me medical pronunciation": {
        "intent": "pronunciation_general",
        "target_term": None,
        "is_specific_term": False,
        "response": (
            "Yes! I can guide you through the pronunciation, syllable breakdown, and phonetic "
            "structure of any clinical term. Try asking: 'How do I pronounce tachycardia?'"
        ),
        "needs_pronunciation": False,
        "needs_rime": True,
    },
}



def redact_secrets(text: str) -> str:
    """Sanitize text to guarantee API keys are never exposed in logs or exceptions."""
    if not text:
        return text
    redacted = text
    if settings.GEMINI_API_KEY:
        redacted = redacted.replace(settings.GEMINI_API_KEY, "[REDACTED_GEMINI_KEY]")
    if settings.RIME_API_KEY:
        redacted = redacted.replace(settings.RIME_API_KEY, "[REDACTED_RIME_KEY]")
    # Redact common Gemini key patterns if present
    redacted = re.sub(r"AQ\.[A-Za-z0-9_-]{40,}", "[REDACTED_GEMINI_KEY]", redacted)
    redacted = re.sub(r"AIzaSy[A-Za-z0-9_-]{33}", "[REDACTED_GEMINI_KEY]", redacted)
    return redacted


class GeminiService:
    """Service wrapper for Google Gemini API."""

    def __init__(self) -> None:
        self.api_key = settings.GEMINI_API_KEY.strip()
        self.model_id = settings.GEMINI_MODEL.strip() or "gemini-3.5-flash-lite"
        self.fallback_models = ["gemini-3.5-flash-lite", "gemini-3.8-flash", "gemini-2.5-flash"]
        self._client: genai.Client | None = None

        if self.api_key:
            try:
                self._client = genai.Client(api_key=self.api_key)
                logger.info(
                    "Gemini client initialized with model=%s (fallbacks=%s)",
                    self.model_id,
                    self.fallback_models,
                )
            except Exception as exc:
                logger.error("Failed to initialize Gemini client: %s", redact_secrets(str(exc)))
                self._client = None
        else:
            logger.warning("GEMINI_API_KEY not configured. Local fallback engine will be used.")

    @property
    def is_configured(self) -> bool:
        """Return True if a valid Gemini API key is configured."""
        return bool(self.api_key and self._client is not None)

    async def check_health(self) -> dict[str, Any]:
        """Verify Gemini service status and model configuration."""
        if not self.is_configured:
            return {
                "status": "unavailable",
                "configured": False,
                "model": self.model_id,
                "detail": "GEMINI_API_KEY is not configured.",
            }
        return {
            "status": "ok",
            "configured": True,
            "model": self.model_id,
            "fallback_models": self.fallback_models,
        }

    def _deterministic_fallback(
        self,
        user_message: str,
        context_term: str | None = None,
    ) -> GeminiChatOutput:
        """Deterministic local fallback when Gemini API is unavailable, times out, or errors."""
        msg_lower = user_message.lower().strip().rstrip(".?!")

        # 1. Zero-trust safety check
        is_violation, safety_reply = check_medical_safety(user_message)
        if is_violation:
            return GeminiChatOutput(
                intent="safety_boundary",
                target_term=None,
                is_specific_term=False,
                response=safety_reply,
                needs_pronunciation=False,
                needs_pronunciation_service=False,
                needs_rime=True,
            )

        # 2. Static cache lookup
        if msg_lower in STATIC_CACHE:
            cached = STATIC_CACHE[msg_lower]
            return GeminiChatOutput(
                intent=cached["intent"],
                target_term=cached["target_term"],
                is_specific_term=cached["is_specific_term"],
                response=cached["response"],
                needs_pronunciation=cached["needs_pronunciation"],
                needs_pronunciation_service=cached["needs_pronunciation"],
                needs_rime=cached["needs_rime"],
            )

        # 3. Generic terminology category check
        if is_generic_category(msg_lower) or any(
            phrase in msg_lower
            for phrase in [
                "clinical terms",
                "medical words",
                "medical terms",
                "clinical words",
            ]
        ):
            return GeminiChatOutput(
                intent="pronunciation_general",
                target_term=None,
                is_specific_term=False,
                response=(
                    "You can ask me how to pronounce specific medical terms like tachycardia, "
                    "acetaminophen, or hydroxychloroquine. Just say the term or ask "
                    "'How do I pronounce...' followed by any clinical word."
                ),

                needs_pronunciation=False,
                needs_pronunciation_service=False,
                needs_rime=True,
            )

        # 4. Contextual follow-up commands
        if any(w in msg_lower for w in ["slower", "slow down", "say it slower"]):
            return GeminiChatOutput(
                intent="slow",
                target_term=context_term,
                is_specific_term=bool(context_term),
                response="Pronouncing slower at 0.7x speed.",
                needs_pronunciation=bool(context_term),
                needs_pronunciation_service=bool(context_term),
                needs_rime=True,
            )

        if any(w in msg_lower for w in ["again", "repeat", "say it again", "once more"]):
            return GeminiChatOutput(
                intent="repeat",
                target_term=context_term,
                is_specific_term=bool(context_term),
                response="Repeating pronunciation.",
                needs_pronunciation=bool(context_term),
                needs_pronunciation_service=bool(context_term),
                needs_rime=True,
            )

        if any(w in msg_lower for w in ["break it down", "syllables", "syllable"]):
            return GeminiChatOutput(
                intent="syllables",
                target_term=context_term,
                is_specific_term=bool(context_term),
                response="Breaking down syllables.",
                needs_pronunciation=bool(context_term),
                needs_pronunciation_service=bool(context_term),
                needs_rime=True,
            )

        # 5. Medical term resolution (checks exact, alias, and STT misrecognitions)
        resolved = resolve_term(user_message)
        if not resolved:
            candidate = extract_potential_term(user_message)
            if candidate and not is_generic_category(candidate):
                resolved = resolve_term(candidate)

        if resolved:
            is_def = any(w in msg_lower for w in ["what is", "definition", "what does", "mean"])
            return GeminiChatOutput(
                intent="definition" if is_def else "pronounce",
                target_term=resolved.canonical_name,
                is_specific_term=True,
                response=f"Here is the pronunciation for {resolved.canonical_name}.",
                needs_pronunciation=True,
                needs_pronunciation_service=True,
                needs_rime=True,
                fallback_syllables=resolved.syllables,
                fallback_ipa=resolved.ipa,
            )

        # Unverified term candidate
        candidate_term = extract_potential_term(user_message)
        if candidate_term and not is_generic_category(candidate_term):
            if candidate_term.lower() not in [
                "hi",
                "hello",
                "hey",
                "help",
                "thanks",
                "goodbye",
            ]:
                return GeminiChatOutput(
                    intent="pronounce",
                    target_term=candidate_term,
                    is_specific_term=True,
                    response=f"Pronouncing {candidate_term}.",
                    needs_pronunciation=True,
                    needs_pronunciation_service=True,
                    needs_rime=True,
                    fallback_syllables=candidate_term.capitalize(),
                )

        return GeminiChatOutput(
            intent="general",
            target_term=None,
            is_specific_term=False,
            response=(
                "Hello! I am MedSpeak, your medical pronunciation tutor. "
                "Ask me how to pronounce clinical terms or practice medical terminology."
            ),
            needs_pronunciation=False,
            needs_pronunciation_service=False,
            needs_rime=True,
        )

    async def generate_chat_turn(
        self,
        message: str,
        context_term: str | None = None,
    ) -> GeminiChatOutput:
        """Process user message through Gemini API to classify intent and extract target term.

        Returns:
            GeminiChatOutput: Structured output with intent, term, response, and elapsed_ms.
        """
        start_time = time.perf_counter()

        # 1. Immediate zero-trust medical safety check
        is_violation, safety_reply = check_medical_safety(message)
        if is_violation:
            logger.info("Safety boundary triggered server-side for input")
            elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)
            return GeminiChatOutput(
                intent="safety_boundary",
                target_term=None,
                is_specific_term=False,
                response=safety_reply,
                needs_pronunciation=False,
                needs_pronunciation_service=False,
                needs_rime=True,
                elapsed_ms=elapsed_ms,
            )

        clean_lower = message.lower().strip().rstrip(".?!")

        # 2. Check in-memory static cache for lightning-fast sub-millisecond return
        if clean_lower in STATIC_CACHE:
            cached = STATIC_CACHE[clean_lower]
            elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)
            logger.info("Static cache hit for '%s' (%.2fms)", clean_lower, elapsed_ms)
            return GeminiChatOutput(
                intent=cached["intent"],
                target_term=cached["target_term"],
                is_specific_term=cached["is_specific_term"],
                response=cached["response"],
                needs_pronunciation=cached["needs_pronunciation"],
                needs_pronunciation_service=cached["needs_pronunciation"],
                needs_rime=cached["needs_rime"],
                elapsed_ms=elapsed_ms,
            )

        if not self.is_configured or self._client is None:
            logger.info("Gemini not configured; using deterministic fallback engine.")
            output = self._deterministic_fallback(message, context_term)
            output.elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)
            return output

        # 3. Build structured prompt
        context_hint = (
            f"Active conversation medical term: '{context_term}'.\n"
            if context_term
            else "No active medical term in context.\n"
        )
        user_prompt = f"{context_hint}User message: {message}"

        # Fast Gemini configuration: low temperature and bounded tokens
        config = types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=GeminiChatOutput,
            system_instruction=SYSTEM_INSTRUCTION,
            temperature=0.1,
            max_output_tokens=250,
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
        )

        # 4. Call Gemini API with timeout and model fallback
        models_to_try: list[str] = []
        for m in [self.model_id, *self.fallback_models]:
            if m and m not in models_to_try:
                models_to_try.append(m)

        last_error: Exception | None = None

        for model in models_to_try:
            try:
                logger.info("Calling Gemini API with model=%s", model)
                call_coro = self._client.aio.models.generate_content(
                    model=model,
                    contents=user_prompt,
                    config=config,
                )
                response = await asyncio.wait_for(
                    call_coro,
                    timeout=settings.GEMINI_TIMEOUT_SECONDS,
                )

                if not response.text:
                    raise ValueError("Empty response text from Gemini API")

                parsed = GeminiChatOutput.model_validate_json(response.text)

                # Normalize intent
                normalized_intent = parsed.intent.lower().strip()
                if normalized_intent in ["ask_pronunciation", "pronunciation"]:
                    normalized_intent = "pronounce"
                elif normalized_intent in ["ask_definition", "meaning"]:
                    normalized_intent = "definition"
                elif normalized_intent in ["capabilities", "greeting", "info"]:
                    normalized_intent = "general"
                elif normalized_intent in ["pronunciation_general", "general_category"]:
                    normalized_intent = "pronunciation_general"

                if normalized_intent not in [
                    "pronounce",
                    "definition",
                    "slow",
                    "repeat",
                    "syllables",
                    "pronunciation_general",
                    "safety_boundary",
                    "general",
                ]:
                    normalized_intent = "general"

                # If generic category phrase detected, normalize intent
                raw_target = (parsed.target_term or "").strip().lower() or None
                if raw_target and is_generic_category(raw_target):
                    normalized_intent = "pronunciation_general"
                    raw_target = None
                    parsed.is_specific_term = False

                # If follow-up command didn't supply a term, inherit context_term
                if normalized_intent in ["slow", "repeat", "syllables"] and not raw_target:
                    raw_target = context_term

                elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)
                return GeminiChatOutput(
                    intent=normalized_intent,
                    target_term=raw_target,
                    is_specific_term=parsed.is_specific_term and bool(raw_target),
                    response=parsed.response.strip(),
                    needs_pronunciation=(
                        parsed.needs_pronunciation
                        or normalized_intent
                        in ["pronounce", "definition", "slow", "repeat", "syllables"]
                    ),
                    needs_pronunciation_service=(
                        parsed.needs_pronunciation
                        or normalized_intent
                        in ["pronounce", "definition", "slow", "repeat", "syllables"]
                    ),
                    needs_rime=parsed.needs_rime,
                    fallback_syllables=parsed.fallback_syllables,
                    fallback_ipa=parsed.fallback_ipa,
                    elapsed_ms=elapsed_ms,
                )

            except TimeoutError:
                logger.warning(
                    "Gemini API call timed out after %ss for model %s",
                    settings.GEMINI_TIMEOUT_SECONDS,
                    model,
                )
                last_error = TimeoutError("Gemini API request timed out")
                break
            except (errors.APIError, errors.ServerError, errors.ClientError) as api_err:
                sanitized_err = redact_secrets(str(api_err))
                logger.warning("Gemini API error with model %s: %s", model, sanitized_err)
                last_error = api_err
                continue
            except Exception as exc:
                sanitized_err = redact_secrets(str(exc))
                logger.warning("Gemini generation error with model %s: %s", model, sanitized_err)
                last_error = exc
                continue

        logger.warning(
            "Gemini generation failed (%s); reverting to local deterministic fallback.",
            redact_secrets(str(last_error)) if last_error else "unknown error",
        )
        output = self._deterministic_fallback(message, context_term)
        output.elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)
        return output


# Singleton instance
gemini_service = GeminiService()
