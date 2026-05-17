/**
 * X / Twitter banner image - 1500x500 PNG.
 *
 * Served at /banner-x. Upload to the @tapeline_io header on X.
 *
 * Layout: brand mark + wordmark top-left, tagline beneath, accent glow
 * top-right. Same colour palette as the OpenGraph image and email-logo
 * so the cross-surface brand reads consistent.
 *
 * Note on safe area: X crops/overlays the bottom ~60px with the verified
 * badge + profile picture pop-out. Important content stays in the upper
 * 80% of the canvas.
 */
import { ImageResponse } from "next/og";

export const runtime = "edge";

export async function GET() {
  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          background:
            "linear-gradient(135deg, #07090c 0%, #0d1218 50%, #0a0f15 100%)",
          padding: "70px 90px",
          display: "flex",
          flexDirection: "column",
          justifyContent: "center",
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
              "radial-gradient(circle, rgba(34, 197, 94, 0.20) 0%, transparent 70%)",
            display: "flex",
          }}
        />
        {/* Brand mark - stripe + wordmark */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: "22px",
            marginBottom: "30px",
          }}
        >
          <div
            style={{
              width: "110px",
              height: "24px",
              background:
                "linear-gradient(90deg, #22c55e 0%, #14b8a6 100%)",
              borderRadius: "999px",
              display: "flex",
            }}
          />
          <span
            style={{
              fontSize: "76px",
              fontWeight: 700,
              letterSpacing: "-0.035em",
            }}
          >
            Tapeline
          </span>
        </div>
        {/* Tagline */}
        <div
          style={{
            fontSize: "40px",
            fontWeight: 500,
            color: "#a1a1aa",
            lineHeight: 1.2,
            letterSpacing: "-0.02em",
            maxWidth: "1200px",
            display: "flex",
          }}
        >
          Open-formula stock scanner. Public scorecard. Six factors, weights
          on tapeline.io/how-it-works.
        </div>
      </div>
    ),
    { width: 1500, height: 500 },
  );
}
