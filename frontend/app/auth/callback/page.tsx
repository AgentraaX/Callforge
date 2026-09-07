"use client";

import { Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { CircleNotch, WarningCircle } from "@phosphor-icons/react";
import { useAuth } from "../../context/AuthContext";

export const dynamic = "force-dynamic";

function CallbackInner() {
  const router = useRouter();
  const params = useSearchParams();
  const { loginWithToken } = useAuth();
  const [error, setError] = useState("");

  useEffect(() => {
    const token = params.get("token");
    if (!token) {
      setError("No session token was returned. Please try signing in again.");
      return;
    }
    loginWithToken(token)
      .then(() => router.replace("/dashboard"))
      .catch(() => setError("That session couldn't be verified. Please try signing in again."));
    // Only run once, on mount -- loginWithToken/router identity changing shouldn't re-trigger this.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  if (error) {
    return (
      <div className="flex flex-col items-center gap-3 text-center">
        <WarningCircle size={28} weight="fill" className="text-red-400" />
        <p className="max-w-xs text-[14px] leading-relaxed text-white/70">{error}</p>
        <button
          onClick={() => router.replace("/login")}
          className="mt-2 rounded-lg bg-[var(--color-signal)] px-4 py-2 text-[13px] font-semibold text-white transition-colors hover:bg-[var(--color-signal-hover)]"
        >
          Back to sign in
        </button>
      </div>
    );
  }

  return (
    <div className="flex flex-col items-center gap-3 text-center">
      <CircleNotch size={28} className="animate-spin text-[#2FBDBE]" />
      <p className="text-[14px] text-white/60">Signing you in…</p>
    </div>
  );
}

export default function AuthCallbackPage() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-[#0e0e13] px-6">
      <Suspense
        fallback={
          <div className="flex flex-col items-center gap-3 text-center">
            <CircleNotch size={28} className="animate-spin text-[#2FBDBE]" />
            <p className="text-[14px] text-white/60">Signing you in…</p>
          </div>
        }
      >
        <CallbackInner />
      </Suspense>
    </div>
  );
}
