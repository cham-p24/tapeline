/**
 * LinkedIn PERSONAL profile banner - 1584x396 PNG.
 *
 * Served at /banner-linkedin. Upload to the Christian Piyatilaka personal
 * LinkedIn profile cover slot. DO NOT upload to a LinkedIn company page -
 * the company-page cover uses a much wider ~6:1 aspect (1128x191) and
 * uploading this 4:1 banner letterboxes + trips LinkedIn's upload-size
 * validator. The company-page banner is at /banner-linkedin-company.
 *
 * Layout - matches every other Tapeline brand surface (X banner, email
 * logo, all OG images): stripe INLINE with the "Tapeline" wordmark, NOT
 * stacked above it. Same hierarchy as banner-x.
 *
 * Safe area: the personal-profile avatar circle pops up from below the
 * banner with the top ~25% of the circle clipping into the bottom ~120px
 * of the canvas at bottom-left. Content is anchored to the TOP of the
 * canvas so the avatar can't reach it.
 */
import { ImageResponse } from "next/og";
import { loadInter } from "@/lib/og-fonts";

export const runtime = "edge";

export async function GET() {
  const fonts = await loadInter([500, 700]);
  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          background:
            "linear-gradient(135deg, #07090c 0%, #0d1218 50%, #0a0f15 100%)",
          padding: "60px 96px 0 96px",
          display: "flex",
          flexDirection: "column",
          justifyContent: "flex-start",
          gap: "24px",
          fontFamily: "Inter, system-ui, sans-serif",
          color: "#f4f4f5",
          position: "relative",
        }}
      >
        {/* Accent glow top-right */}
        <div
          style={{
            position: "absolute",
            top: "-180px",
            right: "-180px",
            width: "560px",
            height: "560px",
            background:
              "radial-gradient(circle, rgba(59, 130, 246, 0.20) 0%, transparent 70%)",
            display: "flex",
          }}
        />
        {/* Brand mark - stripe + wordmark INLINE, same row.
            Matches banner-x, email-logo, and the og.tsx helper layout
            so the brand reads consistent across every surface. */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: "26px",
          }}
        >
          <div
            style={{
              width: "120px",
              height: "26px",
              background: "#3b82f6",
              borderRadius: "999px",
              display: "flex",
            }}
          />
          <span
            style={{
              fontSize: "92px",
              fontWeight: 700,
              letterSpacing: "-0.04em",
              lineHeight: 1,
            }}
          >
            Tapeline
          </span>
        </div>
        {/* Tagline - one line, sits at y~180 well clear of where the
            avatar circle clips in at y~280+. */}
        <div
          style={{
            fontSize: "36px",
            fontWeight: 500,
            color: "#a1a1aa",
            lineHeight: 1.25,
            letterSpacing: "-0.02em",
            maxWidth: "1392px",
            display: "flex",
          }}
        >
          One score per US stock. Public scorecard. Public formula.
        </div>
      </div>
    ),
    { width: 1584, height: 396, fonts },
  );
}
