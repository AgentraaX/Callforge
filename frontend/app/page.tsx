import Link from "next/link";
import {
  Phone,
  MagnifyingGlass,
  CalendarCheck,
  Database,
  Code,
  FileText,
  Hash,
  ArrowRight,
  CheckCircle,
  GlobeHemisphereWest,
  Lightning,
  Waveform,
  ShieldCheck,
  X,
} from "@phosphor-icons/react/dist/ssr";

import ScrollReveal from "./components/ScrollReveal";
import Logo from "./components/brand/Logo";
import HeroBlobs from "./components/HeroBlobs";
import AnimatedNav from "./components/AnimatedNav";
import StickyBottomBar from "./components/StickyBottomBar";
import CapabilityStrip from "./components/CapabilityStrip";
import VideoShowcase from "./components/VideoShowcase";
import EscalationFlow from "./components/EscalationFlow";
import AgentCards from "./components/AgentCards";
import ThemeButton from "./components/ui/ThemeButton";
import PrimaryCta from "./components/PrimaryCta";
import { SectionHeading, Muted } from "./components/ui/Section";
import { BRAND, COPY, DISPOSITION, LINKS, SITE_METRICS } from "../lib/site-metrics";

/* ─── Page ──────────────────────────────────────────────────────────── */
export default function Home() {
  return (
    <>
      <AnimatedNav />

      {/* ── Hero ───────────────────────────────────────────────── */}
      <section
        id="demo"
        className="relative flex min-h-[calc(100svh-3.5rem)] items-center overflow-hidden scroll-mt-16 lg:min-h-0"
      >
        <div className="absolute inset-0 dot-grid opacity-40" aria-hidden="true" />
        <HeroBlobs />

        <div className="relative mx-auto w-full max-w-[84rem] 2xl:max-w-[92rem] px-5 pb-14 pt-12 sm:px-8 sm:pt-16 lg:py-20 xl:py-24">
          <div className="mx-auto max-w-2xl text-center lg:text-left">
            {/* copy */}
            <div>
              <ScrollReveal>
                <span className="inline-flex items-center gap-2 rounded-full bg-signal px-3 py-1 font-mono text-[10px] font-semibold uppercase tracking-[0.18em] text-white">
                  <span className="h-1.5 w-1.5 rounded-full bg-white" />
                  Together, every call is covered
                </span>
                <p className="mt-4 font-mono text-[11px] font-medium uppercase tracking-[0.24em] text-signal">
                  Sales OS — Chapter 01
                </p>
                <h1 className="mt-2 font-display text-display font-bold uppercase leading-[0.92] tracking-[-0.02em] text-ink">
                  Your AI
                  <br />
                  sales floor
                </h1>
                <p className="mt-4 max-w-[44ch] font-serif text-[19px] italic leading-[1.45] text-slate">
                  When every call is answered, every lead is worked, and no pipeline goes cold.
                </p>
              </ScrollReveal>

              <ScrollReveal delay={0.1}>
                <p className="mt-5 max-w-[50ch] text-[14.5px] leading-[1.6] text-slate">
                  {BRAND.blurb}
                </p>
              </ScrollReveal>

              <ScrollReveal delay={0.15}>
                <div className="mx-auto mt-5 grid max-w-md grid-cols-1 gap-x-8 gap-y-2 sm:grid-cols-2 lg:mx-0">
                  {[
                    "Custom voice cloning",
                    "24/7 outbound calls",
                    "Automatic lead scoring",
                    "Books meetings on the call",
                  ].map((item) => (
                    <div key={item} className="flex items-center gap-2">
                      <CheckCircle size={15} weight="fill" className="shrink-0 text-signal" />
                      <span className="text-[13.5px] font-medium text-ink">{item}</span>
                    </div>
                  ))}
                </div>
              </ScrollReveal>

              <ScrollReveal delay={0.2}>
                <div className="mt-7 flex flex-wrap items-center justify-center gap-3 lg:justify-start">
                  <PrimaryCta size="lg" />
                  <ThemeButton
                    href={LINKS.contactSales}
                    variant="secondary"
                    size="lg"
                    iconRight={<ArrowRight size={15} weight="bold" />}
                  >
                    {COPY.ctaSecondary}
                  </ThemeButton>
                </div>
              </ScrollReveal>

              <ScrollReveal delay={0.3}>
                <p className="mt-7 flex items-center justify-center gap-2 font-mono text-[11px] uppercase tracking-[0.12em] text-slate lg:justify-start">
                  <span className="h-1.5 w-1.5 rounded-full bg-signal pulse-dot" />
                  {SITE_METRICS.latency} · {SITE_METRICS.telephony}
                </p>
              </ScrollReveal>
            </div>
          </div>
        </div>
      </section>

      <CapabilityStrip />

      {/* ── CONNECTED — how a call works ────────────────────────── */}
      <section id="how-it-works" className="scroll-mt-16 bg-paper py-20 sm:py-24">
        <div className="mx-auto max-w-[84rem] 2xl:max-w-[92rem] px-5 sm:px-8">
          <ScrollReveal>
            <SectionHeading
              eyebrow={DISPOSITION.connected}
              title={
                <>
                  How a CallForge call <Muted>runs itself</Muted>
                </>
              }
              subtitle="Every call follows the same playbook a good rep would — rapport, discovery, objections, close — with no human on the line."
            />
          </ScrollReveal>

          <div className="mt-10 grid grid-cols-1 gap-5 md:grid-cols-3">
            {[
              {
                icon: Phone,
                title: "It dials and opens with rapport",
                desc: "Your persona places a real outbound call and opens like a person, not a script. Callers don't realise they're talking to AI.",
              },
              {
                icon: MagnifyingGlass,
                title: "It qualifies as it talks",
                desc: "Company, pain point, budget signal, and urgency are extracted from the conversation and scored automatically.",
              },
              {
                icon: CalendarCheck,
                title: "It books or escalates",
                desc: "Hot leads get a meeting booked on the call. Anything it shouldn't handle is escalated to a human with the full transcript.",
              },
            ].map((step, i) => {
              const Icon = step.icon;
              return (
                <ScrollReveal key={step.title} delay={i * 0.08}>
                  <div className={`card-ring h-full p-6 ${i < 2 ? "step-connector" : ""}`}>
                    <div className="flex items-center gap-3">
                      <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-signal-tint font-mono text-[12px] font-medium text-signal">
                        {String(i + 1).padStart(2, "0")}
                      </span>
                      <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-signal-tint">
                        <Icon size={18} className="text-signal" />
                      </span>
                    </div>
                    <h3 className="mt-4 text-[16px] font-semibold text-ink">{step.title}</h3>
                    <p className="mt-2 text-[14px] leading-[1.55] text-slate">{step.desc}</p>
                  </div>
                </ScrollReveal>
              );
            })}
          </div>
        </div>
      </section>

      {/* ── QUALIFYING — lead scoring ───────────────────────────── */}
      <section id="features" className="scroll-mt-16 bg-paper-alt py-20 sm:py-24">
        <div className="mx-auto max-w-[84rem] 2xl:max-w-[92rem] px-5 sm:px-8">
          <div className="grid grid-cols-1 items-center gap-12 lg:grid-cols-2">
            <ScrollReveal>
              <div className="card-ring p-5">
                <p className="font-mono text-[10px] uppercase tracking-[0.16em] text-slate">
                  Lead — extracted live
                </p>
                <div className="mt-3 space-y-3">
                  <div className="grid grid-cols-2 gap-3">
                    {[
                      ["Company", "Meridian Freight"],
                      ["Contact", "Operations lead"],
                      ["Pain point", "Manual outbound doesn't scale"],
                      ["Budget signal", "$500–1,000 / mo mentioned"],
                    ].map(([label, value]) => (
                      <div key={label} className="rounded-lg bg-paper-alt p-3">
                        <p className="text-[10px] font-medium uppercase tracking-wide text-slate">
                          {label}
                        </p>
                        <p className="mt-0.5 text-[14px] font-semibold text-ink">{value}</p>
                      </div>
                    ))}
                  </div>
                  <div className="rounded-lg bg-paper-alt p-3">
                    <p className="text-[10px] font-medium uppercase tracking-wide text-slate">
                      Urgency
                    </p>
                    <div className="mt-1 flex items-center gap-2">
                      <span className="rounded bg-signal-tint px-2 py-0.5 font-mono text-[11px] font-medium uppercase text-signal">
                        High
                      </span>
                      <span className="text-[13px] text-slate">Evaluating this quarter</span>
                    </div>
                  </div>
                  <div className="rounded-lg bg-paper-alt p-3">
                    <p className="text-[10px] font-medium uppercase tracking-wide text-slate">
                      Lead score
                    </p>
                    <div className="mt-1 flex items-center gap-3">
                      <div className="h-2 flex-1 overflow-hidden rounded-full bg-[var(--color-hairline)]">
                        <div className="h-full rounded-full bg-signal" style={{ width: "84%" }} />
                      </div>
                      <span className="font-mono text-[13px] font-medium text-signal">84 / 100</span>
                    </div>
                  </div>
                </div>
              </div>
            </ScrollReveal>

            <ScrollReveal delay={0.1}>
              <SectionHeading
                eyebrow={DISPOSITION.qualifying}
                title={
                  <>
                    Every call becomes a scored lead <Muted>your team can act on</Muted>
                  </>
                }
                subtitle="CallForge pulls structured data out of the conversation and scores intent automatically. Hot leads trigger a booking; warm leads enter your nurture; everything lands in your CRM."
              />
              <ul className="mt-6 space-y-2.5">
                {[
                  "Company, contact, pain point, budget, and urgency — every call",
                  "Hot / warm / cold scored from real intent signals",
                  "Flows straight into contacts, deals, and the pipeline",
                ].map((point) => (
                  <li key={point} className="flex gap-2.5">
                    <CheckCircle size={17} weight="fill" className="mt-0.5 shrink-0 text-signal" />
                    <span className="text-[14px] leading-[1.55] text-slate">{point}</span>
                  </li>
                ))}
              </ul>
            </ScrollReveal>
          </div>
        </div>
      </section>

      {/* ── OBJECTION — grounded answers ────────────────────────── */}
      <section className="bg-paper py-20 sm:py-24">
        <div className="mx-auto max-w-[84rem] 2xl:max-w-[92rem] px-5 sm:px-8">
          <div className="grid grid-cols-1 items-start gap-12 lg:grid-cols-2">
            <ScrollReveal>
              <SectionHeading
                eyebrow={DISPOSITION.objection}
                title={
                  <>
                    Answers grounded in your facts — <Muted>never invented</Muted>
                  </>
                }
                subtitle="A made-up price or feature loses the deal and your credibility. Four layers keep every answer traceable to the knowledge base you gave the persona."
              />
              <div className="mt-6 space-y-3">
                {[
                  { icon: Database, title: "RAG-only knowledge base", desc: "Answers come from your verified documents, rate cards, and SOPs — nothing else." },
                  { icon: Code, title: "Structured output validation", desc: "Responses are constrained to valid schemas. No free-form hallucination." },
                  { icon: FileText, title: "Source attribution", desc: "Every answer traces to a specific document and passage." },
                  { icon: Hash, title: "Number verification", desc: "Prices, phone numbers, and IDs are checked against source data before they're spoken." },
                ].map((layer, i) => {
                  const Icon = layer.icon;
                  return (
                    <ScrollReveal key={layer.title} delay={i * 0.07}>
                      <div className="flex gap-3 rounded-xl bg-card p-4 shadow-[inset_0_0_0_1px_var(--color-hairline-strong)]">
                        <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-signal-tint">
                          <Icon size={18} className="text-signal" />
                        </span>
                        <div>
                          <h3 className="text-[14px] font-semibold text-ink">{layer.title}</h3>
                          <p className="mt-1 text-[13px] leading-[1.5] text-slate">{layer.desc}</p>
                        </div>
                      </div>
                    </ScrollReveal>
                  );
                })}
              </div>
            </ScrollReveal>

            <ScrollReveal delay={0.15}>
              <div className="card-ring space-y-3 p-5 lg:sticky lg:top-24">
                <p className="font-mono text-[10px] uppercase tracking-[0.16em] text-slate">
                  Grounded response
                </p>
                <div className="rounded-lg bg-paper-alt p-3">
                  <p className="text-[13px] leading-[1.55] text-ink">
                    &ldquo;The Pro plan is{" "}
                    <span className="font-semibold text-signal">$149/month</span> — unlimited calls, and it includes{" "}
                    <span className="font-semibold text-signal">voice cloning</span>.&rdquo;
                  </p>
                </div>
                <p className="font-mono text-[10px] uppercase tracking-[0.16em] text-slate">
                  Source citations
                </p>
                {[
                  ["Knowledge base — Pricing", "“Pro plan: $149/mo, unlimited calls, includes voice cloning”"],
                  ["Knowledge base — Features", "“Voice cloning: available on Pro and Enterprise”"],
                ].map(([title, quote], i) => (
                  <div key={i} className="flex items-start gap-2 rounded-lg bg-paper-alt p-2.5">
                    <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded bg-signal-tint font-mono text-[10px] font-medium text-signal">
                      {i + 1}
                    </span>
                    <div>
                      <p className="text-[12px] font-medium text-ink">{title}</p>
                      <p className="text-[11px] text-slate">{quote}</p>
                    </div>
                  </div>
                ))}
              </div>
            </ScrollReveal>
          </div>
        </div>
      </section>

      {/* ── ESCALATED — smart handoff ───────────────────────────── */}
      <section className="bg-paper-alt py-20 sm:py-24">
        <div className="mx-auto max-w-[84rem] 2xl:max-w-[92rem] px-5 sm:px-8">
          <ScrollReveal>
            <SectionHeading
              eyebrow={DISPOSITION.escalated}
              title={
                <>
                  Complex calls reach a human <Muted>with full context</Muted>
                </>
              }
              subtitle="When a call needs judgement, CallForge hands off immediately with a written case summary. Nothing is lost, no caller is left waiting."
            />
          </ScrollReveal>
          <EscalationFlow />
        </div>
      </section>

      {/* ── SUPERVISED — the dashboard ─────────────────────────── */}
      <section className="bg-paper py-20 sm:py-24">
        <div className="mx-auto max-w-[84rem] 2xl:max-w-[92rem] px-5 sm:px-8">
          <ScrollReveal>
            <SectionHeading
              eyebrow={DISPOSITION.supervised}
              title={
                <>
                  Your team sees every call <Muted>live</Muted>
                </>
              }
              subtitle="AI handles the volume; humans keep the quality. Live transcripts, lead scoring, and one-click takeover in a single view."
            />
          </ScrollReveal>
          <ScrollReveal delay={0.05} className="mt-10">
            <p className="mb-4 font-mono text-[11px] uppercase tracking-[0.2em] text-[var(--color-live)]">
              See it running
            </p>
            <VideoShowcase />
          </ScrollReveal>
        </div>
      </section>

      {/* ── Meet your AI reps ───────────────────────────────────── */}
      <section className="bg-paper-alt py-20 sm:py-24">
        <div className="mx-auto max-w-[84rem] 2xl:max-w-[92rem] px-5 sm:px-8">
          <ScrollReveal>
            <SectionHeading
              title={
                <>
                  Meet your <Muted>AI sales team</Muted>
                </>
              }
              subtitle={`Build ${SITE_METRICS.personaCount} personas or a dozen — each with its own name, pitch, personality, and voice. They work your pipeline as one coordinated team.`}
            />
          </ScrollReveal>

          <AgentCards />
        </div>
      </section>

      {/* ── Comparison ──────────────────────────────────────────── */}
      <section className="bg-paper py-20 sm:py-24">
        <div className="mx-auto max-w-5xl px-5 sm:px-8">
          <ScrollReveal>
            <SectionHeading
              title={
                <>
                  What you get that <Muted>generic AI tools don&apos;t</Muted>
                </>
              }
              subtitle="Purpose-built for cold-calling sales — real technique, real telephony, real oversight."
            />
          </ScrollReveal>

          <ScrollReveal delay={0.1} className="mt-10">
            <div className="card-ring overflow-hidden">
              <div className="grid border-b border-[var(--color-hairline-strong)] sm:grid-cols-[1.4fr_1fr_1fr]">
                <div className="hidden items-center px-5 py-4 sm:flex">
                  <span className="font-mono text-[11px] uppercase tracking-[0.12em] text-slate">
                    Capability
                  </span>
                </div>
                <div className="flex items-center gap-2 px-5 py-3.5 sm:justify-center sm:bg-signal-tint sm:py-4">
                  <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-md bg-signal">
                    <Phone size={11} weight="fill" className="text-white" />
                  </span>
                  <span className="text-[13px] font-bold text-signal">CallForge</span>
                  <span className="text-[12px] font-medium text-slate/70 sm:hidden">
                    vs generic AI tools
                  </span>
                </div>
                <div className="hidden items-center justify-center border-l border-[var(--color-hairline)] px-5 py-4 sm:flex">
                  <span className="text-[13px] font-semibold text-slate/70">Generic AI tools</span>
                </div>
              </div>

              {[
                "Custom sales personas & pitch",
                "Real ElevenLabs voice cloning",
                "Real-time supervisor dashboard",
                "Anti-hallucination grounding",
                "Automatic lead scoring",
                "Real outbound calls (Telnyx)",
                "Live browser voice (LiveKit)",
              ].map((feature, i, rows) => (
                <div
                  key={feature}
                  className={`grid transition-colors hover:bg-signal-tint/50 sm:grid-cols-[1.4fr_1fr_1fr] ${
                    i < rows.length - 1 ? "border-b border-[var(--color-hairline)]" : ""
                  }`}
                >
                  <div className="flex items-center px-5 py-4">
                    <div>
                      <span className="text-[14px] font-semibold text-ink">{feature}</span>
                      <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1.5 sm:hidden">
                        <span className="inline-flex items-center gap-1.5 rounded-full bg-signal-tint px-2 py-0.5">
                          <CheckCircle size={11} weight="fill" className="text-signal" />
                          <span className="text-[11px] font-semibold text-signal">Built-in</span>
                        </span>
                        <span className="inline-flex items-center gap-1.5">
                          <X size={11} weight="bold" className="text-slate/50" />
                          <span className="text-[11px] font-medium text-slate/60">Not available</span>
                        </span>
                      </div>
                    </div>
                  </div>
                  <div className="hidden items-center justify-center gap-2 border-l border-[var(--color-signal-line)] bg-signal-tint/60 px-5 py-4 sm:flex">
                    <CheckCircle size={16} weight="fill" className="shrink-0 text-signal" />
                    <span className="text-[13px] font-semibold text-signal">Built-in</span>
                  </div>
                  <div className="hidden items-center justify-center gap-2 border-l border-[var(--color-hairline)] px-5 py-4 sm:flex">
                    <X size={13} weight="bold" className="shrink-0 text-slate/45" />
                    <span className="text-[13px] font-medium text-slate/60">Not available</span>
                  </div>
                </div>
              ))}
            </div>
          </ScrollReveal>
        </div>
      </section>

      {/* ── Infrastructure ─────────────────────────────────────── */}
      <section className="relative overflow-hidden bg-paper-alt py-20 sm:py-24">
        <div className="absolute inset-0 dot-grid opacity-25" aria-hidden="true" />
        <div className="relative mx-auto max-w-[84rem] 2xl:max-w-[92rem] px-5 sm:px-8">
          <ScrollReveal>
            <SectionHeading
              title={
                <>
                  Built on <Muted>proven voice infrastructure</Muted>
                </>
              }
              subtitle="Sub-second response, concurrent call handling, and an API that connects to the tools you already run."
            />
          </ScrollReveal>

          <div className="mt-10 grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-4">
            {[
              { icon: Waveform, title: "Voice pipeline", spec: "STT → your LLM → TTS", desc: "End-to-end streaming voice with sub-second response." },
              { icon: ShieldCheck, title: "Safety", spec: SITE_METRICS.grounding, desc: "Retrieval, structured output, attribution, and number checks." },
              { icon: GlobeHemisphereWest, title: "Telephony", spec: "Outbound via Telnyx", desc: "Dial real numbers — the agent calls out like a human rep." },
              { icon: Lightning, title: "Integration", spec: "REST + WebSocket + CRM", desc: "Connect your CRM, calendar, and operations systems." },
            ].map((card, i) => {
              const Icon = card.icon;
              return (
                <ScrollReveal key={card.title} delay={i * 0.05}>
                  <div className="card-ring group h-full p-6">
                    <span className="mb-4 flex h-9 w-9 items-center justify-center rounded-lg bg-signal-tint transition-colors group-hover:bg-signal-line">
                      <Icon size={19} className="text-signal transition-transform group-hover:scale-110" />
                    </span>
                    <h3 className="text-[15px] font-semibold text-ink">{card.title}</h3>
                    <p className="mt-1.5 font-mono text-[12px] text-signal">{card.spec}</p>
                    <p className="mt-2 text-[13px] leading-[1.5] text-slate">{card.desc}</p>
                  </div>
                </ScrollReveal>
              );
            })}
          </div>
        </div>
      </section>

      {/* ── Pricing ────────────────────────────────────────────── */}
      <section id="pricing" className="scroll-mt-16 bg-paper py-20 sm:py-24">
        <div className="mx-auto max-w-[84rem] 2xl:max-w-[92rem] px-5 sm:px-8">
          <ScrollReveal>
            <SectionHeading
              align="center"
              title={
                <>
                  Simple, transparent <Muted>pricing</Muted>
                </>
              }
              subtitle="Start free. Scale as you grow. No hidden fees."
            />
          </ScrollReveal>

          <div className="mx-auto mt-12 grid max-w-5xl grid-cols-1 gap-6 md:grid-cols-3">
            {[
              {
                name: "Starter",
                desc: "For small teams getting started with AI voice agents.",
                price: "Free",
                period: "/forever",
                features: ["1 AI persona", "100 calls per month", "English + Urdu", "Basic lead scoring", "Email support"],
                cta: COPY.ctaPrimary,
                href: LINKS.signup,
                featured: false,
              },
              {
                name: "Professional",
                desc: "For growing companies that need full capabilities.",
                price: "$499",
                period: "/month",
                features: [`${SITE_METRICS.personaCount} AI personas`, "Unlimited calls", "Custom voice cloning", "Advanced lead scoring", "Supervisor dashboard", "CRM integration", "Priority support"],
                cta: COPY.ctaPrimary,
                href: LINKS.signup,
                featured: true,
              },
              {
                name: "Enterprise",
                desc: "For large operations with custom requirements.",
                price: "Custom",
                period: "",
                features: ["Custom personas", "Unlimited everything", "Custom voice cloning", "Dedicated infrastructure", "SLA guarantee", "On-premise option", "Dedicated account manager"],
                cta: "Contact sales",
                href: LINKS.contactSales,
                featured: false,
              },
            ].map((plan, i) => (
              <ScrollReveal key={plan.name} delay={i * 0.08} className={plan.featured ? "md:-my-4" : ""}>
                <div
                  className={`relative flex h-full flex-col ${
                    plan.featured
                      ? "rounded-2xl border-t-[3px] border-t-signal bg-card p-8 shadow-[inset_0_0_0_1px_var(--color-signal-line),0_20px_48px_-16px_rgba(0,0,0,0.55)]"
                      : "card-ring p-7"
                  }`}
                >
                  {plan.featured && (
                    <span className="absolute -top-3 left-1/2 -translate-x-1/2 rounded-full bg-signal px-3.5 py-1 font-mono text-[10px] font-medium uppercase tracking-[0.08em] text-white shadow-[0_6px_18px_-4px_rgba(59,111,229,0.6)]">
                      Most popular
                    </span>
                  )}
                  <h3 className="text-[16px] font-semibold text-ink">{plan.name}</h3>
                  <p className="mt-1.5 text-[13px] leading-[1.5] text-slate">{plan.desc}</p>
                  <div className="mt-6 flex items-baseline gap-1.5">
                    <span className="font-display text-[40px] font-semibold leading-none tracking-[-0.02em] text-ink">
                      {plan.price}
                    </span>
                    {plan.period && <span className="text-[14px] text-slate">{plan.period}</span>}
                  </div>
                  <div className="mt-6 flex-1 space-y-3 border-t border-[var(--color-hairline)] pt-6">
                    {plan.features.map((f) => (
                      <div key={f} className="flex items-start gap-2.5">
                        <CheckCircle size={14} weight="fill" className="mt-[3px] shrink-0 text-signal" />
                        <span className="text-[13px] leading-[1.4] text-ink">{f}</span>
                      </div>
                    ))}
                  </div>
                  {plan.href === LINKS.signup ? (
                    <PrimaryCta
                      size="md"
                      fullWidth
                      className="mt-7"
                      loggedOutLabel={plan.cta}
                    />
                  ) : (
                    <ThemeButton
                      href={plan.href}
                      variant="secondary"
                      fullWidth
                      className="mt-7"
                      iconRight={<ArrowRight size={14} weight="bold" />}
                    >
                      {plan.cta}
                    </ThemeButton>
                  )}
                </div>
              </ScrollReveal>
            ))}
          </div>
        </div>
      </section>

      {/* ── Final CTA — the one bold block ──────────────────────── */}
      <section className="relative overflow-hidden bg-signal py-24">
        <div
          aria-hidden="true"
          className="absolute inset-0 opacity-[0.14]"
          style={{
            backgroundImage:
              "radial-gradient(circle, rgba(255,255,255,0.9) 1px, transparent 1px)",
            backgroundSize: "26px 26px",
          }}
        />
        <div className="relative mx-auto max-w-3xl px-5 text-center sm:px-8">
          <ScrollReveal>
            <p className="font-mono text-[11px] uppercase tracking-[0.28em] text-white/70">
              One team · one number
            </p>
            <h2 className="mx-auto mt-4 max-w-[20ch] font-display text-h2 font-bold leading-[1.08] tracking-[-0.02em] text-white text-balance">
              {COPY.finalCtaHeadline}
            </h2>
            <p className="mx-auto mt-4 max-w-[50ch] text-[16px] leading-[1.65] text-white/75">
              {COPY.finalCtaSub}
            </p>
            <div className="mt-8 flex flex-wrap justify-center gap-3">
              <PrimaryCta size="lg" className="!bg-white !text-signal hover:!bg-white/90" />
              <ThemeButton
                href={LINKS.contactSales}
                size="lg"
                className="!bg-white/10 !text-white ring-1 ring-inset ring-white/25 hover:!bg-white/20"
                iconRight={<ArrowRight size={15} weight="bold" />}
              >
                Book a demo
              </ThemeButton>
            </div>
            <div className="mt-9 flex flex-wrap items-center justify-center gap-x-8 gap-y-3">
              {["No credit card required", "Deploy in minutes", "Cancel anytime"].map((item) => (
                <div key={item} className="flex items-center gap-2">
                  <CheckCircle size={15} weight="fill" className="shrink-0 text-white/80" />
                  <span className="text-[13px] font-medium text-white/80">{item}</span>
                </div>
              ))}
            </div>
          </ScrollReveal>
        </div>
      </section>

      {/* ── Footer ─────────────────────────────────────────────── */}
      <footer className="border-t border-[var(--color-hairline)] bg-paper-alt">
        <div className="mx-auto max-w-[84rem] 2xl:max-w-[92rem] px-5 py-12 sm:px-8">
          <div className="grid grid-cols-1 gap-8 sm:grid-cols-2 lg:grid-cols-4">
            <div>
              <div className="mb-3">
                <Logo href={null} />
              </div>
              <p className="max-w-[34ch] text-[13px] leading-[1.55] text-slate">
                AI voice agents that cold-call, pitch, and book meetings for your sales team —
                automatically, around the clock.
              </p>
            </div>
            <div>
              <h4 className="mb-3 font-mono text-[11px] font-medium uppercase tracking-[0.14em] text-slate">
                Product
              </h4>
              <div className="space-y-2">
                <a href={LINKS.features} className="block text-[13px] text-slate transition-colors hover:text-signal">Features</a>
                <a href={LINKS.pricing} className="block text-[13px] text-slate transition-colors hover:text-signal">Pricing</a>
                <a href={LINKS.demo} className="block text-[13px] text-slate transition-colors hover:text-signal">Watch a call</a>
                <Link href={LINKS.dashboard} className="block text-[13px] text-slate transition-colors hover:text-signal">Dashboard</Link>
              </div>
            </div>
            <div>
              <h4 className="mb-3 font-mono text-[11px] font-medium uppercase tracking-[0.14em] text-slate">
                Get started
              </h4>
              <div className="space-y-2">
                <Link href={LINKS.signup} className="block text-[13px] text-slate transition-colors hover:text-signal">Start free</Link>
                <Link href={LINKS.login} className="block text-[13px] text-slate transition-colors hover:text-signal">Log in</Link>
                <a href={LINKS.contactSales} className="block text-[13px] text-slate transition-colors hover:text-signal">Talk to sales</a>
              </div>
            </div>
            <div>
              <h4 className="mb-3 font-mono text-[11px] font-medium uppercase tracking-[0.14em] text-slate">
                Company
              </h4>
              <div className="space-y-2 text-[13px] text-slate">
                <p>{BRAND.company}</p>
                <a href={LINKS.contactSales} className="block transition-colors hover:text-signal">
                  {BRAND.salesEmail}
                </a>
              </div>
            </div>
          </div>

          <div className="mt-10 border-t border-[var(--color-hairline)] pt-6">
            <span className="text-[13px] text-slate">
              &copy; {new Date().getFullYear()} {BRAND.company}. All rights reserved.
            </span>
          </div>
        </div>
      </footer>

      <StickyBottomBar />
    </>
  );
}
