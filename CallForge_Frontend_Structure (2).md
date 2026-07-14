# CallForge — Frontend Development Documentation

**Scope:** Visual direction, page-by-page specification, build order, and quality process for the 2-week MVP
**Team:** Frontend Lead (Person 1) + Frontend Support (Person 2)
**Stack:** React · Tailwind CSS · Axios/Fetch · WebSockets (live call feed)

---

## 1. Visual Direction — "Command Center," Not a Generic Admin Panel

CallForge's actual job is to let a sales manager watch and intervene in AI phone calls happening *right now*. The interface should feel less like a CRUD admin panel and more like a **live operations console** — the kind of focused, high-signal surface you'd find at a trading desk or an air-traffic control station, adapted for sales calls. That framing drives every layout decision below; it is not decoration bolted onto a template.

### Token System

| Category | Decision |
|---|---|
| **Background** | Near-black navy, `#0B1120` base, `#111A2E` for elevated panels — not pure black, keeps depth |
| **Primary accent** | Electric blue `#3B82F6` — used for the AI/system voice, active states, primary actions |
| **Live/active accent** | Signal green `#22C55E` — reserved *only* for "call is live" / "AI speaking" indicators, never used decoratively |
| **Human/takeover accent** | Violet `#8B5CF6` — reserved *only* for Ghost Mode / human-in-call states, so a glance tells you who's talking |
| **Warning/objection** | Amber `#F59E0B` — objection flags, retry states |
| **Danger** | Red `#EF4444` — dropped calls, failed bookings, errors only |
| **Display type** | A geometric sans (e.g. Inter or General Sans) at a confident weight for numbers and headers — this product is read in glances, not paragraphs |
| **Body/data type** | Same family, lighter weight, tabular figures enabled for any numeric column (durations, percentages, call counts) so digits align |
| **Monospace** | Used only for the live transcript panel — sets it apart visually as a "raw feed," distinct from the rest of the UI |
| **Radius & elevation** | Small radius (6–8px), subtle 1px borders over heavy shadows — panels read as instrument surfaces, not soft cards |

### Signature Element

Every active call gets a **live pulse indicator**: a small animated ring around the call's status dot that beats in sync with actual voice activity (driven by the WebSocket's sentiment/audio-activity signal, not a generic CSS loop). This is the one place motion is deliberate and meaningful — it's how a manager tells "AI mid-sentence" from "waiting for prospect" from "silence/dead air" at a glance across a whole grid of concurrent calls. No other part of the UI animates for decoration.

### Restraint Rule

The pulse indicator and the green/violet speaker-state color coding are the two moments of personality. Everything else — tables, forms, settings — stays quiet, disciplined, and information-dense so those two signals stand out instead of competing with decoration.

---

## 2. Repository / Folder Structure

```
callforge-frontend/
├── src/
│   ├── foundation/                  # Design tokens + primitives (P1, Day 1–2)
│   │   ├── tokens.css               # Color, type, spacing, radius variables
│   │   ├── Button.jsx
│   │   ├── StatusDot.jsx            # Powers the live pulse indicator
│   │   ├── DataTable.jsx
│   │   └── Modal.jsx
│   │
│   ├── pages/                       # One file per full page — the real unit of work
│   │   ├── LoginPage.jsx                    (P2)
│   │   ├── CommandCenterPage.jsx            (P1) — main live dashboard
│   │   ├── CallDetailPage.jsx               (P1) — expanded single-call view
│   │   ├── CampaignManagerPage.jsx          (P2)
│   │   ├── CampaignDetailPage.jsx           (P2)
│   │   ├── ObjectionPlaybookPage.jsx        (P2)
│   │   ├── AnalyticsPage.jsx                (P1, Week 2)
│   │   └── SettingsPage.jsx                 (P1, Week 2)
│   │
│   ├── sections/                    # Reusable page-sections, scoped to one page's domain
│   │   ├── command-center/
│   │   │   ├── ActiveCallGrid.jsx
│   │   │   └── SystemStatusBar.jsx
│   │   ├── call-detail/
│   │   │   ├── TranscriptFeed.jsx
│   │   │   ├── SentimentTimeline.jsx
│   │   │   └── InterventionControls.jsx     # Take Over / Whisper / Book Meeting
│   │   ├── campaigns/
│   │   │   ├── CampaignTable.jsx
│   │   │   └── OutboundDialerPanel.jsx
│   │   └── analytics/
│   │       ├── ConversionChart.jsx
│   │       └── ABComparisonPanel.jsx
│   │
│   ├── api/
│   │   ├── client.js                # Axios instance, base config, interceptors
│   │   ├── calls.js
│   │   ├── campaigns.js
│   │   ├── objections.js
│   │   └── analytics.js
│   │
│   ├── hooks/
│   │   ├── useLiveCall.js           # WebSocket subscription, drives the pulse indicator
│   │   ├── useAuth.js
│   │   └── useCampaigns.js
│   │
│   ├── context/
│   │   └── AuthContext.jsx
│   │
│   └── App.jsx
│
├── tests/
│   ├── unit/
│   └── e2e/
│
├── .github/workflows/ci.yml
└── docs/
    └── PAGE_SPEC.md                 # This document's Section 3, kept in-repo
```

