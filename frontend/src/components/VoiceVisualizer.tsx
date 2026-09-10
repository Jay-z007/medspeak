"use client";

import React, { useEffect, useRef } from "react";

export type OrbState =
  | "idle"
  | "listening"
  | "user_speaking"
  | "thinking"
  | "medspeak_speaking"
  | "error";

interface VoiceVisualizerProps {
  state: OrbState;
  audioLevel?: number; // Normalized 0.0 - 1.0 from microphone or audio playback
  size?: number; // Diameter in pixels (default 240)
  className?: string;
  onClick?: () => void;
}

export function VoiceVisualizer({
  state,
  audioLevel = 0,
  size = 240,
  className = "",
  onClick,
}: VoiceVisualizerProps) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const smoothedLevelRef = useRef<number>(0);
  const rotationAngleRef = useRef<number>(0);
  const phaseRef = useRef<number>(0);
  const animFrameRef = useRef<number | null>(null);

  // Check reduced motion preference
  const prefersReducedMotion =
    typeof window !== "undefined" &&
    window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext("2d", { alpha: true });
    if (!ctx) return;

    // Retina display resolution support
    const dpr = window.devicePixelRatio || 1;
    canvas.width = size * dpr;
    canvas.height = size * dpr;
    ctx.scale(dpr, dpr);

    const centerX = size / 2;
    const centerY = size / 2;
    const baseRadius = size * 0.32;

    const render = () => {
      // Smooth audio level with lerp to avoid abrupt jumps
      const targetLevel = state === "user_speaking" || state === "medspeak_speaking" ? audioLevel : 0;
      smoothedLevelRef.current += (targetLevel - smoothedLevelRef.current) * 0.18;
      const smoothLevel = Math.min(1.0, Math.max(0, smoothedLevelRef.current));

      // Phase update for idle/listening breathing
      phaseRef.current += 0.025;
      const breathing = Math.sin(phaseRef.current) * 0.015;

      if (state === "thinking") {
        rotationAngleRef.current += 0.02;
      } else {
        rotationAngleRef.current += 0.005;
      }

      ctx.clearRect(0, 0, size, size);

      // 1. Layer: Outer Ambient Soft Shadow & Aura
      const auraRadius = baseRadius * 1.5 + smoothLevel * 30;
      const auraGrad = ctx.createRadialGradient(
        centerX,
        centerY,
        baseRadius * 0.7,
        centerX,
        centerY,
        auraRadius
      );

      if (state === "error") {
        auraGrad.addColorStop(0, "rgba(220, 38, 38, 0.08)");
        auraGrad.addColorStop(1, "rgba(0, 0, 0, 0)");
      } else {
        const auraAlpha =
          state === "user_speaking"
            ? 0.12 + smoothLevel * 0.15
            : state === "medspeak_speaking"
            ? 0.14 + smoothLevel * 0.12
            : state === "listening"
            ? 0.06
            : 0.03;
        auraGrad.addColorStop(0, `rgba(255, 255, 255, ${auraAlpha})`);
        auraGrad.addColorStop(0.6, `rgba(180, 180, 190, ${auraAlpha * 0.3})`);
        auraGrad.addColorStop(1, "rgba(0, 0, 0, 0)");
      }

      ctx.fillStyle = auraGrad;
      ctx.beginPath();
      ctx.arc(centerX, centerY, auraRadius, 0, Math.PI * 2);
      ctx.fill();

      // 2. Layer: Concentric Sound Rings (Only in Listening / Speaking / Thinking)
      if (!prefersReducedMotion && state !== "idle") {
        const ringCount = state === "user_speaking" || state === "medspeak_speaking" ? 3 : 2;
        for (let i = 1; i <= ringCount; i++) {
          const ringExpansion = (smoothLevel * 35 * i) / ringCount;
          const ringOffset = Math.sin(phaseRef.current + i * 1.5) * 3;
          const r = baseRadius + 14 * i + ringExpansion + ringOffset;

          ctx.save();
          ctx.beginPath();
          ctx.arc(centerX, centerY, r, 0, Math.PI * 2);

          const ringAlpha =
            state === "user_speaking"
              ? Math.max(0.04, 0.28 - i * 0.08 + smoothLevel * 0.2)
              : state === "medspeak_speaking"
              ? Math.max(0.05, 0.32 - i * 0.08 + smoothLevel * 0.15)
              : state === "thinking"
              ? 0.1
              : 0.06;

          ctx.strokeStyle = `rgba(255, 255, 255, ${ringAlpha})`;
          ctx.lineWidth = i === 1 ? 1.5 : 1.0;

          if (state === "thinking") {
            ctx.setLineDash([4, 8]);
            ctx.lineDashOffset = -rotationAngleRef.current * 20;
          }

          ctx.stroke();
          ctx.restore();
        }
      }

      // 3. Layer: Main 3D Metallic Sphere Body
      // Scale dynamic response: breathing + audio amplitude
      const currentScale =
        prefersReducedMotion
          ? 1.0
          : state === "user_speaking"
          ? 1.0 + breathing + smoothLevel * 0.08
          : state === "medspeak_speaking"
          ? 1.0 + breathing + smoothLevel * 0.06
          : 1.0 + breathing;

      const sphereRadius = baseRadius * currentScale;

      // Base sphere shadow
      ctx.save();
      ctx.shadowColor = "rgba(0, 0, 0, 0.85)";
      ctx.shadowBlur = 32;
      ctx.shadowOffsetY = 12;

      // Volumetric sphere gradient (charcoal to deep obsidian with silver rim)
      const sphereGrad = ctx.createRadialGradient(
        centerX - sphereRadius * 0.32,
        centerY - sphereRadius * 0.32,
        sphereRadius * 0.1,
        centerX,
        centerY,
        sphereRadius
      );

      sphereGrad.addColorStop(0, "rgba(240, 240, 245, 0.95)"); // Soft metallic white light
      sphereGrad.addColorStop(0.2, "rgba(160, 160, 170, 0.85)"); // Silver-grey reflection
      sphereGrad.addColorStop(0.5, "rgba(40, 40, 46, 0.95)"); // Deep graphite
      sphereGrad.addColorStop(0.85, "rgba(18, 18, 22, 1.0)"); // Near-black charcoal
      sphereGrad.addColorStop(1.0, "rgba(9, 9, 11, 1.0)"); // Deep obsidian edge

      ctx.fillStyle = sphereGrad;
      ctx.beginPath();
      ctx.arc(centerX, centerY, sphereRadius, 0, Math.PI * 2);
      ctx.fill();
      ctx.restore();

      // 4. Layer: Specular Curved Highlights & Precision Glass Rim
      const rimGrad = ctx.createLinearGradient(
        centerX - sphereRadius,
        centerY - sphereRadius,
        centerX + sphereRadius,
        centerY + sphereRadius
      );
      rimGrad.addColorStop(0, "rgba(255, 255, 255, 0.45)");
      rimGrad.addColorStop(0.5, "rgba(255, 255, 255, 0.08)");
      rimGrad.addColorStop(1, "rgba(0, 0, 0, 0.6)");

      ctx.lineWidth = 1.0;
      ctx.strokeStyle = rimGrad;
      ctx.beginPath();
      ctx.arc(centerX, centerY, sphereRadius - 0.5, 0, Math.PI * 2);
      ctx.stroke();

      // 5. Layer: Internal Core Glow / Resonance
      if (state === "user_speaking" || state === "medspeak_speaking" || state === "thinking") {
        const coreAlpha =
          state === "user_speaking"
            ? 0.15 + smoothLevel * 0.35
            : state === "medspeak_speaking"
            ? 0.2 + smoothLevel * 0.3
            : 0.12;

        const coreGrad = ctx.createRadialGradient(
          centerX,
          centerY,
          0,
          centerX,
          centerY,
          sphereRadius * 0.65
        );
        coreGrad.addColorStop(0, `rgba(255, 255, 255, ${coreAlpha})`);
        coreGrad.addColorStop(0.7, `rgba(200, 200, 210, ${coreAlpha * 0.3})`);
        coreGrad.addColorStop(1, "rgba(0, 0, 0, 0)");

        ctx.fillStyle = coreGrad;
        ctx.beginPath();
        ctx.arc(centerX, centerY, sphereRadius * 0.65, 0, Math.PI * 2);
        ctx.fill();
      }

      // 6. Layer: Thinking Orbital Satellite Arc
      if (state === "thinking" && !prefersReducedMotion) {
        ctx.save();
        ctx.translate(centerX, centerY);
        ctx.rotate(rotationAngleRef.current);

        ctx.beginPath();
        ctx.arc(0, 0, sphereRadius + 8, 0, Math.PI * 0.7);
        ctx.strokeStyle = "rgba(255, 255, 255, 0.55)";
        ctx.lineWidth = 1.8;
        ctx.lineCap = "round";
        ctx.stroke();

        ctx.beginPath();
        ctx.arc(0, 0, sphereRadius + 8, Math.PI, Math.PI * 1.7);
        ctx.strokeStyle = "rgba(255, 255, 255, 0.25)";
        ctx.lineWidth = 1.2;
        ctx.lineCap = "round";
        ctx.stroke();

        ctx.restore();
      }

      animFrameRef.current = requestAnimationFrame(render);
    };

    render();

    return () => {
      if (animFrameRef.current) {
        cancelAnimationFrame(animFrameRef.current);
      }
    };
  }, [state, audioLevel, size, prefersReducedMotion]);

  return (
    <div
      onClick={onClick}
      className={`relative flex items-center justify-center select-none cursor-pointer transition-transform duration-200 ${className}`}
      style={{ width: size, height: size }}
      role="region"
      aria-label={`MedSpeak Voice Orb: ${state}`}
    >
      <canvas
        ref={canvasRef}
        style={{ width: size, height: size }}
        className="relative z-10"
      />
    </div>
  );
}
