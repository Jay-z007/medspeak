# MedSpeak

MedSpeak is a voice-first medical terminology pronunciation tutor powered by Gemini, Rime TTS, and speech recognition.

---

## What it does

- **Talk using your microphone** — Practice clinical pronunciation naturally in a hands-free voice loop.
- **Ask how to pronounce medical terms** — Get accurate syllabic breakdowns with primary stress indicated and International Phonetic Alphabet (IPA) transcriptions.
- **Ask what a term means** — Hear and read clear, concise clinical definitions and classifications.
- **Have normal conversations** — Greet MedSpeak, ask questions about what it can do, and receive helpful educational guidance.
- **Ask it to repeat or speak slower** — Say *"Say it slower"* to hear terms spoken at 0.7x speed, or *"Repeat that"* to hear it again.
- **Type instead of speaking** — Full text-based chat interface is always available.

> **Educational Disclaimer**: MedSpeak is an educational pronunciation and terminology tutor. It does not provide medical diagnoses, treatment plans, prescriptions, or clinical medical advice.

---

## How it works

```
User
  ↓
Speech-to-Text
  ↓
Gemini — conversation + intent
  ↓
MedSpeak — terminology + pronunciation
  ↓
Rime TTS — voice
  ↓
User
```

- **Speech-to-Text** — converts the user's spoken audio into text.
- **Gemini** — understands the conversation context and identifies what the user wants.
- **MedSpeak** — resolves terminology, manages pronunciation routing, maintains context, and ensures medical safety boundaries.
- **Rime TTS** — converts the final response into natural, human-grade speech.

---

## Features

- Voice conversation with automatic speech detection (VAD)
- Hands-free conversational loop
- Text conversation option
- Medical terminology pronunciation guidance
- 16 built-in verified clinical terms with exact IPA and syllable stress
- Dynamic Gemini fallback pronunciation for arbitrary medical terms
- Contextual follow-ups: *"Say it slower"* (0.7x speed) and *"Repeat that"*
- Speech-to-Text phonetic recovery (e.g. *"a set of amino phen"* → *acetaminophen*)
- Voice interruption and barge-in support
- High-fidelity Rime TTS audio synthesis
- Monochromatic, responsive fintech-inspired interface

---

## Tech Stack

- **Frontend**: Next.js 15, React 19, Tailwind CSS, Web Audio API
- **Backend**: FastAPI, Python 3.10+, Uvicorn, Pydantic
- **Conversational Brain**: Google Gemini API (`gemini-3.8-flash`) via `google-genai` SDK
- **Speech Synthesis**: Rime Cloud TTS API (`coda` / `astra`)
- **Speech Recognition**: Faster-Whisper (local on-device STT)

---

## Requirements

- **Node.js** 18.x or higher
- **Python** 3.10 or higher
- A **Google Gemini API key** ([Google AI Studio](https://aistudio.google.com/))
- A **Rime API key** ([Rime](https://rime.ai/))

---

## Setup

### 1. Clone the repository

```bash
git clone <REPOSITORY_URL>
cd medspeak
```

### 2. Configure and run the backend

```bash
cd backend

# Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate    # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Create your environment file
cp ../.env.example .env
```

Open `backend/.env` and add your API keys:

```env
GEMINI_API_KEY=your_gemini_api_key_here
RIME_API_KEY=your_rime_api_key_here
```

Start the FastAPI server:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

The backend is running at `http://localhost:8000`. You can verify health at `http://localhost:8000/health`.

### 3. Configure and run the frontend

In a new terminal window:

```bash
cd frontend

# Install dependencies
npm install

# Start the development server
npm run dev
```

Open `http://localhost:3000` in your browser.

---

## How to use it

Once the app is running in your browser:

1. **Tap the Microphone button** (or click Start Conversation) and allow microphone access.
2. **Try saying:**
   - *"How do I pronounce tachycardia?"*
   - *"Say it slower."*
   - *"What does acetaminophen mean?"*
   - *"How do I pronounce bronchoscopy?"*
   - *"What can you do?"*
3. MedSpeak will transcribe your speech, determine the intended clinical word, display syllables and IPA, and speak the response back automatically.

---

## License

MIT License. Designed and built for educational medical pronunciation practice.
