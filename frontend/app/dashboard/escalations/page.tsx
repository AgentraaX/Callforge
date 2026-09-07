"use client";

import { ShieldWarning } from "@phosphor-icons/react";
import { useDashboardData } from "../useDashboardData";
import { CallTranscriptModal } from "../_components/CallTranscriptModal";
import { EmptyState, ErrorNote, FadeIn, Panel, PanelHeader, PageHeader, Skeleton, timeAgo } from "../_components/ui";
import { useState } from "react";

export default function EscalationsPage() {
  const { escalations, loading, error } = useDashboardData();
  const [openCall, setOpenCall] = useState<string | null>(null);

  const pending = escalations.filter((e) => e.status === "pending");
  const resolved = escalations.filter((e) => e.status !== "pending");

  return (
    <div className="space-y-6">
      <PageHeader
        title="Escalations"
        subtitle="Calls where the agent handed off to a human. Newest first."
      />

      {error && <ErrorNote message={error} />}

      <FadeIn>
        <Panel className="overflow-hidden">
          <PanelHeader title="Needs attention" count={pending.length} />
          {loading && escalations.length === 0 ? (
            <Skeleton rows={3} />
          ) : pending.length === 0 ? (
            <EmptyState
              icon={ShieldWarning}
              title="No open escalations"
              note="When a caller asks for a human, the case shows up here with its transcript and a summary."
            />
          ) : (
            <ul className="divide-y divide-[rgba(255,255,255,0.08)]">
              {pending.map((c) => (
                <li key={c.case_id} className="px-5 py-4">
                  <div className="flex flex-wrap items-start justify-between gap-2">
                    <div className="min-w-0">
                      <p className="text-[13px] font-semibold text-[var(--color-ink)]">
                        {c.reason.replace(/_/g, " ")}
                        {c.caller_name ? ` · ${c.caller_name}` : ""}
                      </p>
                      <p className="mt-1 text-[12.5px] leading-relaxed text-[var(--color-slate)]">{c.summary}</p>
                    </div>
                    <div className="flex shrink-0 items-center gap-2">
                      {c.priority === "high" && (
                        <span className="rounded-full bg-red-500/15 px-2 py-1 text-[10.5px] font-semibold text-red-400 ring-1 ring-red-100">
                          High priority
                        </span>
                      )}
                      <span className="text-[11px] text-[var(--color-slate)]/60">{timeAgo(new Date(c.created_at * 1000).toISOString())}</span>
                    </div>
                  </div>
                  <button
                    onClick={() => setOpenCall(c.call_id)}
                    className="mt-2 text-[12px] font-semibold text-[var(--color-signal)] hover:underline"
                  >
                    View transcript →
                  </button>
                </li>
              ))}
            </ul>
          )}
        </Panel>
      </FadeIn>

      {resolved.length > 0 && (
        <Panel className="overflow-hidden">
          <PanelHeader title="Resolved" count={resolved.length} />
          <ul className="divide-y divide-[rgba(255,255,255,0.08)]">
            {resolved.map((c) => (
              <li key={c.case_id} className="flex items-center justify-between px-5 py-3">
                <span className="text-[13px] text-[var(--color-slate)]">
                  {c.reason.replace(/_/g, " ")}
                  {c.caller_name ? ` · ${c.caller_name}` : ""}
                </span>
                <span className="text-[11px] capitalize text-[var(--color-slate)]/60">{c.status}</span>
              </li>
            ))}
          </ul>
        </Panel>
      )}

      {openCall && <CallTranscriptModal callId={openCall} onClose={() => setOpenCall(null)} />}
    </div>
  );
}
