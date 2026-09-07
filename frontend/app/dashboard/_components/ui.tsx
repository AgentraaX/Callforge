"use client";

import type { ReactNode } from "react";
import type { Icon } from "@phosphor-icons/react";
import { motion } from "motion/react";
import type { DealStage, Lifecycle, CallOutcome } from "../../../lib/crm-types";

/* ── Tokens shared with app/dashboard/page.tsx ─────────────────────── */
export const PANEL = "rounded-2xl bg-[var(--color-card)] shadow-[inset_0_0_0_1px_rgba(255,255,255,0.14)]";
export const TEAL = "var(--color-signal)";
export const NAVY = "var(--color-ink)";
export const MUTED = "var(--color-slate)";

/* ── Formatters ───────────────────────────────────────────────────── */

export function initials(name: string): string {
  const trimmed = (name || "").trim();
  if (!trimmed) return "?";
  return trimmed
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((p) => p[0])
    .join("")
    .toUpperCase();
}

export function timeAgo(iso: string | null): string {
  if (!iso) return "—";
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return "—";
  const diffS = Math.max(0, (Date.now() - then) / 1000);
  if (diffS < 60) return "just now";
  const min = Math.floor(diffS / 60);
  if (min < 60) return `${min}m ago`;
  const hr = Math.floor(min / 60);
  if (hr < 24) return `${hr}h ago`;
  const days = Math.floor(hr / 24);
  if (days < 30) return `${days}d ago`;
  return new Date(iso).toLocaleDateString();
}

export function formatMoney(amount: number | null | undefined, currency = "USD"): string {
  if (amount === null || amount === undefined) return "—";
  try {
    return new Intl.NumberFormat("en-US", {
      style: "currency",
      currency,
      maximumFractionDigits: 0,
    }).format(amount);
  } catch {
    return `${currency} ${Math.round(amount).toLocaleString()}`;
  }
}

export function formatDuration(seconds: number): string {
  const s = Math.max(0, Math.round(seconds));
  const m = Math.floor(s / 60);
  return `${m}:${String(s % 60).padStart(2, "0")}`;
}

/* ── Layout primitives ────────────────────────────────────────────── */

export function PageHeader({
  eyebrow,
  title,
  subtitle,
  actions,
}: {
  /** Optional mono kicker. Omit on most pages — only set it where it adds signal. */
  eyebrow?: string;
  title: string;
  subtitle?: string;
  actions?: ReactNode;
}) {
  return (
    <header className="flex flex-wrap items-end justify-between gap-4">
      <div>
        {eyebrow && (
          <p className="mb-1.5 font-mono text-[11px] font-medium uppercase tracking-[0.18em] text-[var(--color-signal)]">
            {eyebrow}
          </p>
        )}
        <h1 className="text-[26px] font-semibold tracking-[-0.01em] text-[var(--color-ink)] sm:text-[30px]">
          {title}
        </h1>
        {subtitle && (
          <p className="mt-1.5 max-w-2xl text-[14px] leading-relaxed text-[var(--color-slate)]">{subtitle}</p>
        )}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </header>
  );
}

export function Panel({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <div className={`${PANEL} ${className}`}>{children}</div>;
}

export function PanelHeader({ title, count, actions }: { title: string; count?: string | number; actions?: ReactNode }) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-3 border-b border-[rgba(255,255,255,0.08)] px-5 py-4">
      <div className="flex items-center gap-3">
        <h2 className="text-[15px] font-semibold text-[var(--color-ink)]">{title}</h2>
        {count !== undefined && (
          <span className="rounded-full bg-[rgba(255,255,255,0.06)] px-2.5 py-0.5 text-[11px] font-semibold text-[var(--color-slate)]">
            {count}
          </span>
        )}
      </div>
      {actions}
    </div>
  );
}

export function EmptyState({
  icon: IconCmp,
  title,
  note,
  action,
}: {
  icon: Icon;
  title: string;
  note: string;
  action?: ReactNode;
}) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 px-6 py-14 text-center">
      <span className="flex h-11 w-11 items-center justify-center rounded-full bg-[rgba(255,255,255,0.04)] text-[var(--color-slate)]/60 ring-1 ring-[rgba(255,255,255,0.08)]">
        <IconCmp size={20} weight="duotone" />
      </span>
      <p className="text-[13.5px] font-semibold text-[var(--color-ink)]">{title}</p>
      <p className="max-w-xs text-[12.5px] leading-relaxed text-[var(--color-slate)]">{note}</p>
      {action}
    </div>
  );
}

export function Skeleton({ rows = 5 }: { rows?: number }) {
  return (
    <div className="space-y-2 p-4">
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="h-10 animate-pulse rounded-lg bg-[rgba(255,255,255,0.06)]" />
      ))}
    </div>
  );
}

