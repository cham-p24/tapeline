/**
 * /roadmap OG image. Communicates "you can see what's coming" + the
 * Premium-vote angle in the share preview.
 */
import { ImageResponse } from "next/og";

export const runtime = "edge";
export const alt = "Tapeline roadmap — public, prioritised by Premium votes";
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
              background: "linear-gradient(90deg, #22c55e 0%, #14b8a6 100%)",
              borderRadius: "999px",
              display: "flex",
            }}
          />
          <span style={{ fontSize: "30px", fontWeight: 600, letterSpacing: "-0.02em" }}>
            Tapeline
          </span>
          <span style={{ fontSize: "30px", color: "#52525b", marginLeft: "auto", display: "flex" }}>
            Roadmap
          </span>
        </div>

        <div style={{ marginTop: "60px", display: "flex", flexDirection: "column", gap: "12px" }}>
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
            What&rsquo;s shipping next.
          </div>
          <div style={{ fontSize: "26px", color: "#a1a1aa", lineHeight: 1.4, display: "flex", maxWidth: "950px" }}>
            Public list. Premium subscribers vote on order — counts update live.
          </div>
        </div>

        {/* Status pillars */}
        <div
          style={{
            marginTop: "auto",
            display: "flex",
            gap: "20px",
          }}
        >
          <Pillar
            label="Shipped"
            count="6"
            color="#22c55e"
          />
          <Pillar
            label="In progress"
            count="3"
            color="#fbbf24"
          />
          <Pillar
            label="Up next"
            count="8"
            color="#14b8a6"
          />
        </div>
      </div>
    ),
    { ...size }
  );
}

function Pillar({ label, count, color }: { label: string; count: string; color: string }) {
  return (
    <div
      style={{
        flex: 1,
        display: "flex",
        flexDirection: "column",
        gap: "8px",
        padding: "28px 32px",
        borderRadius: "20px",
        background: `${color}14`,
        border: `2px solid ${color}55`,
      }}
    >
      <span
        style={{
          fontSize: "16px",
          color,
          textTransform: "uppercase",
          letterSpacing: "0.12em",
          display: "flex",
          fontWeight: 600,
        }}
      >
        {label}
      </span>
      <span style={{ fontSize: "72px", fontWeight: 700, color, letterSpacing: "-0.03em", display: "flex" }}>
        {count}
      </span>
    </div>
  );
}
