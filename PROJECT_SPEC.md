# MedSpeak — Project Specification

## 1. Product

Build a production-quality hackathon web application called MedSpeak.

MedSpeak is a voice-first medical terminology pronunciation tutor.

The user can:

1. Search/type a medical term.
2. Ask how to pronounce it.
3. Hear the pronunciation using Rime TTS.
4. Ask for a slower pronunciation.
5. Ask for repetition.
6. Ask for syllable breakdown.
7. Practice saying the term.
8. Receive a pronunciation similarity score.
9. Interrupt the assistant while it is speaking.
10. Correct/change their request during speech.
11. Handle misspelled/unknown terminology safely.

The product is NOT a medical diagnosis or treatment assistant.

It must never provide:
- diagnosis
- treatment recommendations
- prescriptions
- dosage recommendations
- patient-specific medical advice

It is strictly an educational pronunciation tool.

---

# 2. Critical Rime Requirement

Rime is the PRIMARY and DEFAULT TTS provider.

The normal judged application path MUST use Rime.

Architecture:

User
→ frontend
→ backend
→ terminology resolver
→ delivery controller
→ Rime
→ audio
→ browser

Rime API credentials must remain server-side.

Never expose:
- RIME_API_KEY
- backend secrets
- provider credentials

to the frontend.

Fallback TTS may exist, but:

1. Rime must be the default.
2. The UI must visibly indicate the active provider.
3. Fallback mode must be disclosed.
4. Fallback must never silently replace Rime.

The exact Rime model, speaker, language, endpoint, audio format and transport must come from environment configuration.

Do not invent a Rime model configuration.

Create a Rime preflight script that verifies:

- API key exists
- endpoint works
- model exists
- speaker exists
- language works
- selected audio format works
- synthesis succeeds
- returned audio is playable

---

# 3. Core User Experience

Main screen:

Large central voice interface.

Example:

"How do I pronounce hydroxychloroquine?"

Application responds:

Hydroxychloroquine

IPA:
...

Syllables:
hy-droxy-chlo-ro-quine

[▶ Hear pronunciation]
[🐢 Slow]
[↻ Repeat]
[Split syllables]
[🎙 Practice]

The user can also speak commands:

"Slower."

"Again."

"Break it down."

"My turn."

"Stop."

---

# 4. Voice States

Implement explicit session states:

idle
listening
processing
speaking
interrupted
error

The UI must visibly display the current state.

Example:

Listening...
Processing...
Speaking...
Interrupted
Ready

---

# 5. Interruption

This is a critical feature.

When the assistant is speaking and the user says:

"WAIT — slower."

the current audio must stop immediately.

Implement generation IDs.

Every request/audio stream/tool result gets:

generation_id

When an interruption occurs:

1. increment generation
2. immediately stop browser playback
3. invalidate old audio
4. invalidate stale tool results
5. preserve current terminology context
6. process the new instruction
7. synthesize the new response
8. play only the newest generation

Old audio MUST NOT resume after interruption.

---

# 6. Terminology Engine

Do NOT let an LLM invent medical pronunciations.

Create a terminology database.

Schema:

medical_terms:

id
canonical_name
category
ipa
phonemes
syllables
stress_pattern
source
source_version
verified

term_aliases:

id
term_id
alias

Resolver behavior:

Exact match
→ return term

Alias match
→ return term

Fuzzy match
→ show suggestions

Unknown term
→ ask user to clarify

Never fabricate pronunciation data.

Use RapidFuzz for fuzzy matching.

---

# 7. Intent Router

Support:

pronounce
slow_down
repeat
syllables
practice
stop
unknown

Simple commands should be deterministic.

Examples:

"slower"
"slow down"
→ slow_down

"again"
"repeat that"
→ repeat

"break it down"
"syllables"
→ syllables

"practice"
"my turn"
→ practice

"stop"
"wait"
→ stop

Do not unnecessarily call an LLM for simple commands.

---

# 8. Delivery Controller

