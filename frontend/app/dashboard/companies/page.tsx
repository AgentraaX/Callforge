"use client";

import { useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { Buildings, MagnifyingGlass, Plus } from "@phosphor-icons/react";
import { createCompany, listCompanies } from "../../../lib/crm";
import type { Company } from "../../../lib/crm-types";
import { useMutation, useResource } from "../_hooks/useCrm";
import { DataTable, Pagination, type Column } from "../_components/DataTable";
import {
  EmptyState,
  ErrorNote,
  FadeIn,
  Panel,
  PageHeader,
  PrimaryButton,
  Skeleton,
  timeAgo,
} from "../_components/ui";
import { SlideOver, TextAreaField, TextField } from "../_components/SlideOver";

const PAGE_SIZE = 25;
const EMPTY = { name: "", domain: "", industry: "", size: "", website: "", phone: "", notes: "" };

export default function CompaniesPage() {
  const router = useRouter();
  const [q, setQ] = useState("");
  const [offset, setOffset] = useState(0);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState(EMPTY);

  const { data, loading, error, reload } = useResource(
    () => listCompanies({ q: q || undefined, limit: PAGE_SIZE, offset }),
    [q, offset],
  );
  const mutation = useMutation();

  const columns: Column<Company>[] = useMemo(
    () => [
      {
        key: "name",
        label: "Company",
        render: (c) => (
          <div>
            <p className="text-[13px] font-semibold text-[var(--color-ink)]">{c.name}</p>
            {c.domain && <p className="mt-0.5 text-[11px] text-[var(--color-slate)]/70">{c.domain}</p>}
          </div>
        ),
      },
      { key: "industry", label: "Industry", render: (c) => c.industry || "—" },
      { key: "size", label: "Size", render: (c) => c.size || "—" },
      { key: "phone", label: "Phone", render: (c) => c.phone || "—" },
      {
        key: "created",
        label: "Added",
        render: (c) => <span className="text-[12px] text-[var(--color-slate)]/80">{timeAgo(c.created_at)}</span>,
      },
    ],
    [],
  );

  return (
    <div className="space-y-6">
      <PageHeader
        title="Companies"
        subtitle="Accounts your contacts belong to."
        actions={
          <PrimaryButton onClick={() => setShowForm(true)}>
            <Plus size={14} weight="bold" /> New company
          </PrimaryButton>
        }
      />

      <FadeIn>
        <Panel className="overflow-hidden">
          <div className="flex items-center gap-3 border-b border-[rgba(255,255,255,0.08)] px-5 py-3">
            <label className="flex h-9 flex-1 items-center gap-2 rounded-lg bg-[rgba(255,255,255,0.04)] px-3 ring-1 ring-[rgba(255,255,255,0.10)] focus-within:bg-[var(--color-card)] focus-within:ring-2 focus-within:ring-[var(--color-signal)]/40">
              <MagnifyingGlass size={15} className="shrink-0 text-[var(--color-slate)]/60" />
              <input
                value={q}
                onChange={(e) => {
                  setOffset(0);
                  setQ(e.target.value);
                }}
                placeholder="Search companies…"
                className="w-full bg-transparent text-[13px] text-[var(--color-ink)] outline-none placeholder:text-[var(--color-slate)]/50"
              />
            </label>
          </div>

          {error && <div className="p-4"><ErrorNote message={error} /></div>}
          {loading && !data ? (
            <Skeleton />
          ) : !loading && (data?.items.length ?? 0) === 0 ? (
            <EmptyState
              icon={Buildings}
              title="No companies yet"
              note="Add the accounts you sell into, then link contacts and deals to them."
              action={
                <PrimaryButton onClick={() => setShowForm(true)}>
                  <Plus size={14} weight="bold" /> New company
                </PrimaryButton>
              }
            />
          ) : (
            data && (
              <>
                <DataTable
                  columns={columns}
                  rows={data.items}
                  onRowClick={(c) => router.push(`/dashboard/companies/${c.id}`)}
                />
                <Pagination total={data.total} limit={PAGE_SIZE} offset={offset} onChange={setOffset} />
              </>
            )
          )}
        </Panel>
      </FadeIn>

      <SlideOver
        open={showForm}
        onClose={() => setShowForm(false)}
        title="New company"
        footer={
          <PrimaryButton
            className="ml-auto"
            disabled={mutation.pending || !form.name.trim()}
            onClick={async () => {
              const r = await mutation.run(() => createCompany(form));
              if (r.ok) {
                setForm(EMPTY);
                setShowForm(false);
                reload();
                router.push(`/dashboard/companies/${r.data.id}`);
              }
            }}
          >
            {mutation.pending ? "Saving…" : "Create company"}
          </PrimaryButton>
        }
      >
        <TextField label="Name" required value={form.name} onChange={(v) => setForm({ ...form, name: v })} />
        <TextField label="Domain" value={form.domain} placeholder="acme.com" onChange={(v) => setForm({ ...form, domain: v })} />
        <TextField label="Industry" value={form.industry} onChange={(v) => setForm({ ...form, industry: v })} />
        <TextField label="Size" value={form.size} placeholder="11-50" onChange={(v) => setForm({ ...form, size: v })} />
        <TextField label="Website" value={form.website} onChange={(v) => setForm({ ...form, website: v })} />
        <TextField label="Phone" value={form.phone} onChange={(v) => setForm({ ...form, phone: v })} />
        <TextAreaField label="Notes" value={form.notes} onChange={(v) => setForm({ ...form, notes: v })} />
        {mutation.error && <p className="text-[12px] text-rose-600">{mutation.error}</p>}
      </SlideOver>
    </div>
  );
}