export function ErrorNote({ message }: { message: string }) {
  return (
    <div className="rounded-xl bg-amber-500/15 px-4 py-3 text-[12.5px] text-amber-300 ring-1 ring-amber-100">
      {message}
    </div>
  );
}

export function Avatar({ name, size = 32 }: { name: string; size?: number }) {
  return (
    <span
      className="flex shrink-0 items-center justify-center rounded-full bg-[rgba(255,255,255,0.04)] font-bold text-[var(--color-ink)] ring-1 ring-[rgba(255,255,255,0.10)]"
      style={{ width: size, height: size, fontSize: size * 0.36 }}
    >
      {initials(name)}
    </span>
  );
}

/* ── Buttons ──────────────────────────────────────────────────────── */

export function PrimaryButton({
  children,
  onClick,
  type = "button",
  disabled,
  className = "",
}: {
  children: ReactNode;
  onClick?: () => void;
  type?: "button" | "submit";
  disabled?: boolean;
  className?: string;
}) {
  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled}
      className={`inline-flex items-center gap-2 rounded-xl bg-[var(--color-signal)] px-4 py-2 text-[13px] font-semibold text-white transition-colors hover:bg-[var(--color-signal-hover)] disabled:pointer-events-none disabled:opacity-40 ${className}`}
    >
      {children}
    </button>
  );
}

export function GhostButton({
  children,
  onClick,
  className = "",
}: {
  children: ReactNode;
  onClick?: () => void;
  className?: string;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-[12.5px] font-semibold text-[var(--color-slate)] ring-1 ring-[rgba(255,255,255,0.14)] transition-colors hover:bg-[rgba(255,255,255,0.04)] hover:text-[var(--color-ink)] ${className}`}
    >
      {children}
    </button>
  );
}

/* ── Badges ───────────────────────────────────────────────────────── */

function Pill({ label, cls }: { label: string; cls: string }) {
  return (
    <span className={`inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-[11px] font-semibold capitalize ring-1 ${cls}`}>
      {label}
    </span>
  );
}

const STAGE_CLS: Record<DealStage, string> = {
  new: "bg-slate-50 text-slate-600 ring-slate-200",
  qualified: "bg-blue-50 text-blue-600 ring-blue-100",
  demo: "bg-indigo-50 text-indigo-600 ring-indigo-100",
  proposal: "bg-violet-50 text-violet-600 ring-violet-100",
  negotiation: "bg-amber-500/15 text-amber-700 ring-amber-100",
  won: "bg-emerald-500/15 text-emerald-300 ring-emerald-100",
  lost: "bg-rose-50 text-rose-600 ring-rose-100",
};

export const STAGE_LABEL: Record<DealStage, string> = {
  new: "New",
  qualified: "Qualified",
  demo: "Demo",
  proposal: "Proposal",
  negotiation: "Negotiation",
  won: "Won",
  lost: "Lost",
};

export function StageBadge({ stage }: { stage: DealStage }) {
  return <Pill label={STAGE_LABEL[stage]} cls={STAGE_CLS[stage]} />;
}

const LIFECYCLE_CLS: Record<Lifecycle, string> = {
  lead: "bg-slate-50 text-slate-600 ring-slate-200",
  mql: "bg-sky-50 text-sky-600 ring-sky-100",
  sql: "bg-indigo-50 text-indigo-600 ring-indigo-100",
  customer: "bg-emerald-500/15 text-emerald-300 ring-emerald-100",
  churned: "bg-rose-50 text-rose-600 ring-rose-100",
};

export function LifecycleBadge({ stage }: { stage: Lifecycle }) {
  return <Pill label={stage === "mql" || stage === "sql" ? stage.toUpperCase() : stage} cls={LIFECYCLE_CLS[stage]} />;
}

const OUTCOME_CLS: Record<CallOutcome, string> = {
  booked: "bg-emerald-500/15 text-emerald-300 ring-emerald-100",
  callback: "bg-amber-500/15 text-amber-700 ring-amber-100",
  declined: "bg-slate-50 text-slate-500 ring-slate-200",
  escalated: "bg-rose-50 text-rose-600 ring-rose-100",
  none: "bg-slate-50 text-slate-500 ring-slate-200",
};

export function OutcomeBadge({ outcome }: { outcome: CallOutcome }) {
  return <Pill label={outcome === "none" ? "no outcome" : outcome} cls={OUTCOME_CLS[outcome]} />;
}

/* ── Animated wrapper ─────────────────────────────────────────────── */

export function FadeIn({ children, delay = 0 }: { children: ReactNode; delay?: number }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, delay, ease: "easeOut" }}
    >
      {children}
    </motion.div>
  );
}
