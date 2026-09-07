"use client";

import { useEffect, useRef, useState } from "react";
import { motion, useReducedMotion } from "motion/react";
import { Play, Pause } from "@phosphor-icons/react";

/* One clip — the agent placing a real call. Autoplays muted while on screen. */
const CLIP = {
  webm: "/hero-a.webm",
  mp4: "/hero-b.mp4",
  label: "Live call",
  caption: "The agent dials, opens with rapport, and works the objection — in real time.",
};

export default function VideoShowcase() {
  const reduce = useReducedMotion();
  const ref = useRef<HTMLVideoElement>(null);
  const [playing, setPlaying] = useState(false);

  useEffect(() => {
    const el = ref.current;
    if (!el || reduce) return;
    const io = new IntersectionObserver(
      ([e]) => {
        if (e.isIntersecting) el.play().catch(() => {});
        else el.pause();
      },
      { threshold: 0.3 },
    );
    io.observe(el);
    return () => io.disconnect();
  }, [reduce]);

  const toggle = () => {
    const el = ref.current;
    if (!el) return;
    if (el.paused) el.play().catch(() => {});
    else el.pause();
  };

  return (
    <motion.div
      initial={reduce ? false : { opacity: 0, y: 20 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, amount: 0.3 }}
      transition={{ duration: 0.5, ease: [0.22, 1, 0.36, 1] }}
      className="group relative mx-auto max-w-4xl overflow-hidden rounded-2xl bg-[var(--color-console)] shadow-[0_30px_80px_-30px_rgba(0,0,0,0.75)] ring-1 ring-[var(--color-hairline-strong)]"
    >
      <div
        aria-hidden="true"
        className="pointer-events-none absolute -inset-16 opacity-40 blur-3xl transition-opacity duration-500 group-hover:opacity-70"
        style={{
          background:
            "radial-gradient(45% 45% at 50% 25%, rgba(59,111,229,0.4) 0%, transparent 70%)",
        }}
      />

      <div className="relative aspect-video">
        <video
          ref={ref}
          className="h-full w-full object-cover"
          muted
          loop
          autoPlay={!reduce}
          playsInline
          preload="metadata"
          onPlay={() => setPlaying(true)}
          onPause={() => setPlaying(false)}
        >
          <source src={CLIP.webm} type="video/webm" />
          <source src={CLIP.mp4} type="video/mp4" />
        </video>

        <button
          type="button"
          onClick={toggle}
          aria-label={playing ? "Pause video" : "Play video"}
          className="absolute inset-0 flex items-center justify-center focus-visible:outline-none"
        >
          <span
            className={`flex h-16 w-16 items-center justify-center rounded-full bg-signal text-white shadow-[0_12px_36px_-6px_rgba(59,111,229,0.75)] transition-all ${
              playing ? "scale-90 opacity-0 group-hover:opacity-100" : "scale-100 opacity-100"
            }`}
          >
            {playing ? <Pause size={22} weight="fill" /> : <Play size={22} weight="fill" />}
          </span>
        </button>

        <div className="pointer-events-none absolute inset-x-0 bottom-0 bg-gradient-to-t from-black/85 via-black/25 to-transparent p-5 pt-16">
          <span className="font-mono text-[10px] uppercase tracking-[0.2em] text-[var(--color-live)]">
            {CLIP.label}
          </span>
          <p className="mt-1 max-w-[46ch] text-[14px] font-medium text-white/90">
            {CLIP.caption}
          </p>
        </div>
      </div>
    </motion.div>
  );
}
