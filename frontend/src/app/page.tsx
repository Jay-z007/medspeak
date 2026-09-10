"use client";

import React, { useState, useRef, useEffect } from "react";
import { VoiceVisualizer } from "@/components/VoiceVisualizer";
import { useVoiceConversation } from "@/hooks/useVoiceConversation";
import { useHealth } from "@/hooks/useHealth";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  Mic,
  Volume2,
  RotateCcw,
  Sparkles,
  Keyboard,
  ArrowRight,
  Trash2,
  ChevronDown,
  ChevronUp,
} from "lucide-react";

const SUGGESTED_TERMS = [
  "How do I pronounce hydroxychloroquine?",
  "Break down tachycardia",
  "How do I say omeprazole?",
  "Can you say it slower?",
];

function FormattedContent({ text }: { text: string }) {
  const lines = text.split("\n");

  return (
    <div className="space-y-1.5 text-xs sm:text-sm leading-relaxed text-zinc-300">
      {lines.map((line, idx) => {
        const trimmed = line.trim();
        if (!trimmed) {
          return <div key={idx} className="h-1" />;
        }

        const isBullet = trimmed.startsWith("- ") || trimmed.startsWith("* ");
        const content = isBullet ? trimmed.slice(2) : line;
        const parts = content.split(/(\*\*.*?\*\*|\*.*?\*)/g);

        const renderedLine = parts.map((part, pIdx) => {
          if (part.startsWith("**") && part.endsWith("**")) {
            return (
              <strong key={pIdx} className="font-semibold text-white">
                {part.slice(2, -2)}
              </strong>
            );
          }
          if (part.startsWith("*") && part.endsWith("*")) {
            return (
              <em key={pIdx} className="italic text-zinc-300">
                {part.slice(1, -1)}
              </em>
            );
          }
          return part;
        });

        if (isBullet) {
          return (
            <div key={idx} className="flex items-start gap-2 pl-2">
              <span className="text-zinc-500 mt-1 select-none text-[9px]">■</span>
              <span>{renderedLine}</span>
            </div>
          );
        }

        return <p key={idx}>{renderedLine}</p>;
      })}
    </div>
  );
}

