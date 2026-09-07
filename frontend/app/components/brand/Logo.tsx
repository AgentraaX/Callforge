import Link from "next/link";

/* The one CallForge logo. Previously copy-pasted (with drift) across
   AnimatedNav, the page footer, AuthChrome, and a different lockup in
   DashboardShell. Import this instead.

   Server component — safe in any layout, page, or client tree. */

interface LogoProps {
  /** "wordmark" = mark + "CallForge" text (default). "mark" = glyph only. */
  variant?: "wordmark" | "mark";
  /** Glyph edge length in px. Default 28. */
  size?: number;
  /** Small uppercase label under the wordmark, e.g. "CRM". Wordmark only. */
  sublabel?: string;
  /** Link target. `null` renders a plain element; omitted defaults to "/". */
  href?: string | null;
  /** Text colour for the wordmark on dark surfaces. */
  tone?: "light" | "dark";
  className?: string;
}

function Glyph({ size }: { size: number }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 28 28"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className="shrink-0"
      aria-hidden="true"
    >
      <rect width="28" height="28" rx="7" fill="#3B6FE5" />
      {/* phone handset */}
      <path
        d="M8.5 10.5C8.5 9.67 9.17 9 10 9H11.5C12.05 9 12.5 9.45 12.5 10V12C12.5 12.55 12.05 13 11.5 13H10.5C10.5 15.21 12.29 17 14.5 17V16.5C14.5 15.95 14.95 15.5 15.5 15.5H17.5C18.05 15.5 18.5 15.95 18.5 16.5V18C18.5 18.83 17.83 19.5 17 19.5C12.58 19.5 9 15.92 9 11.5C9 10.67 8.5 10.5 8.5 10.5Z"
        fill="white"
        fillOpacity="0.95"
      />
      {/* signal waves */}
      <path
        d="M15 9.5C16.38 9.5 17.5 10.62 17.5 12"
        stroke="white"
        strokeWidth="1.4"
        strokeLinecap="round"
        fill="none"
        opacity="0.9"
      />
      <path
        d="M15 7C17.76 7 20 9.24 20 12"
        stroke="white"
        strokeWidth="1.4"
        strokeLinecap="round"
        fill="none"
        opacity="0.6"
      />
    </svg>
  );
}

export default function Logo({
  variant = "wordmark",
  size = 28,
  sublabel,
  href,
  tone = "light",
  className = "",
}: LogoProps) {
  const wordColor = tone === "dark" ? "text-white" : "text-[var(--color-ink)]";
  const subColor = tone === "dark" ? "text-white/60" : "text-[var(--color-slate)]/70";

  const inner =
    variant === "mark" ? (
      <Glyph size={size} />
    ) : (
      <span className={`inline-flex items-center gap-2.5 ${className}`}>
        <Glyph size={size} />
        <span className="leading-none">
          <span className={`block text-[15px] font-semibold tracking-tight ${wordColor}`}>
            CallForge
          </span>
          {sublabel && (
            <span
              className={`mt-1 block text-[9.5px] font-semibold uppercase tracking-[0.16em] ${subColor}`}
            >
              {sublabel}
            </span>
          )}
        </span>
      </span>
    );

  if (href === null) {
    return variant === "mark" ? (
      <span className={className} aria-label="CallForge">
        {inner}
      </span>
    ) : (
      inner
    );
  }

  return (
    <Link
      href={href ?? "/"}
      aria-label="CallForge home"
      className={variant === "mark" ? className : "inline-flex"}
    >
      {inner}
    </Link>
  );
}
