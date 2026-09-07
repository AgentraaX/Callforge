/** Shared TypeScript types for CallForge frontend. */

export interface STTResult {
  text: string;
  language: string;
  confidence: number;
  is_code_switched: boolean;
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
  fallback_pitch: number;
  fallback_rate: number;
}

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
  created_at: string;
  updated_at: string;
}

export interface Booking {
  booking_id: string;
  call_id: string;
  lead_id: string | null;
  slot_label: string;
  purpose: string;
  contact_name: string;
  status: "confirmed" | "cancelled" | "completed";
  created_at: string;
}

export interface EscalationCase {
  case_id: string;
  call_id: string;
  reason: string;
  summary: string;
  caller_name: string;
  priority: "high" | "normal";
  status: "pending" | "assigned" | "resolved";
  created_at: string;
}

export interface CallState {
  id: string;
  state: "ringing" | "live" | "paused" | "transferring" | "needs_human" | "ended";
  caller: string;
  agent: PersonaPayload | null;
  transcript: { who: string; name: string; text: string }[];
  lead: Lead | null;
  escalated: boolean;
  started_at: string;
}

// WebSocket message types (client -> server)
export type ClientMessage =
  | { type: "hello"; user: { email: string; name: string }; caller_id?: string; persona_id?: string }
  | { type: "start" }
  | { type: "audio"; data: string; mime: string }
  | { type: "text"; text: string }
  | { type: "pause" }
  | { type: "resume" }
  | { type: "hangup" };

// WebSocket message types (server -> client)
export type ServerMessage =
  | { type: "call_meta"; call_id: string }
  | { type: "state"; value: string }
  | { type: "transcript"; who: string; name: string; text: string }
  | { type: "speak"; text: string; audio: string | null; mime: string; agent: PersonaPayload; append?: boolean }
  | { type: "hold"; ms: number; to: PersonaPayload }
  | { type: "turn_end" }
  | { type: "end"; call_id: string }
  | { type: "escalated"; case_id: string }
  | { type: "error"; message: string };
