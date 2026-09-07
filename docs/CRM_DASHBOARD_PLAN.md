# CallForge CRM Dashboard — Build Plan

> **Status (implemented on branch `feat/crm-dashboard`)**
> Backend: `app/db/` (async engine + models), `app/crm/` (orgs, repository, schemas,
> routes, analytics, search, ingest), Alembic (`alembic/`), `/api/crm/*` mounted in
> `main.py`, call→CRM ingest wired into `realtime/ws.py` + `/internal/calls/{id}/finalize`
> + the LiveKit worker. 10 pytest cases green against SQLite (`pytest.ini`,
> `tests/test_crm_*.py`). Run Postgres per `packages/backend/.env.example`.
> Frontend: nav rebuilt on real routes (`DashboardShell.tsx`), new pages under
> `app/dashboard/` — `contacts`, `contacts/[id]`, `companies`, `companies/[id]`,
> `deals` (kanban, native drag-drop), `calls`, `activities`, `escalations`,
> `settings` — overview rebuilt on `/api/crm/analytics/overview`, global ⌘K search
> wired, dialer accepts `?to=`. Shared primitives in `app/dashboard/_components/`,
> data hooks in `app/dashboard/_hooks/useCrm.ts`, API client in `lib/crm.ts`.
> No new npm deps (SWR → hand-rolled `useResource`; kanban → native HTML5 DnD).
> `next build` needs network for `next/font` (Google Fonts) — unrelated to this work.

## Context

Today CallForge has an **operations monitor**, not a CRM. The `/dashboard` page is a
single read-only scroll view of: live calls (from `/ws/dashboard`), auto-extracted
per-call "leads" (`sales/leads.py`), bookings, and escalations. Everything lives in
**in-memory Python dicts** (`bus.calls`, `LEADS`, `BOOKINGS`, `CASES`, `PERSONAS`,
`USERS`) and is **wiped on every backend restart**. There is no concept of a
persistent Contact, Company, Deal/pipeline, Task, or a saved call history with
transcripts, and no way to edit records or follow up on a prospect over time.

The goal: turn this into a real **team CRM** — persistent contacts, companies,
a drag-drop deal pipeline, activities/tasks, and a searchable call history that the
voice agent automatically feeds. A sales team logs in, sees a shared pipeline,
places calls from a contact record, and every call lands back on that contact's
timeline with its transcript and outcome.

### Decisions locked with the user
- **Scope:** full pipeline CRM (Contacts, Companies, Deals + board, Activities/Tasks, Notes, Call history).
- **Persistence:** PostgreSQL + SQLAlchemy 2.0 (async) + Alembic migrations.
- **Migration blast radius:** CRM entities only. Auth (`USERS`/`SESSIONS`), personas,
  and the live-call bus/`run_turn` path stay in-memory for now. The DB is additive.
- **Sharing model:** team/org. CRM rows carry `org_id` + `owner_email`; teammates in
  the same org share the pipeline.

---

## Architecture overview

```
 Auth (in-memory, unchanged)  ──►  resolve_org(user)  ──►  Organization / OrgMembership (Postgres)
                                                             │
 Voice call ends (ws.py finally / LiveKit session end)       │  org_id + owner_email
        │  persist_call(call_id)                             ▼
        ▼                                        ┌───────────────────────────────┐
 crm/ingest.py  ── reads bus.calls + LEADS ────► │  Postgres (CRM tables)        │
   • upsert Contact by phone                     │  Organization, OrgMembership,  │
   • CallRecord + transcript snapshot            │  Company, Contact, Deal,       │
   • Activity(type=call) on timeline             │  Activity, CallRecord          │
   • booking confirmed → create/advance Deal     └───────────────────────────────┘
                                                             ▲
 Frontend /dashboard/*  ── crmFetch (Bearer) ──► /api/crm/*  │  all queries org-scoped
```

---

## Backend

### B1. DB foundation — *why: nothing persists today*

**New deps** (`packages/backend/requirements.txt`): `sqlalchemy[asyncio]>=2.0`,
`asyncpg>=0.29`, `alembic>=1.13`, `psycopg2-binary>=2.9` (Alembic sync driver).

**`docker-compose.yml`:** add a `db` service (`postgres:16-alpine`, volume, healthcheck),
`depends_on: [db]` on `backend` + `livekit_agent`, and
`DATABASE_URL=postgresql+asyncpg://callforge:callforge@db:5432/callforge`.
`.env.example`: add the same `DATABASE_URL` line (localhost host for non-Docker).

