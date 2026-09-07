/* Mirrors backend/app/crm/schemas.py. Timestamps arrive as ISO
   strings (Pydantic serialises datetime that way -- unlike the epoch-float
   leads/bookings in lib/api.ts). */

export type Lifecycle = "lead" | "mql" | "sql" | "customer" | "churned";
export type DealStage =
  | "new"
  | "qualified"
  | "demo"
  | "proposal"
  | "negotiation"
  | "won"
  | "lost";
export type ActivityType = "note" | "task" | "call" | "email" | "meeting";
export type CallOutcome = "booked" | "callback" | "declined" | "escalated" | "none";

export const DEAL_STAGES: DealStage[] = [
  "new",
  "qualified",
  "demo",
  "proposal",
  "negotiation",
  "won",
  "lost",
];
export const OPEN_DEAL_STAGES: DealStage[] = [
  "new",
  "qualified",
  "demo",
  "proposal",
  "negotiation",
];
export const LIFECYCLES: Lifecycle[] = ["lead", "mql", "sql", "customer", "churned"];

export interface Page<T> {
  items: T[];
  total: number;
  limit: number;
  offset: number;
}

export interface Company {
  id: string;
  name: string;
  domain: string | null;
  industry: string | null;
  size: string | null;
  website: string | null;
  phone: string | null;
  notes: string | null;
  owner_email: string;
  created_at: string;
  updated_at: string;
}

export interface Contact {
  id: string;
  first_name: string | null;
  last_name: string | null;
  full_name: string;
  email: string | null;
  phone: string | null;
  title: string | null;
  company_id: string | null;
  lifecycle_stage: Lifecycle;
  source: string | null;
  do_not_call: boolean;
  tags: string[];
  last_contacted_at: string | null;
  owner_email: string;
  created_at: string;
  updated_at: string;
}

export interface Deal {
  id: string;
  title: string;
  contact_id: string | null;
  company_id: string | null;
  stage: DealStage;
  amount: number | null;
  currency: string;
  expected_close_date: string | null;
  probability: number | null;
  lost_reason: string | null;
  closed_at: string | null;
  board_order: number;
  owner_email: string;
  created_at: string;
  updated_at: string;
}

export interface BoardColumn {
  stage: DealStage;
  count: number;
  total_amount: number;
  deals: Deal[];
}

export interface DealBoard {
  columns: BoardColumn[];
}

export interface Activity {
  id: string;
  type: ActivityType;
  subject: string;
  body: string | null;
  due_at: string | null;
  completed_at: string | null;
  contact_id: string | null;
  deal_id: string | null;
  call_id: string | null;
  author_email: string;
  owner_email: string;
  created_at: string;
  updated_at: string;
}

export interface TranscriptLine {
  who: string;
  name: string;
  text: string;
}

export interface CallRecord {
  id: string;
  persona_id: string | null;
  persona_name: string | null;
  direction: string;
  from_number: string | null;
  to_number: string | null;
  contact_id: string | null;
  status: string;
  outcome: CallOutcome;
  started_at: string | null;
  ended_at: string | null;
  duration_s: number;
  language: string;
  escalated: boolean;
  case_id: string | null;
  recording_url: string | null;
  owner_email: string;
  created_at: string;
}

export interface CallDetail extends CallRecord {
  transcript: TranscriptLine[];
  lead_snapshot: Record<string, unknown> | null;
}

export interface TimelineItem {
  kind: "call" | "activity" | "deal";
  id: string;
  at: string;
  title: string;
  subtitle: string | null;
  meta: Record<string, unknown>;
}

export interface Timeline {
  items: TimelineItem[];
}

export interface Org {
  id: string;
  name: string;
  created_at: string;
}

export interface Member {
  email: string;
  role: "owner" | "member";
  created_at: string;
}

export interface StageCount {
  stage: DealStage;
  count: number;
  total_amount: number;
}

export interface DayCount {
  date: string;
  count: number;
}

export interface AnalyticsOverview {
  contacts: number;
  open_deals: number;
  pipeline_value: number;
  won_this_month: number;
  win_rate: number;
  calls_this_week: number;
  bookings_this_week: number;
  open_tasks: number;
  overdue_tasks: number;
  deals_by_stage: StageCount[];
  calls_per_day: DayCount[];
}

export interface SearchHit {
  kind: "contact" | "company" | "deal";
  id: string;
  label: string;
  sublabel: string | null;
}

export interface SearchResults {
  hits: SearchHit[];
}
