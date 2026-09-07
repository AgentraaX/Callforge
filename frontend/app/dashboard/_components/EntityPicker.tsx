"use client";

import { useEffect, useMemo, useState } from "react";
import { listCompanies, listContacts } from "../../../lib/crm";

const labelCls = "mb-1.5 block text-[11px] font-semibold uppercase tracking-wide text-[var(--color-slate)]/70";
const inputCls =
  "h-10 w-full rounded-lg bg-[rgba(255,255,255,0.04)] px-3 text-[13.5px] text-[var(--color-ink)] outline-none ring-1 ring-[rgba(255,255,255,0.10)] focus:bg-[var(--color-card)] focus:ring-2 focus:ring-[var(--color-signal)]/40";

interface Option {
  id: string;
  label: string;
}

/** Simple picker -- loads up to 200 rows once and filters client-side.
 * Good enough for the create/edit forms; the list pages have server search. */
export function EntityPicker({
  kind,
  label,
  value,
  onChange,
  allowEmpty = true,
}: {
  kind: "contact" | "company";
  label: string;
  value: string | null;
  onChange: (id: string | null) => void;
  allowEmpty?: boolean;
}) {
  const [options, setOptions] = useState<Option[]>([]);
  const [query, setQuery] = useState("");

  useEffect(() => {
    const load =
      kind === "contact"
        ? listContacts({ limit: 200 }).then((p) =>
            p.items.map((c) => ({ id: c.id, label: c.full_name || c.email || c.phone || "Unnamed" })),
          )
        : listCompanies({ limit: 200 }).then((p) => p.items.map((c) => ({ id: c.id, label: c.name })));
    load.then(setOptions).catch(() => setOptions([]));
  }, [kind]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    const rows = q ? options.filter((o) => o.label.toLowerCase().includes(q)) : options;
    return rows.slice(0, 50);
  }, [options, query]);

  const selectedLabel = options.find((o) => o.id === value)?.label;

  return (
    <div className="mb-4">
      <span className={labelCls}>{label}</span>
      {value ? (
        <div className="flex items-center justify-between rounded-lg bg-[rgba(255,255,255,0.04)] px-3 py-2 text-[13px] text-[var(--color-ink)] ring-1 ring-[rgba(255,255,255,0.10)]">
          <span className="truncate">{selectedLabel || "Selected"}</span>
          {allowEmpty && (
            <button
              type="button"
              onClick={() => onChange(null)}
              className="text-[11px] font-semibold text-[var(--color-signal)] hover:underline"
            >
              Change
            </button>
          )}
        </div>
      ) : (
        <>
          <input
            className={inputCls}
            placeholder={`Search ${kind === "contact" ? "contacts" : "companies"}…`}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
          {query && (
            <ul className="mt-1 max-h-44 overflow-y-auto rounded-lg ring-1 ring-[rgba(255,255,255,0.10)]">
              {filtered.length === 0 && (
                <li className="px-3 py-2 text-[12px] text-[var(--color-slate)]/70">No matches</li>
              )}
              {filtered.map((o) => (
                <li key={o.id}>
                  <button
                    type="button"
                    onClick={() => {
                      onChange(o.id);
                      setQuery("");
                    }}
                    className="block w-full px-3 py-2 text-left text-[13px] text-[var(--color-ink)] hover:bg-[rgba(255,255,255,0.04)]"
                  >
                    {o.label}
                  </button>
                </li>
              ))}
            </ul>
          )}
        </>
      )}
    </div>
  );
}
