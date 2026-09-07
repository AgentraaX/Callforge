"use client";

/* Shared chrome for /login and /signup -- kept in one place so the two
   pages can never drift from each other or from the landing's design
   language (see app/globals.css): midnight-navy surfaces, one bold blue
   block, Inter body, restrained motion. */
import { useEffect, useState } from "react";
import { motion } from "motion/react";
import { Eye, EyeSlash, type Icon } from "@phosphor-icons/react";

/* Re-export shim — the shared logo now lives in components/brand/Logo.
   Kept so app/login and app/signup imports don't need to change. */
export { default as Logo } from "./brand/Logo";

/* ── Official multi-colour Google mark ───────────────────────────────── */
export function GoogleMark() {
  return (
    <svg width="16" height="16" viewBox="0 0 18 18" aria-hidden="true" className="shrink-0">
      <path fill="#4285F4" d="M17.64 9.2045c0-.6381-.0573-1.2518-.1636-1.8409H9v3.4814h4.8436c-.2086 1.125-.8427 2.0782-1.7959 2.7164v2.2581h2.9087c1.7018-1.5668 2.6836-3.874 2.6836-6.615z" />
      <path fill="#34A853" d="M9 18c2.43 0 4.4673-.806 5.9564-2.18l-2.9087-2.2581c-.8059.54-1.8368.859-3.0477.859-2.344 0-4.3282-1.5831-5.036-3.7104H.9573v2.3318C2.4382 15.9832 5.4818 18 9 18z" />
      <path fill="#FBBC05" d="M3.964 8.7104c-.18-.54-.2823-1.1168-.2823-1.7104s.1023-1.1705.2823-1.7104V2.9582H.9573C.3477 4.1732 0 5.5477 0 7s.3477 2.8268.9573 4.0418l3.0067-2.3314z" />
      <path fill="#EA4335" d="M9 3.5795c1.3214 0 2.5077.4541 3.4405 1.346l2.5813-2.5814C13.4632.8918 11.426 0 9 0 5.4818 0 2.4382 2.0168.9573 4.9582L3.964 7.2895C4.6718 5.1622 6.6559 3.5795 9 3.5795z" />
    </svg>
  );
}

/* ── Password visibility toggle ──────────────────────────────────────── */
export function PwToggle({ visible, onToggle }: { visible: boolean; onToggle: () => void }) {
  const ToggleIcon = visible ? EyeSlash : Eye;
  return (
    <button
      type="button"
      onClick={onToggle}
      className="absolute right-3 top-1/2 -translate-y-1/2 text-[var(--color-slate)]/50 transition-colors hover:text-[var(--color-slate)]"
      aria-label={visible ? "Hide password" : "Show password"}
      tabIndex={-1}
    >
      <ToggleIcon size={16} />
    </button>
  );
}

/* ── Marketing panel (desktop only) ──────────────────────────────────── */
interface Feature {
  icon: Icon;
  title: string;
  body: string;
}

const CALL_STATES = ["Listening", "Thinking", "Speaking"] as const;

function LiveCallChip() {
  const [i, setI] = useState(0);
  useEffect(() => {
    const id = setInterval(() => setI((n) => (n + 1) % CALL_STATES.length), 1800);
    return () => clearInterval(id);
  }, []);
  return (
    <div className="inline-flex items-center gap-2 rounded-full bg-white/10 px-3.5 py-2 text-[12px] font-medium text-white/80 ring-1 ring-white/20">
      <span className="relative flex h-1.5 w-1.5">
        <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-white opacity-60" />
        <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-white" />
      </span>
      Call in progress ·{" "}
      <motion.span key={i} initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="font-semibold text-white">
        {CALL_STATES[i]}
      </motion.span>
    </div>
  );
}

export function AuthMarketingPanel({
  headline,
  subcopy,
  features,
}: {
  headline: string;
  subcopy: string;
  features: Feature[];
}) {
  return (
    <div className="relative hidden flex-1 overflow-hidden bg-signal lg:flex lg:h-screen lg:items-center lg:justify-center">
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 opacity-[0.14]"
        style={{
          backgroundImage:
            "radial-gradient(circle, rgba(255,255,255,0.9) 1px, transparent 1px)",
          backgroundSize: "26px 26px",
        }}
      />

      <div className="relative w-full max-w-[440px] px-10">
        <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.45, ease: "easeOut" }}>
          <LiveCallChip />

          <p className="mt-6 font-mono text-[10px] uppercase tracking-[0.26em] text-white/70">
            One team · one number
          </p>
          <h2 className="mt-3 font-display text-[30px] font-bold leading-[1.08] tracking-[-0.01em] text-white text-balance">
            {headline}
          </h2>
          <p className="mt-3 text-[14.5px] leading-relaxed text-white/75">{subcopy}</p>

          <ul className="mt-9 space-y-5">
            {features.map((f) => {
              const FeatureIcon = f.icon;
              return (
                <li key={f.title} className="flex items-start gap-3.5">
                  <span className="mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-white/12 text-white ring-1 ring-white/20">
                    <FeatureIcon size={17} weight="duotone" />
                  </span>
                  <div>
                    <p className="text-[13.5px] font-semibold text-white">{f.title}</p>
                    <p className="mt-0.5 text-[13px] leading-relaxed text-white/65">{f.body}</p>
                  </div>
                </li>
              );
            })}
          </ul>
        </motion.div>
      </div>
    </div>
  );
}
