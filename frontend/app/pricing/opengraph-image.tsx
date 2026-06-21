/**
 * /pricing-specific OG image. Twitter / LinkedIn / Slack show this whenever
 * someone pastes the pricing page link. Lets the social card sell directly.
 */
import { ImageResponse } from "next/og";

export const runtime = "edge";
export const alt = "Tapeline pricing — $24.99/mo Pro · $39.99/mo Premium (USD)";
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
          position: "relative",
        }}
      >
        <div
          style={{
            position: "absolute",
            top: "-150px",
            right: "-150px",
            width: "500px",
            height: "500px",
            background: "radial-gradient(circle, rgba(59, 130, 246, 0.18) 0%, transparent 70%)",
            display: "flex",
          }}
        />

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
            Pricing
          </span>
        </div>

        <div style={{ marginTop: "56px", display: "flex", flexDirection: "column", gap: "8px" }}>
          <div
            style={{
              fontSize: "60px",
              fontWeight: 700,
              letterSpacing: "-0.03em",
              lineHeight: 1.1,
              display: "flex",
            }}
          >
            Live scanner. Public scorecard.
          </div>
          <div style={{ fontSize: "30px", color: "#a1a1aa", lineHeight: 1.4, display: "flex" }}>
            Three tiers. 14-day Premium trial. No credit card. Prices in USD.
          </div>
        </div>

        {/* Pricing tiles */}
        <div style={{ marginTop: "auto", display: "flex", gap: "20px" }}>
          <Tile
            tier="Free"
            price="$0"
            sub="forever"
            note="Live scores · top-10 scanner · 5 look-ups/day"
          />
          <Tile
            tier="Pro"
            price="$24.99"
            sub="/mo annual"
            note="Full live scanner · alerts · CSV"
            outline
          />
          <Tile
            tier="Premium"
            price="$39.99"
            sub="/mo annual"
            note="+ Congress · Insider · API · Telegram"
            highlight
          />
        </div>
      </div>
    ),
    { ...size }
  );
}

function Tile({
  tier,
  price,
  sub,
  note,
  outline,
  highlight,
}: {
  tier: string;
  price: string;
  sub: string;
  note: string;
  outline?: boolean;
  highlight?: boolean;
}) {
  const border = highlight
    ? "2px solid rgba(34, 197, 94, 0.6)"
    : outline
    ? "1px solid #2a3242"
    : "1px solid #1d232e";
  const bg = highlight
    ? "linear-gradient(180deg, rgba(34,197,94,0.10), rgba(20,184,166,0.04))"
    : "#0d1218";
  return (
    <div
      style={{
        flex: 1,
        display: "flex",
        flexDirection: "column",
        gap: "8px",
        padding: "28px 24px",
        borderRadius: "20px",
        border,
        background: bg,
      }}
    >
      <div
        style={{
          fontSize: "16px",
          color: highlight ? "#22c55e" : "#a1a1aa",
          textTransform: "uppercase",
          letterSpacing: "0.12em",
          display: "flex",
        }}
      >
        {tier}
      </div>
      <div style={{ display: "flex", alignItems: "baseline", gap: "8px" }}>
        <span style={{ fontSize: "48px", fontWeight: 700, letterSpacing: "-0.02em" }}>{price}</span>
        <span style={{ fontSize: "18px", color: "#71717a", display: "flex" }}>{sub}</span>
      </div>
      <div style={{ fontSize: "16px", color: "#71717a", marginTop: "4px", display: "flex" }}>{note}</div>
    </div>
  );
}
