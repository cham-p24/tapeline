/**
 * /verify OG image. This page's whole pitch is "here is the record you can
 * download and check yourself", so the social card shows the raw-dataset
 * endpoints — the actual verifiable artifact — not a claim about it.
 *
 * COMPLIANCE (docs/COMPLIANCE_COPY_RULES.md): strictly descriptive. No returns,
 * no vs-SPY figure, no evaluative language — only the MECHANISM of verification,
 * matching the page's title/meta/H1 which are safe by construction.
 */
import { ImageResponse } from "next/og";

export const runtime = "edge";
export const alt = "Tapeline — a stock screener whose full record you can download and check yourself";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

export default async function OG() {
  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          flexDirection: "column",
          background: "linear-gradient(135deg, #07090c 0%, #0d1218 50%, #0a0f15 100%)",
          padding: "70px 80px",
          fontFamily: "Inter, system-ui, sans-serif",
          color: "#f4f4f5",
        }}
      >
        {/* Brand */}
        <div style={{ display: "flex", alignItems: "center", gap: "14px" }}>
          <div
            style={{
              width: "56px",
              height: "12px",
              background: "#3b82f6",
              borderRadius: "999px",
              display: "flex",
            }}
          />
          <span style={{ fontSize: "30px", fontWeight: 600, letterSpacing: "-0.02em" }}>
            Tapeline
          </span>
          <span style={{ fontSize: "30px", color: "#52525b", marginLeft: "auto", display: "flex" }}>
            Verify
          </span>
        </div>

        <div style={{ marginTop: "44px", display: "flex", flexDirection: "column", gap: "8px" }}>
          <div
            style={{
              fontSize: "54px",
              fontWeight: 700,
              letterSpacing: "-0.03em",
              lineHeight: 1.1,
              display: "flex",
            }}
          >
            The record. Downloadable.
          </div>
          <div style={{ fontSize: "26px", color: "#a1a1aa", lineHeight: 1.4, display: "flex", maxWidth: "900px" }}>
            Every daily top-10 pick, its six factors, and how it did the next session. Append-only &mdash; losing days kept.
          </div>
        </div>

        {/* The actual verifiable artifact: the raw dataset endpoints */}
        <div
          style={{
            marginTop: "48px",
            padding: "32px",
            borderRadius: "16px",
            background: "#0a0f15",
            border: "1px solid #1d232e",
            fontFamily: "JetBrains Mono, ui-monospace, monospace",
            fontSize: "24px",
            color: "#e4e4e7",
            lineHeight: 1.6,
            display: "flex",
            flexDirection: "column",
            gap: "4px",
          }}
        >
          <span style={{ display: "flex" }}>
            <span style={{ color: "#22c55e" }}>GET</span>
            <span style={{ color: "#e4e4e7" }}>{`  /api/scorecard.csv`}</span>
            <span style={{ color: "#71717a" }}>{`   full append-only archive`}</span>
          </span>
          <span style={{ display: "flex" }}>
            <span style={{ color: "#22c55e" }}>GET</span>
            <span style={{ color: "#e4e4e7" }}>{`  /api/scorecard.json`}</span>
            <span style={{ color: "#71717a" }}>{`  same record, machine-readable`}</span>
          </span>
        </div>

        {/* Footer */}
        <div style={{ marginTop: "auto", fontSize: "20px", color: "#71717a", display: "flex" }}>
          tapeline.io/verify
        </div>
      </div>
    ),
    { ...size }
  );
}