export default function Home() {
  const { health } = useHealth(5000);
  const {
    state,
    isActivated,
    audioLevel,
    messages,
    activeTerm,
    statusText,
    liveTranscript,
    error,
    activateVoice,
    sendTextMessage,
    replayAudio,
    clearChat,
  } = useVoiceConversation();

  const [showTextInput, setShowTextInput] = useState<boolean>(false);
  const [textInputValue, setTextInputValue] = useState<string>("");
  const [showTranscript, setShowTranscript] = useState<boolean>(true);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, liveTranscript]);

  const handleTextSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!textInputValue.trim()) return;
    sendTextMessage(textInputValue);
    setTextInputValue("");
  };

  const isRimeConnected = !!health;

  return (
    <main className="min-h-screen bg-[#09090b] text-zinc-100 flex flex-col antialiased selection:bg-zinc-800 selection:text-white relative overflow-x-hidden">
      {/* Ambient Monochromatic Radial Depth */}
      <div
        className="pointer-events-none fixed inset-0 z-0 opacity-40"
        style={{
          background:
            "radial-gradient(circle at 50% 28%, rgba(255, 255, 255, 0.05) 0%, rgba(255, 255, 255, 0.015) 35%, rgba(0, 0, 0, 0) 70%)",
        }}
      />

      {/* Top Header Navigation */}
      <header className="relative z-10 w-full border-b border-white/[0.06] bg-[#09090b]/80 backdrop-blur-xl px-5 sm:px-8 py-3.5 flex items-center justify-between">
        {/* Brand & System Metadata */}
        <div className="flex items-center gap-3">
          <div className="w-7 h-7 rounded-lg bg-zinc-900 border border-white/[0.12] flex items-center justify-center text-white shadow-sm font-semibold text-xs tracking-tight">
            M
          </div>
          <div className="flex items-center gap-2">
            <span className="text-xs font-semibold tracking-wider text-white uppercase font-mono">
              MedSpeak
            </span>
            <span className="text-[10px] text-zinc-500 font-mono hidden sm:inline-block">
              {"// Clinical S2S"}
            </span>
          </div>
        </div>

        {/* Status Indicators & Session Controls */}
        <div className="flex items-center gap-2.5 sm:gap-3">
          {/* Rime Voice Status Pill */}
          <div
            className="flex items-center gap-2 px-2.5 py-1 rounded-full bg-zinc-950/90 border border-white/[0.07] text-[10px] font-mono tracking-wide text-zinc-400"
            title={isRimeConnected ? "Rime Cloud Voice Engine Connected" : "Connecting to voice service..."}
          >
            <span
              className={`w-1.5 h-1.5 rounded-full ${
                isRimeConnected ? "bg-emerald-400 shadow-[0_0_8px_rgba(52,211,153,0.6)]" : "bg-zinc-600"
              }`}
            />
            <span className="uppercase text-zinc-300">Rime Voice</span>
            <span className="text-zinc-600">•</span>
            <span className="hidden sm:inline text-zinc-400">
              {isRimeConnected ? "Online" : "Offline"}
            </span>
          </div>

          {messages.length > 0 && (
            <Button
              variant="ghost"
              size="sm"
              onClick={clearChat}
              className="text-zinc-400 hover:text-zinc-200 text-xs gap-1 h-7 px-2"
              title="Reset conversation session"
            >
              <Trash2 className="w-3 h-3" />
              <span className="hidden sm:inline">Reset</span>
            </Button>
          )}
        </div>
      </header>

      {/* Main Experience Viewport */}
      <div className="relative z-10 flex-1 max-w-4xl w-full mx-auto px-4 sm:px-6 py-6 flex flex-col justify-between">
        {/* Hero Section: Central 3D Monochromatic Orb */}
        <section className="flex-1 flex flex-col items-center justify-center my-auto text-center py-6 sm:py-10 space-y-6 sm:space-y-8">
          {/* The Living 3D Voice Visualizer Orb */}
          <div className="relative group">
            <VoiceVisualizer
              state={state}
              audioLevel={audioLevel}
              size={240}
              onClick={!isActivated ? activateVoice : undefined}
            />

            {/* Tap Activation Overlay on Initial State */}
            {!isActivated && (
              <button
                onClick={activateVoice}
                className="absolute inset-0 z-20 flex flex-col items-center justify-center rounded-full bg-black/40 hover:bg-black/20 backdrop-blur-[2px] transition-all cursor-pointer group-hover:scale-105"
                aria-label="Start Voice Conversation"
              >
                <div className="px-4 py-2 rounded-full bg-zinc-900/90 border border-white/20 text-white text-xs font-mono tracking-wider uppercase shadow-xl flex items-center gap-2 group-hover:border-white/40 transition-colors">
                  <Mic className="w-3.5 h-3.5 text-zinc-300" />
                  <span>Start Conversation</span>
                </div>
              </button>
            )}
          </div>

          {/* Real-time State & Transcript Indicators */}
          <div className="space-y-2 max-w-md mx-auto">
            <h2 className="text-sm sm:text-base font-mono uppercase tracking-widest text-zinc-200 font-medium">
              {statusText}
            </h2>

            {/* Context Term Badge */}
            {activeTerm && (
              <div className="flex items-center justify-center gap-1.5 pt-0.5">
                <span className="text-[10px] uppercase font-mono tracking-wider text-zinc-500">
                  Target:
                </span>
                <span className="px-2 py-0.5 rounded text-[11px] font-mono bg-zinc-900 border border-white/[0.08] text-zinc-200">
                  {activeTerm}
                </span>
              </div>
            )}

            {/* Real-time Utterance / Processing Preview */}
            {liveTranscript && (
              <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-zinc-900/90 border border-white/[0.1] text-xs font-mono text-zinc-300 animate-fade-in-up">
                <span className="w-1.5 h-1.5 rounded-full bg-zinc-300 animate-pulse" />
                <span>{liveTranscript}</span>
              </div>
            )}

            {error && (
              <p className="text-xs font-mono text-rose-400 bg-rose-950/20 border border-rose-900/40 rounded-lg p-2 max-w-xs mx-auto">
                {error}
              </p>
            )}
          </div>

          {/* Quick-Prompt Suggestions (Hidden after conversation starts) */}
          {messages.length === 0 && isActivated && (
            <div className="w-full max-w-sm space-y-2 pt-2 animate-fade-in-up">
              <span className="text-[10px] font-mono uppercase tracking-widest text-zinc-500 block">
                Suggested Voice Queries
              </span>
              <div className="grid gap-1.5">
                {SUGGESTED_TERMS.map((term, idx) => (
                  <button
                    key={idx}
                    onClick={() => sendTextMessage(term)}
                    className="w-full text-left px-3.5 py-2.5 rounded-lg bg-zinc-950/60 hover:bg-zinc-900/80 border border-white/[0.05] hover:border-white/[0.15] text-zinc-300 hover:text-white text-xs font-mono transition-all flex items-center justify-between group"
                  >
                    <span>{term}</span>
                    <ArrowRight className="w-3 h-3 text-zinc-600 group-hover:text-zinc-300 transition-colors" />
                  </button>
                ))}
              </div>
            </div>
          )}
        </section>

        {/* Secondary Conversation Transcript & Text Controls */}
        <section className="space-y-3 pt-4">
          {/* Conversation Log Collapsible Drawer */}
          {messages.length > 0 && (
            <Card className="bg-zinc-950/80 border-white/[0.06] overflow-hidden transition-all duration-200">
              <div
                onClick={() => setShowTranscript((prev) => !prev)}
                className="px-4 py-2.5 border-b border-white/[0.05] bg-zinc-900/40 flex items-center justify-between cursor-pointer hover:bg-zinc-900/60 transition-colors"
              >
                <div className="flex items-center gap-2">
                  <span className="text-[10px] font-mono uppercase tracking-widest text-zinc-400 font-medium">
                    Conversation Transcript
                  </span>
                  <Badge variant="status" className="text-[9px]">
                    {messages.length} Turns
                  </Badge>
                </div>
                <button
                  aria-label={showTranscript ? "Collapse transcript" : "Expand transcript"}
                  className="text-zinc-500 hover:text-zinc-300"
                >
                  {showTranscript ? (
                    <ChevronDown className="w-3.5 h-3.5" />
                  ) : (
                    <ChevronUp className="w-3.5 h-3.5" />
                  )}
                </button>
              </div>

              {showTranscript && (
                <CardContent className="p-0">
                  <ScrollArea className="max-h-[300px] p-4 space-y-4">
                    {messages.map((msg) => (
                      <div
                        key={msg.id}
                        className={`flex flex-col mb-3 animate-fade-in-up ${
                          msg.role === "user" ? "items-end" : "items-start"
                        }`}
                      >
                        <div
                          className={`rounded-xl p-3.5 max-w-[92%] sm:max-w-[85%] text-xs leading-relaxed border ${
                            msg.role === "user"
                              ? "bg-zinc-900 border-white/[0.1] text-zinc-100"
                              : "bg-black/80 border-white/[0.06] text-zinc-200"
                          }`}
                        >
                          {/* Turn Metadata Header */}
                          <div className="flex items-center justify-between gap-3 pb-2 mb-2 border-b border-white/[0.05] text-[10px] font-mono text-zinc-500">
                            <span className="uppercase tracking-wider font-semibold text-zinc-400 flex items-center gap-1.5">
                              {msg.role === "user" ? (
                                <>
                                  <Mic className="w-2.5 h-2.5" />
                                  <span>{msg.isVoice ? "Voice Input" : "User"}</span>
                                </>
                              ) : (
                                <>
                                  <Sparkles className="w-2.5 h-2.5" />
                                  <span>MedSpeak • Rime TTS</span>
                                  {msg.pronunciationSource === "verified_database" && (
                                    <span className="px-1.5 py-0.5 rounded bg-emerald-950/40 border border-emerald-500/25 text-emerald-400 text-[9px] font-mono capitalize">
                                      Verified term
                                    </span>
                                  )}
                                  {msg.pronunciationSource === "gemini_fallback" && (
                                    <span className="px-1.5 py-0.5 rounded bg-amber-950/40 border border-amber-500/25 text-amber-300 text-[9px] font-mono capitalize">
                                      AI pronunciation
                                    </span>
                                  )}
                                </>
                              )}
                            </span>
                            <div className="flex items-center gap-2">
                              {msg.term && (
                                <span className="text-zinc-400 font-mono">[{msg.term}]</span>
                              )}
                              {msg.timing && msg.timing.total_response_ms > 0 && (
                                <span
                                  className="text-[9px] text-zinc-500 font-mono"
                                  title={`Routing: ${msg.timing.routing_ms}ms | Gemini: ${msg.timing.gemini_ms}ms | Rime: ${msg.timing.rime_ms}ms`}
                                >
                                  {Math.round(msg.timing.total_response_ms)}ms
                                </span>
                              )}
                            </div>
                          </div>


                          {/* Message Body */}
                          {msg.role === "assistant" ? (
                            <FormattedContent text={msg.content} />
                          ) : (
                            <p className="font-mono text-zinc-200">{msg.content}</p>
                          )}

                          {/* Assistant Replay Actions */}
                          {msg.role === "assistant" && (
                            <div className="mt-2.5 pt-2 border-t border-white/[0.05] flex items-center justify-between gap-2">
                              <div className="flex items-center gap-1.5">
                                <Button
                                  variant="subtle"
                                  size="sm"
                                  onClick={() => replayAudio(msg, 1.0)}
                                  className="h-6 px-2 text-[10px] gap-1 font-mono"
                                  title="Replay pronunciation speech"
                                >
                                  <Volume2 className="w-2.5 h-2.5" />
                                  <span>Replay</span>
                                </Button>
                                <Button
                                  variant="subtle"
                                  size="sm"
                                  onClick={() => replayAudio(msg, 0.7)}
                                  className="h-6 px-2 text-[10px] gap-1 font-mono"
                                  title="Listen slowly (0.7x)"
                                >
                                  <span>🐢 Slower</span>
                                </Button>
                                <Button
                                  variant="subtle"
                                  size="sm"
                                  onClick={() => replayAudio(msg, 1.0)}
                                  className="h-6 px-2 text-[10px] gap-1 font-mono"
                                  title="Repeat pronunciation"
                                >
                                  <RotateCcw className="w-2.5 h-2.5" />
                                  <span>Again</span>
                                </Button>
                              </div>
                            </div>
                          )}
                        </div>
                      </div>
                    ))}
                    <div ref={messagesEndRef} />
                  </ScrollArea>
                </CardContent>
              )}
            </Card>
          )}

          {/* Secondary Text Input Affordance (Accessible Fallback) */}
          <div className="flex flex-col items-center">
            {!showTextInput ? (
              <button
                onClick={() => setShowTextInput(true)}
                className="text-[11px] font-mono text-zinc-500 hover:text-zinc-300 transition-colors flex items-center gap-1 py-1"
              >
                <Keyboard className="w-3 h-3" />
                <span>Type instead</span>
              </button>
            ) : (
              <form
                onSubmit={handleTextSubmit}
                className="w-full max-w-lg flex items-center gap-2 bg-zinc-950 border border-white/[0.08] rounded-lg p-1.5 animate-fade-in-up"
              >
                <input
                  type="text"
                  value={textInputValue}
                  onChange={(e) => setTextInputValue(e.target.value)}
                  placeholder="Ask pronunciation or type 'slower'..."
                  className="flex-1 bg-transparent px-3 py-1.5 text-xs font-mono text-white placeholder:text-zinc-600 focus:outline-none"
                />
                <Button type="submit" size="sm" variant="default" className="h-7 px-3 text-[11px]">
                  Send
                </Button>
                <button
                  type="button"
                  onClick={() => setShowTextInput(false)}
                  className="text-xs text-zinc-500 hover:text-zinc-300 px-2"
                >
                  ✕
                </button>
              </form>
            )}
          </div>

          <Separator className="bg-white/[0.04]" />

          {/* Bottom Precision Metadata Footer */}
          <footer className="flex items-center justify-between text-[10px] font-mono text-zinc-600 px-1">
            <span>MedSpeak Speech-to-Speech Tutor</span>
            <span>Rime Voice • Faster-Whisper VAD</span>
          </footer>
        </section>
      </div>
    </main>
  );
}