**`app/config.py`:** `database_url` already exists but is unused — wire it. Add
`crm_auto_create_tables: bool = True` and helper properties `db_async_url` /
`db_sync_url` (swap the driver prefix for Alembic).

**`app/db/__init__.py`** (new): async `engine`, `async_session_factory`,
`Base = DeclarativeBase`, and a `get_session()` FastAPI dependency (`async with`
yielding an `AsyncSession`). `init_db()` runs `Base.metadata.create_all` when
`crm_auto_create_tables` (dev convenience) — Alembic is the real path.

**`app/db/models.py`** (new) — all rows: `id: str` (uuid4 hex PK), `org_id` (indexed
FK), `owner_email`, `created_at`, `updated_at`.
- `Organization` — `name`.
- `OrgMembership` — `org_id`, `email` (indexed, unique per org), `role` (`owner`/`member`).
- `Company` — `name`, `domain`, `industry`, `size`, `website`, `phone`, `notes`.
- `Contact` — `first_name`, `last_name`, `full_name`, `email`, `phone` (E.164,
  **indexed** — call matching), `title`, `company_id` (nullable FK),
  `lifecycle_stage` (`lead`/`mql`/`sql`/`customer`/`churned`), `source`,
  `do_not_call` bool, `tags` (JSON list), `last_contacted_at`.
- `Deal` — `title`, `contact_id` FK, `company_id` nullable FK, `stage`
  (`new`/`qualified`/`demo`/`proposal`/`negotiation`/`won`/`lost`), `amount`
  (Numeric), `currency`, `expected_close_date`, `probability`, `lost_reason`,
  `closed_at`, `board_order` (float, for within-column ordering).
- `Activity` — unified timeline row: `type` (`note`/`task`/`call`/`email`/`meeting`),
  `subject`, `body`, `due_at`, `completed_at`, `contact_id` FK, `deal_id` nullable FK,
  `call_id` nullable (links `CallRecord`), `author_email`.
- `CallRecord` — `id` **=** the `bus` `call_id` (so a live call maps 1:1 to its
  saved record), `persona_id`, `persona_name`, `direction`, `from_number`,
  `to_number`, `contact_id` nullable FK, `status`, `outcome`
  (`booked`/`callback`/`declined`/`escalated`/`none`), `started_at`, `ended_at`,
  `duration_s`, `language`, `escalated` bool, `case_id`, `transcript` (JSON array of
  `{who,name,text}`), `lead_snapshot` (JSON), `recording_url` (nullable, future).

**Alembic** (new): `alembic.ini`, `alembic/env.py` (reads `settings.db_sync_url`,
`target_metadata = Base.metadata`), `alembic/versions/0001_init_crm.py` creating all
tables. Document `alembic upgrade head`; keep `create_all` for the zero-setup dev path.

**`app/main.py`:** call `await init_db()` in the startup hook; add `db_ok` to `/health`
(cheap `SELECT 1`).

### B2. Org resolution — *why: auth has no org table, CRM data must be shared + scoped*

**`app/crm/orgs.py`** (new): `resolve_org(session, user) -> Organization`. Look up
`OrgMembership` by `user.email`; if none, create an `Organization`
(`name = user.company or f"{user.name}'s team"`) + an `owner` membership, commit,
return. Cached per-request. Every CRM route depends on this, so `org_id` scoping is
automatic and a user can never read another org's rows.
Also: `add_member(org, email, role)` and `list_members(org)` for the settings page.

### B3. CRM CRUD API — *why: create/read/update/delete the pipeline*

**`app/crm/repository.py`** (new): generic async helpers, all take `(session, org_id, ...)`:
`list_(Model, filters, sort, limit, offset)`, `get(Model, id)` (404 if wrong org),
`create`, `update` (patch semantics), `delete`. One place for pagination + org
enforcement.

**`app/crm/schemas.py`** (new): Pydantic v2 request/response models per entity
(`ContactIn/Out`, `DealIn/Out`, `BoardColumn`, `TimelineItem`, `AnalyticsOverview`, …).

