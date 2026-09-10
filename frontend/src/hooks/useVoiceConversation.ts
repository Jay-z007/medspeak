"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { ChatMessage } from "@/types/chat";
import { sendVoiceMessage, sendChatMessage, synthesizeAudio } from "@/lib/api";
import { OrbState } from "@/components/VoiceVisualizer";

export function useVoiceConversation() {
  const [state, setState] = useState<OrbState>("idle");
  const [isActivated, setIsActivated] = useState<boolean>(false);
  const [audioLevel, setAudioLevel] = useState<number>(0);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [activeTerm, setActiveTerm] = useState<string | null>(null);
  const [statusText, setStatusText] = useState<string>("Tap to start conversation");
  const [liveTranscript, setLiveTranscript] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Audio & Hardware References
  const audioContextRef = useRef<AudioContext | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const mediaStreamRef = useRef<MediaStream | null>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const currentAudioRef = useRef<HTMLAudioElement | null>(null);

  // VAD & State Tracking References
  const stateRef = useRef<OrbState>("idle");
  stateRef.current = state;

  const activeTermRef = useRef<string | null>(null);
  activeTermRef.current = activeTerm;

  const speechStartTimeRef = useRef<number>(0);
  const lastSpeechTimeRef = useRef<number>(0);
  const consecutiveSpeechFramesRef = useRef<number>(0);
  const generationIdRef = useRef<number>(0);
  const vadRafIdRef = useRef<number | null>(null);

  // Stop currently playing audio playback
  const stopAudioPlayback = useCallback(() => {
    if (currentAudioRef.current) {
      currentAudioRef.current.pause();
      currentAudioRef.current.currentTime = 0;
      currentAudioRef.current = null;
    }
    generationIdRef.current += 1;
  }, []);

  // Play synthesized response audio
  const playResponseAudio = useCallback((src: string) => {
    stopAudioPlayback();
    const generationId = generationIdRef.current;

    try {
      const audio = new Audio(src);
      currentAudioRef.current = audio;
      setState("medspeak_speaking");
      setStatusText("MedSpeak is speaking...");

      audio.onended = () => {
        if (generationIdRef.current === generationId) {
          currentAudioRef.current = null;
          setState("listening");
          setStatusText("I'm listening");
        }
      };

      audio.onerror = () => {
        if (generationIdRef.current === generationId) {
          console.warn("Audio playback error occurred");
          currentAudioRef.current = null;
          setState("listening");
          setStatusText("I'm listening");
        }
      };

      const playPromise = audio.play();
      if (playPromise !== undefined) {
        playPromise.catch((err) => {
          console.warn("Autoplay audio blocked or interrupted:", err);
          if (generationIdRef.current === generationId) {
            currentAudioRef.current = null;
            setState("listening");
            setStatusText("I'm listening");
          }
        });
      }
    } catch (err) {
      console.error("Audio playback failure:", err);
      setState("listening");
      setStatusText("I'm listening");
    }
  }, [stopAudioPlayback]);

  // Dispatch recorded user audio blob to backend STT & Rime TTS
  const processRecordedAudio = useCallback(async (audioBlob: Blob) => {
    if (audioBlob.size < 256) {
      // Discard silent or near-empty recording
      setState("listening");
      setStatusText("I'm listening");
      return;
    }

    setState("thinking");
    setStatusText("Understanding...");
    setLiveTranscript("Analyzing medical speech...");

    const requestGenId = ++generationIdRef.current;

    try {
      const response = await sendVoiceMessage(audioBlob, 1.0, activeTermRef.current);

      if (generationIdRef.current !== requestGenId) {
        // Obsoleted by user interruption
        return;
      }

      setLiveTranscript(null);

      if (response.intent === "stt_failure" || !response.transcript) {
        setStatusText("Couldn't hear clearly. Try again.");
        setTimeout(() => {
          if (generationIdRef.current === requestGenId) {
            setState("listening");
            setStatusText("I'm listening");
          }
        }, 1200);
        return;
      }

      // Update active target term
      if (response.term) {
        setActiveTerm(response.term);
      }

      // Append messages to conversation history
      const userMessage: ChatMessage = {
        id: `user-${Date.now()}`,
        role: "user",
        content: response.transcript,
        timestamp: new Date().toISOString(),
        isVoice: true,
      };

      const assistantMessage: ChatMessage = {
        id: `ai-${Date.now()}`,
        role: "assistant",
        content: response.reply,
        timestamp: new Date().toISOString(),
        intent: response.intent,
        term: response.term,
        provider: response.provider,
        pronunciationSource: response.pronunciation_source,
        speechText: response.speech_text,
        audioBase64: response.audio_base64,
        audioFormat: response.audio_format || "mp3",
        timing: response.timing,
      };

      setMessages((prev) => [...prev, userMessage, assistantMessage]);

      // Automatically play Rime voice response
      if (response.audio_base64) {
        const audioUrl = `data:audio/${response.audio_format || "mp3"};base64,${response.audio_base64}`;
        playResponseAudio(audioUrl);
      } else {
        setState("listening");
        setStatusText("I'm listening");
      }
    } catch (err: unknown) {
      console.error("Voice processing failed:", err);
      setLiveTranscript(null);
      setError("Failed to connect to MedSpeak voice service.");
      setState("listening");
      setStatusText("I'm listening");
    }
  }, [playResponseAudio]);

  // Voice Activity Detection (VAD) loop running on AnalyserNode
  const runVadLoop = useCallback(() => {
    const analyser = analyserRef.current;
    if (!analyser) return;

    const bufferLength = analyser.fftSize;
    const timeDomainData = new Uint8Array(bufferLength);

    const checkAudioFrame = () => {
      if (!analyserRef.current) return;

      analyser.getByteTimeDomainData(timeDomainData);

      // Compute Root Mean Square (RMS) volume normalized to 0.0 - 1.0
      let sumSquares = 0;
      for (let i = 0; i < bufferLength; i++) {
        const normalized = (timeDomainData[i] - 128) / 128;
        sumSquares += normalized * normalized;
      }
      const rawRms = Math.sqrt(sumSquares / bufferLength);
      const normalizedLevel = Math.min(1.0, rawRms * 3.8);
      setAudioLevel(normalizedLevel);

      const now = Date.now();
      const currentState = stateRef.current;

      // 1. In LISTENING state: Detect user speech initiation
      if (currentState === "listening") {
        if (rawRms > 0.038) {
          consecutiveSpeechFramesRef.current += 1;
          if (consecutiveSpeechFramesRef.current >= 3) {
            // User began speaking!
            speechStartTimeRef.current = now;
            lastSpeechTimeRef.current = now;
            setState("user_speaking");
            setStatusText("Hearing you...");
            setLiveTranscript("Listening to speech...");

            // Start recording audio
            audioChunksRef.current = [];
            if (mediaRecorderRef.current && mediaRecorderRef.current.state === "inactive") {
              try {
                mediaRecorderRef.current.start(100);
              } catch (e) {
                console.warn("MediaRecorder start warning:", e);
              }
            }
          }
        } else {
          consecutiveSpeechFramesRef.current = 0;
        }
      }

      // 2. In USER_SPEAKING state: Track utterance and detect silence conclusion
      else if (currentState === "user_speaking") {
        if (rawRms > 0.032) {
          lastSpeechTimeRef.current = now;
        }

        const elapsedSilence = now - lastSpeechTimeRef.current;
        const totalDuration = now - speechStartTimeRef.current;

        // Utterance complete if silence exceeds 950ms after at least 400ms speech
        if (elapsedSilence > 950 && totalDuration > 400) {
          if (mediaRecorderRef.current && mediaRecorderRef.current.state === "recording") {
            try {
              mediaRecorderRef.current.stop();
            } catch (e) {
              console.warn("MediaRecorder stop warning:", e);
            }
          }
        }
      }

      // 3. In MEDSPEAK_SPEAKING state: Interruption (Barge-in) Detection
      else if (currentState === "medspeak_speaking") {
        // Elevated threshold to avoid speaker playback bleed trigger
        if (rawRms > 0.075) {
          consecutiveSpeechFramesRef.current += 1;
          if (consecutiveSpeechFramesRef.current >= 4) {
            // User interrupted!
            stopAudioPlayback();
            speechStartTimeRef.current = now;
            lastSpeechTimeRef.current = now;
            setState("user_speaking");
            setStatusText("Hearing you...");
            setLiveTranscript("Listening to speech...");

            audioChunksRef.current = [];
            if (mediaRecorderRef.current && mediaRecorderRef.current.state === "inactive") {
              try {
                mediaRecorderRef.current.start(100);
              } catch (e) {
                console.warn("MediaRecorder start warning on barge-in:", e);
              }
            }
          }
        } else {
          consecutiveSpeechFramesRef.current = 0;
        }
      }

      vadRafIdRef.current = requestAnimationFrame(checkAudioFrame);
    };

    vadRafIdRef.current = requestAnimationFrame(checkAudioFrame);
  }, [stopAudioPlayback]);

  // Activate / Initialize Voice Conversation
  const activateVoice = useCallback(async () => {
    setError(null);
    stopAudioPlayback();

    try {
      // 1. Unlock / Initialize AudioContext
      const AudioContextClass =
        window.AudioContext ||
        (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
      const audioCtx = new AudioContextClass();
      if (audioCtx.state === "suspended") {
        await audioCtx.resume();
      }
      audioContextRef.current = audioCtx;

      // 2. Request user microphone
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        },
      });
      mediaStreamRef.current = stream;

      // 3. Setup AnalyserNode for VAD
      const analyser = audioCtx.createAnalyser();
      analyser.fftSize = 256;
      analyser.smoothingTimeConstant = 0.4;
      const source = audioCtx.createMediaStreamSource(stream);
      source.connect(analyser);
      analyserRef.current = analyser;

      // 4. Setup MediaRecorder for audio recording
      const mimeTypes = ["audio/webm;codecs=opus", "audio/webm", "audio/mp4", "audio/wav"];
      const supportedType = mimeTypes.find((type) => MediaRecorder.isTypeSupported(type)) || "";
      const options = supportedType ? { mimeType: supportedType } : undefined;
      const mediaRecorder = new MediaRecorder(stream, options);

      mediaRecorder.ondataavailable = (event: BlobEvent) => {
        if (event.data && event.data.size > 0) {
          audioChunksRef.current.push(event.data);
        }
      };

      mediaRecorder.onstop = () => {
        const audioBlob = new Blob(audioChunksRef.current, {
          type: supportedType || "audio/webm",
        });
        audioChunksRef.current = [];
        processRecordedAudio(audioBlob);
      };

      mediaRecorderRef.current = mediaRecorder;

      setIsActivated(true);
      setState("listening");
      setStatusText("I'm listening");

      // 5. Start continuous VAD loop
      runVadLoop();
    } catch (err: unknown) {
      console.error("Microphone activation failed:", err);
      setIsActivated(false);
      setState("error");
      if (err instanceof DOMException && err.name === "NotAllowedError") {
        setError("Microphone permission denied. Enable microphone access in browser settings.");
        setStatusText("Microphone permission denied");
      } else {
        setError("Could not access microphone.");
        setStatusText("Microphone unavailable");
      }
    }
  }, [processRecordedAudio, runVadLoop, stopAudioPlayback]);

  // Secondary text message sending (fallback / accessibility)
  const sendTextMessage = useCallback(async (text: string) => {
    const trimmed = text.trim();
    if (!trimmed) return;

    stopAudioPlayback();
    setError(null);
    setState("thinking");
    setStatusText("Understanding...");

    const userMessage: ChatMessage = {
      id: `user-${Date.now()}`,
      role: "user",
      content: trimmed,
      timestamp: new Date().toISOString(),
      isVoice: false,
    };

    setMessages((prev) => [...prev, userMessage]);
    const requestGenId = ++generationIdRef.current;

    try {
      const response = await sendChatMessage(trimmed, true, 1.0, activeTermRef.current);

      if (generationIdRef.current !== requestGenId) {
        return;
      }

      if (response.term) {
        setActiveTerm(response.term);
      }

      const assistantMessage: ChatMessage = {
        id: `ai-${Date.now()}`,
        role: "assistant",
        content: response.reply,
        timestamp: new Date().toISOString(),
        intent: response.intent,
        term: response.term,
        provider: response.provider,
        pronunciationSource: response.pronunciation_source,
        speechText: response.speech_text,
        audioBase64: response.audio_base64,
        audioFormat: response.audio_format || "mp3",
        timing: response.timing,
      };

      setMessages((prev) => [...prev, assistantMessage]);

      if (response.audio_base64) {
        const audioUrl = `data:audio/${response.audio_format || "mp3"};base64,${response.audio_base64}`;
        playResponseAudio(audioUrl);
      } else {
        setState("listening");
        setStatusText("I'm listening");
      }
    } catch (err: unknown) {
      console.error("Text message failed:", err);
      setError("Failed to send message to tutor service.");
      setState("listening");
      setStatusText("I'm listening");
    }
  }, [playResponseAudio, stopAudioPlayback]);

  // Replay speech at specified speed
  const replayAudio = useCallback(async (msg: ChatMessage, speed: number = 1.0) => {
    stopAudioPlayback();
    setError(null);

    // Direct playback if normal speed and base64 exists
    if (speed === 1.0 && msg.audioBase64) {
      const audioUrl = `data:audio/${msg.audioFormat || "mp3"};base64,${msg.audioBase64}`;
      playResponseAudio(audioUrl);
      return;
    }

    // Synthesize new audio at desired speed
    const textToSpeak = msg.speechText || msg.content;
    try {
      setState("thinking");
      setStatusText("Synthesizing pronunciation...");
      const audioUrl = await synthesizeAudio(textToSpeak, speed);
      playResponseAudio(audioUrl);
    } catch (err: unknown) {
      console.error("Replay synthesis error:", err);
      setError("Failed to synthesize audio replay.");
      setState("listening");
      setStatusText("I'm listening");
    }
  }, [playResponseAudio, stopAudioPlayback]);

  // Clear conversation history
  const clearChat = useCallback(() => {
    stopAudioPlayback();
    setMessages([]);
    setActiveTerm(null);
    setError(null);
    setLiveTranscript(null);
    if (isActivated) {
      setState("listening");
      setStatusText("I'm listening");
    } else {
      setState("idle");
      setStatusText("Tap to start conversation");
    }
  }, [isActivated, stopAudioPlayback]);

  // Clean up all resources on unmount
  useEffect(() => {
    return () => {
      stopAudioPlayback();
      if (vadRafIdRef.current) {
        cancelAnimationFrame(vadRafIdRef.current);
      }
      if (mediaStreamRef.current) {
        mediaStreamRef.current.getTracks().forEach((track) => track.stop());
      }
      if (audioContextRef.current && audioContextRef.current.state !== "closed") {
        audioContextRef.current.close().catch(() => {});
      }
    };
  }, [stopAudioPlayback]);

  return {
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
  };
}
