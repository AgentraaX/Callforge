import type { ReactNode } from "react";

/* Section scaffolding for the landing page. Extracted from the ~12 near-identical
   eyebrow / <h2> / <p> blocks in app/page.tsx so the type scale and rhythm stay
   consistent.

   The eyebrow is a call **disposition code** (CONNECTED, QUALIFYING, OBJECTION,
   BOOKED, ESCALATED, SUPERVISED) set in mono — it names the real stage of an
   outbound call the section is about, not decoration. */

export function Eyebrow({
  children,
  tone = "light",
  className = "",
}: {
  children: ReactNode;
  tone?: "light" | "dark";
  className?: string;
}) {
  return (
    <span
      className={`inline-flex items-center gap-2 font-mono text-[11px] font-medium uppercase tracking-[0.22em] ${
        tone === "dark" ? "text-live" : "text-signal"
      } ${className}`}
    >
      <span
        aria-hidden="true"
        className={`h-1.5 w-1.5 rounded-[1px] ${
          tone === "dark" ? "bg-live" : "bg-signal"
        }`}
      />
      {children}
    </span>
  );
}

interface SectionHeadingProps {
  eyebrow?: string;
  title: ReactNode;
  subtitle?: ReactNode;
  align?: "left" | "center";
  as?: "h1" | "h2";
  tone?: "light" | "dark";
  className?: string;
}

export function SectionHeading({
  eyebrow,
  title,
  subtitle,
  align = "left",
  as = "h2",
  tone = "light",
  className = "",
}: SectionHeadingProps) {
  const Tag = as;
  const alignCls = align === "center" ? "text-center items-center" : "text-left items-start";
  const headingColor = tone === "dark" ? "text-white" : "text-ink";
  const subColor = tone === "dark" ? "text-white/60" : "text-slate";

  return (
    <div className={`flex flex-col ${alignCls} ${className}`}>
      {eyebrow && <Eyebrow tone={tone}>{eyebrow}</Eyebrow>}
      <Tag
        className={`font-display font-bold tracking-[-0.02em] text-balance ${
          as === "h1" ? "text-display leading-[1.02]" : "mt-3 text-h2 leading-[1.08]"
        } ${headingColor}`}
      >
        {title}
      </Tag>
      {subtitle && (
        <p
          className={`mt-4 max-w-[58ch] text-[15px] leading-[1.6] ${subColor} ${
            align === "center" ? "mx-auto" : ""
          }`}
        >
          {subtitle}
        </p>
      )}
    </div>
  );
}

/* Muted second clause inside a heading — replaces the inline
   <span className="text-[#3E526A]"> pattern. */
export function Muted({ children }: { children: ReactNode }) {
  return <span className="text-slate">{children}</span>;
}