**Why pages, not components, are the unit of planning:** a component library review tells you nothing about whether the *product* works. Every day below is scoped to shipping one real, navigable page end to end — foundation primitives exist to serve the pages, not the other way around.

---

## 3. Page-by-Page Specification

### 3.1 Login Page — *(P2)*

A single centered panel on the full navy background — no sidebar, no distraction. Email/password fields, one primary action. Failed login shows the reason inline, in the interface's own voice ("That password doesn't match this email" — not a generic "Error"). This is the only page that's allowed to feel calm and empty; everything after it is dense.

### 3.2 Command Center Page — *(P1)* — the product's core screen

This is what a sales manager has open all day. Three zones:

- **System Status Bar** (top, always visible): total active calls, calls today, current conversion rate, a single-glance system-health chip. This is the "instrument panel" strip.
- **Active Call Grid** (main area): every live call as a compact row/card, each with the pulse indicator, prospect name/company, call stage (BANT progress as a thin inline progress bar, not a separate page), and current sentiment color. Sorted with anything needing attention (objection raised, long silence) surfaced to the top automatically — the manager should not have to hunt.
- **Quick Filter Rail** (left, collapsible): filter by campaign, by stage, by "needs attention." Not a full sidebar nav — this page *is* the destination, navigation to other pages lives in a slim top bar instead of a heavy permanent sidebar, so the call grid gets maximum width.

Clicking any row opens the Call Detail Page — never a modal. A live call deserves a full page, not a popup you might lose.

### 3.3 Call Detail Page — *(P1)*

Two-column layout:

- **Left (60%): Transcript Feed** — monospace, auto-scrolling, speaker-labeled with color coding (blue = AI, neutral = prospect, violet = human if Ghost Mode is active). This is the "raw feed" moment referenced in the signature element.
- **Right (40%), stacked top to bottom:**
  - **Sentiment Timeline** — a compact line/area chart of sentiment over the call's duration so far, not just a single current-state badge.
  - **BANT Progress** — the four qualification criteria as a checklist that fills in live as the AI confirms each one.
  - **Intervention Controls** — Take Over, Whisper, Book Meeting. Take Over is visually the most weighted action on the page (larger, distinct violet accent) since it's the feature no competitor has. Once active, the whole page's accent shifts to signal "you are live," not the AI — this is the "no ambiguous state" requirement from the review process.

### 3.4 Campaign Manager Page — *(P2)*

A dense, sortable table — campaign name, status, leads count, conversion so far, pitch variant in use. Status is a colored chip (draft/active/paused), not decorative iconography. "New Campaign" is the one clearly primary action in the top-right; everything else is inline row actions (pause/resume/duplicate) so the manager never leaves the table to make routine changes.

### 3.5 Campaign Detail Page — *(P2)*

Header strip with campaign-level stats (leads dialed / booked / conversion %), then a leads table below with per-lead status. The Outbound Dialer panel (CSV upload) lives here, not as a separate page — uploading leads is an action *on* a campaign, not a standalone destination.

### 3.6 Objection Playbook Page — *(P2)*

A list of objections, each expandable to show its response(s) and a live success-rate percentage. A/B variants of a response sit side by side, not toggled between — the manager should be able to compare wording and performance in one glance. Editing is inline (click to edit the response text directly), not a separate edit modal — this keeps the page feeling like a working document the sales team actively maintains, not an admin form.

