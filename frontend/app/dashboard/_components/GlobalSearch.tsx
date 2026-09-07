"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { AnimatePresence, motion } from "motion/react";
import { MagnifyingGlass, X } from "@phosphor-icons/react";
import { search as crmSearch } from "../../../lib/crm";
import type { SearchHit } from "../../../lib/crm-types";

function hitHref(hit: SearchHit): string {
  if (hit.kind === "contact") return `/dashboard/contacts/${hit.id}`;
  if (hit.kind === "company") return `/dashboard/companies/${hit.id}`;
  return `/dashboard/deals?deal=${hit.id}`;
}

function useSearch() {
  const [q, setQ] = useState("");
  const [hits, setHits] = useState<SearchHit[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const term = q.trim();
    if (term.length < 2) {
      setHits([]);
      setLoading(false);
      return;
    }
    setLoading(true);
    const id = setTimeout(() => {
      crmSearch(term)
        .then((r) => setHits(r.hits))
        .catch(() => setHits([]))
        .finally(() => setLoading(false));
    }, 200);
    return () => clearTimeout(id);
  }, [q]);

  return { q, setQ, hits, loading };
}

/* Shared results list + keyboard handling for both the inline and sheet views. */
function Results({
  hits,
  loading,
  q,
  activeIndex,
  onPick,
}: {
  hits: SearchHit[];
  loading: boolean;
  q: string;
  activeIndex: number;
  onPick: (hit: SearchHit) => void;
}) {
  if (q.trim().length < 2) {
    return (
      <p className="px-3.5 py-3 text-[12px] text-[var(--color-slate)]/70">
        Type at least 2 characters to search.
      </p>
    );
  }
  if (loading && hits.length === 0) {
    return <p className="px-3.5 py-3 text-[12px] text-[var(--color-slate)]/70">Searching…</p>;
  }
  if (hits.length === 0) {
    return (
      <p className="px-3.5 py-3 text-[12px] text-[var(--color-slate)]/70">
        Nothing matches “{q.trim()}”.
      </p>
    );
  }
  return (
    <ul className="max-h-[min(60vh,22rem)] overflow-y-auto py-1">
      {hits.map((h, i) => (
        <li key={`${h.kind}-${h.id}`}>
          <button
            type="button"
            onMouseDown={(e) => e.preventDefault()}
            onClick={() => onPick(h)}
            aria-selected={i === activeIndex}
            className={`flex w-full items-center justify-between gap-3 px-3.5 py-2.5 text-left transition-colors ${
              i === activeIndex ? "bg-[rgba(255,255,255,0.06)]" : "hover:bg-[rgba(255,255,255,0.04)]"
            }`}
          >
            <span className="min-w-0">
              <span className="block truncate text-[13px] font-medium text-[var(--color-ink)]">
                {h.label}
              </span>
              {h.sublabel && (
                <span className="block truncate text-[11px] text-[var(--color-slate)]/70">
                  {h.sublabel}
                </span>
              )}
            </span>
            <span className="shrink-0 font-mono text-[10px] uppercase tracking-wide text-[var(--color-slate)]/50">
              {h.kind}
            </span>
          </button>
        </li>
      ))}
    </ul>
  );
}

