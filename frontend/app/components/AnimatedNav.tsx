"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { ArrowRight, List, X } from "@phosphor-icons/react";
import ScrollWaveform from "./ScrollWaveform";
import Logo from "./brand/Logo";
import ThemeButton from "./ui/ThemeButton";
import { LINKS } from "../../lib/site-metrics";
import { useAuth } from "../context/AuthContext";

const NAV_LINKS = [
  { href: "#how-it-works", id: "how-it-works", label: "How it works" },
  { href: "#features", id: "features", label: "Features" },
  { href: "#pricing", id: "pricing", label: "Pricing" },
];

export default function AnimatedNav() {
  const { isAuthenticated } = useAuth();
  const [scrolled, setScrolled] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [active, setActive] = useState<string | null>(null);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 20);
    window.addEventListener("scroll", onScroll, { passive: true });
    onScroll();
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  useEffect(() => {
    const sections = NAV_LINKS.map((l) => document.getElementById(l.id)).filter(
      (el): el is HTMLElement => el !== null,
    );
    if (sections.length === 0) return;
    const observer = new IntersectionObserver(
      (entries) => {
        const visible = entries
          .filter((e) => e.isIntersecting)
          .sort((a, b) => b.intersectionRatio - a.intersectionRatio)[0];
        if (visible) setActive(visible.target.id);
      },
      { rootMargin: "-45% 0px -50% 0px" },
    );
    sections.forEach((s) => observer.observe(s));
    return () => observer.disconnect();
  }, []);

  return (
    <nav
      className={`sticky top-0 z-50 transition-shadow duration-300 ${
        scrolled
          ? "nav-scrolled"
          : "border-b border-[var(--color-hairline)] bg-[rgba(15,30,61,0.7)] backdrop-blur-md"
      }`}
    >
      <div className="mx-auto flex h-14 max-w-[84rem] 2xl:max-w-[92rem] items-center justify-between px-5 sm:px-8">
        <Logo href="/" />

        <div className="hidden items-center gap-7 md:flex">
          {NAV_LINKS.map((link) => (
            <a
              key={link.href}
              href={link.href}
              aria-current={active === link.id ? "true" : undefined}
              className={`nav-link ${active === link.id ? "nav-link-active" : ""}`}
            >
              {link.label}
            </a>
          ))}
        </div>

        <div className="flex items-center gap-3">
          {isAuthenticated ? (
            <ThemeButton
              href={LINKS.dashboard}
              size="sm"
              iconRight={<ArrowRight size={13} weight="bold" />}
            >
              Go to dashboard
            </ThemeButton>
          ) : (
            <>
              <Link
                href={LINKS.login}
                className="hidden text-[13px] font-medium text-slate transition-colors hover:text-ink sm:block"
              >
                Log in
              </Link>
              <ThemeButton
                href={LINKS.signup}
                size="sm"
                className="hidden sm:inline-flex"
                iconRight={<ArrowRight size={13} weight="bold" />}
              >
                Start free
              </ThemeButton>
            </>
          )}
          <button
            onClick={() => setMobileOpen((o) => !o)}
            className="flex h-9 w-9 items-center justify-center rounded-lg text-slate hover:bg-paper-alt md:hidden"
            aria-label={mobileOpen ? "Close menu" : "Open menu"}
            aria-expanded={mobileOpen}
          >
            {mobileOpen ? <X size={20} weight="bold" /> : <List size={20} weight="bold" />}
          </button>
        </div>
      </div>

      {mobileOpen && (
        <div className="border-t border-[var(--color-hairline)] bg-paper md:hidden">
          <div className="space-y-1 px-5 py-4">
            {NAV_LINKS.map((link) => (
              <a
                key={link.href}
                href={link.href}
                className="block rounded-lg px-2 py-2 text-[14px] font-medium text-slate transition-colors hover:bg-paper-alt hover:text-ink"
                onClick={() => setMobileOpen(false)}
              >
                {link.label}
              </a>
            ))}
            <div className="flex gap-3 pt-3">
              {isAuthenticated ? (
                <ThemeButton
                  href={LINKS.dashboard}
                  fullWidth
                  iconRight={<ArrowRight size={13} weight="bold" />}
                >
                  Go to dashboard
                </ThemeButton>
              ) : (
                <>
                  <ThemeButton
                    href={LINKS.signup}
                    fullWidth
                    iconRight={<ArrowRight size={13} weight="bold" />}
                  >
                    Start free
                  </ThemeButton>
                  <ThemeButton href={LINKS.login} variant="secondary" fullWidth>
                    Log in
                  </ThemeButton>
                </>
              )}
            </div>
          </div>
        </div>
      )}

      <ScrollWaveform />
    </nav>
  );
}
