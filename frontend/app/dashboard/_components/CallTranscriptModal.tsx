"use client";

import { AnimatePresence, motion } from "motion/react";
import { X } from "@phosphor-icons/react";
import { getCall } from "../../../lib/crm";
import { useResource } from "../_hooks/useCrm";
import { formatDuration, OutcomeBadge, Skeleton, timeAgo } from "./ui";

export function CallTranscriptModal({ callId, onClose }: { callId: string; onClose: () => void }) {
  const { data, loading, error } = useResource(() => getCall(callId), [callId]);

  return (
    <AnimatePresence>
      <motion.div
        className="fixed inset-0 z-50 flex items-center justify-center bg-[rgba(0,0,0,0.55)] p-4"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        onClick={onClose}
      >
        <motion.div
          className="flex max-h-[80vh] w-full max-w-lg flex-col overflow-hidden rounded-2xl bg-[var(--color-card)] shadow-2xl"
          initial={{ scale: 0.96, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          exit={{ scale: 0.96, opacity: 0 }}
          onClick={(e) => e.stopPropagation()}
          role="dialog"
          aria-label="Call transcript"
        >
          <div className="flex items-center justify-between border-b border-[rgba(255,255,255,0.08)] px-5 py-4">
            <div>
              <p className="text-[14px] font-semibold text-[var(--color-ink)]">Call transcript</p>
              {data && (
                <p className="mt-0.5 flex items-center gap-2 text-[12px] text-[var(--color-slate)]">
                  {data.persona_name || "Agent"} · {formatDuration(data.duration_s)} ·{" "}
                  {timeAgo(data.started_at || data.created_at)}
                </p>
              )}
            </div>
            <button
              onClick={onClose}
              aria-label="Close"
              className="rounded-lg p-1.5 text-[var(--color-slate)] transition-colors hover:bg-[rgba(255,255,255,0.04)] hover:text-[var(--color-ink)]"
            >
              <X size={18} weight="bold" />
            </button>
          </div>

          <div className="flex-1 overflow-y-auto px-5 py-4">
            {loading && <Skeleton rows={5} />}
            {error && <p className="text-[13px] text-rose-600">{error}</p>}
            {data && (
              <>
                <div className="mb-3 flex items-center gap-2">
                  <OutcomeBadge outcome={data.outcome} />
                  {data.escalated && (
                    <span className="rounded-full bg-rose-50 px-2 py-0.5 text-[10.5px] font-semibold text-rose-600 ring-1 ring-rose-100">
                      Escalated
                    </span>
                  )}
                </div>
                <div className="space-y-3">
                  {data.transcript.length === 0 && (
                    <p className="text-[13px] text-[var(--color-slate)]/60">No transcript was captured for this call.</p>
                  )}
                  {data.transcript.map((line, i) => (
                    <div
                      key={i}
                      className={`flex ${line.who === "caller" ? "justify-end" : "justify-start"}`}
                    >
                      <div
                        className={`max-w-[80%] rounded-2xl px-3.5 py-2 text-[13px] leading-relaxed ${
                          line.who === "caller"
                            ? "bg-[var(--color-signal)] text-white"
                            : "bg-[rgba(255,255,255,0.04)] text-[var(--color-ink)] ring-1 ring-[rgba(255,255,255,0.08)]"
                        }`}
                      >
                        {line.who !== "caller" && (
                          <p className="mb-0.5 text-[10px] font-semibold uppercase tracking-wide text-[var(--color-signal)]">
                            {line.name}
                          </p>
                        )}
                        {line.text}
                      </div>
                    </div>
                  ))}
                </div>
              </>
            )}
          </div>
        </motion.div>
      </motion.div>
    </AnimatePresence>
  );
}
