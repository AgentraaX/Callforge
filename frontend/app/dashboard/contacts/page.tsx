"use client";

import { useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { MagnifyingGlass, Plus, Users } from "@phosphor-icons/react";
import { createContact, listContacts } from "../../../lib/crm";
import { LIFECYCLES, type Contact, type Lifecycle } from "../../../lib/crm-types";
import { useMutation, useResource } from "../_hooks/useCrm";
import { DataTable, Pagination, type Column } from "../_components/DataTable";
import { EntityPicker } from "../_components/EntityPicker";
import {
  Avatar,
  EmptyState,
  ErrorNote,
  FadeIn,
  LifecycleBadge,
  Panel,
  PageHeader,
  PrimaryButton,
  Skeleton,
  timeAgo,
} from "../_components/ui";
import {
  CheckboxField,
  SelectField,
  SlideOver,
  TextField,
} from "../_components/SlideOver";

const PAGE_SIZE = 25;

const EMPTY_FORM = {
  first_name: "",
  last_name: "",
  email: "",
  phone: "",
  title: "",
  company_id: null as string | null,
  lifecycle_stage: "lead" as Lifecycle,
  do_not_call: false,
};

export default function ContactsPage() {
  const router = useRouter();
  const [q, setQ] = useState("");
  const [stage, setStage] = useState<Lifecycle | "">("");
  const [offset, setOffset] = useState(0);
  const [sort, setSort] = useState("-created_at");
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState(EMPTY_FORM);

  const { data, loading, error, reload } = useResource(
    () =>
      listContacts({
        q: q || undefined,
        lifecycle_stage: stage || undefined,
        limit: PAGE_SIZE,
        offset,
        order_by: sort,
      }),
    [q, stage, offset, sort],
  );
  const mutation = useMutation();

  const columns: Column<Contact>[] = useMemo(
    () => [
      {
        key: "name",
        label: "Contact",
        sortKey: "full_name",
        render: (c) => (
          <div className="flex items-center gap-3">
            <Avatar name={c.full_name || c.email || "?"} />
            <div className="min-w-0">
              <p className="whitespace-nowrap text-[13px] font-semibold text-[var(--color-ink)]">
                {c.full_name || "Unnamed contact"}
              </p>
              <p className="mt-0.5 whitespace-nowrap text-[11px] text-[var(--color-slate)]/70">
                {c.email || c.phone || "no contact details"}
              </p>
            </div>
          </div>
        ),
      },
      { key: "title", label: "Title", render: (c) => c.title || "—" },
      { key: "phone", label: "Phone", render: (c) => c.phone || "—" },
      {
        key: "stage",
        label: "Stage",
        sortKey: "lifecycle_stage",
        render: (c) => <LifecycleBadge stage={c.lifecycle_stage} />,
      },
      {
        key: "updated",
        label: "Last activity",
        sortKey: "last_contacted_at",
        render: (c) => (
          <span className="text-[12px] text-[var(--color-slate)]/80">
            {timeAgo(c.last_contacted_at || c.updated_at)}
          </span>
        ),
      },
    ],
    [],
  );

  async function submit() {
    const r = await mutation.run(() =>
      createContact({
        ...form,
        full_name: [form.first_name, form.last_name].filter(Boolean).join(" ").trim() || undefined,
      }),
    );
    if (r.ok) {
      setShowForm(false);
      setForm(EMPTY_FORM);
      router.push(`/dashboard/contacts/${r.data.id}`);
    }
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Contacts"
        subtitle="Everyone your team is selling to. Calls placed by the voice agent land on the matching contact automatically."
        actions={
          <PrimaryButton onClick={() => setShowForm(true)}>
            <Plus size={14} weight="bold" />
            New contact
          </PrimaryButton>
        }
      />

      <FadeIn>
        <Panel className="overflow-hidden">
          <div className="flex flex-wrap items-center gap-3 border-b border-[rgba(255,255,255,0.08)] px-5 py-3">
            <label className="flex h-9 flex-1 min-w-[220px] items-center gap-2 rounded-lg bg-[rgba(255,255,255,0.04)] px-3 ring-1 ring-[rgba(255,255,255,0.10)] focus-within:bg-[var(--color-card)] focus-within:ring-2 focus-within:ring-[var(--color-signal)]/40">
              <MagnifyingGlass size={15} className="shrink-0 text-[var(--color-slate)]/60" />
              <input
                value={q}
                onChange={(e) => {
                  setOffset(0);
                  setQ(e.target.value);
                }}
                placeholder="Search name, email, phone…"
                className="w-full bg-transparent text-[13px] text-[var(--color-ink)] outline-none placeholder:text-[var(--color-slate)]/50"
              />
            </label>
            <select
              value={stage}
              onChange={(e) => {
                setOffset(0);
                setStage(e.target.value as Lifecycle | "");
              }}
              className="h-9 rounded-lg bg-[rgba(255,255,255,0.04)] px-3 text-[13px] text-[var(--color-ink)] ring-1 ring-[rgba(255,255,255,0.10)]"
            >
              <option value="">All stages</option>
              {LIFECYCLES.map((s) => (
                <option key={s} value={s}>
                  {s === "mql" || s === "sql" ? s.toUpperCase() : s[0].toUpperCase() + s.slice(1)}
                </option>
              ))}
            </select>
          </div>

          {error && <div className="p-4"><ErrorNote message={error} /></div>}
          {loading && !data ? (
            <Skeleton />
          ) : !loading && (data?.items.length ?? 0) === 0 ? (
            <EmptyState
              icon={Users}
              title="No contacts yet"
              note="Add one manually, or place a call from the Dialer and it'll create the contact for you."
              action={
                <PrimaryButton onClick={() => setShowForm(true)}>
                  <Plus size={14} weight="bold" /> New contact
                </PrimaryButton>
              }
            />
          ) : (
            data && (
              <>
                <DataTable
                  columns={columns}
                  rows={data.items}
                  sort={sort}
                  onSortChange={setSort}
                  onRowClick={(c) => router.push(`/dashboard/contacts/${c.id}`)}
                />
                <Pagination
                  total={data.total}
                  limit={PAGE_SIZE}
                  offset={offset}
                  onChange={setOffset}
                />
              </>
            )
          )}
        </Panel>
      </FadeIn>

      <SlideOver
        open={showForm}
        onClose={() => setShowForm(false)}
        title="New contact"
        footer={
          <div className="flex items-center justify-between">
            {mutation.error && <span className="text-[12px] text-rose-600">{mutation.error}</span>}
            <PrimaryButton onClick={submit} disabled={mutation.pending} className="ml-auto">
              {mutation.pending ? "Saving…" : "Create contact"}
            </PrimaryButton>
          </div>
        }
      >
        <TextField label="First name" value={form.first_name} onChange={(v) => setForm({ ...form, first_name: v })} />
        <TextField label="Last name" value={form.last_name} onChange={(v) => setForm({ ...form, last_name: v })} />
        <TextField label="Email" type="email" value={form.email} onChange={(v) => setForm({ ...form, email: v })} />
        <TextField label="Phone (E.164)" value={form.phone} placeholder="+14155552671" onChange={(v) => setForm({ ...form, phone: v })} />
        <TextField label="Title" value={form.title} onChange={(v) => setForm({ ...form, title: v })} />
        <EntityPicker
          kind="company"
          label="Company"
          value={form.company_id}
          onChange={(id) => setForm({ ...form, company_id: id })}
        />
        <SelectField
          label="Lifecycle stage"
          value={form.lifecycle_stage}
          onChange={(v) => setForm({ ...form, lifecycle_stage: v })}
          options={LIFECYCLES.map((s) => ({ value: s, label: s === "mql" || s === "sql" ? s.toUpperCase() : s[0].toUpperCase() + s.slice(1) }))}
        />
        <CheckboxField
          label="Do not call"
          checked={form.do_not_call}
          onChange={(v) => setForm({ ...form, do_not_call: v })}
        />
      </SlideOver>
    </div>
  );
}
