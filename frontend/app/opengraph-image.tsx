/**
 * Dynamic Open Graph image for the landing page.
 *
 * Next.js 14 App Router auto-generates `<meta property="og:image">` and
 * `<meta name="twitter:image">` tags pointing at the route this file owns.
 * Twitter, LinkedIn, Slack, iMessage, etc. fetch this when users paste a
 * tapeline.io link — without it the preview is blank or shows the favicon.
 *
 * Edge-runtime + ImageResponse keeps the rendered PNG cacheable at the CDN
 * layer so we're not paying compute on every social-card crawl.
 */
import { ImageResponse } from "next/og";

export const runtime = "edge";
export const alt = "Tapeline — Read the tape. Live.";
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
          padding: "80px",
          position: "relative",
          fontFamily: "Inter, system-ui, sans-serif",
          color: "#f4f4f5",
        }}
      >
        {/* Subtle accent glow top-right */}
        <div
          style={{
            position: "absolute",
            top: "-200px",
            right: "-200px",
            width: "600px",
            height: "600px",
            background: "radial-gradient(circle, rgba(34, 197, 94, 0.18) 0%, transparent 70%)",
            display: "flex",
          }}
        />

        {/* Brand mark */}
        <div style={{ display: "flex", alignItems: "center", gap: "14px" }}>
          <div
            style={{
              width: "56px",
              height: "12px",
              background: "linear-gradient(90deg, #22c55e 0%, #14b8a6 100%)",
              borderRadius: "999px",
              display: "flex",
            }}
          />
          <span style={{ fontSize: "32px", fontWeight: 600, letterSpacing: "-0.02em" }}>
            Tapeline
          </span>
        </div>

        {/* Hero */}
        <div style={{ marginTop: "64px", display: "flex", flexDirection: "column", gap: "24px" }}>
          <div
            style={{
              fontSize: "84px",
              fontWeight: 700,
              lineHeight: 1.05,
              letterSpacing: "-0.035em",
              maxWidth: "950px",
              display: "flex",
            }}
          >
            One score. One sentence. Every US ticker.
          </div>
          <div
            style={{
              fontSize: "30px",
              color: "#a1a1aa",
              lineHeight: 1.4,
              maxWidth: "900px",
              display: "flex",
            }}
          >
            Live quantitative scanner with squeeze detection, market regime, congressional trades, and a public scorecard.
          </div>
        </div>

        {/* Footer row */}
        <div
          style={{
            marginTop: "auto",
            display: "flex",
            justifyContent: "space-between",
            alignItems: "flex-end",
            gap: "40px",
          }}
        >
          <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
            <span
              style={{
                fontSize: "16px",
                color: "#52525b",
                textTransform: "uppercase",
                letterSpacing: "0.12em",
                display: "flex",
              }}
            >
              From
            </span>
            <span style={{ fontSize: "44px", fontWeight: 700, letterSpacing: "-0.02em", display: "flex" }}>
              <span style={{ color: "#22c55e" }}>$24.99</span>
              <span style={{ color: "#a1a1aa", fontWeight: 500, fontSize: "28px", marginLeft: "10px", marginTop: "12px" }}>
                USD / mo
              </span>
            </span>
          </div>

          <div
            style={{
              display: "flex",
              gap: "32px",
              fontSize: "20px",
              color: "#a1a1aa",
            }}
          >
            <span style={{ display: "flex" }}>tapeline.io</span>
          </div>
        </div>
      </div>
    ),
    { ...size }
  );
}
