"use client";

import { Suspense, useEffect, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import { CircleNotch, PhoneCall, WarningCircle } from "@phosphor-icons/react";
import {
  createDashboardWS,
  dialCall,
  fetchPersonas,
  type CallState,
  type PersonaPayload,
} from "../../../lib/api";
import { type CallAnimationState } from "../../components/CallAnimation";
import { CallHero } from "../../components/CallHero";

function toE164Hint(value: string): string {
  if (!value) return "";
  if (!value.startsWith("+")) return "Include the country code, e.g. +1 for the US";
  if (!/^\+[1-9]\d{6,14}$/.test(value)) return "That doesn't look like a valid phone number";
  return "";
}

function callAnimationState(call: CallState | null): CallAnimationState {
  if (!call) return "idle";
  if (call.state === "ended" || call.state === "end") return "ended";
  if (call.state === "ringing") return "ringing";
  return "listening"; // Telnyx calls don't expose thinking/speaking granularity to the dashboard feed
}

export default function DialerPage() {
  return (
    <Suspense fallback={null}>
      <DialerPageInner />
    </Suspense>
  );
}

function DialerPageInner() {
  const searchParams = useSearchParams();
  const presetPersonaId = searchParams.get("persona_id") || "";
  const presetNumber = searchParams.get("to") || "";

  const [personas, setPersonas] = useState<PersonaPayload[]>([]);
  const [personaId, setPersonaId] = useState(presetPersonaId);
  const [toNumber, setToNumber] = useState(presetNumber);
  const [dialing, setDialing] = useState(false);
  const [error, setError] = useState("");
  const [activeCallId, setActiveCallId] = useState<string | null>(null);
  const [call, setCall] = useState<CallState | null>(null);

  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    fetchPersonas()
      .then((list) => {
        setPersonas(list);
        if (!presetPersonaId && list.length > 0) setPersonaId(list[0].id);
      })
      .catch(() => setPersonas([]));
  }, [presetPersonaId]);

  useEffect(() => {
    return () => {
      wsRef.current?.close();
    };
  }, []);

  function watchCall(callId: string) {
    wsRef.current?.close();
    let ws: WebSocket;
    try {
      ws = createDashboardWS();
    } catch {
      return;
    }
    wsRef.current = ws;
    ws.onmessage = (evt) => {
      let msg: { type?: string; calls?: CallState[]; call?: CallState };
      try {
        msg = JSON.parse(evt.data);
      } catch {
        return;
      }
      if (msg.type === "snapshot" && msg.calls) {
        const match = msg.calls.find((c) => c.id === callId);
        if (match) setCall(match);
      } else if (msg.type === "call_update" && msg.call?.id === callId) {
        setCall(msg.call);
      }
    };
  }

  async function handleDial() {
    setError("");
    const hint = toE164Hint(toNumber);
    if (hint) {
      setError(hint);
      return;
    }
    if (!personaId) {
      setError("Pick a persona to call as first.");
      return;
    }
    setDialing(true);
    try {
      const { call_id } = await dialCall(toNumber, personaId);
      setActiveCallId(call_id);
      watchCall(call_id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to place the call");
    } finally {
      setDialing(false);
    }
  }

  function reset() {
    setActiveCallId(null);
    setCall(null);
    wsRef.current?.close();
  }

  const activePersona = personas.find((p) => p.id === personaId);
  const isLive = !!activeCallId && call?.state !== "ended" && call?.state !== "end";

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <header>
        <p className="text-[12px] font-semibold uppercase tracking-[0.18em] text-[var(--color-signal)]">Command Center</p>
        <h1 className="mt-1.5 text-[26px] font-semibold tracking-[-0.01em] text-[var(--color-ink)] sm:text-[30px]">
          Dialer
        </h1>
        <p className="mt-1.5 max-w-2xl text-[14px] leading-relaxed text-[var(--color-slate)]">
          Place a real outbound phone call via Telnyx. The agent's voice goes out over the phone
          line, not this browser -- this page shows a live transcript and status while the call is
          in progress.
        </p>
      </header>

      {!activeCallId ? (
        <div className="rounded-2xl bg-[var(--color-card)] p-6 shadow-[inset_0_0_0_1px_rgba(255,255,255,0.14)]">
          <div className="space-y-4">
            <label className="block">
              <span className="mb-1.5 block text-[11px] font-semibold uppercase tracking-wide text-[var(--color-slate)]/70">
                Calling as
              </span>
              <select
                value={personaId}
                onChange={(e) => setPersonaId(e.target.value)}
                className="h-11 w-full rounded-lg bg-[rgba(255,255,255,0.04)] px-3 text-[13.5px] text-[var(--color-ink)] outline-none ring-1 ring-[rgba(255,255,255,0.10)] focus:ring-2 focus:ring-[var(--color-signal)]/40"
              >
                {personas.length === 0 && <option value="">No personas yet</option>}
                {personas.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name}{p.company ? ` -- ${p.company}` : ""}
                  </option>
                ))}
              </select>
              {personas.length === 0 && (
                <span className="mt-1.5 block text-[12px] text-[var(--color-slate)]">
                  <a href="/dashboard/personas" className="font-semibold text-[var(--color-signal)] underline underline-offset-2">
                    Create a persona
                  </a>{" "}
                  before dialing.
                </span>
              )}
            </label>

            <label className="block">
              <span className="mb-1.5 block text-[11px] font-semibold uppercase tracking-wide text-[var(--color-slate)]/70">
                Client's phone number
              </span>
              <input
                value={toNumber}
                onChange={(e) => setToNumber(e.target.value)}
                placeholder="+14155552671"
                className="h-11 w-full rounded-lg bg-[rgba(255,255,255,0.04)] px-3 text-[13.5px] text-[var(--color-ink)] outline-none ring-1 ring-[rgba(255,255,255,0.10)] focus:ring-2 focus:ring-[var(--color-signal)]/40"
              />
              <span className="mt-1.5 block text-[12px] text-[var(--color-slate)]/70">
                E.164 format, e.g. +1 415 555 2671. The call will show as coming from CallForge's number.
              </span>
            </label>

            <button
              onClick={handleDial}
              disabled={dialing || !toNumber || !personaId}
              className="inline-flex items-center gap-2 rounded-xl bg-[var(--color-signal)] px-5 py-2.5 text-[13.5px] font-semibold text-white transition-colors hover:bg-[var(--color-signal-hover)] disabled:pointer-events-none disabled:opacity-40"
            >
              {dialing ? <CircleNotch size={15} className="animate-spin" /> : <PhoneCall size={15} weight="fill" />}
              {dialing ? "Dialing…" : "Call now"}
            </button>
          </div>

          {error && (
            <div className="mt-4 flex items-start gap-2.5 rounded-xl bg-red-500/15 px-4 py-3 text-[12.5px] leading-relaxed text-red-300 ring-1 ring-red-100">
              <WarningCircle size={15} weight="fill" className="mt-0.5 shrink-0" />
              {error}
            </div>
          )}
        </div>
      ) : (
        <div className="overflow-hidden rounded-2xl bg-[var(--color-card)] shadow-[inset_0_0_0_1px_rgba(255,255,255,0.14)]">
          <CallHero
            state={callAnimationState(call)}
            agentName={activePersona?.name || "Connecting…"}
            agentSubtitle={`Calling ${toNumber}`}
            isLive={isLive}
            onRestart={!isLive ? reset : undefined}
          />

          <div className="max-h-[420px] min-h-[200px] space-y-3 overflow-y-auto px-5 py-5">
            {(!call || call.transcript.length === 0) && (
              <p className="text-center text-[13px] text-[var(--color-slate)]/60">
                {isLive ? "Ringing… waiting for the call to connect." : "No transcript yet."}
              </p>
            )}
            {call?.transcript.map((line, i) => (
              <div key={i} className={`flex ${line.who === "caller" ? "justify-end" : "justify-start"}`}>
                <div
                  className={`max-w-[80%] rounded-2xl px-4 py-2.5 text-[13.5px] leading-relaxed ${
                    line.who === "caller"
                      ? "bg-[var(--color-signal)] text-white"
                      : "bg-[rgba(255,255,255,0.04)] text-[var(--color-ink)] ring-1 ring-[rgba(255,255,255,0.08)]"
                  }`}
                >
                  {line.who === "agent" && (
                    <p className="mb-0.5 text-[10.5px] font-semibold uppercase tracking-wide text-[var(--color-signal)]">
                      {line.name}
                    </p>
                  )}
                  {line.text}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
