"use client";

import { CalendarCheck, ChatCircleText, NotePencil, PhoneCall } from "@phosphor-icons/react";
import type { Icon } from "@phosphor-icons/react";
import type { TimelineItem } from "../../../lib/crm-types";
import { EmptyState, timeAgo } from "./ui";

const KIND_ICON: Record<string, Icon> = {
  call: PhoneCall,
  deal: CalendarCheck,
  activity: NotePencil,
};

const KIND_TINT: Record<string, string> = {
  call: "bg-[var(--color-signal-tint)] text-[var(--color-signal)]",
  deal: "bg-emerald-500/15 text-emerald-600",
  activity: "bg-slate-100 text-slate-600",
};

export function Timeline({
  items,
  onSelectCall,
}: {
  items: TimelineItem[];
  onSelectCall?: (callId: string) => void;
}) {
  if (items.length === 0) {
    return (
      <EmptyState
        icon={ChatCircleText}
        title="Nothing on the timeline yet"
        note="Calls, notes, tasks and deals for this contact show up here in order."
      />
    );
  }

  return (
    <ul className="space-y-0 px-5 py-4">
      {items.map((item, i) => {
        const IconCmp = KIND_ICON[item.kind] || NotePencil;
        const clickable = item.kind === "call" && onSelectCall;
        return (
          <li key={`${item.kind}-${item.id}`} className="relative flex gap-3 pb-5 last:pb-0">
            {i < items.length - 1 && (
              <span className="absolute bottom-1 left-[15px] top-9 w-px bg-[rgba(255,255,255,0.10)]" aria-hidden="true" />
            )}
            <span
              className={`relative z-10 flex h-8 w-8 shrink-0 items-center justify-center rounded-full ${KIND_TINT[item.kind]}`}
            >
              <IconCmp size={14} weight="duotone" />
            </span>
            <div className="min-w-0 flex-1 pt-0.5">
              <button
                type="button"
                disabled={!clickable}
                onClick={clickable ? () => onSelectCall(item.id) : undefined}
                className={`text-left text-[13px] font-medium leading-snug text-[var(--color-ink)] ${
                  clickable ? "hover:text-[var(--color-signal)]" : "cursor-default"
                }`}
              >
                {item.title}
              </button>
              {item.subtitle && (
                <p className="mt-0.5 text-[12px] capitalize text-[var(--color-slate)]/80">{item.subtitle}</p>
              )}
              {typeof item.meta?.body === "string" && item.meta.body && (
                <p className="mt-1 line-clamp-2 text-[12px] leading-relaxed text-[var(--color-slate)]">
                  {item.meta.body as string}
                </p>
              )}
              <p className="mt-1 text-[11px] text-[var(--color-slate)]/60">{timeAgo(item.at)}</p>
            </div>
          </li>
        );
      })}
    </ul>
  );
}