**`app/crm/routes.py`** (new): `APIRouter(prefix="/api/crm")`, every route
`Depends(_current_user)` (reuse the existing dependency in `main.py` — extract it to
`app/auth/deps.py` so both modules import it) + `Depends(resolve_org)`.
- `GET/POST /contacts`, `GET/PATCH/DELETE /contacts/{id}`
- `GET /contacts/{id}/timeline` — merged `CallRecord` + `Activity` + `Deal` events, newest first
- `GET/POST /companies`, `GET/PATCH/DELETE /companies/{id}`
- `GET/POST /deals`, `GET/PATCH/DELETE /deals/{id}`
- `GET /deals/board` — columns by `stage` with count + summed `amount`
- `PATCH /deals/{id}/move` — `{stage, board_order}` (drag-drop target)
- `GET/POST /activities`, `PATCH/DELETE /activities/{id}`, `POST /activities/{id}/complete`
- `GET /calls`, `GET /calls/{id}` (full transcript), `POST /calls/{id}/link-contact`
- `GET /analytics/overview` — see B5
- `GET /search?q=` — see B5
- `GET /org`, `GET /org/members`, `POST /org/members` (invite by email)

Mount in `main.py`: `app.include_router(crm_routes.router)`.

### B4. Call → CRM ingest — *why: the agent should populate the CRM automatically*

**`app/realtime/bus.py`:** `open_call()` gains `owner_email` / `org_id` params, stored
on the call dict.
**`app/main.py` `dial_call` + `livekit_token`:** pass the authenticated user's
`owner_email` and `resolve_org` id into `open_call`. For browser `/ws/call`, read them
from the `hello` message's email.

**`app/crm/ingest.py`** (new): `async def persist_call(call_id)` —
reads `bus.calls[call_id]`, `leads.get(call_id)`, related `BOOKINGS`/`CASES`; then in
one transaction:
1. upsert `Contact` by `phone` within the org (create if new, else touch `last_contacted_at`);
2. write `CallRecord` (id = call_id, transcript snapshot, outcome derived from
   booking/escalation/lead `next_step`);
3. `Activity(type="call", contact_id=…, call_id=…, subject=outcome)`;
4. if a booking was confirmed → `Deal` (stage `demo`, title from persona/company) or
   advance an existing open deal for that contact.
Idempotent (safe to call twice — upsert on `CallRecord.id`).

**Hook points:**
- `app/realtime/ws.py` — both `handle_call` and `handle_telnyx_media` `finally` blocks,
  right after `bus.close_call(call_id)`: `await persist_call(call_id)` (guarded, never
  breaks teardown).
- LiveKit path: add `POST /internal/calls/{id}/finalize` in `main.py` (shared-secret
  guarded, like the other `/internal/*`), called from
  `app/voice_agent/agent.py::_on_session_end` via `internal_client.py`.

### B5. Analytics + search — *why: the overview page and the ⌘K box need real data*

**`app/crm/analytics.py`** (new): `overview(session, org_id)` → aggregate queries:
contact count, open-deal count + summed pipeline `amount`, win rate
(`won / (won+lost)`), calls this week, bookings this week, open/overdue task counts,
deals-by-stage, and a 14-day `calls_per_day` series. Pure SQL aggregates, no Python loops.

**`app/crm/search.py`** (new): `search(session, org_id, q)` → `ILIKE` across
`Contact.full_name/email/phone`, `Company.name`, `Deal.title`; returns a small typed
union list for the top-bar search.

### B6. Keep-working / hardening notes
- Existing `/api/leads`, `/api/bookings`, `/api/escalations`, `/ws/dashboard` stay as
  the **live-call monitor** feed (used by the new "Live Calls" widget). Out of scope to
  migrate, but flag: they are currently unauthenticated and global — recommend a
  follow-up to org-scope them once leads move to `Contact`.
- No change to `run_turn`, the sales playbook, STT/TTS, or persona logic.

---

## Frontend

### F1. Infrastructure — *why: many new list/detail pages need auth + caching*

- **`package.json`:** add `swr` (list/detail caching + optimistic mutation) and
  `@hello-pangea/dnd` (deal board drag-drop). Everything else reuses what's installed
  (`motion`, `@phosphor-icons/react`, Tailwind v4).
- **`app/context/AuthContext.tsx`:** expose `token` (read from `localStorage`
  `callforge_token`) so the SWR fetcher can send `Authorization: Bearer`.
- **`lib/crm-types.ts`** (new): TS interfaces mirroring `app/crm/schemas.py`.
- **`lib/crm.ts`** (new): `crmFetch(path, init)` — always attaches the bearer token,
  throws typed errors (mirror `parseAuthError` in `lib/api.ts`); typed functions per
  resource (`listContacts`, `getContact`, `patchDeal`, `moveDeal`, `analyticsOverview`, …).
