"use client";

import Link from "next/link";
import { useMemo } from "react";
import type { Icon } from "@phosphor-icons/react";
import {
  ArrowRight,
  CalendarCheck,
  CurrencyDollar,
  ListChecks,
  PhoneCall,
  TrendUp,
  Users,
} from "@phosphor-icons/react";
import { analyticsOverview, listActivities, listCalls } from "../../lib/crm";
import type { AnalyticsOverview, DealStage } from "../../lib/crm-types";
import type { CallState } from "../../lib/api";

/* Shown before any data loads, or when the backend has nothing yet — so the
   page reads as "0 across the board" instead of a wall of empty cards. */
const STAGE_ORDER: DealStage[] = ["new", "qualified", "demo", "proposal", "negotiation", "won"];

function emptyOverview(): AnalyticsOverview {
  const today = new Date();
  const days = Array.from({ length: 14 }, (_, i) => {
    const d = new Date(today);
    d.setDate(d.getDate() - (13 - i));
    return { date: d.toISOString().slice(0, 10), count: 0 };
  });
  return {
    contacts: 0,
    open_deals: 0,
    pipeline_value: 0,
    won_this_month: 0,
    win_rate: 0,
    calls_this_week: 0,
    bookings_this_week: 0,
    open_tasks: 0,
    overdue_tasks: 0,
    deals_by_stage: STAGE_ORDER.map((stage) => ({ stage, count: 0, total_amount: 0 })),
    calls_per_day: days,
  };
}
import { useDashboardData } from "./useDashboardData";
import { useResource } from "./_hooks/useCrm";
import { CallVolumeChart, PipelineChart, PipelineValueChart } from "./_components/OverviewCharts";
import {
  Avatar,
  ErrorNote,
  FadeIn,
  formatDuration,
  formatMoney,
  OutcomeBadge,
  Panel,
  PanelHeader,
  PageHeader,
  Skeleton,
  timeAgo,
} from "./_components/ui";

