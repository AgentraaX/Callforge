"use client";

import { useEffect, useState } from "react";
import { UserPlus } from "@phosphor-icons/react";
import { getOrg, inviteMember, listMembers, updateOrg } from "../../../lib/crm";
import { useAuth } from "../../context/AuthContext";
import { useMutation, useResource } from "../_hooks/useCrm";
import {
  Avatar,
  ErrorNote,
  FadeIn,
  GhostButton,
  Panel,
  PanelHeader,
  PageHeader,
  PrimaryButton,
  Skeleton,
} from "../_components/ui";

export default function SettingsPage() {
  const { user } = useAuth();
  const org = useResource(() => getOrg(), []);
  const members = useResource(() => listMembers(), []);
  const mutation = useMutation();

  const [name, setName] = useState("");
  const [invite, setInvite] = useState("");

  useEffect(() => {
    if (org.data) setName(org.data.name);
  }, [org.data]);

  const myRole = members.data?.find((m) => m.email === user?.email)?.role;
  const isOwner = myRole === "owner";

  return (
    <div className="space-y-6">
      <PageHeader title="Settings" subtitle="Your organisation and the teammates who share this pipeline." />

      {(org.error || members.error) && <ErrorNote message={org.error || members.error || ""} />}

      <FadeIn>
        <Panel className="p-5">
          <h2 className="text-[15px] font-semibold text-[var(--color-ink)]">Organisation</h2>
          {org.loading && !org.data ? (
            <Skeleton rows={2} />
          ) : (
            <div className="mt-4 flex flex-wrap items-end gap-3">
              <label className="block flex-1 min-w-[220px]">
                <span className="mb-1.5 block text-[11px] font-semibold uppercase tracking-wide text-[var(--color-slate)]/70">
                  Name
                </span>
                <input
                  value={name}
                  disabled={!isOwner}
                  onChange={(e) => setName(e.target.value)}
                  className="h-10 w-full rounded-lg bg-[rgba(255,255,255,0.04)] px-3 text-[13.5px] text-[var(--color-ink)] ring-1 ring-[rgba(255,255,255,0.10)] disabled:opacity-60"
                />
              </label>
              {isOwner && (
                <PrimaryButton
                  disabled={mutation.pending || !name.trim() || name === org.data?.name}
                  onClick={async () => {
                    const r = await mutation.run(() => updateOrg(name));
                    if (r.ok) org.reload();
                  }}
                >
                  Save
                </PrimaryButton>
              )}
            </div>
          )}
          {!isOwner && (
            <p className="mt-2 text-[12px] text-[var(--color-slate)]/70">Only an owner can rename the organisation.</p>
          )}
        </Panel>
      </FadeIn>

      <FadeIn delay={0.05}>
        <Panel className="overflow-hidden">
          <PanelHeader title="Members" count={members.data?.length ?? 0} />
          {members.loading && !members.data ? (
            <Skeleton rows={3} />
          ) : (
            <ul className="divide-y divide-[rgba(255,255,255,0.08)]">
              {(members.data || []).map((m) => (
                <li key={m.email} className="flex items-center gap-3 px-5 py-3">
                  <Avatar name={m.email} />
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-[13px] font-medium text-[var(--color-ink)]">{m.email}</p>
                  </div>
                  <span
                    className={`rounded-full px-2.5 py-1 text-[11px] font-semibold capitalize ring-1 ${
                      m.role === "owner"
                        ? "bg-[var(--color-signal-line)] text-[var(--color-signal)] ring-[rgba(5,118,118,0.2)]"
                        : "bg-[rgba(255,255,255,0.06)] text-[var(--color-slate)] ring-[rgba(255,255,255,0.10)]"
                    }`}
                  >
                    {m.role}
                  </span>
                </li>
              ))}
            </ul>
          )}

          {isOwner && (
            <div className="flex flex-wrap items-center gap-2 border-t border-[rgba(255,255,255,0.08)] px-5 py-4">
              <input
                value={invite}
                type="email"
                onChange={(e) => setInvite(e.target.value)}
                placeholder="teammate@company.com"
                className="h-10 flex-1 min-w-[220px] rounded-lg bg-[rgba(255,255,255,0.04)] px-3 text-[13.5px] text-[var(--color-ink)] ring-1 ring-[rgba(255,255,255,0.10)]"
              />
              <GhostButton
                onClick={async () => {
                  const r = await mutation.run(() => inviteMember(invite.trim()));
                  if (r.ok) {
                    setInvite("");
                    members.reload();
                  }
                }}
              >
                <UserPlus size={13} /> Add member
              </GhostButton>
            </div>
          )}
          {mutation.error && <p className="px-5 pb-3 text-[12px] text-rose-600">{mutation.error}</p>}
        </Panel>
      </FadeIn>

      <p className="text-[12px] text-[var(--color-slate)]/70">
        Adding a member lets an existing CallForge account with that email see this org&rsquo;s CRM data on
        their next sign-in.
      </p>
    </div>
  );
}
