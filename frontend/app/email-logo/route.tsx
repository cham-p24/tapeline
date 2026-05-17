/**
 * Email-signature logo — 220x60 PNG.
 *
 * Served at /email-logo. Used as the inline `<img>` in Gmail "Send mail as"
 * signatures across every tapeline.io alias (christian, billing, legal,
 * press, support) so inbound + outbound mail carries a consistent brand mark.
 *
 * Mirrors the brand mark from icon.tsx (dark bg + green->teal gradient stripe)
 * scaled to a horizontal wordmark size that renders cleanly in email clients.
 * Edge-rendered so the CDN caches the PNG and we're not paying compute per
 * email render.
 */
import { ImageResponse } from "next/og";
import { loadInter } from "@/lib/og-fonts";

export const runtime = "edge";

export async function GET() {
  const fonts = await loadInter([600]);
  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          background: "#0a0a0a",
          borderRadius: "8px",
          display: "flex",
          alignItems: "center",
          padding: "0 18px",
          fontFamily: "Inter, system-ui, sans-serif",
        }}
      >
        <div
          style={{
            width: "32px",
            height: "8px",
            background: "#3b82f6",
            borderRadius: "999px",
            display: "flex",
            marginRight: "14px",
          }}
        />
        <span
          style={{
            color: "#f4f4f5",
            fontSize: "28px",
            fontWeight: 600,
            letterSpacing: "-0.025em",
          }}
        >
          Tapeline
        </span>
      </div>
    ),
    { width: 220, height: 60, fonts },
  );
}