Create a delivery controller.

It decides:

text
speed
repetition
syllable formatting

Example:

normal:

"Hydroxychloroquine."

slow:

"Hydroxychloroquine."

with slower Rime configuration

repeat:

"Hydroxychloroquine. Hydroxychloroquine."

syllables:

"hy. droxy. chlo. ro. quine."

IMPORTANT:

Rime speed semantics differ by model.

Do not assume a universal speedAlpha meaning.

The selected production model must be tested and the correct configuration documented.

---

# 9. Rime Service

Create:

backend/app/services/rime.py

It should provide:

synthesize()
stream()
health_check()

It must:

- use async HTTP/WebSocket
- read credentials from environment
- support the selected production configuration
- return audio
- expose timing information
- handle timeout
- handle provider errors
- retry safely when appropriate

Never hardcode secrets.

---

# 10. Speech Recognition

Implement browser microphone recording.

Frontend:

MediaRecorder/Web Audio API

Backend:

speech-to-text service.

Prefer faster-whisper for initial implementation.

Pipeline:

microphone
→ audio
→ STT
→ transcript
→ intent router

Do not require a perfect realtime STT system for the first implementation.

A reliable push-to-talk flow is acceptable initially.

---

# 11. Practice Mode

Practice flow:

1. Show target term.
2. Play correct Rime pronunciation.
3. User records themselves.
4. STT transcribes their speech.
5. Compare target with transcription.
6. Calculate similarity.
7. Display score.
8. Give concise feedback.

Call the score:

"Pronunciation similarity"

NOT:

"Medical accuracy"

Initial scoring can use RapidFuzz.

Example:

90+:
Excellent

75–89:
Very close

50–74:
Getting there — try again slowly

<50:
Let's try it once more

Clearly label this as a prototype pronunciation estimate.

---

# 12. Safety

MedSpeak must not become a medical assistant.

If the user asks:

"What dose should I take?"

respond:

"I'm MedSpeak, a pronunciation tutor. I can help you pronounce medical terms, but I can't provide treatment or dosage advice."

If user asks diagnosis:

"I'm focused on pronunciation and medical terminology, not diagnosis."

Never send patient information to the system.

Do not store PHI.

---

# 13. UI

Design should feel like:

modern
premium
medical
minimal
voice-first

Avoid:
- generic dashboard UI
- huge tables
- unnecessary menus
- corporate hospital aesthetic

Main interface should prioritize:

medical term
pronunciation
audio
practice
voice interaction

Include:

Provider badge:
"Voice: Rime"

Session status

Transcript

Pronunciation card

Practice score

Speed control

Replay

Interrupt button

---

# 14. Accessibility

Support:

keyboard navigation
ARIA labels
captions/transcripts
visible focus states
high contrast
text-based interaction
audio controls

Never make voice the only way to operate the application.

---

# 15. Metrics

Track:

user_turn_end
stt_complete
intent_complete
resolver_complete
rime_request_start
first_audio_received
playback_start
audio_complete

Calculate:

TTFA:
first_audio_received - user_turn_end

E2E:
audio_complete - user_turn_end

Track:

warm requests
cold requests
cache hits
cache misses
Rime failures
interruptions
successful recoveries

Do not claim performance numbers until measured.

---

# 16. Cache

Cache generated Rime audio.

Cache key should include:

model
speaker
language
speed
text
audio format

Do not allow cache to hide whether Rime generated the audio.

The provider badge must remain:

"Voice: Rime"

when the audio originated from Rime.

---

# 17. API

Implement:

GET /health

POST /api/pronounce

POST /api/practice

POST /api/rime/preflight

WebSocket:

/ws/session/{session_id}

Events:

user_text
user_audio
interrupt
assistant_text
audio_start
audio_chunk
audio_end
error
state_change

---

# 18. Repository

Create:

frontend/
backend/
data/
scripts/
tests/
docs/

Backend:

backend/app/
backend/app/api/
backend/app/services/
backend/app/core/
backend/app/models/

