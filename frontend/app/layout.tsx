import type { Metadata } from "next";
import { Inter, Space_Grotesk, IBM_Plex_Mono, Newsreader } from "next/font/google";
import "./globals.css";
import { AuthProvider } from "./context/AuthContext";
import { BRAND } from "../lib/site-metrics";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter",
  display: "swap",
});

/* Display face — hero headline, section titles, big numbers. */
const spaceGrotesk = Space_Grotesk({
  subsets: ["latin"],
  weight: ["500", "600", "700"],
  variable: "--font-display",
  display: "swap",
});

/* Mono — call timers, disposition codes, tabular data. */
const plexMono = IBM_Plex_Mono({
  subsets: ["latin"],
  weight: ["400", "500"],
  variable: "--font-mono",
  display: "swap",
});

/* Serif italic — the one "kickoff poster" accent line under big headlines. */
const newsreader = Newsreader({
  subsets: ["latin"],
  weight: ["400", "500"],
  style: ["italic"],
  variable: "--font-serif",
  display: "swap",
});

const SITE_URL = process.env.NEXT_PUBLIC_SITE_URL || `https://${BRAND.domain}`;

export const metadata: Metadata = {
  metadataBase: new URL(SITE_URL),
  title: {
    default: "CallForge — AI cold-calling sales agents",
    template: "%s · CallForge",
  },
  description: BRAND.blurb,
  applicationName: BRAND.product,
  publisher: BRAND.company,
  keywords: [
    "AI voice agent",
    "cold calling AI",
    "sales automation",
    "AI sales agent",
    "voice cloning",
    "CallForge",
    "AgentraX",
  ],
  alternates: { canonical: "/" },
  openGraph: {
    type: "website",
    siteName: BRAND.product,
    title: "CallForge — AI cold-calling sales agents",
    description: BRAND.blurb,
    url: SITE_URL,
  },
  twitter: {
    card: "summary_large_image",
    title: "CallForge — AI cold-calling sales agents",
    description: BRAND.blurb,
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html
      lang="en"
      className={`${inter.variable} ${spaceGrotesk.variable} ${plexMono.variable} ${newsreader.variable}`}
    >
      <body>
        <AuthProvider>{children}</AuthProvider>
      </body>
    </html>
  );
}
