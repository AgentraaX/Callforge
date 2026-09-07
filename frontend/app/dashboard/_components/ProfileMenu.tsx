"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { AnimatePresence, motion } from "motion/react";
import { CaretDown, Gear, SignOut } from "@phosphor-icons/react";

interface ProfileMenuProps {
  name: string;
  email: string;
  role: string;
  initials: string;
  onLogout: () => void;
}

export default function ProfileMenu({ name, email, role, initials, onLogout }: ProfileMenuProps) {
  const [open, setOpen] = useState(false);
  const [signingOut, setSigningOut] = useState(false);
  const ref = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-haspopup="menu"
        aria-expanded={open}
        aria-label="Account menu"
        className="flex items-center gap-1.5 rounded-full py-0.5 pl-0.5 pr-1.5 ring-1 ring-transparent transition hover:ring-[rgba(255,255,255,0.14)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-signal)]"
      >
        <span className="flex h-9 w-9 items-center justify-center rounded-full bg-[var(--color-signal)] text-[12px] font-bold text-white">
          {initials}
        </span>
        <CaretDown
          size={12}
          weight="bold"
          className={`text-[var(--color-slate)]/60 transition-transform ${open ? "rotate-180" : ""}`}
        />
      </button>

      <AnimatePresence>
        {open && (
          <motion.div
            role="menu"
            initial={{ opacity: 0, y: -6, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -6, scale: 0.98 }}
            transition={{ duration: 0.15, ease: "easeOut" }}
            className="absolute right-0 top-12 z-50 w-64 overflow-hidden rounded-xl bg-[var(--color-card)] shadow-lg ring-1 ring-[rgba(255,255,255,0.14)]"
          >
            <div className="border-b border-[rgba(255,255,255,0.08)] px-4 py-3">
              <p className="truncate text-[13px] font-semibold text-[var(--color-ink)]">{name}</p>
              <p className="truncate text-[12px] text-[var(--color-slate)]/80">{email}</p>
              <p className="mt-0.5 truncate text-[11px] text-[var(--color-slate)]/60">{role}</p>
            </div>
            <div className="p-1.5">
              <Link
                href="/dashboard/settings"
                role="menuitem"
                onClick={() => setOpen(false)}
                className="flex items-center gap-2.5 rounded-lg px-2.5 py-2 text-[13px] font-medium text-[var(--color-slate)] transition-colors hover:bg-[rgba(255,255,255,0.04)] hover:text-[var(--color-ink)]"
              >
                <Gear size={16} />
                Settings
              </Link>
              <button
                type="button"
                role="menuitem"
                disabled={signingOut}
                onClick={() => {
                  setSigningOut(true);
                  onLogout();
                }}
                className="flex w-full items-center gap-2.5 rounded-lg px-2.5 py-2 text-left text-[13px] font-medium text-[var(--color-slate)] transition-colors hover:bg-red-500/15 hover:text-red-400 disabled:opacity-60"
              >
                <SignOut size={16} />
                {signingOut ? "Signing out…" : "Sign out"}
              </button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
