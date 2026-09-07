"use client";

import { useEffect, useRef, useState } from "react";
import { Room, RoomEvent, Track } from "livekit-client";
import {
  MicrophoneStage,
  PhoneCall,
  SpeakerHigh,
  WarningCircle,
} from "@phosphor-icons/react";
import {
  createDashboardWS,
  fetchPersonas,
  getLiveKitToken,
  type CallState,
  type PersonaPayload,
} from "../../../lib/api";
import { type CallAnimationState, useAudioLevel } from "../../components/CallAnimation";
import { CallHero } from "../../components/CallHero";

type CallPhase = "idle" | "connecting" | "live" | "ended" | "error";

function callAnimationState(call: CallState | null, phase: CallPhase): CallAnimationState {
  if (phase === "connecting") return "ringing";
  if (phase === "ended") return "ended";
  if (!call) return "listening";
  if (call.state === "thinking") return "thinking";
  if (call.state === "speaking") return "speaking";
  return "listening";
}

export default function TestCallPage() {
  const [personas, setPersonas] = useState<PersonaPayload[]>([]);
  const [personasLoading, setPersonasLoading] = useState(true);
  const [selectedPersonaId, setSelectedPersonaId] = useState<string>("");

  const [phase, setPhase] = useState<CallPhase>("idle");
  const [errorMsg, setErrorMsg] = useState("");
  const [call, setCall] = useState<CallState | null>(null);

  const roomRef = useRef<Room | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const transcriptEndRef = useRef<HTMLDivElement | null>(null);

  // Real playback loudness from the agent's actual audio track -- drives
  // the orb's motion while speaking, not a canned animation.
  const audioLevel = useAudioLevel(audioRef.current, phase === "live");

  useEffect(() => {
    fetchPersonas()
      .then((list) => {
        setPersonas(list);
        if (list.length > 0) setSelectedPersonaId(list[0].id);
      })
      .catch(() => setPersonas([]))
      .finally(() => setPersonasLoading(false));
  }, []);

  useEffect(() => {
    transcriptEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [call?.transcript.length]);

  useEffect(() => {
    return () => {
      roomRef.current?.disconnect();
      wsRef.current?.close();
    };
  }, []);

  function watchCall(callId: string) {
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

  async function startCall() {
    if (!selectedPersonaId) {
      setPhase("error");
      setErrorMsg("Create a sales persona first, then come back and pick it here.");
      return;
    }

    setPhase("connecting");
    setErrorMsg("");
    setCall(null);

    try {
      const { token, ws_url, call_id } = await getLiveKitToken(selectedPersonaId);

      const room = new Room();
      roomRef.current = room;

      room.on(RoomEvent.TrackSubscribed, (track) => {
        if (track.kind === Track.Kind.Audio && audioRef.current) {
          track.attach(audioRef.current);
        }
      });

      room.on(RoomEvent.Disconnected, () => {
        setPhase((p) => (p === "ended" ? p : "ended"));
      });

      await room.connect(ws_url, token);
      await room.localParticipant.setMicrophoneEnabled(true);

      watchCall(call_id);
      setPhase("live");
    } catch (err) {
      setPhase("error");
      setErrorMsg(
        err instanceof Error
          ? err.message
          : "Couldn't start the call -- check LiveKit is configured on the backend.",
      );
    }
  }

  function endCall() {
    roomRef.current?.disconnect();
    wsRef.current?.close();
    setPhase("ended");
  }

  const live = phase === "live" || phase === "connecting";
  const agent = call?.agent || null;

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <header>
        <p className="text-[12px] font-semibold uppercase tracking-[0.18em] text-[var(--color-signal)]">Command Center</p>
        <h1 className="mt-1.5 text-[26px] font-semibold tracking-[-0.01em] text-[var(--color-ink)] sm:text-[30px]">
          Test a Call
        </h1>
        <p className="mt-1.5 max-w-2xl text-[14px] leading-relaxed text-[var(--color-slate)]">
          Real WebRTC voice over LiveKit -- your actual mic, the agent's real ElevenLabs voice, real
          barge-in (you can interrupt it mid-sentence). Sales technique, grounding, and lead capture
          are the same engine the phone dialer uses.
        </p>
      </header>

      {phase === "idle" && (
        <div className="rounded-2xl bg-[var(--color-card)] p-8 text-center shadow-[inset_0_0_0_1px_rgba(255,255,255,0.14)]">
          <span className="mx-auto flex h-14 w-14 items-center justify-center rounded-full bg-[var(--color-signal-tint)] text-[var(--color-signal)]">
            <MicrophoneStage size={24} weight="duotone" />
          </span>
          <p className="mt-4 text-[15px] font-semibold text-[var(--color-ink)]">Ready to start a voice call</p>
          <p className="mx-auto mt-1.5 max-w-sm text-[13px] leading-relaxed text-[var(--color-slate)]">
            Your browser will ask for microphone permission -- allow it, then talk like a real caller.
          </p>

          {personasLoading ? (
            <p className="mx-auto mt-4 max-w-sm text-[13px] text-[var(--color-slate)]">Loading your personas…</p>
          ) : personas.length === 0 ? (
            <p className="mx-auto mt-4 max-w-sm text-[13px] leading-relaxed text-[var(--color-slate)]">
              You don't have a sales persona yet.{" "}
              <a href="/dashboard/personas" className="font-semibold text-[var(--color-signal)] underline underline-offset-2">
                Create one
              </a>{" "}
              first -- name, pitch, voice -- then come back here to test it.
            </p>
          ) : (
            <div className="mx-auto mt-4 max-w-xs text-left">
              <label className="mb-1.5 block text-[11px] font-semibold uppercase tracking-wide text-[var(--color-slate)]/70">
                Calling as
              </label>
              <select
                value={selectedPersonaId}
                onChange={(e) => setSelectedPersonaId(e.target.value)}
                className="h-10 w-full rounded-lg bg-[rgba(255,255,255,0.04)] px-3 text-[13.5px] text-[var(--color-ink)] outline-none ring-1 ring-[rgba(255,255,255,0.10)] focus:ring-2 focus:ring-[var(--color-signal)]/40"
              >
                {personas.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name}{p.company ? ` -- ${p.company}` : ""}
                  </option>
                ))}
              </select>
            </div>
          )}

          <button
            onClick={startCall}
            disabled={personas.length === 0}
            className="mt-5 inline-flex items-center gap-2 rounded-xl bg-[var(--color-signal)] px-5 py-2.5 text-[13.5px] font-semibold text-white transition-colors hover:bg-[var(--color-signal-hover)] disabled:pointer-events-none disabled:opacity-40"
          >
            <PhoneCall size={15} weight="fill" />
            Start call
          </button>
        </div>
      )}

      {phase === "error" && (
        <div className="flex items-start gap-3 rounded-2xl bg-red-500/15 p-5 text-red-800 ring-1 ring-red-100">
          <WarningCircle size={18} weight="fill" className="mt-0.5 shrink-0" />
          <div>
            <p className="text-[13.5px] font-semibold">Couldn't connect</p>
            <p className="mt-1 text-[13px] leading-relaxed">{errorMsg}</p>
            <button
              onClick={startCall}
              className="mt-3 inline-flex items-center gap-1.5 rounded-lg bg-[var(--color-card)] px-3 py-1.5 text-[12.5px] font-semibold text-red-300 ring-1 ring-red-200 transition-colors hover:bg-red-100"
            >
              Try again
            </button>
          </div>
        </div>
      )}

      {(live || phase === "ended") && (
        <div className="overflow-hidden rounded-2xl bg-[var(--color-card)] shadow-[inset_0_0_0_1px_rgba(255,255,255,0.14)]">
          <CallHero
            state={callAnimationState(call, phase)}
            audioLevel={audioLevel}
            agentName={agent?.name || "Connecting…"}
            agentSubtitle={agent?.company ? `calling from ${agent.company}` : "live voice call"}
            isLive={phase !== "ended"}
            onEndCall={endCall}
            caseId={call?.case_id}
            onRestart={startCall}
          />

          <div className="max-h-[420px] min-h-[240px] space-y-3 overflow-y-auto px-5 py-5">
            {(!call || call.transcript.length === 0) && (
              <p className="text-center text-[13px] text-[var(--color-slate)]/60">
                {phase === "connecting" ? "Connecting…" : "Waiting for the greeting..."}
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
                    <p className="mb-0.5 flex items-center gap-1 text-[10.5px] font-semibold uppercase tracking-wide text-[var(--color-signal)]">
                      <SpeakerHigh size={11} weight="fill" />
                      {line.name}
                    </p>
                  )}
                  {line.text}
                </div>
              </div>
            ))}
            <div ref={transcriptEndRef} />
          </div>

        </div>
      )}

      <audio ref={audioRef} autoPlay className="hidden" />
    </div>
  );
}
