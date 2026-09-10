export interface TimingMetrics {
  stt_final_ms: number;
  gemini_ms: number;
  routing_ms: number;
  pronunciation_ms: number;
  rime_ms: number;
  total_response_ms: number;
}

export interface ChatRequest {
  message: string;
  synthesize_audio?: boolean;
  speed?: number;
  context_term?: string | null;
}

export interface ChatResponse {
  reply: string;
  intent: "pronounce" | "definition" | "safety_boundary" | "general" | "stt_failure" | "slow" | "repeat" | "syllables" | "pronunciation_general" | string;
  term?: string | null;
  provider: string;
  pronunciation_source?: "verified_database" | "gemini_fallback" | null;
  speech_text?: string | null;
  audio_base64?: string | null;
  audio_format?: string;
  timing?: TimingMetrics;
}

export interface VoiceChatResponse extends ChatResponse {
  transcript: string;
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: string;
  intent?: string;
  term?: string | null;
  provider?: string;
  pronunciationSource?: "verified_database" | "gemini_fallback" | null;
  speechText?: string | null;
  audioBase64?: string | null;
  audioFormat?: string;
  isVoice?: boolean;
  timing?: TimingMetrics;
}

