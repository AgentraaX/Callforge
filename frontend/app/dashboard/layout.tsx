import type { Metadata } from "next";
import DashboardShell from "./DashboardShell";
import AuthGuard from "./AuthGuard";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Dashboard",
  description:
    "Your CallForge CRM — contacts, pipeline, tasks, and every call the voice agent has run.",
};

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div
      className="antialiased"
      style={{
        fontFamily:
          "var(--font-inter, ui-sans-serif, system-ui, sans-serif)",
      }}
    >
      <AuthGuard>
        <DashboardShell>{children}</DashboardShell>
      </AuthGuard>
    </div>
  );
}
