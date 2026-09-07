"use client";

import { useEffect, useRef, useState } from "react";

/** The living presence of the call -- a fluid, colorful gradient orb (in
 * the spirit of ChatGPT/Grok/Gemini voice mode) that visibly reacts to
 * the agent's real state, not a canned loop. When a live `<audio>`
 * element is available (browser voice calls), its actual output level
 * drives the orb's motion in real time via the Web Audio API; the
 * Dialer's real phone calls have no local audio to analyze, so the orb
 * falls back to a rich authored animation per state -- both are "real"
 * in the sense that they're driven by the actual call state, never
 * random or decorative. */

export type CallAnimationState = "idle" | "ringing" | "thinking" | "speaking" | "listening" | "ended";

/** Reads real playback loudness (0..1) from an <audio> element via the Web
 * Audio API. Must be called from a component that OWNS the audio element
 * for its whole lifetime (e.g. the page) -- not from the orb itself, which
 * mounts/unmounts with call state. A `MediaElementAudioSourceNode` can
 * only ever be created once per <audio> element (the browser throws on a
 * second attempt), so the source/context live in refs keyed to the
 * element and are created exactly once. */
export function useAudioLevel(audioEl: HTMLMediaElement | null | undefined, enabled: boolean): number {
  const [level, setLevel] = useState(0);
  const ctxRef = useRef<AudioContext | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const sourceRef = useRef<MediaElementAudioSourceNode | null>(null);
  const rafRef = useRef<number>(0);
  const elRef = useRef<HTMLMediaElement | null>(null);

  useEffect(() => {
    if (!enabled || !audioEl) {
      setLevel(0);
      return;
    }

    try {
      if (!ctxRef.current) {
        const AudioCtxCtor: typeof AudioContext =
          window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
        ctxRef.current = new AudioCtxCtor();
      }
      const ctx = ctxRef.current;
      if (ctx.state === "suspended") void ctx.resume();

      // Only ever create the source node once for this exact element.
      if (!sourceRef.current || elRef.current !== audioEl) {
        sourceRef.current = ctx.createMediaElementSource(audioEl);
        elRef.current = audioEl;
        const analyser = ctx.createAnalyser();
        analyser.fftSize = 256;
        analyser.smoothingTimeConstant = 0.55;
        sourceRef.current.connect(analyser);
        sourceRef.current.connect(ctx.destination);
        analyserRef.current = analyser;
      }

      const analyser = analyserRef.current;
      if (!analyser) return;
      const data = new Uint8Array(analyser.frequencyBinCount);

      const tick = () => {
        analyser.getByteFrequencyData(data);
        let sum = 0;
        for (let i = 0; i < data.length; i++) sum += data[i];
        setLevel(sum / data.length / 255);
        rafRef.current = requestAnimationFrame(tick);
      };
      tick();
    } catch {
      // Autoplay/CORS/unsupported -- orb falls back to its authored
      // per-state animation, never a broken call.
      setLevel(0);
    }

    return () => cancelAnimationFrame(rafRef.current);
  }, [audioEl, enabled]);

  return level;
}

const STATE_PROFILE: Record<CallAnimationState, { spin: number; scale: number; glow: number; sat: number }> = {
  idle: { spin: 14, scale: 1, glow: 0.32, sat: 0.9 },
  ringing: { spin: 5, scale: 1.03, glow: 0.6, sat: 1.15 },
  thinking: { spin: 2.4, scale: 0.95, glow: 0.55, sat: 1.05 },
  listening: { spin: 9, scale: 1, glow: 0.42, sat: 1 },
  speaking: { spin: 2.2, scale: 1.05, glow: 0.85, sat: 1.35 },
  ended: { spin: 26, scale: 0.88, glow: 0.14, sat: 0.5 },
};