export default function OverviewPage() {
  const analytics = useResource(() => analyticsOverview(), []);
  const recentCalls = useResource(() => listCalls({ limit: 6 }), []);
  const myTasks = useResource(
    () => listActivities({ type: "task", status: "open", limit: 6, order_by: "due_at" }),
    [],
  );
  const { liveCalls, wsConnected } = useDashboardData();

  /* fall back to an all-zero overview so the page never shows blank cards */
  const a = analytics.data ?? emptyOverview();
  const initialLoad = analytics.loading && !analytics.data && !analytics.error;
  const activeCalls = liveCalls.filter((c) => c.state !== "ended" && c.state !== "end");

  const stats: { label: string; value: string; note: string; icon: Icon }[] = [
    { label: "Contacts", value: String(a.contacts), note: `${a.calls_this_week} calls this week`, icon: Users },
    {
      label: "Open pipeline",
      value: formatMoney(a.pipeline_value, "USD"),
      note: `${a.open_deals} open deals`,
      icon: CurrencyDollar,
    },
    {
      label: "Win rate",
      value: `${Math.round(a.win_rate * 100)}%`,
      note: `${a.won_this_month} won this month`,
      icon: TrendUp,
    },
    {
      label: "Bookings",
      value: String(a.bookings_this_week),
      note: "demos booked this week",
      icon: CalendarCheck,
    },
    {
      label: "Open tasks",
      value: String(a.open_tasks),
      note: `${a.overdue_tasks} overdue`,
      icon: ListChecks,
    },
  ];

  return (
    <div className="space-y-6">
      <PageHeader
        title="Overview"
        subtitle="Pipeline health, recent calls, and what needs your attention — live from the CallForge backend."
      />

      {analytics.error && (
        <ErrorNote message={`Couldn't load live analytics (${analytics.error}). Showing zeros.`} />
      )}

      {initialLoad ? (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-5">
          {[0, 1, 2, 3, 4].map((i) => (
            <div key={i} className="card-ring h-[120px] animate-pulse p-5" />
          ))}
        </div>
      ) : (
        <section className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-5">
          {stats.map((s, i) => {
            const IconCmp = s.icon;
            return (
              <FadeIn key={s.label} delay={i * 0.04}>
                <div className="card-ring h-full p-5">
                  <div className="flex items-start justify-between">
                    <p className="pt-1 text-[11px] font-semibold uppercase tracking-[0.12em] text-[var(--color-slate)]/80">
                      {s.label}
                    </p>
                    <span className="flex h-9 w-9 items-center justify-center rounded-full bg-[var(--color-signal-tint)] text-[var(--color-signal)]">
                      <IconCmp size={16} weight="duotone" />
                    </span>
                  </div>
                  <p className="mt-3 text-[24px] font-semibold leading-none tracking-tight text-[var(--color-ink)]">
                    {s.value}
                  </p>
                  <p className="mt-2.5 text-[11.5px] text-[var(--color-slate)]/70">{s.note}</p>
                </div>
              </FadeIn>
            );
          })}
        </section>
      )}

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <FadeIn>
          <Panel className="p-5">
            <h2 className="text-[15px] font-semibold text-[var(--color-ink)]">Call volume</h2>
            <p className="text-[12px] text-[var(--color-slate)]/70">Last 14 days</p>
            <div className="mt-4">
              {initialLoad ? <Skeleton rows={2} /> : <CallVolumeChart data={a.calls_per_day} />}
            </div>
          </Panel>
        </FadeIn>
        <FadeIn delay={0.05}>
          <Panel className="p-5">
            <h2 className="text-[15px] font-semibold text-[var(--color-ink)]">Pipeline by stage</h2>
            <p className="text-[12px] text-[var(--color-slate)]/70">Deal count</p>
            <div className="mt-4">
              {initialLoad ? (
                <Skeleton rows={4} />
              ) : (
                <PipelineChart stages={a.deals_by_stage.filter((s) => s.stage !== "lost")} />
              )}
            </div>
          </Panel>
        </FadeIn>
        <FadeIn delay={0.1}>
          <Panel className="p-5">
            <h2 className="text-[15px] font-semibold text-[var(--color-ink)]">Pipeline value</h2>
            <p className="text-[12px] text-[var(--color-slate)]/70">By stage — hover to inspect</p>
            <div className="mt-4">
              {initialLoad ? (
                <Skeleton rows={4} />
              ) : (
                <PipelineValueChart stages={a.deals_by_stage.filter((s) => s.stage !== "lost")} />
              )}
            </div>
          </Panel>
        </FadeIn>
      </div>

      <FadeIn>
        <LiveCallsPanel calls={activeCalls} wsConnected={wsConnected} />
      </FadeIn>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <FadeIn>
          <Panel className="overflow-hidden">
            <PanelHeader
              title="Recent calls"
              actions={
                <Link
                  href="/dashboard/calls"
                  className="inline-flex items-center gap-1 text-[12px] font-semibold text-[var(--color-signal)] hover:text-[var(--color-signal-hover)]"
                >
                  All calls <ArrowRight size={12} weight="bold" />
                </Link>
              }
            />
            <div className="divide-y divide-[rgba(255,255,255,0.08)]">
              {(recentCalls.data?.items || []).map((c) => (
                <Link
                  key={c.id}
                  href={c.contact_id ? `/dashboard/contacts/${c.contact_id}` : "/dashboard/calls"}
                  className="flex items-center gap-3 px-5 py-3 transition-colors hover:bg-[rgba(255,255,255,0.04)]"
                >
                  <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-[var(--color-signal-tint)] text-[var(--color-signal)]">
                    <PhoneCall size={13} weight="duotone" />
                  </span>
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-[13px] font-medium text-[var(--color-ink)]">
                      {c.to_number || c.from_number || "Call"}
                    </p>
                    <p className="text-[11px] text-[var(--color-slate)]/70">
                      {c.persona_name || "Agent"} · {formatDuration(c.duration_s)} ·{" "}
                      {timeAgo(c.started_at || c.created_at)}
                    </p>
                  </div>
                  <OutcomeBadge outcome={c.outcome} />
                </Link>
              ))}
              {!recentCalls.loading && (recentCalls.data?.items.length ?? 0) === 0 && (
                <p className="px-5 py-8 text-center text-[12.5px] text-[var(--color-slate)]/60">No calls yet.</p>
              )}
            </div>
          </Panel>
        </FadeIn>

        <FadeIn delay={0.05}>
          <Panel className="overflow-hidden">
            <PanelHeader
              title="My open tasks"
              actions={
                <Link
                  href="/dashboard/activities"
                  className="inline-flex items-center gap-1 text-[12px] font-semibold text-[var(--color-signal)] hover:text-[var(--color-signal-hover)]"
                >
                  All tasks <ArrowRight size={12} weight="bold" />
                </Link>
              }
            />
            <div className="divide-y divide-[rgba(255,255,255,0.08)]">
              {(myTasks.data?.items || []).map((t) => (
                <Link
                  key={t.id}
                  href={t.contact_id ? `/dashboard/contacts/${t.contact_id}` : "/dashboard/activities"}
                  className="flex items-center justify-between gap-3 px-5 py-3 transition-colors hover:bg-[rgba(255,255,255,0.04)]"
                >
                  <p className="truncate text-[13px] text-[var(--color-ink)]">{t.subject}</p>
                  {t.due_at && (
                    <span
                      className={`shrink-0 text-[11px] ${
                        new Date(t.due_at).getTime() < Date.now()
                          ? "font-semibold text-rose-400"
                          : "text-[var(--color-slate)]/70"
                      }`}
                    >
                      {timeAgo(t.due_at)}
                    </span>
                  )}
                </Link>
              ))}
              {!myTasks.loading && (myTasks.data?.items.length ?? 0) === 0 && (
                <p className="px-5 py-8 text-center text-[12.5px] text-[var(--color-slate)]/60">Nothing due yet.</p>
              )}
            </div>
          </Panel>
        </FadeIn>
      </div>
    </div>
  );
}

