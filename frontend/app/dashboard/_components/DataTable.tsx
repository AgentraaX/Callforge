"use client";

import type { ReactNode } from "react";
import { CaretDown, CaretLeft, CaretRight, CaretUp } from "@phosphor-icons/react";

export interface Column<T> {
  key: string;
  label: string;
  /** column name to pass to the backend order_by; omit to disable sorting */
  sortKey?: string;
  render: (row: T) => ReactNode;
  className?: string;
}

export function DataTable<T extends { id: string }>({
  columns,
  rows,
  onRowClick,
  sort,
  onSortChange,
  minWidth = 640,
}: {
  columns: Column<T>[];
  rows: T[];
  onRowClick?: (row: T) => void;
  sort?: string; // e.g. "-created_at"
  onSortChange?: (next: string) => void;
  minWidth?: number;
}) {
  const activeKey = sort?.replace(/^-/, "");
  const activeDesc = sort?.startsWith("-");

  function toggle(col: Column<T>) {
    if (!col.sortKey || !onSortChange) return;
    if (activeKey === col.sortKey) {
      onSortChange(activeDesc ? col.sortKey : `-${col.sortKey}`);
    } else {
      onSortChange(`-${col.sortKey}`);
    }
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-left" style={{ minWidth }}>
        <thead>
          <tr className="border-b border-[rgba(255,255,255,0.08)] bg-[rgba(255,255,255,0.04)]">
            {columns.map((col) => {
              const isActive = activeKey === col.sortKey;
              return (
                <th key={col.key} className={`px-5 py-3 ${col.className || ""}`}>
                  {col.sortKey && onSortChange ? (
                    <button
                      onClick={() => toggle(col)}
                      className={`group inline-flex items-center gap-1 text-[11px] font-semibold uppercase tracking-[0.08em] transition-colors ${
                        isActive ? "text-[var(--color-signal)]" : "text-[var(--color-slate)]/80 hover:text-[var(--color-ink)]"
                      }`}
                    >
                      {col.label}
                      {isActive ? (
                        activeDesc ? (
                          <CaretDown size={11} weight="fill" />
                        ) : (
                          <CaretUp size={11} weight="fill" />
                        )
                      ) : (
                        <CaretUp size={11} className="text-[var(--color-slate)]/25 group-hover:text-[var(--color-slate)]/60" />
                      )}
                    </button>
                  ) : (
                    <span className="text-[11px] font-semibold uppercase tracking-[0.08em] text-[var(--color-slate)]/80">
                      {col.label}
                    </span>
                  )}
                </th>
              );
            })}
          </tr>
        </thead>
        <tbody className="divide-y divide-[rgba(255,255,255,0.08)]">
          {rows.map((row) => (
            <tr
              key={row.id}
              onClick={onRowClick ? () => onRowClick(row) : undefined}
              className={`transition-colors hover:bg-[rgba(255,255,255,0.04)] ${onRowClick ? "cursor-pointer" : ""}`}
            >
              {columns.map((col) => (
                <td key={col.key} className={`px-5 py-3.5 text-[13px] text-[var(--color-slate)] ${col.className || ""}`}>
                  {col.render(row)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function Pagination({
  total,
  limit,
  offset,
  onChange,
}: {
  total: number;
  limit: number;
  offset: number;
  onChange: (nextOffset: number) => void;
}) {
  if (total <= limit) return null;
  const from = offset + 1;
  const to = Math.min(offset + limit, total);
  return (
    <div className="flex items-center justify-between border-t border-[rgba(255,255,255,0.08)] px-5 py-3 text-[12px] text-[var(--color-slate)]">
      <span className="tabular-nums">
        {from}–{to} of {total}
      </span>
      <div className="flex items-center gap-1">
        <button
          disabled={offset === 0}
          onClick={() => onChange(Math.max(0, offset - limit))}
          className="rounded-lg p-1.5 ring-1 ring-[rgba(255,255,255,0.14)] transition-colors hover:bg-[rgba(255,255,255,0.04)] disabled:opacity-30"
          aria-label="Previous page"
        >
          <CaretLeft size={13} weight="bold" />
        </button>
        <button
          disabled={to >= total}
          onClick={() => onChange(offset + limit)}
          className="rounded-lg p-1.5 ring-1 ring-[rgba(255,255,255,0.14)] transition-colors hover:bg-[rgba(255,255,255,0.04)] disabled:opacity-30"
          aria-label="Next page"
        >
          <CaretRight size={13} weight="bold" />
        </button>
      </div>
    </div>
  );
}
