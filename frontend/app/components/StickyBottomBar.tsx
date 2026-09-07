"use client";

import { useEffect, useState } from "react";
import ThemeButton from "./ui/ThemeButton";
import PrimaryCta from "./PrimaryCta";
import { COPY, LINKS } from "../../lib/site-metrics";
import { useAuth } from "../context/AuthContext";

export default function StickyBottomBar() {
  const { isAuthenticated } = useAuth();
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const onScroll = () => setVisible(window.scrollY > 600);
    window.addEventListener("scroll", onScroll, { passive: true });
    onScroll();
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  return (
    <div
      className={`fixed inset-x-0 bottom-0 z-50 transition-all duration-300 ${
        visible ? "translate-y-0 opacity-100" : "pointer-events-none translate-y-full opacity-0"
      }`}
    >
      <div className="border-t border-[var(--color-hairline)] bg-[rgba(15,30,61,0.9)] backdrop-blur-md">
        <div className="mx-auto flex max-w-[84rem] 2xl:max-w-[92rem] items-center justify-between gap-4 px-5 py-3 sm:px-8">
          <span className="hidden text-[13.5px] text-slate sm:block">
            {isAuthenticated ? "Your AI sales floor is ready." : COPY.finalCtaHeadline}
          </span>
          <div className="flex w-full items-center justify-center gap-3 sm:w-auto">
            <PrimaryCta size="sm" />
            {!isAuthenticated && (
              <ThemeButton href={LINKS.contactSales} variant="ghost" size="sm">
                {COPY.ctaSecondary}
              </ThemeButton>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