### 3.7 Analytics Page — *(P1, Week 2)*

Three to four focused charts, not a dashboard-of-everything: conversion trend over time, objection success rates, A/B pitch comparison, and the morning briefing summary rendered as a real in-app view (matching the emailed version exactly). Every chart states its own takeaway in a one-line caption above it — a number without a sentence explaining what it means is not finished.

### 3.8 Settings Page — *(P1, Week 2)*

Voice tuning (speed/tone/pitch) with a live preview if feasible, otherwise a clear "changes apply to the next call" note so nobody assumes it's retroactive. Kept deliberately plain — this is the one page where "quiet and disciplined" fully wins over any personality.

---

## 4. API Contract Consumption — Owned by Person 2 (Day 1), Used by Both

`api/client.js` is the single Axios instance both devs use — no page calls `fetch` directly.

| Concern | Rule |
|---|---|
| Base URL | Read from `.env`, never hardcoded |
| Auth | Token attached via Axios interceptor, refresh handled centrally |
| Error handling | Every API call surfaces an error in the interface's own voice (what happened, what to do) — no silent failures, no unhandled promise rejections |
| Loading states | Every data-fetching page has an explicit loading + error + empty state, and the empty state is written as an invitation to act ("No campaigns yet — create your first one"), not a blank table |

Endpoint shapes are pulled from the backend's `docs/API_CONTRACT.md` — confirm shape with backend before building a page around assumed fields.

---

## 5. Day-by-Day Build Plan (with Build Steps, Acceptance Criteria & Review)

Same daily rhythm as backend, so both teams stay in sync:

1. **Morning (15 min):** Standup — yesterday's result, today's target, blockers.
2. **Build:** Ship one real, navigable increment of the assigned page against its spec in Section 3.
3. **Self-test:** Check against acceptance criteria in a real browser, with real (or realistic mock) data — not just "looks right in the editor."
4. **End-of-day review (30 min):** The other frontend dev reviews the PR against the Definition of Done (Section 6). Nothing merges to `main` unreviewed.
5. **Log:** One line in the shared build log — what shipped, what's open, what's blocking.

### WEEK 1 — Inbound Foundation

#### Person 1 (Frontend Lead) — Command Center & Call Detail

| Day | Build | Acceptance Criteria | Review Check |
|---|---|---|---|
| 1 | Project setup, foundation tokens/primitives, CI lint/build | `npm run build` succeeds clean; tokens.css defines the full palette from Section 1 | P2 confirms folder structure and tokens before building on top of it |
| 2 | `StatusDot` + pulse-indicator primitive, `Button`, `DataTable` | Pulse animation is driven by a prop (not a hardcoded CSS loop) and can represent AI-speaking / human-speaking / idle states | Reviewed for reuse — no page-specific styling leaking into the primitive |
| 3 | Command Center Page shell — Status Bar + Filter Rail + top nav | Page navigable, layout matches Section 3.2 structure at desktop width | Tested at mobile and desktop — filter rail collapses correctly, doesn't break the grid |
| 4 | Active Call Grid against mock data | Grid renders call rows with correct stage progress bar and sentiment color, "needs attention" sorts to top | Confirm component accepts the real API shape from `API_CONTRACT.md`, not just the mock |
| 5 | Call Detail Page — Transcript Feed + Sentiment Timeline | Transcript auto-scrolls and appends correctly with speaker color coding; timeline renders against a 50+ turn mock call | No layout break, no memory leak on unmount with a long transcript |
| 6 | Call Detail Page — BANT Progress + Intervention Controls | Controls trigger correct handler stubs; buttons disabled during in-flight requests | Confirm "who's live" visual state is unambiguous when toggled — no confusing intermediate state |
| 7 | Polish + responsive pass on both pages; handoff notes for P2 | Full manual click-through of both pages with no console errors | Joint review with P2: confirm `PAGE_SPEC.md` matches what actually shipped |

#### Person 2 (Frontend Support) — Login, Campaigns, Playbook, Auth

