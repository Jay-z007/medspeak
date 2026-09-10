import { HealthStatus } from "@/types/health";
import { ChatResponse, VoiceChatResponse } from "@/types/chat";

function getBaseUrl(): string {
  const rawBase = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
  return rawBase.replace(/\/+$/, "");
}

export async function fetchHealth(): Promise<HealthStatus> {
  const configuredBase = getBaseUrl();

  const endpoints = [
    `${configuredBase}/health`,
    "/api/backend/health",
  ];

  let lastError: Error | null = null;

  for (const url of endpoints) {
    try {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 10000);

      const response = await fetch(url, {
        method: "GET",
        headers: {
          "Content-Type": "application/json",
          Accept: "application/json",
        },
        cache: "no-store",
        signal: controller.signal,
      });

      clearTimeout(timeoutId);

      if (response.ok) {
        const data = (await response.json()) as HealthStatus;
        if (data && typeof data === "object" && "status" in data) {
          return data;
        }
      }
      lastError = new Error(`Health check returned HTTP ${response.status}`);
    } catch (err: unknown) {
      lastError =
        err instanceof Error ? err : new Error(`Failed to reach ${url}`);
    }
  }

  throw lastError || new Error("FastAPI backend is offline or unreachable");
}

export async function sendChatMessage(
  message: string,
  synthesizeAudio: boolean = true,
  speed: number = 1.0,
  contextTerm?: string | null,
): Promise<ChatResponse> {
  const configuredBase = getBaseUrl();

  const endpoints = [
    `${configuredBase}/api/chat`,
    "/api/backend/api/chat",
  ];

  let lastError: Error | null = null;

  for (const url of endpoints) {
    try {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 25000);

      const response = await fetch(url, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Accept: "application/json",
        },
        body: JSON.stringify({
          message,
          synthesize_audio: synthesizeAudio,
          speed,
          context_term: contextTerm,
        }),
        signal: controller.signal,
      });

      clearTimeout(timeoutId);

      if (response.ok) {
        const data = (await response.json()) as ChatResponse;
        if (data && typeof data === "object" && "reply" in data) {
          return data;
        }
      }

      const errorText = await response.text();
      lastError = new Error(`Chat API error (HTTP ${response.status}): ${errorText}`);
    } catch (err: unknown) {
      lastError =
        err instanceof Error ? err : new Error(`Failed to connect to ${url}`);
    }
  }

  throw lastError || new Error("Failed to reach MedSpeak chat service");
}

export async function sendVoiceMessage(
  audioBlob: Blob,
  speed: number = 1.0,
  contextTerm?: string | null,
): Promise<VoiceChatResponse> {
  const configuredBase = getBaseUrl();

  const endpoints = [
    `${configuredBase}/api/chat/voice`,
    "/api/backend/api/chat/voice",
  ];

  const formData = new FormData();
  formData.append("audio", audioBlob, "mic_recording.webm");
  formData.append("speed", speed.toString());
  if (contextTerm) {
    formData.append("context_term", contextTerm);
  }

  let lastError: Error | null = null;

  for (const url of endpoints) {
    try {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 30000);

      const response = await fetch(url, {
        method: "POST",
        body: formData,
        signal: controller.signal,
      });

      clearTimeout(timeoutId);

      if (response.ok) {
        const data = (await response.json()) as VoiceChatResponse;
        if (data && typeof data === "object" && "reply" in data) {
          return data;
        }
      }

      const errorText = await response.text();
      lastError = new Error(`Voice API error (HTTP ${response.status}): ${errorText}`);
    } catch (err: unknown) {
      lastError =
        err instanceof Error ? err : new Error(`Failed to connect to ${url}`);
    }
  }

  throw lastError || new Error("Failed to reach MedSpeak voice service");
}

export async function synthesizeAudio(
  text: string,
  speed: number = 1.0,
): Promise<string> {
  const configuredBase = getBaseUrl();

  const endpoints = [
    `${configuredBase}/api/chat/synthesize`,
    "/api/backend/api/chat/synthesize",
  ];

  let lastError: Error | null = null;

  for (const url of endpoints) {
    try {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 20000);

      const response = await fetch(url, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ text, speed }),
        signal: controller.signal,
      });

      clearTimeout(timeoutId);

      if (response.ok) {
        const blob = await response.blob();
        return URL.createObjectURL(blob);
      }

      const errorText = await response.text();
      lastError = new Error(`Synthesis API error (HTTP ${response.status}): ${errorText}`);
    } catch (err: unknown) {
      lastError =
        err instanceof Error ? err : new Error(`Failed to connect to ${url}`);
    }
  }

  throw lastError || new Error("Failed to reach MedSpeak synthesis service");
}
