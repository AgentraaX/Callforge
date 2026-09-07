const API_URL = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000").replace(/\/+$/, "");
const TOKEN_KEY = "callforge_token";

function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(TOKEN_KEY);
}

function authHeaders(extra?: Record<string, string>): Record<string, string> {
  const token = getToken();
  return {
    ...(extra || {}),
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  };
}

/* Mirrors shared/types.ts, corrected against what the backend
   actually sends: created_at/updated_at are Python time.time() floats
   (epoch seconds) serialized straight to JSON numbers, not ISO strings --
   the shared contract's "string" annotation for these doesn't match
   reality, verified directly against a live backend response. */
export interface Lead {
  id: string;
  call_id: string;
  company: string | null;
  contact_name: string | null;
  contact_phone: string | null;
  pain_point: string | null;
  budget_signal: string | null;
  next_step: string | null;
  urgency: string;
  score: "hot" | "warm" | "cold";
  notes: string | null;
  created_at: number;
  updated_at: number;
}

export interface Booking {
  booking_id: string;
  call_id: string;
  lead_id: string | null;
  slot_label: string;
  purpose: string;
  contact_name: string;
  status: "confirmed" | "cancelled" | "completed";
  created_at: number;
}

export interface EscalationCase {
  case_id: string;
  call_id: string;
  reason: string;
  summary: string;
  caller_name: string;
  priority: "high" | "normal";
  status: "pending" | "assigned" | "resolved";
  created_at: number;
}

export interface PersonaPayload {
  id: string;
  name: string;
  role: string;
  title: string;
  company: string;
  product_pitch: string;
  personality: string;
  knowledge_text: string;
  opening_line: string;
  call_goal: string;
  elevenlabs_voice_id: string;
  default_emotion: string;
  language_mode: string;
  fallback_pitch: number;
  fallback_rate: number;
}

export interface PersonaInput {
  name: string;
  company: string;
  product_pitch: string;
  personality: string;
  knowledge_text: string;
  opening_line: string;
  call_goal: string;
  elevenlabs_voice_id: string;
  default_emotion: string;
  language_mode: string;
}

export interface LeadStats {
  hot: number;
  warm: number;
  cold: number;
  total: number;
}

export interface CallState {
  id: string;
  state: "ringing" | "greeting" | "listening" | "thinking" | "speaking" | "hold" | "transferring" | "live" | "paused" | "needs_human" | "end" | "ended";
  caller: string;
  agent: PersonaPayload | null;
  transcript: { who: string; name: string; text: string }[];
  lead: Lead | null;
  language: string;
  escalated: boolean;
  case_id: string | null;
  started_at: number;
}

export interface ApiUser {
  email: string;
  name: string;
  company: string;
}

export interface AuthResponse {
  token: string;
  user: ApiUser;
}

async function parseAuthError(res: Response): Promise<never> {
  let detail = "Something went wrong. Please try again.";
  try {
    const body = await res.json();
    if (typeof body.detail === "string") detail = body.detail;
  } catch {
    /* non-JSON error body -- keep default message */
  }
  throw new Error(detail);
}

export async function signup(
  email: string,
  password: string,
  name: string,
  company: string,
): Promise<AuthResponse> {
  const res = await fetch(`${API_URL}/api/auth/signup`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password, name, company }),
  });
  if (!res.ok) return parseAuthError(res);
  return res.json();
}

