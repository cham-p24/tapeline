/**
 * LinkedIn banner image - 1584x396 PNG.
 *
 * Served at /banner-linkedin. Upload to either the Christian Piyatilaka
 * personal profile header OR a Tapeline company page header. Spec is
 * the LinkedIn personal banner size; for a company page header (1128x191)
 * a different route would be needed - this banner can also be center-
 * cropped to that aspect by LinkedIn if uploaded there.
 *
 * Wider + shorter than the X banner. Layout shifts to single-row with
 * brand mark left, tagline right, since vertical real estate is tighter.
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
          padding: "0 96px",
          display: "flex",
          alignItems: "center",
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
              "radial-gradient(circle, rgba(34, 197, 94, 0.20) 0%, transparent 70%)",
            display: "flex",
          }}
        />
        {/* Left: brand mark stacked */}
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            gap: "16px",
            flex: "0 0 auto",
          }}
        >
          <div
            style={{
              width: "100px",
              height: "20px",
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
              lineHeight: 1,
            }}
          >
            Tapeline
          </span>
        </div>
        {/* Right: tagline */}
        <div
          style={{
            marginLeft: "80px",
            fontSize: "34px",
            fontWeight: 500,
            color: "#a1a1aa",
            lineHeight: 1.25,
            letterSpacing: "-0.02em",
            maxWidth: "780px",
            display: "flex",
          }}
        >
          Open-formula stock scanner. Public scorecard back-checks every
          call vs SPY.
        </div>
      </div>
    ),
    { width: 1584, height: 396 },
  );
}
