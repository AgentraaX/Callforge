"use client";

import { useMemo, useState } from "react";
import { PhoneCall } from "@phosphor-icons/react";
import { listCalls } from "../../../lib/crm";
import type { CallRecord } from "../../../lib/crm-types";
import { useResource } from "../_hooks/useCrm";
import { CallTranscriptModal } from "../_components/CallTranscriptModal";
import { DataTable, Pagination, type Column } from "../_components/DataTable";
import {
  EmptyState,
  ErrorNote,
  FadeIn,
  formatDuration,
  OutcomeBadge,
  Panel,
  PageHeader,
  Skeleton,
  timeAgo,
} from "../_components/ui";

const PAGE_SIZE = 25;

export default function CallsPage() {
  const [offset, setOffset] = useState(0);
  const [outcome, setOutcome] = useState("");
  const [sort, setSort] = useState("-created_at");
  const [openId, setOpenId] = useState<string | null>(null);

  const { data, loading, error } = useResource(
    () => listCalls({ outcome: outcome || undefined, limit: PAGE_SIZE, offset, order_by: sort }),
    [outcome, offset, sort],
  );

  const columns: Column<CallRecord>[] = useMemo(
    () => [
      {
        key: "to",
        label: "Number",
        render: (c) => (
          <span className="font-medium text-[var(--color-ink)]">{c.to_number || c.from_number || "—"}</span>
        ),
      },
      { key: "persona", label: "Agent", render: (c) => c.persona_name || "—" },
      { key: "outcome", label: "Outcome", render: (c) => <OutcomeBadge outcome={c.outcome} /> },
      {
        key: "duration",
        label: "Duration",
        sortKey: "duration_s",
        render: (c) => <span className="tabular-nums">{formatDuration(c.duration_s)}</span>,
      },
      {
        key: "when",
        label: "When",
        sortKey: "created_at",
        render: (c) => (
          <span className="text-[12px] text-[var(--color-slate)]/80">{timeAgo(c.started_at || c.created_at)}</span>
        ),
      },
    ],
    [],
  );

  return (
    <div className="space-y-6">
      <PageHeader
        title="Call history"
        subtitle="Every call the voice agent has run, with its transcript and outcome."
      />

      <FadeIn>
        <Panel className="overflow-hidden">
          <div className="flex items-center gap-3 border-b border-[rgba(255,255,255,0.08)] px-5 py-3">
            <select
              value={outcome}
              onChange={(e) => {
                setOffset(0);
                setOutcome(e.target.value);
              }}
              className="h-9 rounded-lg bg-[rgba(255,255,255,0.04)] px-3 text-[13px] text-[var(--color-ink)] ring-1 ring-[rgba(255,255,255,0.10)]"
            >
              <option value="">All outcomes</option>
              <option value="booked">Booked</option>
              <option value="callback">Callback</option>
              <option value="declined">Declined</option>
              <option value="escalated">Escalated</option>
              <option value="none">No outcome</option>
            </select>
          </div>

          {error && <div className="p-4"><ErrorNote message={error} /></div>}
          {loading && !data ? (
            <Skeleton />
          ) : !loading && (data?.items.length ?? 0) === 0 ? (
            <EmptyState
              icon={PhoneCall}
              title="No calls yet"
              note="Place a call from the Dialer or a contact record. It'll show up here when it ends."
            />
          ) : (
            data && (
              <>
                <DataTable
                  columns={columns}
                  rows={data.items}
                  sort={sort}
                  onSortChange={setSort}
                  onRowClick={(c) => setOpenId(c.id)}
                />
                <Pagination total={data.total} limit={PAGE_SIZE} offset={offset} onChange={setOffset} />
              </>
            )
          )}
        </Panel>
      </FadeIn>

      {openId && <CallTranscriptModal callId={openId} onClose={() => setOpenId(null)} />}
    </div>
  );
}
