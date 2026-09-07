"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  fetchBookings,
  fetchEscalations,
  fetchLeads,
  fetchLeadStats,
  fetchPersonas,
  createDashboardWS,
  type Booking,
  type CallState,
  type EscalationCase,
  type Lead,
  type LeadStats,
  type PersonaPayload,
} from "../../lib/api";

export interface DashboardData {
  leads: Lead[];
  stats: LeadStats | null;
  bookings: Booking[];
  escalations: EscalationCase[];
  personas: PersonaPayload[];
  liveCalls: CallState[];
  loading: boolean;
  error: string | null;
  wsConnected: boolean;
  refresh: () => void;
}

const POLL_MS = 15_000;
const WS_RETRY_MS = 3_000;

/** Fetches real leads/bookings/escalations/personas from the backend and
 * keeps a live call list in sync over /ws/dashboard. Shared by the shell
 * (sidebar counts) and the overview page (everything else) so both read
 * from the same source instead of drifting. */
export function useDashboardData(): DashboardData {
  const [leads, setLeads] = useState<Lead[]>([]);
  const [stats, setStats] = useState<LeadStats | null>(null);
  const [bookings, setBookings] = useState<Booking[]>([]);
  const [escalations, setEscalations] = useState<EscalationCase[]>([]);
  const [personas, setPersonas] = useState<PersonaPayload[]>([]);
  const [liveCalls, setLiveCalls] = useState<CallState[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [wsConnected, setWsConnected] = useState(false);

  const load = useCallback(async () => {
    try {
      const [l, s, b, e, p] = await Promise.all([
        fetchLeads(),
        fetchLeadStats(),
        fetchBookings(),
        fetchEscalations(),
        fetchPersonas(),
      ]);
      setLeads(l);
      setStats(s);
      setBookings(b);
      setEscalations(e);
      setPersonas(p);
      setError(null);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Couldn't reach the CallForge backend. Is it running?",
      );
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
    const interval = setInterval(load, POLL_MS);
    return () => clearInterval(interval);
  }, [load]);

  // Live call feed over /ws/dashboard, with basic reconnect.
  const cancelledRef = useRef(false);
  useEffect(() => {
    cancelledRef.current = false;
    let ws: WebSocket | null = null;
    let retryTimer: ReturnType<typeof setTimeout> | null = null;

    const connect = () => {
      if (cancelledRef.current) return;
      try {
        ws = createDashboardWS();
      } catch {
        retryTimer = setTimeout(connect, WS_RETRY_MS);
        return;
      }

      ws.onopen = () => {
        if (!cancelledRef.current) setWsConnected(true);
      };

      ws.onmessage = (evt) => {
        let msg: { type?: string; calls?: CallState[]; call?: CallState };
        try {
          msg = JSON.parse(evt.data);
        } catch {
          return;
        }
        if (msg.type === "snapshot" && msg.calls) {
          setLiveCalls(msg.calls);
        } else if (msg.type === "call_update" && msg.call) {
          const updated = msg.call;
          setLiveCalls((prev) => {
            const idx = prev.findIndex((c) => c.id === updated.id);
            if (idx === -1) return [updated, ...prev];
            const next = [...prev];
            next[idx] = updated;
            return next;
          });
        }
      };

      const scheduleRetry = () => {
        if (cancelledRef.current) return;
        setWsConnected(false);
        retryTimer = setTimeout(connect, WS_RETRY_MS);
      };
      ws.onclose = scheduleRetry;
      ws.onerror = scheduleRetry;
    };

    connect();
    return () => {
      cancelledRef.current = true;
      if (retryTimer) clearTimeout(retryTimer);
      ws?.close();
    };
  }, []);

  return {
    leads,
    stats,
    bookings,
    escalations,
    personas,
    liveCalls,
    loading,
    error,
    wsConnected,
    refresh: load,
  };
}