| Day | Build | Acceptance Criteria | Review Check |
|---|---|---|---|
| 1 | API client layer (`api/client.js`), base Axios config, interceptors | A test call to a stub/mock endpoint succeeds with auth header attached | P1 confirms API client is the only path used — no ad hoc fetch calls anywhere |
| 2 | Login Page | Correct success/redirect and failure paths; failure message is specific, not generic | Confirm token storage approach reviewed (no plaintext in localStorage without justification) |
| 3 | Campaign Manager Page — table, status chips, New Campaign action | Full CRUD works against mock data; row actions (pause/resume) work inline | Confirm error states are visible in the interface's voice, not just logged to console |
| 4 | Campaign Detail Page — stats header + leads table | Leads table paginates correctly; stats reflect real percentages, not hardcoded | Test with 0 leads and 500+ leads — both render without breaking |
| 5 | Objection Playbook Page — inline-editable list with A/B response comparison | Add/edit/delete work and persist through a page refresh; A/B responses render side by side | Confirm optimistic UI update rolls back correctly on a failed save |
| 6 | Morning Briefing content (in-app draft) + email template parity | Both versions pull from the same data structure so numbers match exactly | Cross-check the two renderings side by side — no drift allowed |
| 7 | Full API integration for all P2 pages against the real backend | Every P2-owned page works end-to-end against the real backend, not mocks | Joint review — Friday Week 1 checklist (Section 7) run in full |

### WEEK 2 — Outbound + Intelligence

#### Person 1

| Day | Build | Acceptance Criteria | Review Check |
|---|---|---|---|
| 8 | Ghost Mode wiring — Intervention Controls call the real takeover endpoint | Takeover correctly flips the page's accent state and calls the backend | UI clearly shows "you are live" vs "AI is live" at all times — tested explicitly |
| 9 | Real-time WebSocket wiring for Command Center + Call Detail | Both pages update within ~1s of a backend event, no manual refresh | Reconnect after a dropped WebSocket recovers without a full page reload |
| 10 | Analytics Page — Conversion Chart + A/B Comparison Panel | Charts render correctly against real aggregated data, each with its takeaway caption | Numbers cross-checked against backend analytics directly, not assumed |
| 11 | Analytics Page — Objection success charts + in-app Morning Briefing view | Renders correctly against real data; matches email version from Week 1 exactly | Verify empty/zero-data states don't render broken or blank charts |
| 12 | Settings Page — voice tuning controls | Slider changes correctly bounded and sent to backend config, with the "applies next call" note | Confirm out-of-range values are rejected client-side, not just trusted to the backend |
| 13 | Polish, bug fixes, performance pass across all P1 pages | No console errors/warnings; Lighthouse performance check done | P2 does a full click-through as a "new user" to catch anything P1 has gotten used to |
| 14 | Demo preparation — recorded backup video | Backup demo video recorded and works standalone if live demo fails | Joint go/no-go review against Section 7 before calling it "demo ready" |

#### Person 2

| Day | Build | Acceptance Criteria | Review Check |
|---|---|---|---|
| 8 | Outbound Dialer panel (on Campaign Detail Page) — CSV upload | Upload validates file format/columns before submit; clear, specific error on a bad file | Test with a malformed CSV — must fail gracefully, not silently drop rows |
| 9 | Lead enrichment display within Campaign Detail's leads table | Enrichment fields render when present, gracefully hidden when absent | No broken layout when enrichment data is partially missing |
| 10 | Mobile responsive pass — all P2 pages | Every P2 page usable on a real mobile viewport, not just a resized desktop browser | Tested on an actual phone or device emulator |
| 11 | Objection Analytics numbers reconciled against Analytics Page | Success-rate calculations match exactly between Objection Playbook and Analytics Page | Confirm consistent rounding/formatting across the whole app |
| 12 | Cross-browser testing across all pages | Works correctly on Chrome, Firefox, Safari at minimum | Any browser-specific bug logged and fixed, not deferred silently |
| 13 | Full-app content pass — remove all placeholder/lorem-ipsum text | Every page shows real or realistic copy in the interface's own voice | P1 spot-checks each page for leftover placeholder content |
| 14 | Demo support — dry run alongside P1 | Full demo flow rehearsed end-to-end at least twice | Joint go/no-go review against Section 7 before calling it "demo ready" |

---

## 6. Definition of Done (applies to every task, every day)

A task is **not done** until all of the following are true:

