/* Single source of truth for every number, capability claim, and repeated
   marketing string on the site.

   Rule (PRODUCT.md): no fabricated metrics or customer claims — the demo
   speaks for itself. Everything here is either demonstrable from the working
   product or a plain capability statement. Call-volume counters, CSAT %, uptime
   %, and cost-per-minute figures were removed because they cannot be shown.

   Product = CallForge. Company = AgentraX (legal footer + <meta publisher> only). */

export const BRAND = {
  product: "CallForge",
  company: "AgentraX",
  tagline: "AI sales agents that cold-call and close while you sleep",
  /* one description, reused for <meta> and the footer blurb */
  blurb:
    "CallForge builds a custom AI sales persona — your name, your pitch, your cloned voice — that cold-calls, handles objections, and books meetings automatically, around the clock.",
  domain: "callforge.ai",
  salesEmail: "sales@callforge.ai",
} as const;

/* Repeated headlines / CTA copy — kept here so the sticky bar, hero, and final
   CTA can never drift. */
export const COPY = {
  finalCtaHeadline: "Ready to put your sales calls on autopilot?",
  finalCtaSub:
    "Deploy your AI voice team in days, not months. Start handling calls 24/7 with zero hold time.",
  ctaPrimary: "Start free",
  ctaSecondary: "Talk to sales",
} as const;

/* Where the CTAs point. `demo` is the in-page anchor of the interactive hero
   console (Phase 3). */
export const LINKS = {
  signup: "/signup",
  login: "/login",
  dashboard: "/dashboard",
  demo: "#demo",
  pricing: "#pricing",
  features: "#features",
  howItWorks: "#how-it-works",
  contactSales: `mailto:${BRAND.salesEmail}`,
} as const;

/* Demonstrable capability facts. Strings, not invented figures. */
export const SITE_METRICS = {
  personaCount: 4,
  latency: "sub-second response",
  grounding: "4-layer anti-hallucination",
  intents: "11 intents with entity extraction",
  languages: "English + Urdu",
  telephony: "Real outbound calls · Telnyx",
  webrtc: "Live browser calls · LiveKit",
  leadScoring: "Automatic hot / warm / cold scoring",
} as const;

/* The factual capability strip that replaces the fabricated logo marquee. */
export const CAPABILITY_STRIP: readonly string[] = [
  SITE_METRICS.telephony,
  SITE_METRICS.webrtc,
  SITE_METRICS.grounding,
  SITE_METRICS.languages,
];

/* Call disposition codes — the structural device for section eyebrows.
   These are the real stages an outbound call moves through. */
export const DISPOSITION = {
  connected: "CONNECTED",
  qualifying: "QUALIFYING",
  objection: "OBJECTION",
  booked: "BOOKED",
  escalated: "ESCALATED",
  supervised: "SUPERVISED",
} as const;

export interface Persona {
  name: string;
  role: string;
  desc: string;
  /* solid accent for text / pills */
  color: string;
  /* [from, to] for the avatar gradient */
  gradient: [string, string];
  specialties: [string, string];
}

/* The four working personas from the demo (PRODUCT.md "Evidence on Hand"). */
export const PERSONAS: readonly Persona[] = [
  {
    name: "Ahmed",
    role: "Cold Calling",
    desc: "Opens with rapport, not a script. Qualifies prospects and surfaces pain points before ever pitching.",
    color: "#057676",
    gradient: ["#057676", "#0a9e9e"],
    specialties: ["Lead Qualification", "Rapport Building"],
  },
  {
    name: "Bilal",
    role: "Objection Handling",
    desc: 'Handles price pushback, competitor comparisons, and "not interested" — grounded only in what you told it.',
    color: "#3B82F6",
    gradient: ["#2563EB", "#60A5FA"],
    specialties: ["Objection Handling", "Grounded Answers"],
  },
  {
    name: "Mahnoor",
    role: "Demo Booking",
    desc: "Offers real available slots and books the meeting on the call — no back-and-forth, no dropped leads.",
    color: "#8B5CF6",
    gradient: ["#7C3AED", "#A78BFA"],
    specialties: ["Slot Booking", "Calendar Sync"],
  },
  {
    name: "Shahzaib",
    role: "Follow-up Agent",
    desc: "Proactively follows up on stale leads, pending quotes, and incomplete bookings to re-engage prospects.",
    color: "#EAB308",
    gradient: ["#CA8A04", "#FACC15"],
    specialties: ["Re-engagement", "Pipeline Recovery"],
  },
];
