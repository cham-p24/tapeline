import { ImageResponse } from "next/og";

/**
 * Shared 1200x630 Open Graph card for section/landing pages.
 *
 * Pages like /signals, /daily-picks, /stocks, /sectors are the most
 * link-shared surfaces (the viral loop). Before this they fell back to the
 * generic homepage card; a page-specific eyebrow + headline + subhead
 * converts a paste-into-Slack/X far better. One renderer, called by each
 * route's opengraph-image.tsx with its own copy — zero chrome duplication.
 *
 * Render rules (Satori / next-og is strict): every container sets
 * display:flex, text lives in <span>/<div> leaves, and copy stays ASCII so
 * the default font never hits a missing glyph (no en-dashes / smart quotes).
 * Copy MUST stay descriptive, never prescriptive (publisher-exemption
 * voice): no buy / sell / recommend / "best to buy".
 */
const SIZE = { width: 1200, height: 630 };

export type SectionCardProps = {
  /** Small uppercase accent line, e.g. "LIVE SCANNER". */
  eyebrow: string;
  /** Hero line — descriptive, never prescriptive. */
  headline: string;
  /** Supporting sentence. */
  subhead: string;
  /** Bottom-left descriptive note. */
  footerNote: string;
  /** Bottom-right URL path, e.g. "tapeline.io/signals". */
  path: string;
};

export function sectionCard(props: SectionCardProps): ImageResponse {
  const accent = "#3b82f6";
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
        {/* Accent corner glow */}
        <div
          style={{
            position: "absolute",
            top: "-200px",
            right: "-200px",
            width: "600px",
            height: "600px",
            background: `radial-gradient(circle, ${accent}2e 0%, transparent 70%)`,
            display: "flex",
          }}
        />

        {/* Brand mark */}
        <div style={{ display: "flex", alignItems: "center", gap: "14px" }}>
          <div
            style={{
              width: "56px",
              height: "12px",
              background: accent,
              borderRadius: "999px",
              display: "flex",
            }}
          />
          <span style={{ fontSize: "32px", fontWeight: 600, letterSpacing: "-0.02em" }}>
            Tapeline
          </span>
        </div>

        {/* Hero */}
        <div style={{ marginTop: "54px", display: "flex", flexDirection: "column", gap: "22px" }}>
          <span
            style={{
              fontSize: "22px",
              fontWeight: 600,
              letterSpacing: "0.16em",
              textTransform: "uppercase",
              color: accent,
              display: "flex",
            }}
          >
            {props.eyebrow}
          </span>
          <div
            style={{
              fontSize: "76px",
              fontWeight: 700,
              lineHeight: 1.05,
              letterSpacing: "-0.035em",
              maxWidth: "980px",
              display: "flex",
            }}
          >
            {props.headline}
          </div>
          <div
            style={{
              fontSize: "29px",
              color: "#a1a1aa",
              lineHeight: 1.4,
              maxWidth: "950px",
              display: "flex",
            }}
          >
            {props.subhead}
          </div>
        </div>

        {/* Footer */}
        <div
          style={{
            marginTop: "auto",
            display: "flex",
            justifyContent: "space-between",
            alignItems: "flex-end",
            gap: "40px",
          }}
        >
          <span style={{ fontSize: "21px", color: "#52525b", display: "flex", maxWidth: "780px" }}>
            {props.footerNote}
          </span>
          <span style={{ fontSize: "21px", color: "#a1a1aa", display: "flex" }}>{props.path}</span>
        </div>
      </div>
    ),
    { ...SIZE },
  );
}