export async function login(email: string, password: string): Promise<AuthResponse> {
  const res = await fetch(`${API_URL}/api/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  if (!res.ok) return parseAuthError(res);
  return res.json();
}

/** Full-page redirect target for Google/GitHub sign-in -- navigate with
 * window.location.href, never fetch() this (it's a browser redirect flow
 * that ends on the provider's own consent screen). */
export function oauthStartUrl(provider: "google" | "github"): string {
  return `${API_URL}/api/auth/oauth/${provider}/start`;
}

/** Thrown by fetchMe. `status` is the HTTP status, or 0 for a network failure
 * (offline, CORS, backend cold-starting). Only status 401 means the session is
 * genuinely invalid — everything else is a transient error the caller should
 * not treat as a logout. */
export class SessionError extends Error {
  status: number;
  constructor(status: number) {
    super(status === 401 ? "Session expired" : "Could not verify session");
    this.name = "SessionError";
    this.status = status;
  }
}

export async function fetchMe(token: string): Promise<ApiUser> {
  let res: Response;
  try {
    res = await fetch(`${API_URL}/api/auth/me`, {
      headers: { Authorization: `Bearer ${token}` },
    });
  } catch {
    throw new SessionError(0);
  }
  if (!res.ok) throw new SessionError(res.status);
  return res.json();
}

export async function apiLogout(token: string): Promise<void> {
  await fetch(`${API_URL}/api/auth/logout`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
  }).catch(() => {
    /* best-effort -- local session clears regardless */
  });
}

export async function fetchLeads(): Promise<Lead[]> {
  const res = await fetch(`${API_URL}/api/leads`);
  if (!res.ok) throw new Error("Failed to fetch leads");
  return (await res.json()).leads;
}

export async function fetchLeadStats(): Promise<LeadStats> {
  const res = await fetch(`${API_URL}/api/leads/stats`);
  if (!res.ok) throw new Error("Failed to fetch stats");
  return res.json();
}

export async function fetchBookings(): Promise<Booking[]> {
  const res = await fetch(`${API_URL}/api/bookings`);
  if (!res.ok) throw new Error("Failed to fetch bookings");
  return (await res.json()).bookings;
}

export async function fetchAvailableSlots() {
  const res = await fetch(`${API_URL}/api/bookings/available`);
  if (!res.ok) throw new Error("Failed to fetch slots");
  return (await res.json()).slots;
}

export async function fetchEscalations(): Promise<EscalationCase[]> {
  const res = await fetch(`${API_URL}/api/escalations`);
  if (!res.ok) throw new Error("Failed to fetch escalations");
  return (await res.json()).cases;
}

/* ── Personas (per-user, requires auth) ───────────────────────────── */

export async function fetchPersonas(): Promise<PersonaPayload[]> {
  const res = await fetch(`${API_URL}/api/personas`, { headers: authHeaders() });
  if (!res.ok) throw new Error("Failed to fetch personas");
  return (await res.json()).personas;
}

export async function createPersona(input: PersonaInput): Promise<PersonaPayload> {
  const res = await fetch(`${API_URL}/api/personas`, {
    method: "POST",
    headers: authHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify(input),
  });
  if (!res.ok) return parseAuthError(res);
  return res.json();
}

export async function updatePersona(id: string, input: PersonaInput): Promise<PersonaPayload> {
  const res = await fetch(`${API_URL}/api/personas/${id}`, {
    method: "PUT",
    headers: authHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify(input),
  });
  if (!res.ok) return parseAuthError(res);
  return res.json();
}

export async function deletePersona(id: string): Promise<void> {
  const res = await fetch(`${API_URL}/api/personas/${id}`, {
    method: "DELETE",
    headers: authHeaders(),
  });
  if (!res.ok) throw new Error("Failed to delete persona");
}

export async function previewPersonaVoice(
  id: string,
  language: "en" | "ur" = "en",
): Promise<{ audio: string; mime: string; text: string }> {
  const res = await fetch(`${API_URL}/api/personas/${id}/preview-voice?language=${language}`, {
    method: "POST",
    headers: authHeaders(),
  });
  if (!res.ok) return parseAuthError(res);
  return res.json();
}

export interface ElevenLabsVoice {
  voice_id: string;
  name: string;
  category: string | null;
  preview_url: string | null;
}

export async function fetchVoices(): Promise<ElevenLabsVoice[]> {
  const res = await fetch(`${API_URL}/api/voices`, { headers: authHeaders() });
  if (!res.ok) throw new Error("Failed to fetch voices");
  return (await res.json()).voices;
}

export async function cloneVoice(name: string, file: File): Promise<{ voice_id: string }> {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(`${API_URL}/api/voices/clone?name=${encodeURIComponent(name)}`, {
    method: "POST",
    headers: authHeaders(),
    body: form,
  });
  if (!res.ok) return parseAuthError(res);
  return res.json();
}

/* ── LiveKit (browser voice call -- real WebRTC) ──────────────────── */

export interface LiveKitTokenResponse {
  token: string;
  ws_url: string;
  call_id: string;
  room: string;
}

export async function getLiveKitToken(personaId: string): Promise<LiveKitTokenResponse> {
  const res = await fetch(`${API_URL}/api/livekit/token`, {
    method: "POST",
    headers: authHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify({ persona_id: personaId }),
  });
  if (!res.ok) return parseAuthError(res);
  return res.json();
}

/* ── Dialer (real outbound Telnyx calls) ──────────────────────────── */

export async function dialCall(toNumber: string, personaId: string): Promise<{ call_id: string }> {
  const res = await fetch(`${API_URL}/api/calls/dial`, {
    method: "POST",
    headers: authHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify({ to_number: toNumber, persona_id: personaId }),
  });
  if (!res.ok) return parseAuthError(res);
  return res.json();
}

export async function fetchHealth() {
  const res = await fetch(`${API_URL}/health`);
  if (!res.ok) throw new Error("Failed to fetch health");
  return res.json();
}

export function createDashboardWS(): WebSocket {
  const wsUrl = API_URL.replace(/^http/, "ws") + "/ws/dashboard";
  return new WebSocket(wsUrl);
}
