"use client";

/* Minimal data-fetching hooks for the CRM pages -- no SWR, same hand-rolled
   pattern as useDashboardData.ts. useResource caches nothing across mounts;
   each page owns its data and calls reload() after a mutation. */
import { useCallback, useEffect, useRef, useState } from "react";
import { CrmError } from "../../../lib/crm";

interface ResourceState<T> {
  data: T | null;
  loading: boolean;
  error: string | null;
  reload: () => void;
}

export function useResource<T>(
  fetcher: () => Promise<T>,
  deps: ReadonlyArray<unknown> = [],
): ResourceState<T> {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [nonce, setNonce] = useState(0);

  // eslint-disable-next-line react-hooks/exhaustive-deps
  const fn = useCallback(fetcher, deps);
  const alive = useRef(true);

  useEffect(() => {
    alive.current = true;
    return () => {
      alive.current = false;
    };
  }, []);

  useEffect(() => {
    setLoading(true);
    fn()
      .then((d) => {
        if (alive.current) {
          setData(d);
          setError(null);
        }
      })
      .catch((e) => {
        if (alive.current) {
          setError(e instanceof CrmError || e instanceof Error ? e.message : "Something went wrong");
        }
      })
      .finally(() => {
        if (alive.current) setLoading(false);
      });
  }, [fn, nonce]);

  const reload = useCallback(() => setNonce((n) => n + 1), []);
  return { data, loading, error, reload };
}

export type MutationResult<T> = { ok: true; data: T } | { ok: false; error: string };

interface MutationState {
  /** Runs `op`, tracking pending/error. Returns a discriminated result so
   * callers can branch on success even when the op returns void. */
  run: <T>(op: () => Promise<T>) => Promise<MutationResult<T>>;
  pending: boolean;
  error: string | null;
  clearError: () => void;
}

export function useMutation(): MutationState {
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const run = useCallback(async <T,>(op: () => Promise<T>): Promise<MutationResult<T>> => {
    setPending(true);
    setError(null);
    try {
      const data = await op();
      return { ok: true, data };
    } catch (e) {
      const msg = e instanceof CrmError || e instanceof Error ? e.message : "Something went wrong";
      setError(msg);
      return { ok: false, error: msg };
    } finally {
      setPending(false);
    }
  }, []);

  return { run, pending, error, clearError: () => setError(null) };
}
