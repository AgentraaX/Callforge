"use client";

import { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { AnimatePresence, motion } from "motion/react";
import type { Icon } from "@phosphor-icons/react";
import {
  Bell,
  Buildings,
  CalendarCheck,
  CaretRight,
  Gear,
  Kanban,
  List,
  ListChecks,
  PhoneCall,
  ShieldWarning,
  SignOut,
  SquaresFour,
  UserSound,
  Users,
  X,
} from "@phosphor-icons/react";
import { useAuth } from "../context/AuthContext";
import { useDashboardData } from "./useDashboardData";
import Logo from "../components/brand/Logo";
import GlobalSearch from "./_components/GlobalSearch";
import ProfileMenu from "./_components/ProfileMenu";

interface ShellUser {
  name: string;
  role: string;
  initials: string;
}

function toShellUser(name: string, company: string): ShellUser {
  const displayName = name || "Guest";
  return {
    name: displayName,
    role: company || "CallForge operator",
    initials: displayName.slice(0, 2).toUpperCase(),
  };
}

interface NavEntry {
  label: string;
  icon: Icon;
  href: string;
  badge?: number;
}

function buildNavGroups(pendingEscalations: number): { label: string; items: NavEntry[] }[] {
  return [
    {
      label: "CRM",
      items: [
        { label: "Overview", icon: SquaresFour, href: "/dashboard" },
        { label: "Contacts", icon: Users, href: "/dashboard/contacts" },
        { label: "Companies", icon: Buildings, href: "/dashboard/companies" },
        { label: "Pipeline", icon: Kanban, href: "/dashboard/deals" },
        { label: "Calls", icon: PhoneCall, href: "/dashboard/calls" },
        { label: "Tasks", icon: ListChecks, href: "/dashboard/activities" },
      ],
    },
    {
      label: "Voice",
      items: [
        { label: "Dialer", icon: PhoneCall, href: "/dashboard/dialer" },
        { label: "Test a Call", icon: PhoneCall, href: "/dashboard/test-call" },
        { label: "Personas", icon: UserSound, href: "/dashboard/personas" },
      ],
    },
    {
      label: "Operations",
      items: [
        { label: "Bookings", icon: CalendarCheck, href: "/dashboard/calls?outcome=booked" },
        {
          label: "Escalations",
          icon: ShieldWarning,
          href: "/dashboard/escalations",
          badge: pendingEscalations || undefined,
        },
        { label: "Settings", icon: Gear, href: "/dashboard/settings" },
      ],
    },
  ];
}

function isActive(pathname: string, href: string): boolean {
  const base = href.split("?")[0];
  if (base === "/dashboard") return pathname === "/dashboard";
  return pathname === base || pathname.startsWith(`${base}/`);
}

/* ── Sidebar ───────────────────────────────────────────────────────── */

function NavButton({ item, active }: { item: NavEntry; active: boolean }) {
  const ItemIcon = item.icon;
  return (
    <Link
      href={item.href}
      aria-current={active ? "page" : undefined}
      className={`group relative flex w-full items-center gap-3 rounded-lg px-3 py-2 text-[13px] font-medium transition-colors ${
        active ? "bg-[var(--color-signal-tint)] text-[var(--color-signal)]" : "text-[var(--color-slate)] hover:bg-[rgba(255,255,255,0.04)] hover:text-[var(--color-ink)]"
      }`}
    >
      {active && <span className="absolute left-0 top-1/2 h-5 w-[3px] -translate-y-1/2 rounded-full bg-[var(--color-signal)]" />}
      <ItemIcon
        size={17}
        weight={active ? "fill" : "duotone"}
        className={active ? "text-[var(--color-signal)]" : "text-[var(--color-slate)]/70 group-hover:text-[var(--color-ink)]"}
      />
      <span className={active ? "font-semibold" : ""}>{item.label}</span>
      {item.badge ? (
        <span className="ml-auto inline-flex items-center justify-center rounded-full bg-red-500/15 px-2 py-0.5 text-[10px] font-bold text-red-400">
          {item.badge}
        </span>
      ) : null}
    </Link>
  );
}

function SidebarContent({
  groups,
  pathname,
  user,
  statusLine,
  onLogout,
  onClose,
}: {
  groups: { label: string; items: NavEntry[] }[];
  pathname: string;
  user: ShellUser;
  statusLine: { title: string; note: string };
  onLogout: () => void;
  onClose?: () => void;
}) {
  return (
    <div className="flex h-full flex-col bg-[var(--color-card)]">
      <div className="relative flex h-16 shrink-0 items-center border-b border-[rgba(255,255,255,0.08)] px-5">
        <Logo variant="wordmark" sublabel="CRM" href="/dashboard" />
        {onClose && (
          <button
            onClick={onClose}
            aria-label="Close menu"
            className="absolute right-4 top-1/2 -translate-y-1/2 rounded-lg p-1.5 text-[var(--color-slate)] hover:bg-[rgba(255,255,255,0.04)]"
          >
            <X size={18} weight="bold" />
          </button>
        )}
      </div>

      <nav className="flex-1 overflow-y-auto px-3 py-5">
        {groups.map((group) => (
          <div key={group.label} className="mb-6 last:mb-0">
            <p className="mb-2 px-3 text-[10px] font-semibold uppercase tracking-[0.16em] text-[var(--color-slate)]/60">
              {group.label}
            </p>
            <div className="space-y-0.5">
              {group.items.map((item) => (
                <NavButton key={item.href} item={item} active={isActive(pathname, item.href)} />
              ))}
            </div>
          </div>
        ))}
      </nav>

      <div className="px-4 pb-3">
        <div className="flex items-center gap-3 rounded-xl bg-[rgba(255,255,255,0.04)] px-4 py-3 ring-1 ring-[rgba(255,255,255,0.08)]">
          <span className="relative flex h-2 w-2 shrink-0">
            <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-60" />
            <span className="relative inline-flex h-2 w-2 rounded-full bg-emerald-500" />
          </span>
          <div className="min-w-0">
            <p className="text-[12px] font-semibold leading-tight text-[var(--color-ink)]">{statusLine.title}</p>
            <p className="mt-0.5 truncate text-[11px] text-[var(--color-slate)]/80">{statusLine.note}</p>
          </div>
        </div>
      </div>

      <div className="shrink-0 border-t border-[rgba(255,255,255,0.08)] p-4">
        <div className="flex items-center gap-3">
          <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-[var(--color-signal)] text-[12px] font-bold text-white">
            {user.initials}
          </span>
          <div className="min-w-0 flex-1">
            <p className="truncate text-[13px] font-semibold leading-tight text-[var(--color-ink)]">{user.name}</p>
            <p className="mt-0.5 truncate text-[11px] text-[var(--color-slate)]/80">{user.role}</p>
          </div>
          <button
            onClick={onLogout}
            title="Sign out"
            aria-label="Sign out"
            className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg text-[var(--color-slate)]/70 ring-1 ring-[rgba(255,255,255,0.10)] transition-all hover:bg-red-500/15 hover:text-red-400"
          >
            <SignOut size={15} />
          </button>
        </div>
      </div>
    </div>
  );
}

/* ── Shell ─────────────────────────────────────────────────────────── */

export default function DashboardShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const { user: authUser, logout } = useAuth();
  const { escalations, liveCalls, personas } = useDashboardData();
  const [drawerOpen, setDrawerOpen] = useState(false);

  const user = toShellUser(authUser?.name || "", authUser?.company || "");
  const activeCalls = liveCalls.filter((c) => c.state !== "ended" && c.state !== "end");
  const pendingEscalations = escalations.filter((e) => e.status === "pending").length;
  const groups = buildNavGroups(pendingEscalations);

  const activeLabel =
    groups.flatMap((g) => g.items).find((i) => isActive(pathname, i.href))?.label ?? "Overview";

  const statusLine = {
    title: `${personas.length} personas configured`,
    note:
      activeCalls.length === 0 ? "No live calls right now" : `${activeCalls.length} call(s) in progress`,
  };

  // logout() clears the session and hard-navigates home
  const handleLogout = logout;

  return (
    <div className="min-h-screen bg-[var(--color-paper)] text-[var(--color-ink)]">
      <aside className="fixed inset-y-0 left-0 z-40 hidden w-64 border-r border-[rgba(255,255,255,0.10)] lg:block">
        <SidebarContent
          groups={groups}
          pathname={pathname}
          user={user}
          statusLine={statusLine}
          onLogout={handleLogout}
        />
      </aside>

      <div className="flex min-h-screen flex-col lg:pl-64">
        <header className="sticky top-0 z-30 border-b border-[rgba(255,255,255,0.08)] bg-[rgba(15,30,61,0.85)] backdrop-blur-md">
          <div className="flex h-16 items-center gap-3 px-4 sm:px-6 lg:px-8">
            <button
              onClick={() => setDrawerOpen(true)}
              aria-label="Open menu"
              className="flex h-9 w-9 items-center justify-center rounded-lg text-[var(--color-slate)] ring-1 ring-[rgba(255,255,255,0.10)] hover:bg-[rgba(255,255,255,0.04)] lg:hidden"
            >
              <List size={18} weight="bold" />
            </button>

            <nav aria-label="Breadcrumb" className="flex min-w-0 items-center gap-2 text-[13px]">
              <span className="hidden text-[var(--color-slate)]/70 sm:inline">CallForge</span>
              <CaretRight size={12} className="hidden text-[var(--color-slate)]/40 sm:inline" />
              <span className="truncate font-semibold text-[var(--color-ink)]">{activeLabel}</span>
            </nav>

            <div className="flex-1" />

            <GlobalSearch />

            <Link
              href="/dashboard/escalations"
              aria-label="Escalations"
              className="relative flex h-9 w-9 items-center justify-center rounded-lg text-[var(--color-slate)] ring-1 ring-[rgba(255,255,255,0.10)] hover:bg-[rgba(255,255,255,0.04)]"
            >
              <Bell size={17} />
              {pendingEscalations > 0 && (
                <span className="absolute -right-1 -top-1 flex h-4 min-w-[16px] items-center justify-center rounded-full bg-red-500 px-1 text-[9px] font-bold text-white ring-2 ring-white">
                  {pendingEscalations}
                </span>
              )}
            </Link>

            <ProfileMenu
              name={user.name}
              email={authUser?.email || ""}
              role={user.role}
              initials={user.initials}
              onLogout={handleLogout}
            />
          </div>
        </header>

        <main className="flex-1">
          <div className="mx-auto w-full max-w-[1440px] px-4 py-6 sm:px-6 lg:px-8 lg:py-8">{children}</div>
        </main>
      </div>

      <AnimatePresence>
        {drawerOpen && (
          <>
            <motion.div
              className="fixed inset-0 z-40 bg-[rgba(0,0,0,0.5)] lg:hidden"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.2 }}
              onClick={() => setDrawerOpen(false)}
            />
            <motion.aside
              className="fixed inset-y-0 left-0 z-50 w-64 shadow-2xl lg:hidden"
              initial={{ x: -280 }}
              animate={{ x: 0 }}
              exit={{ x: -280 }}
              transition={{ type: "tween", duration: 0.25, ease: "easeOut" }}
            >
              <SidebarContent
                groups={groups}
                pathname={pathname}
                user={user}
                statusLine={statusLine}
                onLogout={handleLogout}
                onClose={() => setDrawerOpen(false)}
              />
            </motion.aside>
          </>
        )}
      </AnimatePresence>
    </div>
  );
}