- [ ] Code is committed to a feature branch and opened as a PR (never pushed straight to `main`)
- [ ] The acceptance criteria for that day's task (Section 5) are met and demonstrated in a real browser
- [ ] The other frontend dev has reviewed and approved the PR
- [ ] No console errors or warnings introduced by the new code
- [ ] Loading, error, and empty states are handled for every data-fetching page — and the copy for each follows the writing rules in Section 4
- [ ] The page matches the visual direction in Section 1 — no one-off colors bypassing tokens, no decorative use of the green/violet speaker-state colors
- [ ] Responsive behavior checked at mobile and desktop widths
- [ ] Any new reusable primitive is added to `foundation/`, documented, and justified (used in 2+ places) — not created ad hoc inside a page

---

## 7. Review & QA Process

### Daily
- End-of-day PR review between P1 and P2 (Section 5 table).
- Build log entry: what shipped, what's open, what's blocking — visible to the whole team.

### Twice-Weekly Cross-Check (Wed and Fri)
- Frontend Lead + Frontend Support + Product Lead click through the live app together against the real backend — an actual usage pass, not a code review.
- Any bug logged with severity (blocker / major / minor) before moving on.

### Friday Review — End of Week 1 (Must Pass Before Week 2 Starts)

| Check | Pass Criteria |
|---|---|
| Command Center loads | No errors, active call grid renders against real backend data |
| Live call display | A real call appears on the Command Center within ~1s, pulse indicator reflects actual state |
| Call Detail transcript | Live transcript updates correctly as the call progresses, speaker colors correct |
| Campaign CRUD | Create/list/pause all work against the real backend |
| Login/Auth | Works correctly, invalid credentials handled with a specific message |
| No console errors | Full click-through of every shipped page produces a clean console |

If any of these fail, Week 2 scope is cut, not the review — do not carry unresolved Week 1 defects into Week 2 build time.

### Friday Demo — End of Week 2 (Pre-Demo Checklist)

- [ ] Full demo flow rehearsed at least twice end-to-end against the real (or staging) backend
- [ ] A recorded backup demo video exists in case of live failure
- [ ] Every page used in the demo tested on the actual demo device/browser beforehand
- [ ] No placeholder/lorem-ipsum text visible anywhere in the demo path
- [ ] Ghost Mode's "who's live" state verified correct during the rehearsal, not assumed

### Code Review Standards (applies to every PR, not just end-of-week)

- Reviewer actually runs the app and clicks through the change — not just reading the diff.
- Reviewer checks the acceptance criteria for that day's task, not just "does it look reasonable."
- No PR is self-approved. If the other frontend dev is unavailable, the Product Lead or a backend dev reviews instead.
- Comments that block merge must be resolved, not just acknowledged.

---

## 8. Risk Notes Specific to Frontend

- **Visual drift:** without the token system locked by Day 2, the two devs' pages will visibly diverge by Week 2 — lock Section 1 early, don't let this slip.
- **Mock-vs-real data mismatch:** pages built entirely against mock data can break on real API responses — validate against `API_CONTRACT.md` continuously, not just at integration time on Day 7.
- **WebSocket reliability:** the pulse indicator and live transcript are the centerpiece of the demo — reconnect/error handling must be solid well before Day 14, not patched last-minute.
- **Ambiguous live state:** a wrong "who's talking" indicator on the Call Detail Page undermines the entire product thesis — this gets explicit, dedicated testing, not an assumption.
- **Demo-day fragility:** never rely on a single live network path for the demo; always have a recorded backup per Section 7.

---

## 9. Local Dev Setup Checklist

```bash
# 1. Install dependencies
npm install

# 2. Environment config
cp .env.example .env    # set VITE_API_BASE_URL, VITE_WS_URL

# 3. Run dev server
npm run dev

# 4. Run lint + tests before every PR
npm run lint
npm run test

# 5. Production build check
npm run build
```

---

## 10. Daily Standup Questions (Frontend)

- Does every page built so far work against the real backend, or still on mocks?
- Any page that bypassed the token system with one-off styling?
- Is the WebSocket connection stable, including reconnect after a drop?
- Are loading/error/empty states handled for anything shipped yesterday, written in the interface's voice?
- Did yesterday's task actually pass its acceptance criteria, or is it "mostly done"?
- Is there anything currently unreviewed sitting in a PR overnight?