- **`app/dashboard/_hooks/useCrm.ts`** (new): thin SWR wrappers (`useContacts(params)`,
  `useContact(id)`, `useDealBoard()`, `useAnalytics()`, …) with a shared mutate helper.

### F2. Shared UI primitives — *why: don't rebuild the same table/panel 6×*

New `app/dashboard/_components/`, extracted from patterns already in
`app/dashboard/page.tsx`:
- `DataTable.tsx` — generalize the sortable-header table in `LeadsTable` (sort state,
  `SORT_COLUMNS` pattern) + column defs, row click, loading skeleton.
- `SlideOver.tsx` — right-side form panel (create/edit), `motion/react` slide like the
  mobile drawer in `DashboardShell.tsx`.
- `EmptyState.tsx`, `StageBadge.tsx` (from `ScoreBadge`/`SCORE_META`), `Pagination.tsx`,
  `KpiCard.tsx` (from `StatCard`), `Timeline.tsx` (from `ActivityFeed`),
  `MiniChart.tsx` (hand-rolled SVG bars — no chart lib).
- Reuse existing tokens/utilities: `PANEL` class, `#057676`/`#0D2136`, `card-ring`,
  `initials()`, `timeAgo()`, phosphor icons.

### F3. Navigation — *why: the shell is built for one scroll page*

**`app/dashboard/DashboardShell.tsx` `buildNavGroups`:** replace scroll-`target`
entries with real `href` routes. Groups:
- **CRM:** Overview `/dashboard`, Contacts, Companies, Deals, Calls, Tasks
- **Voice:** Dialer, Test a Call, Personas *(unchanged pages)*
- **Monitor:** Live Calls, Escalations
Wire the existing ⌘K search input → `/api/crm/search` (debounced, results dropdown).
Wire the Bell badge → open Tasks (overdue) / Escalations.

### F4. Pages

| Route | What | Why |
|---|---|---|
| `/dashboard` *(rebuild `page.tsx`)* | KPI cards + deals-by-stage + calls/day `MiniChart` + recent calls + my open tasks, from `/api/crm/analytics/overview`. Keep the live-calls panel (`/ws/dashboard`). | The current overview shows only auto-leads; a CRM opens on pipeline health. |
| `/dashboard/contacts` | `DataTable`: search, filter (stage/owner), sort, pagination. "New contact" `SlideOver`. Row → detail. | The core CRM object; nothing today lets you list or add a person. |
| `/dashboard/contacts/[id]` | Header w/ inline edit, **Call** button → `/dashboard/dialer?persona_id=…&to=<phone>`, `Timeline` (calls w/ transcript modal, activities, deals, notes), add-note / add-task inline. | The single-pane-of-glass follow-up view — the reason to have a CRM. |
| `/dashboard/companies` + `/[id]` | Company table + detail (its contacts, deals, activity). | Account-level rollup for B2B pipelines. |
| `/dashboard/deals` | Kanban board by `stage` (`@hello-pangea/dnd`), column totals, drag → `PATCH /deals/{id}/move`; list-view toggle; "New deal" `SlideOver`. | The pipeline is the heart of a sales CRM; drag-drop stage changes are the expected interaction. |
| `/dashboard/calls` + `/[id]` | Call-history table (persona, contact, outcome, duration, date) → transcript viewer. | Calls currently vanish on restart; this is the agent's paper trail. |
| `/dashboard/activities` | "My tasks": open / overdue / completed, quick-complete. | Follow-ups need a worklist, not just per-contact scatter. |
| `/dashboard/settings` | Org name, members list, invite teammate by email; your profile. | Makes the team/org model visible and usable. |

### F5. Click-to-call loop — *why: close the CRM ↔ voice-agent loop*

`/dashboard/dialer/page.tsx` already reads `persona_id` from the query — add a `to`
param that prefills the number field. Contact detail's **Call** button links there.
When the call ends, B4's `persist_call` attaches the `CallRecord` + `Activity` back to
that contact automatically (phone match), so it appears on the timeline with no manual
step.

### F6. Trim the old data hook
`app/dashboard/useDashboardData.ts` — keep the `/ws/dashboard` live-call sync (used by
the Live Calls widget); drop the `leads`/`bookings`/`escalations` polling from the
overview (moved to `/api/crm/analytics/overview`). Escalations page keeps its own fetch.

---

## Rollout order

