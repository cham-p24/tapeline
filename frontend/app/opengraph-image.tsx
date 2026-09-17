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
 *
 * Every number on this card is interpolated (2026-09-17, after #842): the
 * card used to say "Every US ticker" (we score ~11,500 US stocks and ETFs,
 * not every ticker) and showed a bare "$8.25 / mo" with no annual-billing
 * qualifier, which lib/pricing.ts says must never render alone. It also
 * states the price delay, because a share card travels without the page.
 */
import { ImageResponse } from "next/og";
import { PRICE_DELAY_NOTE } from "@/lib/freshness";
import { PRICING, billedAnnuallyNote, usd } from "@/lib/pricing";
import { activeScoredLabel } from "@/lib/universe";

export const runtime = "edge";
export const alt = "Tapeline — Read the tape.";
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
            background: "radial-gradient(circle, rgba(59, 130, 246, 0.18) 0%, transparent 70%)",
            display: "flex",
          }}
        />

        {/* Brand mark */}
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
          <span style={{ fontSize: "32px", fontWeight: 600, letterSpacing: "-0.02em" }}>
            Tapeline
          </span>
        </div>

        {/* Hero */}
        <div style={{ marginTop: "40px", display: "flex", flexDirection: "column", gap: "18px" }}>
          <div
            style={{
              fontSize: "68px",
              fontWeight: 700,
              lineHeight: 1.05,
              letterSpacing: "-0.035em",
              maxWidth: "1040px",
              display: "flex",
            }}
          >
            {`One score. One sentence. ${activeScoredLabel} US stocks and ETFs.`}
          </div>
          <div
            style={{
              fontSize: "26px",
              color: "#a1a1aa",
              lineHeight: 1.4,
              maxWidth: "1040px",
              display: "flex",
            }}
          >
            {`Quantitative scanner with market regime, SEC Form 4 insider filings, and a public scorecard. ${PRICE_DELAY_NOTE}.`}
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
              Free plan · Pro from
            </span>
            <span style={{ fontSize: "44px", fontWeight: 700, letterSpacing: "-0.02em", display: "flex" }}>
              <span style={{ color: "#22c55e" }}>{usd(PRICING.pro.annualPerMonth)}</span>
              <span style={{ color: "#a1a1aa", fontWeight: 500, fontSize: "28px", marginLeft: "10px", marginTop: "12px" }}>
                USD / mo
              </span>
            </span>
            <span style={{ fontSize: "20px", color: "#a1a1aa", display: "flex" }}>
              {`${billedAnnuallyNote(PRICING.pro)}, or ${usd(PRICING.pro.monthly)} monthly`}
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