export default function GlobalSearch() {
  const router = useRouter();
  const { q, setQ, hits, loading } = useSearch();
  const [open, setOpen] = useState(false); // desktop dropdown
  const [sheet, setSheet] = useState(false); // mobile full-screen
  const [activeIndex, setActiveIndex] = useState(0);

  const boxRef = useRef<HTMLDivElement | null>(null);
  const inputRef = useRef<HTMLInputElement | null>(null);
  const sheetInputRef = useRef<HTMLInputElement | null>(null);

  useEffect(() => setActiveIndex(0), [hits]);

  /* ⌘K / Ctrl-K */
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        if (window.matchMedia("(min-width: 768px)").matches) {
          inputRef.current?.focus();
          setOpen(true);
        } else {
          setSheet(true);
        }
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  useEffect(() => {
    const onClick = (e: MouseEvent) => {
      if (boxRef.current && !boxRef.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, []);

  useEffect(() => {
    if (sheet) setTimeout(() => sheetInputRef.current?.focus(), 40);
  }, [sheet]);

  const go = useCallback(
    (hit: SearchHit) => {
      setOpen(false);
      setSheet(false);
      setQ("");
      router.push(hitHref(hit));
    },
    [router, setQ],
  );

  const onKeyNav = (e: React.KeyboardEvent, closeFn: () => void) => {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setActiveIndex((i) => Math.min(hits.length - 1, i + 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActiveIndex((i) => Math.max(0, i - 1));
    } else if (e.key === "Enter" && hits[activeIndex]) {
      e.preventDefault();
      go(hits[activeIndex]);
    } else if (e.key === "Escape") {
      closeFn();
    }
  };

  return (
    <>
      {/* desktop inline */}
      <div ref={boxRef} className="relative hidden md:block">
        <label className="flex h-9 w-72 items-center gap-2 rounded-lg bg-[rgba(255,255,255,0.04)] px-3 ring-1 ring-[rgba(255,255,255,0.10)] focus-within:bg-[var(--color-card)] focus-within:ring-2 focus-within:ring-[var(--color-signal)]/50">
          <MagnifyingGlass size={15} className="shrink-0 text-[var(--color-slate)]/60" />
          <input
            ref={inputRef}
            value={q}
            onChange={(e) => setQ(e.target.value)}
            onFocus={() => setOpen(true)}
            onKeyDown={(e) => onKeyNav(e, () => setOpen(false))}
            placeholder="Search contacts, companies, deals…"
            aria-label="Search"
            className="w-full bg-transparent text-[13px] text-[var(--color-ink)] outline-none placeholder:text-[var(--color-slate)]/50"
          />
          <kbd className="shrink-0 rounded border border-[rgba(255,255,255,0.16)] bg-[var(--color-card)] px-1.5 font-mono text-[10px] text-[var(--color-slate)]/60">
            ⌘K
          </kbd>
        </label>
        {open && q.trim().length >= 1 && (
          <div className="absolute left-0 right-0 top-11 z-50 overflow-hidden rounded-xl bg-[var(--color-card)] shadow-lg ring-1 ring-[rgba(255,255,255,0.14)]">
            <Results hits={hits} loading={loading} q={q} activeIndex={activeIndex} onPick={go} />
          </div>
        )}
      </div>

      {/* mobile trigger */}
      <button
        type="button"
        onClick={() => setSheet(true)}
        aria-label="Search"
        className="flex h-9 w-9 items-center justify-center rounded-lg text-[var(--color-slate)] ring-1 ring-[rgba(255,255,255,0.10)] hover:bg-[rgba(255,255,255,0.04)] md:hidden"
      >
        <MagnifyingGlass size={17} />
      </button>

      {/* mobile sheet */}
      <AnimatePresence>
        {sheet && (
          <motion.div
            className="fixed inset-0 z-[60] bg-[rgba(0,0,0,0.5)] md:hidden"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.15 }}
            onClick={() => setSheet(false)}
          >
            <motion.div
              className="mx-auto mt-0 w-full bg-[var(--color-card)] shadow-xl"
              initial={{ y: -16, opacity: 0 }}
              animate={{ y: 0, opacity: 1 }}
              exit={{ y: -16, opacity: 0 }}
              transition={{ duration: 0.2, ease: "easeOut" }}
              onClick={(e) => e.stopPropagation()}
            >
              <div className="flex h-14 items-center gap-2 border-b border-[rgba(255,255,255,0.10)] px-4">
                <MagnifyingGlass size={16} className="shrink-0 text-[var(--color-slate)]/60" />
                <input
                  ref={sheetInputRef}
                  value={q}
                  onChange={(e) => setQ(e.target.value)}
                  onKeyDown={(e) => onKeyNav(e, () => setSheet(false))}
                  placeholder="Search contacts, companies, deals…"
                  aria-label="Search"
                  className="h-full w-full bg-transparent text-[14px] text-[var(--color-ink)] outline-none placeholder:text-[var(--color-slate)]/50"
                />
                <button
                  type="button"
                  onClick={() => setSheet(false)}
                  aria-label="Close search"
                  className="shrink-0 rounded-lg p-1.5 text-[var(--color-slate)] hover:bg-[rgba(255,255,255,0.04)]"
                >
                  <X size={18} weight="bold" />
                </button>
              </div>
              <Results hits={hits} loading={loading} q={q} activeIndex={activeIndex} onPick={go} />
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  );
}
