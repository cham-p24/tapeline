/**
 * X / Twitter banner image - 1500x500 PNG.
 *
 * Served at /banner-x. Upload to the @tapeline_io header on X.
 *
 * Layout: brand mark + wordmark top-left, tagline beneath, accent glow
 * top-right. Same colour palette as the OpenGraph image and email-logo
 * so the cross-surface brand reads consistent.
 *
 * Note on safe area: X overlays the bottom-left ~30% of the 1500x500
 * banner with the avatar circle (center roughly (150, 420), radius ~90px
 * in banner coords) PLUS a subtle gradient darkening that creeps another
 * ~80px up. Anything visually important needs to sit in the TOP 280px
 * of the canvas, otherwise the profile-pic pop-out chops it. Tagline is
 * one line on purpose - a two-line tagline reliably loses its second
 * line behind the circle.
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
          padding: "60px 90px 0 90px",
          display: "flex",
          flexDirection: "column",
          justifyContent: "flex-start",
          fontFamily: "Inter, system-ui, sans-serif",
          color: "#f4f4f5",
          position: "relative",
        }}
      >
        {/* Accent glow top-right */}
        <div
          style={{
            position: "absolute",
            top: "-220px",
            right: "-220px",
            width: "700px",
            height: "700px",
            background:
              "radial-gradient(circle, rgba(59, 130, 246, 0.20) 0%, transparent 70%)",
            display: "flex",
          }}
        />
        {/* Brand mark - stripe + wordmark. Sits in the top ~180px so it
            stays clear of the avatar circle X overlays at bottom-left. */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: "26px",
            marginBottom: "22px",
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
        {/* Tagline - kept to ONE line so the bottom-half profile-pic
            overlay never amputates a second line. */}
        <div
          style={{
            fontSize: "38px",
            fontWeight: 500,
            color: "#a1a1aa",
            lineHeight: 1.2,
            letterSpacing: "-0.02em",
            maxWidth: "1300px",
            display: "flex",
          }}
        >
          One score per US stock. Public scorecard. Public formula.
        </div>
      </div>
    ),
    { width: 1500, height: 500, fonts },
  );
}
