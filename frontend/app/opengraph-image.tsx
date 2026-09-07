import { ImageResponse } from "next/og";
import { BRAND } from "../lib/site-metrics";

export const runtime = "edge";
export const alt = "CallForge — AI cold-calling sales agents";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

export default function OGImage() {
  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          flexDirection: "column",
          justifyContent: "space-between",
          background: "#0B1220",
          padding: 80,
          color: "#fff",
          fontFamily: "sans-serif",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 20 }}>
          <div
            style={{
              width: 56,
              height: 56,
              borderRadius: 14,
              background: "#057676",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              fontSize: 30,
            }}
          >
            📞
          </div>
          <div style={{ fontSize: 30, fontWeight: 600 }}>{BRAND.product}</div>
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
          <div style={{ fontSize: 68, fontWeight: 700, lineHeight: 1.05, maxWidth: 940 }}>
            AI sales agents that cold-call and close while you sleep
          </div>
          <div style={{ fontSize: 26, color: "rgba(255,255,255,0.6)" }}>
            Real outbound calls · sub-second response · books meetings on the call
          </div>
        </div>

        <div
          style={{
            fontSize: 20,
            color: "#3CC2DD",
            fontFamily: "monospace",
            letterSpacing: 4,
          }}
        >
          {BRAND.company.toUpperCase()}
        </div>
      </div>
    ),
    size,
  );
}
