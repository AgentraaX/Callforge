"use client";

import { PhoneCall, PhoneDisconnect, ShieldWarning } from "@phosphor-icons/react";
import { CallAnimation, type CallAnimationState } from "./CallAnimation";

/** The immersive "presence" moment of a live call -- the orb takes center
 * stage against a dark backdrop (the same dark navy the landing page
 * already uses for its own "live" showcase section, so this reads as the
 * same product, not a bolted-on widget), with the call controls given
 * the same premium weight as the orb itself. Sits above the transcript
 * panel, which stays in the app's normal light/functional register --
 * the pacing contrast is deliberate: one authored "wow" moment, then
 * back to a legible working surface. */
export function CallHero({
  state,
  audioLevel,
  agentName,
  agentSubtitle,
  isLive,
  onEndCall,
  caseId,
  onRestart,
}: {
  state: CallAnimationState;
  audioLevel?: number;
  agentName: string;
  agentSubtitle: string;
  isLive: boolean;
  /** Omit when there's no real way to hang up from here (e.g. a real
   * Telnyx phone call, which only the phone itself can end) -- a status
   * pill is shown instead of a button that couldn't actually do anything. */
  onEndCall?: () => void;
  caseId?: string | null;
  onRestart?: () => void;
}) {
  return (
    <div className="call-hero relative overflow-hidden rounded-t-2xl px-6 py-9 text-center">
      <div className="call-hero-glow pointer-events-none absolute inset-0" aria-hidden="true" />

      <div className="relative">
        <CallAnimation state={state} initials={agentName.slice(0, 2).toUpperCase() || "?"} size={112} audioLevel={audioLevel} />

        <p className="mt-5 text-[17px] font-semibold tracking-[-0.01em] text-white">{agentName || "Connecting…"}</p>
        <p className="mt-1 text-[12.5px] text-white/65">{agentSubtitle}</p>

        {caseId && (
          <span className="mt-3 inline-flex items-center gap-1.5 rounded-full bg-red-500/15 px-2.5 py-1 text-[11px] font-semibold text-red-300 ring-1 ring-red-500/25">
            <ShieldWarning size={12} weight="fill" />
            Case {caseId}
          </span>
        )}

        <div className="mt-7 flex items-center justify-center gap-4">
          {isLive && onEndCall ? (
            <button
              onClick={onEndCall}
              title="End call"
              aria-label="End call"
              className="call-hero-end group flex h-14 w-14 items-center justify-center rounded-full bg-red-500 text-white shadow-[0_8px_24px_-6px_rgba(239,68,68,0.65)] transition-transform duration-150 hover:scale-105 active:scale-95"
            >
              <PhoneDisconnect size={22} weight="fill" className="transition-transform duration-150 group-hover:rotate-[8deg]" />
            </button>
          ) : isLive ? (
            <span className="inline-flex items-center gap-1.5 rounded-full bg-white/10 px-3 py-1.5 text-[11.5px] font-semibold capitalize text-white/70 ring-1 ring-white/10">
              <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" />
              {state}
            </span>
          ) : (
            onRestart && (
              <button
                onClick={onRestart}
                className="inline-flex items-center gap-2 rounded-full bg-[#057676] px-5 py-2.5 text-[13px] font-semibold text-white shadow-[0_8px_24px_-6px_rgba(5,118,118,0.55)] transition-transform duration-150 hover:scale-105 active:scale-95"
              >
                <PhoneCall size={14} weight="fill" />
                Start another call
              </button>
            )
          )}
        </div>
      </div>

      <style jsx>{`
        .call-hero {
          background: radial-gradient(120% 140% at 50% -10%, #16234a 0%, #0d1836 55%, #0a1226 100%);
        }
        .call-hero-glow {
          background: radial-gradient(closest-side, rgba(5, 118, 118, 0.35), transparent 70%);
          top: -20%;
          transform: translateY(-10%);
        }
      `}</style>
    </div>
  );
}