export function CallAnimation({
  state,
  initials,
  size = 56,
  audioLevel = 0,
}: {
  state: CallAnimationState;
  initials: string;
  size?: number;
  /** 0..1 real playback loudness from useAudioLevel(); adds a live,
   * amplitude-reactive kick on top of the authored per-state motion
   * while the agent is actually speaking. Omit for transports with no
   * local audio (e.g. the Telnyx dialer). */
  audioLevel?: number;
}) {
  const profile = STATE_PROFILE[state];
  const reactiveBoost = state === "speaking" ? audioLevel * 0.22 : 0;
  const ringing = state === "ringing";
  const speaking = state === "speaking";
  const showBadge = size >= 72; // small inline badges skip the corner status dot

  return (
    <div className="flex flex-col items-center" style={{ gap: Math.max(6, size * 0.14) }}>
      <div
        className="voice-orb-wrap relative flex shrink-0 items-center justify-center"
        style={
          {
            width: size,
            height: size,
            "--orb-spin": `${profile.spin}s`,
            "--orb-scale": profile.scale + reactiveBoost,
            "--orb-glow": Math.min(1, profile.glow + reactiveBoost * 1.4),
            "--orb-sat": profile.sat,
          } as React.CSSProperties
        }
      >
        {/* Ambient glow halo -- atmosphere, not decoration: it's the one
            signal visible from a glance that the agent is "present". */}
        <span className="voice-orb-glow absolute rounded-full" style={{ inset: -size * 0.35 }} aria-hidden="true" />

        {/* Expanding rings while the phone is ringing */}
        {ringing && (
          <>
            <span className="voice-orb-ring absolute inset-0 rounded-full" />
            <span className="voice-orb-ring absolute inset-0 rounded-full" style={{ animationDelay: "0.7s" }} />
          </>
        )}

        {/* The orb itself -- organic blob morph + rotating conic gradient */}
        <span className="voice-orb-core relative overflow-hidden" style={{ width: size, height: size }} aria-hidden="true">
          <span className="voice-orb-gradient absolute inset-0" />
          <span className="voice-orb-sheen absolute inset-0" />
        </span>

        <span
          className="relative font-bold text-white [text-shadow:0_1px_3px_rgba(0,0,0,0.25)]"
          style={{ fontSize: size * 0.26 }}
        >
          {initials}
        </span>

        {showBadge && state === "thinking" && (
          <span className="absolute -bottom-0.5 -right-0.5 flex h-5 w-5 items-center justify-center rounded-full bg-white shadow-sm ring-1 ring-[rgba(13,33,54,0.08)]">
            <span className="h-2 w-2 animate-pulse rounded-full bg-amber-500" />
          </span>
        )}
      </div>

      {!speaking && (
        <span
          className="text-[11px] font-medium capitalize"
          style={{ color: size >= 72 ? "rgba(255,255,255,0.68)" : "#3E526A99" }}
        >
          {state === "ended" ? "call ended" : state}
        </span>
      )}

      <style jsx>{`
        .voice-orb-glow {
          background: radial-gradient(
            circle,
            rgba(5, 118, 118, calc(var(--orb-glow) * 0.9)) 0%,
            rgba(47, 189, 189, calc(var(--orb-glow) * 0.5)) 45%,
            transparent 72%
          );
          filter: blur(18px);
          transition: opacity 0.4s ease;
        }

        .voice-orb-core {
          border-radius: 42% 58% 70% 30% / 45% 45% 55% 55%;
          animation:
            orb-morph calc(var(--orb-spin) * 1.6) ease-in-out infinite,
            orb-breathe 2.8s ease-in-out infinite;
          box-shadow: 0 6px 24px -6px rgba(5, 118, 118, 0.45), inset 0 0 0 1px rgba(255, 255, 255, 0.12);
          transform: scale(var(--orb-scale));
          transition: transform 0.18s cubic-bezier(0.16, 1, 0.3, 1);
        }

        .voice-orb-gradient {
          background: conic-gradient(
            from 0deg,
            #057676,
            #2fbdbd,
            #6b7fd7,
            #b06bd0,
            #2fbdbd,
            #057676
          );
          filter: saturate(var(--orb-sat));
          animation: orb-spin var(--orb-spin) linear infinite;
        }

        .voice-orb-sheen {
          background: radial-gradient(circle at 32% 28%, rgba(255, 255, 255, 0.55), transparent 45%);
          mix-blend-mode: overlay;
        }

        .voice-orb-ring {
          border: 1.5px solid rgba(5, 118, 118, 0.45);
          animation: orb-ring 2.2s cubic-bezier(0.16, 1, 0.3, 1) infinite;
        }

        @keyframes orb-morph {
          0% {
            border-radius: 42% 58% 70% 30% / 45% 45% 55% 55%;
          }
          25% {
            border-radius: 58% 42% 35% 65% / 60% 40% 60% 40%;
          }
          50% {
            border-radius: 50% 50% 62% 38% / 40% 60% 40% 60%;
          }
          75% {
            border-radius: 38% 62% 45% 55% / 55% 45% 55% 45%;
          }
          100% {
            border-radius: 42% 58% 70% 30% / 45% 45% 55% 55%;
          }
        }

        @keyframes orb-breathe {
          0%,
          100% {
            filter: brightness(1);
          }
          50% {
            filter: brightness(1.06);
          }
        }

        @keyframes orb-spin {
          to {
            transform: rotate(360deg);
          }
        }

        @keyframes orb-ring {
          0% {
            transform: scale(1);
            opacity: 0.55;
          }
          100% {
            transform: scale(1.9);
            opacity: 0;
          }
        }

        @media (prefers-reduced-motion: reduce) {
          .voice-orb-core,
          .voice-orb-gradient,
          .voice-orb-ring {
            animation-duration: 0.01ms !important;
          }
        }
      `}</style>
    </div>
  );
}
