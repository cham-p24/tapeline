/**
 * /changelog OG image. Conveys the "we ship publicly, every change is logged"
 * trust signal in the social preview itself.
 */
import { ImageResponse } from "next/og";

export const runtime = "edge";
export const alt = "Tapeline changelog — every release, public, ordered newest first";
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
            Changelog
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
            What we shipped, when.
          </div>
          <div style={{ fontSize: "26px", color: "#a1a1aa", lineHeight: 1.4, display: "flex", maxWidth: "950px" }}>
            Every release, ordered newest first. Past entries never edited.
          </div>
        </div>

        {/* Faux changelog entries */}
        <div
          style={{
            marginTop: "auto",
            display: "flex",
            flexDirection: "column",
            gap: "12px",
            fontFamily: "JetBrains Mono, ui-monospace, monospace",
          }}
        >
          <Entry tag="shipped" version="0.1.7" title="Public per-ticker share pages" />
          <Entry tag="shipped" version="0.1.6" title="System status page + /api/status" />
          <Entry tag="improvement" version="0.1.5" title="Charm-priced annual ($24.99 / $39.99)" />
        </div>
      </div>
    ),
    { ...size }
  );
}

function Entry({ tag, version, title }: { tag: string; version: string; title: string }) {
  const tagColor = tag === "shipped" ? "#22c55e" : tag === "fix" ? "#ef4444" : "#fbbf24";
  return (
    <div style={{ display: "flex", alignItems: "center", gap: "16px", fontSize: "22px" }}>
      <span
        style={{
          fontSize: "12px",
          color: tagColor,
          background: `${tagColor}1f`,
          border: `1px solid ${tagColor}66`,
          padding: "4px 10px",
          borderRadius: "999px",
          textTransform: "uppercase",
          letterSpacing: "0.1em",
          display: "flex",
        }}
      >
        {tag}
      </span>
      <span style={{ color: "#71717a", display: "flex" }}>v{version}</span>
      <span style={{ color: "#e4e4e7", display: "flex" }}>{title}</span>
    </div>
  );
}
