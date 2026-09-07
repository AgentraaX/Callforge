"use client";

import type { ReactNode } from "react";
import { AnimatePresence, motion } from "motion/react";
import { X } from "@phosphor-icons/react";

export function SlideOver({
  open,
  onClose,
  title,
  children,
  footer,
}: {
  open: boolean;
  onClose: () => void;
  title: string;
  children: ReactNode;
  footer?: ReactNode;
}) {
  return (
    <AnimatePresence>
      {open && (
        <>
          <motion.div
            className="fixed inset-0 z-40 bg-[rgba(0,0,0,0.5)]"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
            onClick={onClose}
          />
          <motion.aside
            className="fixed inset-y-0 right-0 z-50 flex w-full max-w-md flex-col bg-[var(--color-card)] shadow-2xl"
            initial={{ x: 420 }}
            animate={{ x: 0 }}
            exit={{ x: 420 }}
            transition={{ type: "tween", duration: 0.25, ease: "easeOut" }}
            role="dialog"
            aria-label={title}
          >
            <div className="flex h-16 shrink-0 items-center justify-between border-b border-[rgba(255,255,255,0.08)] px-5">
              <h2 className="text-[15px] font-semibold text-[var(--color-ink)]">{title}</h2>
              <button
                onClick={onClose}
                aria-label="Close"
                className="rounded-lg p-1.5 text-[var(--color-slate)] transition-colors hover:bg-[rgba(255,255,255,0.04)] hover:text-[var(--color-ink)]"
              >
                <X size={18} weight="bold" />
              </button>
            </div>
            <div className="flex-1 overflow-y-auto px-5 py-5">{children}</div>
            {footer && (
              <div className="shrink-0 border-t border-[rgba(255,255,255,0.08)] px-5 py-4">{footer}</div>
            )}
          </motion.aside>
        </>
      )}
    </AnimatePresence>
  );
}

/* ── Form fields ──────────────────────────────────────────────────── */

const inputCls =
  "h-10 w-full rounded-lg bg-[rgba(255,255,255,0.04)] px-3 text-[13.5px] text-[var(--color-ink)] outline-none ring-1 ring-[rgba(255,255,255,0.10)] focus:bg-[var(--color-card)] focus:ring-2 focus:ring-[var(--color-signal)]/40";
const labelCls =
  "mb-1.5 block text-[11px] font-semibold uppercase tracking-wide text-[var(--color-slate)]/70";

export function TextField({
  label,
  value,
  onChange,
  placeholder,
  type = "text",
  required,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
  type?: string;
  required?: boolean;
}) {
  return (
    <label className="mb-4 block">
      <span className={labelCls}>
        {label}
        {required && <span className="text-[var(--color-signal)]"> *</span>}
      </span>
      <input
        className={inputCls}
        type={type}
        value={value}
        placeholder={placeholder}
        onChange={(e) => onChange(e.target.value)}
      />
    </label>
  );
}

export function TextAreaField({
  label,
  value,
  onChange,
  placeholder,
  rows = 4,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
  rows?: number;
}) {
  return (
    <label className="mb-4 block">
      <span className={labelCls}>{label}</span>
      <textarea
        className={`${inputCls} h-auto py-2 leading-relaxed`}
        rows={rows}
        value={value}
        placeholder={placeholder}
        onChange={(e) => onChange(e.target.value)}
      />
    </label>
  );
}

export function SelectField<T extends string>({
  label,
  value,
  onChange,
  options,
}: {
  label: string;
  value: T;
  onChange: (v: T) => void;
  options: { value: T; label: string }[];
}) {
  return (
    <label className="mb-4 block">
      <span className={labelCls}>{label}</span>
      <select className={inputCls} value={value} onChange={(e) => onChange(e.target.value as T)}>
        {options.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </select>
    </label>
  );
}

export function CheckboxField({
  label,
  checked,
  onChange,
}: {
  label: string;
  checked: boolean;
  onChange: (v: boolean) => void;
}) {
  return (
    <label className="mb-4 flex cursor-pointer items-center gap-2.5 text-[13px] text-[var(--color-ink)]">
      <input
        type="checkbox"
        checked={checked}
        onChange={(e) => onChange(e.target.checked)}
        className="h-4 w-4 rounded border-[rgba(255,255,255,0.22)] text-[var(--color-signal)] focus:ring-[var(--color-signal)]/40"
      />
      {label}
    </label>
  );
}