Services:

rime.py
stt.py
terminology.py
pronunciation.py
evaluator.py
intent.py
delivery.py
safety.py
cache.py
metrics.py

Frontend:

components/
hooks/
lib/
types/

---

# 19. Testing

Create automated tests for:

terminology exact match
terminology aliases
terminology fuzzy matching
unknown terminology
intent detection
slow command
repeat command
syllable command
practice scoring
Rime configuration validation
Rime failure
session generation
interruption
stale audio rejection
safety prompts

Most importantly test:

START generation 1
→ begin speaking
→ interrupt
→ generation 2
→ old generation audio must be rejected

---

# 20. Failure Handling

If Rime fails:

UI must show:

"Rime unavailable"

If fallback is configured:

"Fallback voice active"

Never silently pretend the fallback is Rime.

If STT fails:

"Couldn't hear that. Try again."

If terminology is unknown:

"I couldn't verify that term. Did you mean..."

If audio fails:

"Audio playback failed. Try replaying."

---

# 21. Demo Terms

Seed the database with representative terms including:

acetaminophen
ibuprofen
amoxicillin
azithromycin
metformin
hydroxychloroquine
clopidogrel
dexamethasone
levothyroxine
sternocleidomastoid
epiglottis
esophagus
electroencephalography
echocardiography
MRI
ECG
COPD
SARS-CoV-2

Include numbers:

10 mg
0.5 mL
2.5 mg

---

# 22. RIME_EVIDENCE.md

Create:

RIME_EVIDENCE.md

It must document:

Provider
Model
Speaker
Language
Endpoint
Audio format
Transport

Acceptance test

Interruption test

Failure test

Measured latency

Known limitations

---

# 23. README

README must contain:

Problem
Solution
Architecture
Setup
Environment variables
Rime configuration
Running locally
Terminology data
Safety
Interruption architecture
Evaluation
Failure behavior
Limitations
Demo instructions

---

# 24. Environment

Create:

.env.example

with placeholders only.

Never commit .env.

Required variables:

RIME_API_KEY
RIME_API_URL
RIME_MODEL_ID
RIME_SPEAKER
RIME_LANGUAGE
RIME_AUDIO_FORMAT
RIME_SAMPLING_RATE

STT configuration

LLM configuration if needed

DATABASE_URL

---

# 25. Development Strategy

Build in this order:

PHASE 1
Project scaffolding

PHASE 2
Rime preflight

PHASE 3
Single pronunciation request

PHASE 4
Terminology database

PHASE 5
Pronunciation UI

PHASE 6
Slow/repeat/syllable controls

PHASE 7
Voice input

PHASE 8
WebSocket session

PHASE 9
Interruption and generation fencing

PHASE 10
Practice mode

PHASE 11
Metrics

PHASE 12
Failure handling

PHASE 13
Testing

PHASE 14
Polish

PHASE 15
README + RIME_EVIDENCE

PHASE 16
Production build

---

# 26. Coding Rules

Do not create fake implementations.

Do not leave TODOs for core functionality.

Do not use mocked Rime responses once Rime credentials are configured.

Do not hardcode API keys.

Do not fabricate medical pronunciation data.

Do not fabricate Rime configuration.

Do not build unnecessary features.

After every phase:

1. run tests
2. run type checking
3. run lint
4. verify application starts
5. fix errors
6. continue

If a dependency/API is uncertain, inspect its current official documentation before implementing it.

Prefer small, testable modules.

Keep the application runnable throughout development.

---

# 27. Definition of Done

The project is DONE only when:

- frontend starts
- backend starts
- Rime preflight passes
- user can enter medical term
- real Rime audio plays
- slow works
- repeat works
- syllable mode works
- microphone input works
- STT works
- practice mode works
- similarity score works
- interruption works
- stale audio is rejected
- unknown term handling works
- safety handling works
- metrics work
- tests pass
- production build succeeds
- README exists
- RIME_EVIDENCE.md exists
- no secrets are committed