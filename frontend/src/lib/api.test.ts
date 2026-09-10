import { describe, it, expect, vi, beforeEach } from "vitest";
import { fetchHealth } from "./api";

describe("fetchHealth API client", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("fetches health status successfully", async () => {
    const mockHealth = {
      status: "ok",
      app: "MedSpeak API",
      version: "0.1.0",
      environment: "development",
      primary_tts_provider: "rime",
      fallback_tts_enabled: false,
      phase_1_status: "ready",
    };

    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => mockHealth,
    });

    const data = await fetchHealth();
    expect(data.status).toBe("ok");
    expect(data.primary_tts_provider).toBe("rime");
    expect(data.phase_1_status).toBe("ready");
    expect(data.app).toBe("MedSpeak API");
  });

  it("throws an error when the health check endpoint returns an error status", async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 503,
    });

    await expect(fetchHealth()).rejects.toThrow("Health check returned HTTP 503");
  });
});

describe("sendChatMessage API client", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("handles verified terminology and timing metrics", async () => {
    const { sendChatMessage } = await import("./api");

    const mockResponse = {
      reply: "Tachycardia is pronounced TAK-i-KAR-dee-uh",
      intent: "pronounce",
      canonical_name: "tachycardia",
      pronunciation_source: "verified_database",
      audio_base64: "base64audio==",
      speed: 1.0,
      context_term: "tachycardia",
      timing: {
        gemini_ms: 120.5,
        routing_ms: 0.8,
        rime_ms: 310.2,
        total_response_ms: 431.5,
      },
    };

    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => mockResponse,
    });

    const result = await sendChatMessage("How do I pronounce tachycardia?");
    expect(result.reply).toContain("Tachycardia");
    expect(result.pronunciation_source).toBe("verified_database");
    expect(result.timing?.routing_ms).toBe(0.8);
    expect(result.timing?.rime_ms).toBe(310.2);
  });

  it("handles gemini_fallback for arbitrary clinical terms", async () => {
    const { sendChatMessage } = await import("./api");

    const mockResponse = {
      reply: "Bronchoscopy is pronounced brong-KOS-kuh-pee",
      intent: "pronounce",
      canonical_name: "bronchoscopy",
      pronunciation_source: "gemini_fallback",
      audio_base64: "base64fallback==",
      speed: 1.0,
      context_term: "bronchoscopy",
      timing: {
        gemini_ms: 450.0,
        routing_ms: 1.2,
        rime_ms: 290.0,
        total_response_ms: 741.2,
      },
    };

    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => mockResponse,
    });

    const result = await sendChatMessage("How do I pronounce bronchoscopy?");
    expect(result.pronunciation_source).toBe("gemini_fallback");
    expect(result.timing?.gemini_ms).toBe(450.0);
  });
});