function LiveCallsPanel({ calls, wsConnected }: { calls: CallState[]; wsConnected: boolean }) {
  const label = useMemo(
    () => (wsConnected ? `${calls.length} in progress` : "connecting…"),
    [wsConnected, calls.length],
  );
  return (
    <Panel className="overflow-hidden">
      <div className="flex items-center justify-between border-b border-[rgba(255,255,255,0.08)] px-5 py-4">
        <div className="flex items-center gap-3">
          <h2 className="text-[15px] font-semibold text-[var(--color-ink)]">Live calls</h2>
          <span
            className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-[11px] font-semibold ring-1 ${
              wsConnected
                ? "bg-emerald-500/15 text-emerald-300 ring-emerald-500/25"
                : "bg-[rgba(255,255,255,0.06)] text-[var(--color-slate)] ring-[rgba(255,255,255,0.12)]"
            }`}
          >
            <span className={`h-1.5 w-1.5 rounded-full ${wsConnected ? "bg-emerald-500" : "bg-[var(--color-slate)]"}`} />
            {label}
          </span>
        </div>
        <Link
          href="/dashboard/dialer"
          className="inline-flex items-center gap-1 text-[12px] font-semibold text-[var(--color-signal)] hover:text-[var(--color-signal-hover)]"
        >
          Dialer <ArrowRight size={12} weight="bold" />
        </Link>
      </div>
      {calls.length === 0 ? (
        <p className="px-5 py-8 text-center text-[12.5px] text-[var(--color-slate)]/60">
          No calls in progress. Calls placed from the Dialer or a contact appear here in real time.
        </p>
      ) : (
        <div className="divide-y divide-[rgba(255,255,255,0.08)]">
          {calls.map((call) => (
            <div key={call.id} className="flex flex-wrap items-center gap-x-5 gap-y-2 px-5 py-3.5">
              <span className="relative flex h-2.5 w-2.5 shrink-0">
                <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-500 opacity-50" />
                <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-emerald-500" />
              </span>
              <div className="min-w-[180px] flex-1">
                <p className="truncate text-[13px] font-semibold text-[var(--color-ink)]">{call.caller || "Caller"}</p>
                <p className="mt-0.5 truncate text-[12px] text-[var(--color-slate)]">
                  {call.transcript.at(-1)?.text || "Connecting…"}
                </p>
              </div>
              {call.agent && (
                <span className="flex items-center gap-2 text-[12.5px] text-[var(--color-slate)]">
                  <Avatar name={call.agent.name} size={22} />
                  {call.agent.name}
                </span>
              )}
              <span className="rounded-full bg-[rgba(255,255,255,0.04)] px-2.5 py-1 text-[11px] font-semibold capitalize text-[var(--color-slate)] ring-1 ring-[rgba(255,255,255,0.10)]">
                {call.state}
              </span>
            </div>
          ))}
        </div>
      )}
    </Panel>
  );
}
