"use client";

import type { ReactNode } from "react";
import { ArrowRight } from "@phosphor-icons/react";
import ThemeButton from "./ui/ThemeButton";
import { LINKS } from "../../lib/site-metrics";
import { useAuth } from "../context/AuthContext";

type Size = "sm" | "md" | "lg";

/* The main "Start free" CTA. When the visitor is already signed in it becomes
   "Go to dashboard" so the landing page never sends a logged-in user back
   through signup. */
export default function PrimaryCta({
  size = "lg",
  fullWidth,
  className = "",
  loggedOutLabel = "Start free",
}: {
  size?: Size;
  fullWidth?: boolean;
  className?: string;
  loggedOutLabel?: string;
}) {
  const { isAuthenticated } = useAuth();
  const label: ReactNode = isAuthenticated ? "Go to dashboard" : loggedOutLabel;
  const href = isAuthenticated ? LINKS.dashboard : LINKS.signup;

  return (
    <ThemeButton
      href={href}
      size={size}
      fullWidth={fullWidth}
      className={className}
      iconRight={<ArrowRight size={size === "sm" ? 13 : 15} weight="bold" />}
    >
      {label}
    </ThemeButton>
  );
}
