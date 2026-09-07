import {
  PhoneOutgoing,
  Broadcast,
  ShieldCheck,
  Translate,
} from "@phosphor-icons/react/dist/ssr";
import { SITE_METRICS } from "../../lib/site-metrics";

/* Replaces the fabricated "Trusted by" logo marquee. Every line here is a real
   capability of the working build (PRODUCT.md: "no fabricated metrics or
   customer claims — the demo speaks for itself"). */

const ITEMS = [
  { icon: PhoneOutgoing, label: SITE_METRICS.telephony },
  { icon: Broadcast, label: SITE_METRICS.webrtc },
  { icon: ShieldCheck, label: SITE_METRICS.grounding },
  { icon: Translate, label: SITE_METRICS.languages },
] as const;

export default function CapabilityStrip() {
  return (
    <section className="border-y border-[var(--color-hairline)] bg-paper-alt">
      <div className="mx-auto max-w-[84rem] 2xl:max-w-[92rem] px-5 py-8 sm:px-8">
        <p className="text-center font-mono text-[11px] font-medium uppercase tracking-[0.22em] text-slate">
          Real infrastructure, not a demo script
        </p>
        <ul className="mt-6 grid grid-cols-2 gap-x-4 gap-y-4 sm:grid-cols-4 sm:gap-x-8">
          {ITEMS.map(({ icon: Icon, label }) => (
            <li
              key={label}
              className="flex items-center justify-center gap-2.5 text-center"
            >
              <Icon
                size={18}
                weight="duotone"
                className="shrink-0 text-signal"
                aria-hidden="true"
              />
              <span className="text-[13px] font-medium text-ink">{label}</span>
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}
