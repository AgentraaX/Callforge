"use client";

import { use, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ArrowLeft, Trash } from "@phosphor-icons/react";
import {
  deleteCompany,
  getCompany,
  listContacts,
  listDeals,
  updateCompany,
} from "../../../../lib/crm";
import type { Company } from "../../../../lib/crm-types";
import { useMutation, useResource } from "../../_hooks/useCrm";
import {
  Avatar,
  ErrorNote,
  FadeIn,
  formatMoney,
  GhostButton,
  LifecycleBadge,
  Panel,
  PanelHeader,
  PrimaryButton,
  Skeleton,
  StageBadge,
} from "../../_components/ui";
import { SlideOver, TextAreaField, TextField } from "../../_components/SlideOver";

export default function CompanyDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const router = useRouter();
  const company = useResource(() => getCompany(id), [id]);
  const contacts = useResource(() => listContacts({ company_id: id, limit: 100 }), [id]);
  const deals = useResource(() => listDeals({ limit: 100 }), [id]);
  const mutation = useMutation();
  const [editing, setEditing] = useState(false);

  const c = company.data;
  if (company.loading && !c) return <Skeleton rows={6} />;
  if (company.error || !c) {
    return (
      <div className="space-y-4">
        <Back />
        <ErrorNote message={company.error || "Company not found"} />
      </div>
    );
  }

  const companyDeals = (deals.data?.items || []).filter((d) => d.company_id === id);

  return (
    <div className="space-y-6">
      <Back />
      <FadeIn>
        <Panel className="p-5">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <h1 className="text-[22px] font-semibold tracking-[-0.01em] text-[var(--color-ink)]">{c.name}</h1>
              <p className="mt-0.5 text-[13px] text-[var(--color-slate)]">
                {[c.industry, c.size, c.domain].filter(Boolean).join(" · ") || "No details yet"}
              </p>
            </div>
            <div className="flex items-center gap-2">
              <GhostButton onClick={() => setEditing(true)}>Edit</GhostButton>
              <button
                onClick={async () => {
                  if (!confirm("Delete this company?")) return;
                  const r = await mutation.run(() => deleteCompany(id));
                  if (r.ok) router.push("/dashboard/companies");
                }}
                aria-label="Delete company"
                className="flex h-8 w-8 items-center justify-center rounded-lg text-[var(--color-slate)]/70 ring-1 ring-[rgba(255,255,255,0.14)] transition-colors hover:bg-rose-50 hover:text-rose-600"
              >
                <Trash size={14} />
              </button>
            </div>
          </div>
          {c.notes && (
            <p className="mt-4 border-t border-[rgba(255,255,255,0.08)] pt-4 text-[13px] leading-relaxed text-[var(--color-slate)]">
              {c.notes}
            </p>
          )}
        </Panel>
      </FadeIn>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <Panel className="overflow-hidden">
          <PanelHeader title="Contacts" count={contacts.data?.total ?? 0} />
          <div className="divide-y divide-[rgba(255,255,255,0.08)]">
            {(contacts.data?.items || []).map((p) => (
              <Link
                key={p.id}
                href={`/dashboard/contacts/${p.id}`}
                className="flex items-center gap-3 px-5 py-3 transition-colors hover:bg-[rgba(255,255,255,0.04)]"
              >
                <Avatar name={p.full_name || p.email || "?"} />
                <div className="min-w-0 flex-1">
                  <p className="truncate text-[13px] font-semibold text-[var(--color-ink)]">{p.full_name || "Unnamed"}</p>
                  <p className="truncate text-[11px] text-[var(--color-slate)]/70">{p.title || p.email || p.phone || "—"}</p>
                </div>
                <LifecycleBadge stage={p.lifecycle_stage} />
              </Link>
            ))}
            {contacts.data && contacts.data.items.length === 0 && (
              <p className="px-5 py-6 text-center text-[12.5px] text-[var(--color-slate)]/60">No contacts linked yet.</p>
            )}
          </div>
        </Panel>

        <Panel className="overflow-hidden">
          <PanelHeader title="Deals" count={companyDeals.length} />
          <div className="divide-y divide-[rgba(255,255,255,0.08)]">
            {companyDeals.map((d) => (
              <Link
                key={d.id}
                href={`/dashboard/deals?deal=${d.id}`}
                className="flex items-center justify-between px-5 py-3 transition-colors hover:bg-[rgba(255,255,255,0.04)]"
              >
                <div className="min-w-0">
                  <p className="truncate text-[13px] font-medium text-[var(--color-ink)]">{d.title}</p>
                  <p className="mt-0.5 text-[11.5px] text-[var(--color-slate)]/70">{formatMoney(d.amount, d.currency)}</p>
                </div>
                <StageBadge stage={d.stage} />
              </Link>
            ))}
            {companyDeals.length === 0 && (
              <p className="px-5 py-6 text-center text-[12.5px] text-[var(--color-slate)]/60">No deals yet.</p>
            )}
          </div>
        </Panel>
      </div>

      {editing && (
        <EditCompanyPanel
          company={c}
          onClose={() => setEditing(false)}
          onSaved={() => {
            setEditing(false);
            company.reload();
          }}
        />
      )}
    </div>
  );
}

function EditCompanyPanel({
  company,
  onClose,
  onSaved,
}: {
  company: Company;
  onClose: () => void;
  onSaved: () => void;
}) {
  const mutation = useMutation();
  const [f, setF] = useState({
    name: company.name,
    domain: company.domain || "",
    industry: company.industry || "",
    size: company.size || "",
    website: company.website || "",
    phone: company.phone || "",
    notes: company.notes || "",
  });
  return (
    <SlideOver
      open
      onClose={onClose}
      title="Edit company"
      footer={
        <PrimaryButton
          className="ml-auto"
          disabled={mutation.pending || !f.name.trim()}
          onClick={async () => {
            const r = await mutation.run(() => updateCompany(company.id, f));
            if (r.ok) onSaved();
          }}
        >
          {mutation.pending ? "Saving…" : "Save changes"}
        </PrimaryButton>
      }
    >
      <TextField label="Name" value={f.name} onChange={(v) => setF({ ...f, name: v })} />
      <TextField label="Domain" value={f.domain} onChange={(v) => setF({ ...f, domain: v })} />
      <TextField label="Industry" value={f.industry} onChange={(v) => setF({ ...f, industry: v })} />
      <TextField label="Size" value={f.size} onChange={(v) => setF({ ...f, size: v })} />
      <TextField label="Website" value={f.website} onChange={(v) => setF({ ...f, website: v })} />
      <TextField label="Phone" value={f.phone} onChange={(v) => setF({ ...f, phone: v })} />
      <TextAreaField label="Notes" value={f.notes} onChange={(v) => setF({ ...f, notes: v })} />
      {mutation.error && <p className="text-[12px] text-rose-600">{mutation.error}</p>}
    </SlideOver>
  );
}

function Back() {
  return (
    <Link
      href="/dashboard/companies"
      className="inline-flex items-center gap-1.5 text-[12.5px] font-semibold text-[var(--color-slate)] transition-colors hover:text-[var(--color-ink)]"
    >
      <ArrowLeft size={13} weight="bold" /> All companies
    </Link>
  );
}
