"use client";

import { Suspense, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Plus, Kanban } from "@phosphor-icons/react";
import { createDeal, dealBoard, deleteDeal, moveDeal } from "../../../lib/crm";
import { DEAL_STAGES, type Deal, type DealStage } from "../../../lib/crm-types";
import { useMutation, useResource } from "../_hooks/useCrm";
import { EntityPicker } from "../_components/EntityPicker";
import {
  EmptyState,
  ErrorNote,
  FadeIn,
  formatMoney,
  PageHeader,
  PrimaryButton,
  Skeleton,
  STAGE_LABEL,
} from "../_components/ui";
import { SlideOver, TextField } from "../_components/SlideOver";

export default function DealsPage() {
  return (
    <Suspense fallback={<Skeleton rows={6} />}>
      <DealsBoard />
    </Suspense>
  );
}

function DealsBoard() {
  const router = useRouter();
  const params = useSearchParams();
  const { data, loading, error, reload } = useResource(() => dealBoard(), []);
  const mutation = useMutation();
  const [showForm, setShowForm] = useState(false);
  const [dragId, setDragId] = useState<string | null>(null);
  const [dragOver, setDragOver] = useState<DealStage | null>(null);

  const focusDealId = params.get("deal");

  async function onDrop(stage: DealStage) {
    setDragOver(null);
    const id = dragId;
    setDragId(null);
    if (!id) return;
    const col = data?.columns.find((c) => c.stage === stage);
    const order = (col?.deals.length ?? 0) + 1;
    if (stage === "lost") {
      const reason = prompt("Reason for losing this deal? (optional)") || undefined;
      await mutation.run(() => moveDeal(id, { stage, board_order: order, lost_reason: reason }));
    } else {
      await mutation.run(() => moveDeal(id, { stage, board_order: order }));
    }
    reload();
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Pipeline"
        subtitle="Drag a deal between stages to update it. Booking a demo on a call opens a deal here automatically."
        actions={
          <PrimaryButton onClick={() => setShowForm(true)}>
            <Plus size={14} weight="bold" />
            New deal
          </PrimaryButton>
        }
      />

      {error && <ErrorNote message={error} />}
      {loading && !data ? (
        <Skeleton rows={6} />
      ) : data && data.columns.every((c) => c.count === 0) ? (
        <FadeIn>
          <div className="rounded-2xl bg-[var(--color-card)] shadow-[inset_0_0_0_1px_rgba(255,255,255,0.14)]">
            <EmptyState
              icon={Kanban}
              title="No deals in the pipeline"
              note="Create a deal, or let the agent open one when it books a demo on a call."
              action={
                <PrimaryButton onClick={() => setShowForm(true)}>
                  <Plus size={14} weight="bold" /> New deal
                </PrimaryButton>
              }
            />
          </div>
        </FadeIn>
      ) : (
        data && (
          <div className="overflow-x-auto pb-2">
            <div className="flex min-w-max gap-4">
              {data.columns.map((col) => (
                <div
                  key={col.stage}
                  onDragOver={(e) => {
                    e.preventDefault();
                    setDragOver(col.stage);
                  }}
                  onDragLeave={() => setDragOver((s) => (s === col.stage ? null : s))}
                  onDrop={() => onDrop(col.stage)}
                  className={`flex w-[260px] shrink-0 flex-col rounded-2xl bg-[var(--color-card)] shadow-[inset_0_0_0_1px_rgba(255,255,255,0.14)] transition-shadow ${
                    dragOver === col.stage ? "ring-2 ring-[var(--color-signal)]/40" : ""
                  }`}
                >
                  <div className="flex items-center justify-between border-b border-[rgba(255,255,255,0.08)] px-4 py-3">
                    <span className="text-[12px] font-semibold uppercase tracking-wide text-[var(--color-ink)]">
                      {STAGE_LABEL[col.stage]}
                    </span>
                    <span className="text-[11px] font-semibold text-[var(--color-slate)]/70">
                      {col.count} · {formatMoney(col.total_amount, "USD")}
                    </span>
                  </div>
                  <div className="flex-1 space-y-2 overflow-y-auto p-2" style={{ maxHeight: "62vh" }}>
                    {col.deals.map((d) => (
                      <DealCard
                        key={d.id}
                        deal={d}
                        highlighted={d.id === focusDealId}
                        onDragStart={() => setDragId(d.id)}
                        onOpen={() => router.push(`/dashboard/deals?deal=${d.id}`)}
                      />
                    ))}
                    {col.deals.length === 0 && (
                      <p className="px-2 py-6 text-center text-[11.5px] text-[var(--color-slate)]/45">Drop here</p>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )
      )}

      {focusDealId && data && (
        <DealDetail
          deal={data.columns.flatMap((c) => c.deals).find((d) => d.id === focusDealId) || null}
          onClose={() => router.push("/dashboard/deals")}
          onChanged={reload}
        />
      )}

      <NewDealPanel
        open={showForm}
        onClose={() => setShowForm(false)}
        onSaved={() => {
          setShowForm(false);
          reload();
        }}
      />
    </div>
  );
}

function DealCard({
  deal,
  highlighted,
  onDragStart,
  onOpen,
}: {
  deal: Deal;
  highlighted: boolean;
  onDragStart: () => void;
  onOpen: () => void;
}) {
  return (
    <button
      draggable
      onDragStart={onDragStart}
      onClick={onOpen}
      className={`block w-full cursor-grab rounded-xl bg-[rgba(255,255,255,0.04)] p-3 text-left ring-1 transition-colors hover:bg-[var(--color-card)] active:cursor-grabbing ${
        highlighted ? "ring-[var(--color-signal)]" : "ring-[rgba(255,255,255,0.10)]"
      }`}
    >
      <p className="line-clamp-2 text-[12.5px] font-semibold text-[var(--color-ink)]">{deal.title}</p>
      <p className="mt-1.5 text-[12px] font-medium tabular-nums text-[var(--color-signal)]">
        {formatMoney(deal.amount, deal.currency)}
      </p>
    </button>
  );
}

function DealDetail({
  deal,
  onClose,
  onChanged,
}: {
  deal: Deal | null;
  onClose: () => void;
  onChanged: () => void;
}) {
  const mutation = useMutation();
  if (!deal) return null;
  return (
    <SlideOver
      open
      onClose={onClose}
      title={deal.title}
      footer={
        <div className="flex items-center justify-between">
          <button
            onClick={async () => {
              if (!confirm("Delete this deal?")) return;
              const r = await mutation.run(() => deleteDeal(deal.id));
              if (r.ok) {
                onChanged();
                onClose();
              }
            }}
            className="text-[12px] font-semibold text-rose-600 hover:underline"
          >
            Delete
          </button>
          <span className="text-[12px] text-[var(--color-slate)]">
            {deal.stage === "won" || deal.stage === "lost"
              ? `Closed ${deal.closed_at ? new Date(deal.closed_at).toLocaleDateString() : ""}`
              : "Open"}
          </span>
        </div>
      }
    >
      <dl className="space-y-3 text-[13px]">
        <Row label="Stage" value={STAGE_LABEL[deal.stage]} />
        <Row label="Amount" value={formatMoney(deal.amount, deal.currency)} />
        <Row label="Owner" value={deal.owner_email} />
        {deal.contact_id && (
          <div>
            <dt className="text-[10.5px] font-semibold uppercase tracking-wide text-[var(--color-slate)]/60">Contact</dt>
            <dd className="mt-0.5">
              <a
                href={`/dashboard/contacts/${deal.contact_id}`}
                className="text-[13px] font-semibold text-[var(--color-signal)] hover:underline"
              >
                View contact →
              </a>
            </dd>
          </div>
        )}
        {deal.lost_reason && <Row label="Lost reason" value={deal.lost_reason} />}
      </dl>
    </SlideOver>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-[10.5px] font-semibold uppercase tracking-wide text-[var(--color-slate)]/60">{label}</dt>
      <dd className="mt-0.5 text-[13px] text-[var(--color-ink)]">{value}</dd>
    </div>
  );
}

function NewDealPanel({
  open,
  onClose,
  onSaved,
}: {
  open: boolean;
  onClose: () => void;
  onSaved: () => void;
}) {
  const mutation = useMutation();
  const [form, setForm] = useState({
    title: "",
    amount: "",
    contact_id: null as string | null,
    company_id: null as string | null,
    stage: "new" as DealStage,
  });
  return (
    <SlideOver
      open={open}
      onClose={onClose}
      title="New deal"
      footer={
        <PrimaryButton
          className="ml-auto"
          disabled={mutation.pending || !form.title.trim()}
          onClick={async () => {
            const r = await mutation.run(() =>
              createDeal({
                title: form.title,
                amount: form.amount ? Number(form.amount) : null,
                contact_id: form.contact_id,
                company_id: form.company_id,
                stage: form.stage,
              }),
            );
            if (r.ok) {
              setForm({ title: "", amount: "", contact_id: null, company_id: null, stage: "new" });
              onSaved();
            }
          }}
        >
          {mutation.pending ? "Saving…" : "Create deal"}
        </PrimaryButton>
      }
    >
      <TextField label="Title" required value={form.title} onChange={(v) => setForm({ ...form, title: v })} />
      <TextField label="Amount (USD)" type="number" value={form.amount} onChange={(v) => setForm({ ...form, amount: v })} />
      <EntityPicker
        kind="contact"
        label="Contact"
        value={form.contact_id}
        onChange={(id) => setForm({ ...form, contact_id: id })}
      />
      <EntityPicker
        kind="company"
        label="Company"
        value={form.company_id}
        onChange={(id) => setForm({ ...form, company_id: id })}
      />
      <label className="mb-4 block">
        <span className="mb-1.5 block text-[11px] font-semibold uppercase tracking-wide text-[var(--color-slate)]/70">
          Stage
        </span>
        <select
          value={form.stage}
          onChange={(e) => setForm({ ...form, stage: e.target.value as DealStage })}
          className="h-10 w-full rounded-lg bg-[rgba(255,255,255,0.04)] px-3 text-[13.5px] text-[var(--color-ink)] ring-1 ring-[rgba(255,255,255,0.10)]"
        >
          {DEAL_STAGES.map((s) => (
            <option key={s} value={s}>
              {STAGE_LABEL[s]}
            </option>
          ))}
        </select>
      </label>
      {mutation.error && <p className="text-[12px] text-rose-600">{mutation.error}</p>}
    </SlideOver>
  );
}