1. **B1** DB foundation (deps, `db` service, `app/db`, models, Alembic, startup, health).
2. **B2** org resolution + `app/auth/deps.py` extraction.
3. **B3** repository + schemas + routes (contacts, companies, deals, activities, org).
4. **B5** analytics + search endpoints.
5. **B4** call ingest + hooks (`ws.py`, `/internal/calls/{id}/finalize`, agent).
6. **F1–F3** frontend infra, shared components, nav.
7. **F4** pages — contacts (list+detail) → deals board → calls → companies → tasks → settings.
8. **F4** overview rebuild + **F5** click-to-call.
9. **Tests, seed script, docs.**

Each backend step is independently testable via `curl`/pytest before any frontend work.

---

## Key files

**Backend — new:** `app/db/__init__.py`, `app/db/models.py`;
`app/crm/{__init__,orgs,repository,schemas,routes,analytics,search,ingest,seed}.py`;
`app/auth/deps.py`; `alembic.ini`, `alembic/env.py`, `alembic/versions/0001_init_crm.py`;
`tests/{conftest,test_crm_repository,test_crm_ingest,test_crm_analytics}.py`.

**Backend — modified:** `requirements.txt`, `docker-compose.yml`, `.env.example`,
`app/config.py`, `app/main.py` (router mount, startup, `/health`, dial passes org,
`/internal/calls/{id}/finalize`), `app/realtime/ws.py` (ingest hook),
`app/realtime/bus.py` (`open_call` org params), `app/voice_agent/agent.py` +
`app/voice_agent/internal_client.py` (finalize on session end).

**Frontend — new:** `app/dashboard/{contacts,companies,deals,calls,activities,settings}/`
pages (+ `[id]` where noted); `app/dashboard/_components/*`;
`app/dashboard/_hooks/useCrm.ts`; `lib/crm.ts`, `lib/crm-types.ts`.

**Frontend — modified:** `package.json` (+`swr`, +`@hello-pangea/dnd`),
`app/context/AuthContext.tsx` (expose `token`), `app/dashboard/DashboardShell.tsx`
(nav routes + search), `app/dashboard/page.tsx` (rebuild), `app/dashboard/useDashboardData.ts`
(trim), `app/dashboard/dialer/page.tsx` (`to` param).

**Reused as-is:** `_current_user` dependency, `bus`/`/ws/dashboard`, `run_turn` and the
whole voice pipeline, persona CRUD, `lib/api.ts` auth helpers, Tailwind tokens in
`globals.css`, `motion/react` + phosphor patterns from `page.tsx`.

---

## Verification

**DB / infra**
- `docker compose up` → `db` healthy, backend migrates, `GET /health` returns
  `database_configured: true` + `db_ok: true`.
- `alembic upgrade head` then `alembic downgrade base` both run clean.

**Org scoping**
- Sign up user A (company "Acme") and user B (same company) → both resolve to one org,
  A's contacts visible to B.
- User C (company "Other") → `GET /api/crm/contacts/{A's id}` returns 404.

**CRM CRUD + persistence**
- Create a company, a contact, a deal via the UI; drag the deal `new → demo`;
  `docker compose restart backend`; deal is still in `demo` (proves persistence — the
  original problem).
- `POST /api/crm/org/members` with a teammate email → they see the shared board on login.

**Call ingest (the automated loop)**
- With `TTS_ENGINE=elevenlabs` + Telnyx configured (or the mock browser `/ws/call`
  path), place a call to a number. After hangup:
  - `/dashboard/calls` shows a `CallRecord` with the full transcript;
  - a `Contact` was auto-created (or matched) by that phone number;
  - its timeline shows an `Activity(type=call)`;
  - if the agent confirmed a booking, a `Deal` exists for that contact.
- Call the same number again → same contact, second call on the timeline (idempotent, no dup contact).

**Analytics / search**
- `/dashboard` KPIs match hand-counted rows; `calls_per_day` has 14 buckets.
- ⌘K "acme" returns the contact, the company, and any deal titled with it.

**Automated**
- `pytest packages/backend/tests` — repository CRUD, cross-org 404, `persist_call`
  (new contact / matched contact / booking→deal / double-call idempotency),
  analytics aggregation on a seeded org.

**Frontend**
- `npm run build` clean (no type errors).
- Manual click-through: every nav route loads, `SlideOver` create/edit round-trips,
  deal drag persists, transcript modal opens, contact "Call" opens the dialer prefilled.
