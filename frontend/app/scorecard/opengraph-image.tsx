/**
 * /scorecard OG image. The scorecard is the trust proof — surface that
 * directly on the social card so the click-through is "see the receipts".
 */
import { ImageResponse } from "next/og";

export const runtime = "edge";
export const alt = "Tapeline public scorecard — every score, back-checked";
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
            Public scorecard
          </span>
        </div>

        <div style={{ marginTop: "60px", display: "flex", flexDirection: "column", gap: "10px" }}>
          <div
            style={{
              fontSize: "70px",
              fontWeight: 700,
              letterSpacing: "-0.03em",
              lineHeight: 1.05,
              display: "flex",
              maxWidth: "1000px",
            }}
          >
            We grade ourselves before you do.
          </div>
          <div
            style={{
              fontSize: "26px",
              color: "#a1a1aa",
              lineHeight: 1.4,
              display: "flex",
              maxWidth: "950px",
            }}
          >
            Every top-10 we publish is back-checked against next-day prices. Every win, every miss, public.
          </div>
        </div>

        {/* Mock scorecard rows */}
        <div
          style={{
            marginTop: "auto",
            display: "flex",
            flexDirection: "column",
            gap: "8px",
            padding: "24px",
            borderRadius: "16px",
            background: "#0a0f15",
            border: "1px solid #1d232e",
            fontFamily: "JetBrains Mono, ui-monospace, monospace",
            fontSize: "22px",
            color: "#e4e4e7",
          }}
        >
          <div
            style={{
              display: "flex",
              gap: "32px",
              fontSize: "14px",
              color: "#71717a",
              textTransform: "uppercase",
              letterSpacing: "0.1em",
              paddingBottom: "8px",
              borderBottom: "1px solid #1d232e",
            }}
          >
            <span style={{ width: "120px", display: "flex" }}>Ticker</span>
            <span style={{ width: "120px", display: "flex" }}>Score</span>
            <span style={{ width: "180px", display: "flex" }}>Next-day</span>
            <span style={{ display: "flex" }}>vs SPY</span>
          </div>
          <Row sym="NVDA" score="92" next="+2.4%" alpha="+1.8%" />
          <Row sym="AMD" score="87" next="+1.7%" alpha="+1.1%" />
          <Row sym="META" score="82" next="-0.3%" alpha="-0.9%" red />
        </div>
      </div>
    ),
    { ...size }
  );
}

function Row({
  sym,
  score,
  next,
  alpha,
  red,
}: {
  sym: string;
  score: string;
  next: string;
  alpha: string;
  red?: boolean;
}) {
  return (
    <div style={{ display: "flex", gap: "32px", paddingTop: "8px" }}>
      <span style={{ width: "120px", fontWeight: 600, display: "flex" }}>{sym}</span>
      <span style={{ width: "120px", color: "#22c55e", fontWeight: 600, display: "flex" }}>{score}</span>
      <span style={{ width: "180px", color: red ? "#ef4444" : "#22c55e", display: "flex" }}>{next}</span>
      <span style={{ color: red ? "#ef4444" : "#22c55e", display: "flex" }}>{alpha}</span>
    </div>
  );
}
