/**
 * /how-it-works OG image. The transparent-formula moat is best illustrated
 * with the formula itself — show it on the social card.
 */
import { ImageResponse } from "next/og";

export const runtime = "edge";
export const alt = "Tapeline scoring formula — 6 factors, public weights";
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
            How it works
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
            The formula. Public.
          </div>
          <div style={{ fontSize: "26px", color: "#a1a1aa", lineHeight: 1.4, display: "flex", maxWidth: "900px" }}>
            Six factors. Public weights. One score. TipRanks, Zacks, Kavout all hide theirs. We don&rsquo;t.
          </div>
        </div>

        {/* The actual formula in a code-style block */}
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
            <span style={{ color: "#22c55e" }}>score</span>
            <span style={{ color: "#71717a" }}>{` = `}</span>
            <span style={{ color: "#fbbf24" }}>0.25</span>
            <span style={{ color: "#71717a" }}>{`*`}</span>
            <span>trend</span>
            <span style={{ color: "#71717a" }}>{` + `}</span>
            <span style={{ color: "#fbbf24" }}>0.20</span>
            <span style={{ color: "#71717a" }}>{`*`}</span>
            <span>relative_strength</span>
          </span>
          <span style={{ display: "flex", paddingLeft: "112px" }}>
            <span style={{ color: "#71717a" }}>{`+ `}</span>
            <span style={{ color: "#fbbf24" }}>0.15</span>
            <span style={{ color: "#71717a" }}>{`*`}</span>
            <span>fundamentals</span>
            <span style={{ color: "#71717a" }}>{` + `}</span>
            <span style={{ color: "#fbbf24" }}>0.15</span>
            <span style={{ color: "#71717a" }}>{`*`}</span>
            <span>smart_money</span>
          </span>
          <span style={{ display: "flex", paddingLeft: "112px" }}>
            <span style={{ color: "#71717a" }}>{`+ `}</span>
            <span style={{ color: "#fbbf24" }}>0.15</span>
            <span style={{ color: "#71717a" }}>{`*`}</span>
            <span>macro</span>
            <span style={{ color: "#71717a" }}>{` + `}</span>
            <span style={{ color: "#fbbf24" }}>0.10</span>
            <span style={{ color: "#71717a" }}>{`*`}</span>
            <span>momentum</span>
          </span>
        </div>

        {/* Footer */}
        <div style={{ marginTop: "auto", fontSize: "20px", color: "#71717a", display: "flex" }}>
          tapeline.io/how-it-works
        </div>
      </div>
    ),
    { ...size }
  );
}
