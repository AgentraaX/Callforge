"use client";

import { useState } from "react";
import Link from "next/link";
import { CheckCircle, ListChecks } from "@phosphor-icons/react";
import { completeActivity, listActivities } from "../../../lib/crm";
import type { Activity } from "../../../lib/crm-types";
import { useMutation, useResource } from "../_hooks/useCrm";
import { EmptyState, ErrorNote, FadeIn, Panel, PageHeader, Skeleton, timeAgo } from "../_components/ui";

type Tab = "open" | "overdue" | "completed";

export default function ActivitiesPage() {
  const [tab, setTab] = useState<Tab>("open");
  const { data, loading, error, reload } = useResource(
    () => listActivities({ type: "task", status: tab, limit: 100, order_by: "due_at" }),
    [tab],
  );
  const mutation = useMutation();

  const tabs: { key: Tab; label: string }[] = [
    { key: "open", label: "Open" },
    { key: "overdue", label: "Overdue" },
    { key: "completed", label: "Completed" },
  ];

  return (
    <div className="space-y-6">
      <PageHeader title="Tasks" subtitle="Your follow-ups across every contact and deal." />

      <FadeIn>
        <Panel className="overflow-hidden">
          <div className="flex gap-1 border-b border-[rgba(255,255,255,0.08)] px-4 py-2">
            {tabs.map((t) => (
              <button
                key={t.key}
                onClick={() => setTab(t.key)}
                className={`rounded-lg px-3 py-1.5 text-[12.5px] font-semibold transition-colors ${
                  tab === t.key
                    ? "bg-[var(--color-signal-line)] text-[var(--color-signal)]"
                    : "text-[var(--color-slate)] hover:bg-[rgba(255,255,255,0.04)]"
                }`}
              >
                {t.label}
              </button>
            ))}
          </div>

          {error && <div className="p-4"><ErrorNote message={error} /></div>}
          {loading && !data ? (
            <Skeleton />
          ) : !loading && (data?.items.length ?? 0) === 0 ? (
            <EmptyState
              icon={ListChecks}
              title={tab === "completed" ? "Nothing completed yet" : "No tasks here"}
              note="Add a task from any contact's timeline to keep follow-ups on track."
            />
          ) : (
            <ul className="divide-y divide-[rgba(255,255,255,0.08)]">
              {(data?.items || []).map((a) => (
                <TaskRow
                  key={a.id}
                  task={a}
                  done={tab === "completed"}
                  onComplete={async () => {
                    await mutation.run(() => completeActivity(a.id));
                    reload();
                  }}
                />
              ))}
            </ul>
          )}
        </Panel>
      </FadeIn>
    </div>
  );
}

function TaskRow({
  task,
  done,
  onComplete,
}: {
  task: Activity;
  done: boolean;
  onComplete: () => void;
}) {
  const overdue = !done && task.due_at && new Date(task.due_at).getTime() < Date.now();
  return (
    <li className="flex items-start gap-3 px-5 py-3.5">
      <button
        onClick={onComplete}
        disabled={done}
        aria-label="Complete task"
        className={`mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center rounded border transition-colors ${
          done
            ? "border-emerald-400 bg-emerald-400 text-white"
            : "border-[rgba(255,255,255,0.25)] hover:border-[var(--color-signal)] hover:bg-[var(--color-signal)]/10"
        }`}
      >
        {done && <CheckCircle size={12} weight="fill" />}
      </button>
      <div className="min-w-0 flex-1">
        <p className={`text-[13px] ${done ? "text-[var(--color-slate)] line-through" : "text-[var(--color-ink)]"}`}>
          {task.subject}
        </p>
        <div className="mt-0.5 flex flex-wrap items-center gap-2 text-[11px] text-[var(--color-slate)]/70">
          {task.due_at && (
            <span className={overdue ? "font-semibold text-rose-600" : ""}>
              {done ? "completed " : "due "}
              {timeAgo(done ? task.completed_at : task.due_at)}
            </span>
          )}
          {task.contact_id && (
            <Link href={`/dashboard/contacts/${task.contact_id}`} className="text-[var(--color-signal)] hover:underline">
              contact →
            </Link>
          )}
        </div>
      </div>
    </li>
  );
}
