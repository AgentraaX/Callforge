"use client";

import { useEffect, useState, type FormEvent } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { motion } from "motion/react";
import { useAuth } from "../context/AuthContext";
import { oauthStartUrl } from "../../lib/api";
import {
  ArrowRight,
  CircleNotch,
  Envelope,
  GithubLogo,
  LockKey,
  PhoneCall,
  ShieldCheck,
  WarningCircle,
} from "@phosphor-icons/react";
import { AuthMarketingPanel, GoogleMark, Logo, PwToggle } from "../components/AuthChrome";

export const dynamic = "force-dynamic";

const isValidEmail = (v: string) => /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(v);

const inputCls =
  "h-11 w-full rounded-lg bg-[rgba(255,255,255,0.04)] pl-10 pr-3.5 text-[14px] text-[var(--color-ink)] outline-none ring-1 ring-[rgba(255,255,255,0.14)] transition-all placeholder:text-[var(--color-slate)]/45 hover:ring-[rgba(255,255,255,0.2)] focus:bg-[var(--color-card)] focus:ring-2 focus:ring-[var(--color-signal)]/45";

export default function LoginPage() {
  const router = useRouter();
  const { login, signup } = useAuth();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPw, setShowPw] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [socialLoading, setSocialLoading] = useState<"google" | "github" | null>(null);

  /* One-tap demo access (SSO link) -- signs up on first use, falls back to
     logging in once the demo account already exists. */
  const runDemo = async () => {
    try {
      await signup("demo@callforge.ai", "demo1234", "Demo User", "CallForge Demo");
    } catch {
      await login("demo@callforge.ai", "demo1234");
    }
    router.push("/dashboard");
  };

  // Reads the ?error=/?provider= the backend appends after a failed or
  // unconfigured Google/GitHub OAuth attempt (it redirects back here).
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const oauthError = params.get("error");
    const provider = params.get("provider");
    const providerLabel = provider === "google" ? "Google" : provider === "github" ? "GitHub" : "That provider";
    if (oauthError === "oauth_not_configured") {
      setError(`${providerLabel} sign-in isn't set up yet. Try the demo access below instead.`);
    } else if (oauthError === "oauth_failed") {
      setError(`${providerLabel} sign-in didn't complete. Please try again.`);
    }
  }, []);

  const handleSocial = (provider: "google" | "github") => {
    setError("");
    setNotice("");
    setSocialLoading(provider);
    window.location.href = oauthStartUrl(provider);
  };

  const handleSso = async () => {
    setError("");
    setNotice("");
    try {
      await runDemo();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong. Please try again.");
    }
  };

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError("");
    setNotice("");

    if (!email.trim()) return setError("Email is required.");
    if (!isValidEmail(email)) return setError("Please enter a valid email address.");
    if (!password) return setError("Password is required.");

    setSubmitting(true);
    try {
      await login(email, password);
      router.push("/dashboard");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong. Please try again.");
    } finally {
      setSubmitting(false);
    }
  };

  const busy = submitting || socialLoading !== null;
  const socialBtnCls =
    "flex h-11 items-center justify-center gap-2.5 rounded-lg text-[13.5px] font-semibold text-[var(--color-ink)] ring-1 ring-[rgba(255,255,255,0.16)] transition-colors hover:bg-[rgba(255,255,255,0.04)] disabled:pointer-events-none disabled:opacity-50";

  return (
    <div className="flex min-h-screen bg-[var(--color-card)]">
      {/* ── Form panel ─────────────────────────────────── */}
      <div className="flex w-full flex-col justify-center px-6 py-12 sm:px-10 lg:w-[480px] lg:shrink-0 xl:w-[520px]">
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.35, ease: "easeOut" }}
          className="mx-auto w-full max-w-[380px]"
        >
          <Logo />

          <h1 className="mt-8 text-[26px] font-semibold tracking-[-0.01em] text-[var(--color-ink)]">
            Welcome back
          </h1>
          <p className="mt-2 text-[14px] leading-relaxed text-[var(--color-slate)]">
            Sign in to manage your AI voice agents.
          </p>

          <div className="mt-7 grid grid-cols-2 gap-3">
            <button type="button" onClick={() => handleSocial("google")} disabled={busy} className={socialBtnCls}>
              {socialLoading === "google" ? <CircleNotch size={16} className="animate-spin" /> : <GoogleMark />}
              Google
            </button>
            <button type="button" onClick={() => handleSocial("github")} disabled={busy} className={socialBtnCls}>
              {socialLoading === "github" ? (
                <CircleNotch size={16} className="animate-spin" />
              ) : (
                <GithubLogo size={16} weight="fill" />
              )}
              GitHub
            </button>
          </div>

          <div className="my-6 flex items-center gap-3">
            <span className="h-px flex-1 bg-[rgba(255,255,255,0.10)]" />
            <span className="text-[10.5px] font-semibold tracking-[0.14em] text-[var(--color-slate)]/60">OR EMAIL</span>
            <span className="h-px flex-1 bg-[rgba(255,255,255,0.10)]" />
          </div>

          {error && (
            <div className="mb-5 flex items-start gap-2.5 rounded-lg bg-red-50 px-3.5 py-2.5 text-[13px] leading-relaxed text-red-700 ring-1 ring-red-100">
              <WarningCircle size={15} weight="fill" className="mt-0.5 shrink-0" />
              {error}
            </div>
          )}
          {notice && (
            <div className="mb-5 rounded-lg bg-[var(--color-signal-tint)] px-3.5 py-2.5 text-[13px] leading-relaxed text-[var(--color-signal-hover)] ring-1 ring-[var(--color-signal-line)]">
              {notice}
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4" noValidate>
            <div>
              <label htmlFor="email" className="mb-1.5 block text-[12.5px] font-medium text-[var(--color-slate)]">
                Email
              </label>
              <div className="relative">
                <Envelope size={16} className="pointer-events-none absolute left-3.5 top-1/2 -translate-y-1/2 text-[var(--color-slate)]/50" />
                <input
                  id="email"
                  type="email"
                  autoComplete="email"
                  placeholder="you@company.com"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className={inputCls}
                />
              </div>
            </div>

            <div>
              <div className="mb-1.5 flex items-center justify-between">
                <label htmlFor="password" className="block text-[12.5px] font-medium text-[var(--color-slate)]">
                  Password
                </label>
                <button
                  type="button"
                  onClick={() => {
                    setError("");
                    setNotice("Password reset isn't wired up yet — try the demo access below instead.");
                  }}
                  className="text-[12px] font-medium text-[var(--color-slate)]/70 transition-colors hover:text-[var(--color-signal)]"
                >
                  Forgot?
                </button>
              </div>
              <div className="relative">
                <LockKey size={16} className="pointer-events-none absolute left-3.5 top-1/2 -translate-y-1/2 text-[var(--color-slate)]/50" />
                <input
                  id="password"
                  type={showPw ? "text" : "password"}
                  autoComplete="current-password"
                  placeholder="••••••••"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className={`${inputCls} pr-11`}
                />
                <PwToggle visible={showPw} onToggle={() => setShowPw((v) => !v)} />
              </div>
            </div>

            <button
              type="submit"
              disabled={busy}
              className="mt-1 flex h-11 w-full items-center justify-center gap-2 rounded-lg bg-[var(--color-signal)] text-[14px] font-semibold text-white transition-colors hover:bg-[var(--color-signal-hover)] disabled:pointer-events-none disabled:opacity-60"
            >
              {submitting ? (
                <>
                  <CircleNotch size={16} className="animate-spin" />
                  Signing in…
                </>
              ) : (
                <>
                  Sign in
                  <ArrowRight size={15} weight="bold" />
                </>
              )}
            </button>
          </form>

          <p className="mt-5 text-center">
            <button
              type="button"
              onClick={handleSso}
              disabled={busy}
              className="text-[13px] font-medium text-[var(--color-slate)] transition-colors hover:text-[var(--color-signal)] disabled:opacity-50"
            >
              Sign in with SSO instead
            </button>
          </p>

          <p className="mt-6 text-center text-[13px] text-[var(--color-slate)]">
            Don&apos;t have an account?{" "}
            <Link href="/signup" className="font-semibold text-[var(--color-signal)] hover:text-[var(--color-signal-hover)]">
              Sign up
            </Link>
          </p>
        </motion.div>

        <p className="mx-auto mt-10 max-w-[380px] text-center text-[11.5px] leading-relaxed text-[var(--color-slate)]/60">
          By using CallForge you agree to our Terms of Service, Privacy, and Security policies.
        </p>
      </div>

      {/* ── Marketing panel ────────────────────────────── */}
      <AuthMarketingPanel
        headline="Your AI sales team, on every call."
        subcopy="CallForge runs real cold-calling conversations under a persona you define — grounded in your own facts, never invented."
        features={[
          {
            icon: PhoneCall,
            title: "Real outbound calls",
            body: "Places live phone calls through Telnyx, straight from your own number.",
          },
          {
            icon: ShieldCheck,
            title: "Never invents facts",
            body: "Every claim it makes is grounded in the persona's own knowledge base.",
          },
        ]}
      />
    </div>
  );
}
