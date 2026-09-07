"use client";

import { use, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  ArrowLeft,
  CalendarPlus,
  NotePencil,
  PhoneCall,
  Trash,
} from "@phosphor-icons/react";
import {
  completeActivity,
  contactTimeline,
  createActivity,
  deleteContact,
  getContact,
  listActivities,
  listDeals,
  updateContact,
} from "../../../../lib/crm";
import { LIFECYCLES, type Contact, type Lifecycle } from "../../../../lib/crm-types";
import { useMutation, useResource } from "../../_hooks/useCrm";
import { CallTranscriptModal } from "../../_components/CallTranscriptModal";
import { Timeline } from "../../_components/Timeline";
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
  timeAgo,
} from "../../_components/ui";
import { SelectField, SlideOver, TextAreaField, TextField } from "../../_components/SlideOver";

export default function ContactDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const router = useRouter();

  const contact = useResource(() => getContact(id), [id]);
  const timeline = useResource(() => contactTimeline(id), [id]);
  const deals = useResource(() => listDeals({ contact_id: id, limit: 50 }), [id]);
  const tasks = useResource(
    () => listActivities({ contact_id: id, type: "task", status: "open", limit: 50 }),
    [id],
  );
  const mutation = useMutation();

  const [editing, setEditing] = useState(false);
  const [noteOpen, setNoteOpen] = useState(false);
  const [taskOpen, setTaskOpen] = useState(false);
  const [transcriptId, setTranscriptId] = useState<string | null>(null);

  const c = contact.data;

  function reloadAll() {
    contact.reload();
    timeline.reload();
    deals.reload();
    tasks.reload();
  }

  if (contact.loading && !c) {
    return (
      <div className="space-y-4">
        <Skeleton rows={2} />
        <Skeleton rows={6} />
      </div>
    );
  }
  if (contact.error || !c) {
    return (
      <div className="space-y-4">
        <BackLink />
        <ErrorNote message={contact.error || "Contact not found"} />
      </div>
    );
  }

  const dialHref = c.phone
    ? `/dashboard/dialer?to=${encodeURIComponent(c.phone)}`
    : "/dashboard/dialer";

  return (
    <div className="space-y-6">
      <BackLink />

      <FadeIn>
        <Panel className="p-5">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div className="flex items-center gap-4">
              <Avatar name={c.full_name || c.email || "?"} size={52} />
              <div>
                <h1 className="text-[22px] font-semibold tracking-[-0.01em] text-[var(--color-ink)]">
                  {c.full_name || "Unnamed contact"}
                </h1>
                <p className="mt-0.5 text-[13px] text-[var(--color-slate)]">
                  {[c.title, c.company_id ? "" : null].filter(Boolean).join(" · ") || "No title"}
                </p>
                <div className="mt-2 flex flex-wrap items-center gap-2">
                  <LifecycleBadge stage={c.lifecycle_stage} />
                  {c.do_not_call && (
                    <span className="rounded-full bg-rose-50 px-2.5 py-1 text-[11px] font-semibold text-rose-600 ring-1 ring-rose-100">
                      Do not call
                    </span>
                  )}
                </div>
              </div>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <PrimaryButton onClick={() => router.push(dialHref)}>
                <PhoneCall size={14} weight="fill" />
                Call
              </PrimaryButton>
              <GhostButton onClick={() => setEditing(true)}>Edit</GhostButton>
              <button
                onClick={async () => {
                  if (!confirm("Delete this contact and its activities?")) return;
                  const r = await mutation.run(() => deleteContact(id));
                  if (r.ok) router.push("/dashboard/contacts");
                }}
                aria-label="Delete contact"
                className="flex h-8 w-8 items-center justify-center rounded-lg text-[var(--color-slate)]/70 ring-1 ring-[rgba(255,255,255,0.14)] transition-colors hover:bg-rose-50 hover:text-rose-600"
              >
                <Trash size={14} />
              </button>
            </div>
          </div>

          <dl className="mt-5 grid grid-cols-2 gap-x-6 gap-y-3 border-t border-[rgba(255,255,255,0.08)] pt-4 text-[13px] sm:grid-cols-4">
            <Detail label="Email" value={c.email} />
            <Detail label="Phone" value={c.phone} />
            <Detail label="Source" value={c.source} />
            <Detail label="Owner" value={c.owner_email} />
          </dl>
        </Panel>
      </FadeIn>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <div className="space-y-6 lg:col-span-2">
          <Panel className="overflow-hidden">
            <PanelHeader
              title="Timeline"
              actions={
                <div className="flex items-center gap-2">
                  <GhostButton onClick={() => setNoteOpen(true)}>
                    <NotePencil size={13} /> Note
                  </GhostButton>
                  <GhostButton onClick={() => setTaskOpen(true)}>
                    <CalendarPlus size={13} /> Task
                  </GhostButton>
                </div>
              }
            />
            {timeline.loading && !timeline.data ? (
              <Skeleton rows={4} />
            ) : (
              <Timeline items={timeline.data?.items || []} onSelectCall={setTranscriptId} />
            )}
          </Panel>
        </div>

        <div className="space-y-6">
          <Panel className="overflow-hidden">
            <PanelHeader title="Deals" count={deals.data?.total ?? 0} />
            <div className="divide-y divide-[rgba(255,255,255,0.08)]">
              {(deals.data?.items || []).map((d) => (
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
              {deals.data && deals.data.items.length === 0 && (
                <p className="px-5 py-6 text-center text-[12.5px] text-[var(--color-slate)]/60">No deals yet.</p>
              )}
            </div>
          </Panel>

          <Panel className="overflow-hidden">
            <PanelHeader title="Open tasks" count={tasks.data?.total ?? 0} />
            <div className="divide-y divide-[rgba(255,255,255,0.08)]">
              {(tasks.data?.items || []).map((t) => (
                <div key={t.id} className="flex items-start gap-3 px-5 py-3">
                  <button
                    onClick={async () => {
                      await mutation.run(() => completeActivity(t.id));
                      reloadAll();
                    }}
                    aria-label="Complete task"
                    className="mt-0.5 h-4 w-4 shrink-0 rounded border border-[rgba(255,255,255,0.25)] transition-colors hover:border-[var(--color-signal)] hover:bg-[var(--color-signal)]/10"
                  />
                  <div className="min-w-0">
                    <p className="text-[13px] text-[var(--color-ink)]">{t.subject}</p>
                    {t.due_at && (
                      <p className="mt-0.5 text-[11px] text-[var(--color-slate)]/70">due {timeAgo(t.due_at)}</p>
                    )}
                  </div>
                </div>
              ))}
              {tasks.data && tasks.data.items.length === 0 && (
                <p className="px-5 py-6 text-center text-[12.5px] text-[var(--color-slate)]/60">Nothing due.</p>
              )}
            </div>
          </Panel>
        </div>
      </div>

      {editing && (
        <EditContactPanel
          contact={c}
          onClose={() => setEditing(false)}
          onSaved={() => {
            setEditing(false);
            reloadAll();
          }}
        />
      )}

      <NotePanel
        open={noteOpen}
        onClose={() => setNoteOpen(false)}
        onSaved={() => {
          setNoteOpen(false);
          timeline.reload();
        }}
        contactId={id}
      />
      <TaskPanel
        open={taskOpen}
        onClose={() => setTaskOpen(false)}
        onSaved={() => {
          setTaskOpen(false);
          reloadAll();
        }}
        contactId={id}
      />

      {transcriptId && (
        <CallTranscriptModal callId={transcriptId} onClose={() => setTranscriptId(null)} />
      )}
    </div>
  );
}

function BackLink() {
  return (
    <Link
      href="/dashboard/contacts"
      className="inline-flex items-center gap-1.5 text-[12.5px] font-semibold text-[var(--color-slate)] transition-colors hover:text-[var(--color-ink)]"
    >
      <ArrowLeft size={13} weight="bold" /> All contacts
    </Link>
  );
}

function Detail({ label, value }: { label: string; value: string | null }) {
  return (
    <div>
      <dt className="text-[10.5px] font-semibold uppercase tracking-wide text-[var(--color-slate)]/60">{label}</dt>
      <dd className="mt-0.5 truncate text-[13px] text-[var(--color-ink)]">{value || "—"}</dd>
    </div>
  );
}

function EditContactPanel({
  contact,
  onClose,
  onSaved,
}: {
  contact: Contact;
  onClose: () => void;
  onSaved: () => void;
}) {
  const mutation = useMutation();
  const [form, setForm] = useState({
    first_name: contact.first_name || "",
    last_name: contact.last_name || "",
    email: contact.email || "",
    phone: contact.phone || "",
    title: contact.title || "",
    lifecycle_stage: contact.lifecycle_stage,
  });

  return (
    <SlideOver
      open
      onClose={onClose}
      title="Edit contact"
      footer={
        <PrimaryButton
          className="ml-auto"
          disabled={mutation.pending}
          onClick={async () => {
            const r = await mutation.run(() =>
              updateContact(contact.id, {
                ...form,
                full_name: [form.first_name, form.last_name].filter(Boolean).join(" ").trim() || undefined,
              }),
            );
            if (r.ok) onSaved();
          }}
        >
          {mutation.pending ? "Saving…" : "Save changes"}
        </PrimaryButton>
      }
    >
      <TextField label="First name" value={form.first_name} onChange={(v) => setForm({ ...form, first_name: v })} />
      <TextField label="Last name" value={form.last_name} onChange={(v) => setForm({ ...form, last_name: v })} />
      <TextField label="Email" value={form.email} onChange={(v) => setForm({ ...form, email: v })} />
      <TextField label="Phone (E.164)" value={form.phone} onChange={(v) => setForm({ ...form, phone: v })} />
      <TextField label="Title" value={form.title} onChange={(v) => setForm({ ...form, title: v })} />
      <SelectField
        label="Lifecycle stage"
        value={form.lifecycle_stage}
        onChange={(v: Lifecycle) => setForm({ ...form, lifecycle_stage: v })}
        options={LIFECYCLES.map((s) => ({
          value: s,
          label: s === "mql" || s === "sql" ? s.toUpperCase() : s[0].toUpperCase() + s.slice(1),
        }))}
      />
      {mutation.error && <p className="text-[12px] text-rose-600">{mutation.error}</p>}
    </SlideOver>
  );
}

function NotePanel({
  open,
  onClose,
  onSaved,
  contactId,
}: {
  open: boolean;
  onClose: () => void;
  onSaved: () => void;
  contactId: string;
}) {
  const mutation = useMutation();
  const [body, setBody] = useState("");
  return (
    <SlideOver
      open={open}
      onClose={onClose}
      title="Add a note"
      footer={
        <PrimaryButton
          className="ml-auto"
          disabled={mutation.pending || !body.trim()}
          onClick={async () => {
            const r = await mutation.run(() =>
              createActivity({ type: "note", subject: "Note", body, contact_id: contactId }),
            );
            if (r.ok) {
              setBody("");
              onSaved();
            }
          }}
        >
          {mutation.pending ? "Saving…" : "Save note"}
        </PrimaryButton>
      }
    >
      <TextAreaField label="Note" value={body} onChange={setBody} rows={6} placeholder="What happened?" />
      {mutation.error && <p className="text-[12px] text-rose-600">{mutation.error}</p>}
    </SlideOver>
  );
}

function TaskPanel({
  open,
  onClose,
  onSaved,
  contactId,
}: {
  open: boolean;
  onClose: () => void;
  onSaved: () => void;
  contactId: string;
}) {
  const mutation = useMutation();
  const [subject, setSubject] = useState("");
  const [due, setDue] = useState("");
  return (
    <SlideOver
      open={open}
      onClose={onClose}
      title="Add a task"
      footer={
        <PrimaryButton
          className="ml-auto"
          disabled={mutation.pending || !subject.trim()}
          onClick={async () => {
            const r = await mutation.run(() =>
              createActivity({
                type: "task",
                subject,
                contact_id: contactId,
                due_at: due ? new Date(due).toISOString() : null,
              }),
            );
            if (r.ok) {
              setSubject("");
              setDue("");
              onSaved();
            }
          }}
        >
          {mutation.pending ? "Saving…" : "Create task"}
        </PrimaryButton>
      }
    >
      <TextField label="Task" value={subject} onChange={setSubject} placeholder="Follow up on pricing" />
      <TextField label="Due" type="datetime-local" value={due} onChange={setDue} />
      {mutation.error && <p className="text-[12px] text-rose-600">{mutation.error}</p>}
    </SlideOver>
  );
}
