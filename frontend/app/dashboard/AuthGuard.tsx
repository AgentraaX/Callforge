"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "../context/AuthContext";

/* TEMP: set NEXT_PUBLIC_DASHBOARD_PREVIEW=1 in .env.local to view the dashboard
   without logging in (styling/QA only). Remove the flag before shipping. */
const PREVIEW = process.env.NEXT_PUBLIC_DASHBOARD_PREVIEW === "1";

function FullScreenSpinner({ label }: { label: string }) {
  return (
    <div className="flex min-h-screen items-center justify-center bg-[var(--color-paper)]">
      <div className="flex items-center gap-3 text-[var(--color-slate)]">
        <svg className="h-5 w-5 animate-spin text-[var(--color-signal)]" viewBox="0 0 24 24" fill="none">
          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3" />
          <path
            className="opacity-75"
            fill="currentColor"
            d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
          />
        </svg>
        <span className="text-[14px] font-medium">{label}</span>
      </div>
    </div>
  );
}

export default function AuthGuard({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, loading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (PREVIEW) return;
    if (!loading && !isAuthenticated) {
      router.replace("/login");
    }
  }, [loading, isAuthenticated, router]);

  if (PREVIEW) return <>{children}</>;
  if (loading) return <FullScreenSpinner label="Loading…" />;
  // signed out (or session dropped) -- show a spinner while we redirect,
  // never a blank screen
  if (!isAuthenticated) return <FullScreenSpinner label="Redirecting…" />;

  return <>{children}</>;
}
