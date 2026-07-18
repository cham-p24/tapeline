/**
 * /scorecard OG image.
 *
 * COMPLIANCE — Rule 3 (the vs-SPY presentation rule). This card travels
 * beyond our control: it is rendered by Slack, X, LinkedIn and iMessage
 * next to whatever text someone else wrote, stripped of the page's
 * disclaimers and of any ability to click through for context. So it carries
 * NO vs-SPY figure, NO hit rate, NO percentage of any kind, no green tick,
 * no arrow and no win/loss framing.
 *
 * What it does carry is the mechanism: the six named factors, the date, the
 * methodology URL, and the fact that the archive is append-only and keeps
 * its losing days. Those are all checkable statements about how the thing
 * works rather than claims about how it did.
 *
 * The previous version of this card rendered mock scorecard rows — NVDA
 * +2.4% / +1.8% vs SPY, AMD +1.7% / +1.1%, META -0.3% — in green and red
 * against real, named tickers. Those numbers were invented for the design.
 * A fabricated performance figure attached to a real security, on an asset
 * built to be screenshotted and reshared, is the worst version of this
 * problem: it is a vs-SPY claim (Rule 3), an implied evaluative statement
 * about specific securities (Rule 2), and it is not true (Rule 4's whole
 * premise — we publish the archive, we do not manufacture it). Do not
 * reintroduce sample rows here, real or illustrative.
 */
import { ImageResponse } from "next/og";

export const runtime = "edge";
export const alt =
  "Tapeline public scorecard — every daily top-10 frozen at the close, append-only, losing days kept";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

// The six named factors of the composite, as published at /how-it-works.
// Naming the inputs is a description of the method; it makes no claim about
// what the output does.
const FACTORS = [
  "Trend",
  "Relative Strength",
  "Fundamentals",
  "Smart Money",
  "Macro",
  "Momentum",
];

export default async function OG() {
  // Generation date, not a data date — the card is static and cached, so it
  // must not imply it is showing a particular session's results.
  const generated = new Date().toLocaleDateString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
    timeZone: "UTC",
  });

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

        {/* Headline — the mechanism, not the outcome. */}
        <div style={{ marginTop: "54px", display: "flex", flexDirection: "column", gap: "14px" }}>
          <div
            style={{
              fontSize: "60px",
              fontWeight: 700,
              letterSpacing: "-0.03em",
              lineHeight: 1.08,
              display: "flex",
              maxWidth: "1020px",
            }}
          >
            Every daily top-10, frozen when it printed.
          </div>
          <div
            style={{
              fontSize: "26px",
              color: "#a1a1aa",
              lineHeight: 1.4,
              display: "flex",
              maxWidth: "980px",
            }}
          >
            Append-only archive. Entries are never re-ranked, back-filled or removed — losing days
            stay on the page.
          </div>
        </div>

        {/* The six named factors — the composite's inputs, published. */}
        <div
          style={{
            marginTop: "auto",
            display: "flex",
            flexDirection: "column",
            gap: "14px",
            padding: "24px 26px",
            borderRadius: "16px",
            background: "#0a0f15",
            border: "1px solid #1d232e",
          }}
        >
          <div
            style={{
              display: "flex",
              fontSize: "14px",
              color: "#71717a",
              textTransform: "uppercase",
              letterSpacing: "0.1em",
            }}
          >
            The six factors behind every score
          </div>
          <div style={{ display: "flex", flexWrap: "wrap", gap: "10px" }}>
            {FACTORS.map((f) => (
              <div
                key={f}
                style={{
                  display: "flex",
                  fontSize: "22px",
                  color: "#e4e4e7",
                  border: "1px solid #1d232e",
                  borderRadius: "999px",
                  padding: "8px 18px",
                  background: "#0d1218",
                }}
              >
                {f}
              </div>
            ))}
          </div>
        </div>

        {/* Methodology URL + date. Neutral grey — no status colour anywhere
            on this card. */}
        <div
          style={{
            marginTop: "22px",
            display: "flex",
            alignItems: "center",
            fontSize: "20px",
            color: "#71717a",
          }}
        >
          <span style={{ display: "flex" }}>tapeline.io/how-it-works</span>
          <span style={{ display: "flex", marginLeft: "auto" }}>{generated}</span>
        </div>
      </div>
    ),
    { ...size }
  );
}
