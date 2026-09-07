"use client";

import {
  createContext,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";
import {
  apiLogout,
  fetchMe,
  login as apiLogin,
  signup as apiSignup,
  SessionError,
  type ApiUser,
} from "../../lib/api";

/* ── Types ────────────────────────────────────────── */
export type User = ApiUser;

interface AuthContextValue {
  user: User | null;
  /** The bearer token for the current session, or null. Read by the CRM
   * API client (lib/crm.ts) so every CRM request is authenticated. */
  token: string | null;
  isAuthenticated: boolean;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  signup: (
    email: string,
    password: string,
    name: string,
    company: string,
  ) => Promise<void>;
  /** Adopts a session token already issued by the backend -- used by the
   * /auth/callback page after a Google/GitHub OAuth redirect, where the
   * token arrives via the URL instead of a login()/signup() call. */
  loginWithToken: (token: string) => Promise<void>;
  logout: () => void;
}

/* ── Constants ────────────────────────────────────── */
const TOKEN_KEY = "callforge_token";
const USER_KEY = "callforge_user";

function readStoredUser(): User | null {
  try {
    const raw = localStorage.getItem(USER_KEY);
    return raw ? (JSON.parse(raw) as User) : null;
  } catch {
    return null;
  }
}

/* ── Context ──────────────────────────────────────── */
const AuthContext = createContext<AuthContextValue | undefined>(undefined);

/* ── Provider ─────────────────────────────────────── */
export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  // On mount: hydrate optimistically from the last-known user so a returning
  // visitor isn't bounced to /login, then verify the token in the background.
  // Sessions live in the backend's in-memory store, so we only drop the
  // session on an explicit 401 -- a network error or a cold-starting backend
  // (status 0 / 5xx) must NOT log the user out.
  useEffect(() => {
    const stored = localStorage.getItem(TOKEN_KEY);
    if (!stored) {
      setLoading(false);
      return;
    }

    const cachedUser = readStoredUser();
    if (cachedUser) {
      setUser(cachedUser);
      setToken(stored);
    }
    setLoading(false);

    fetchMe(stored)
      .then((u) => {
        setUser(u);
        setToken(stored);
        localStorage.setItem(USER_KEY, JSON.stringify(u));
      })
      .catch((err: unknown) => {
        if (err instanceof SessionError && err.status === 401) {
          localStorage.removeItem(TOKEN_KEY);
          localStorage.removeItem(USER_KEY);
          setUser(null);
          setToken(null);
        }
        // transient error: keep the cached session as-is
      });
  }, []);

  const persist = (nextToken: string, u: User) => {
    localStorage.setItem(TOKEN_KEY, nextToken);
    localStorage.setItem(USER_KEY, JSON.stringify(u));
    setToken(nextToken);
    setUser(u);
  };

  const login = async (email: string, password: string) => {
    const { token, user: u } = await apiLogin(email, password);
    persist(token, u);
  };

  const signup = async (
    email: string,
    password: string,
    name: string,
    company: string,
  ) => {
    const { token, user: u } = await apiSignup(email, password, name, company);
    persist(token, u);
  };

  const loginWithToken = async (token: string) => {
    const u = await fetchMe(token);
    persist(token, u);
  };

  const logout = () => {
    const stored = localStorage.getItem(TOKEN_KEY);
    if (stored) void apiLogout(stored);
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
    setToken(null);
    setUser(null);
    // hard navigation home -- guarantees a clean, obvious sign-out with the
    // browser's own loading indicator, and no SPA redirect race
    if (typeof window !== "undefined") window.location.assign("/");
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        token,
        isAuthenticated: !!user,
        loading,
        login,
        signup,
        loginWithToken,
        logout,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

/* ── Hook ─────────────────────────────────────────── */
export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside <AuthProvider>");
  return ctx;
}
