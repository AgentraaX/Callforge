/* CRM API client. Every call is authenticated -- the CRM backend scopes all
   reads/writes to the caller's org. Mirrors backend/app/crm/routes.py.

   Follows the same token-from-localStorage pattern as lib/api.ts's
   authHeaders() so it works outside React too. */
import type {
  Activity,
  ActivityType,
  AnalyticsOverview,
  CallDetail,
  CallRecord,
  Company,
  Contact,
  Deal,
  DealBoard,
  DealStage,
  Lifecycle,
  Member,
  Org,
  Page,
  SearchResults,
  Timeline,
} from "./crm-types";

const API_URL = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000").replace(/\/+$/, "");
const TOKEN_KEY = "callforge_token";

export class CrmError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

function token(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(TOKEN_KEY);
}

async function crmFetch<T>(path: string, init: RequestInit = {}): Promise<T> {
  const t = token();
  const res = await fetch(`${API_URL}/api/crm${path}`, {
    ...init,
    headers: {
      ...(init.body ? { "Content-Type": "application/json" } : {}),
      ...(t ? { Authorization: `Bearer ${t}` } : {}),
      ...(init.headers || {}),
    },
  });
  if (res.status === 204) return undefined as T;
  const text = await res.text();
  const body = text ? JSON.parse(text) : null;
  if (!res.ok) {
    const detail =
      body && typeof body.detail === "string"
        ? body.detail
        : `Request failed (${res.status})`;
    throw new CrmError(detail, res.status);
  }
  return body as T;
}

function qs(params: object): string {
  const p = new URLSearchParams();
  for (const [k, v] of Object.entries(params as Record<string, unknown>)) {
    if (v !== null && v !== undefined && v !== "") p.set(k, String(v));
  }
  const s = p.toString();
  return s ? `?${s}` : "";
}

/* ── Contacts ─────────────────────────────────────────────────────── */

export interface ContactQuery {
  limit?: number;
  offset?: number;
  order_by?: string;
  lifecycle_stage?: Lifecycle;
  company_id?: string;
  owner_email?: string;
  q?: string;
}

export const listContacts = (query: ContactQuery = {}) =>
  crmFetch<Page<Contact>>(`/contacts${qs(query)}`);

export const getContact = (id: string) => crmFetch<Contact>(`/contacts/${id}`);

export const createContact = (data: Partial<Contact>) =>
  crmFetch<Contact>(`/contacts`, { method: "POST", body: JSON.stringify(data) });

export const updateContact = (id: string, data: Partial<Contact>) =>
  crmFetch<Contact>(`/contacts/${id}`, { method: "PATCH", body: JSON.stringify(data) });

export const deleteContact = (id: string) =>
  crmFetch<void>(`/contacts/${id}`, { method: "DELETE" });

export const contactTimeline = (id: string) =>
  crmFetch<Timeline>(`/contacts/${id}/timeline`);

/* ── Companies ────────────────────────────────────────────────────── */

export const listCompanies = (query: { limit?: number; offset?: number; q?: string } = {}) =>
  crmFetch<Page<Company>>(`/companies${qs(query)}`);

export const getCompany = (id: string) => crmFetch<Company>(`/companies/${id}`);

export const createCompany = (data: Partial<Company>) =>
  crmFetch<Company>(`/companies`, { method: "POST", body: JSON.stringify(data) });

export const updateCompany = (id: string, data: Partial<Company>) =>
  crmFetch<Company>(`/companies/${id}`, { method: "PATCH", body: JSON.stringify(data) });

export const deleteCompany = (id: string) =>
  crmFetch<void>(`/companies/${id}`, { method: "DELETE" });

/* ── Deals ────────────────────────────────────────────────────────── */

export const listDeals = (
  query: { limit?: number; offset?: number; stage?: DealStage; contact_id?: string } = {},
) => crmFetch<Page<Deal>>(`/deals${qs(query)}`);

export const dealBoard = () => crmFetch<DealBoard>(`/deals/board`);

export const getDeal = (id: string) => crmFetch<Deal>(`/deals/${id}`);

export const createDeal = (data: Partial<Deal>) =>
  crmFetch<Deal>(`/deals`, { method: "POST", body: JSON.stringify(data) });

export const updateDeal = (id: string, data: Partial<Deal>) =>
  crmFetch<Deal>(`/deals/${id}`, { method: "PATCH", body: JSON.stringify(data) });

export const moveDeal = (
  id: string,
  data: { stage: DealStage; board_order?: number; lost_reason?: string },
) => crmFetch<Deal>(`/deals/${id}/move`, { method: "PATCH", body: JSON.stringify(data) });

export const deleteDeal = (id: string) =>
  crmFetch<void>(`/deals/${id}`, { method: "DELETE" });

/* ── Activities / tasks ───────────────────────────────────────────── */

export interface ActivityQuery {
  limit?: number;
  offset?: number;
  order_by?: string;
  type?: ActivityType;
  contact_id?: string;
  deal_id?: string;
  status?: "open" | "completed" | "overdue";
}

export const listActivities = (query: ActivityQuery = {}) =>
  crmFetch<Page<Activity>>(`/activities${qs(query)}`);

export const createActivity = (data: Partial<Activity>) =>
  crmFetch<Activity>(`/activities`, { method: "POST", body: JSON.stringify(data) });

export const updateActivity = (id: string, data: Partial<Activity>) =>
  crmFetch<Activity>(`/activities/${id}`, { method: "PATCH", body: JSON.stringify(data) });

export const completeActivity = (id: string) =>
  crmFetch<Activity>(`/activities/${id}/complete`, { method: "POST" });

export const deleteActivity = (id: string) =>
  crmFetch<void>(`/activities/${id}`, { method: "DELETE" });

/* ── Calls ────────────────────────────────────────────────────────── */

export const listCalls = (
  query: {
    limit?: number;
    offset?: number;
    order_by?: string;
    outcome?: string;
    contact_id?: string;
  } = {},
) => crmFetch<Page<CallRecord>>(`/calls${qs(query)}`);

export const getCall = (id: string) => crmFetch<CallDetail>(`/calls/${id}`);

export const linkCallContact = (id: string, contact_id: string) =>
  crmFetch<CallDetail>(`/calls/${id}/link-contact`, {
    method: "POST",
    body: JSON.stringify({ contact_id }),
  });

/* ── Analytics + search ───────────────────────────────────────────── */

export const analyticsOverview = () => crmFetch<AnalyticsOverview>(`/analytics/overview`);

export const search = (q: string) => crmFetch<SearchResults>(`/search${qs({ q })}`);

/* ── Org ──────────────────────────────────────────────────────────── */

export const getOrg = () => crmFetch<Org>(`/org`);

export const updateOrg = (name: string) =>
  crmFetch<Org>(`/org`, { method: "PATCH", body: JSON.stringify({ name }) });

export const listMembers = () => crmFetch<Member[]>(`/org/members`);

export const inviteMember = (email: string, role: "owner" | "member" = "member") =>
  crmFetch<Member>(`/org/members`, { method: "POST", body: JSON.stringify({ email, role }) });
