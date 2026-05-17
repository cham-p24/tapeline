/**
 * LinkedIn COMPANY page cover image - 1128x191 PNG.
 *
 * Served at /banner-linkedin-company. Upload to the Tapeline LinkedIn
 * company page (linkedin.com/company/tapeline) cover slot.
 *
 * Important: LinkedIn's company page cover uses a ~6:1 aspect ratio,
 * way wider + shorter than the personal-profile banner (1584x396, ~4:1
 * served at /banner-linkedin). Uploading the personal banner to the
 * company slot triggers a letterbox on LinkedIn's crop tool AND a size-
 * validation upload failure. This route exists specifically to feed the
 * company-page upload modal at the exact spec LinkedIn expects.
 *
 * Layout: single horizontal row. Brand mark + wordmark on the left,
 * tagline on the right, sized so nothing crowds the vertical centre at
 * the tight 191px canvas height.
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
          padding: "0 56px",
          display: "flex",
          alignItems: "center",
          fontFamily: "Inter, system-ui, sans-serif",
          color: "#f4f4f5",
          position: "relative",
        }}
      >
        {/* Accent glow top-right - smaller than the personal banner's
            since the canvas is much shorter. */}
        <div
          style={{
            position: "absolute",
            top: "-100px",
            right: "-100px",
            width: "300px",
            height: "300px",
            background:
              "radial-gradient(circle, rgba(59, 130, 246, 0.20) 0%, transparent 70%)",
            display: "flex",
          }}
        />
        {/* Brand mark - stripe + wordmark inline */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: "16px",
            flex: "0 0 auto",
          }}
        >
          <div
            style={{
              width: "62px",
              height: "14px",
              background: "#3b82f6",
              borderRadius: "999px",
              display: "flex",
            }}
          />
          <span
            style={{
              fontSize: "44px",
              fontWeight: 700,
              letterSpacing: "-0.035em",
              lineHeight: 1,
            }}
          >
            Tapeline
          </span>
        </div>
        {/* Tagline - one short line, sized to leave breathing room next
            to the brand mark on the 1128px canvas. */}
        <div
          style={{
            marginLeft: "44px",
            fontSize: "22px",
            fontWeight: 500,
            color: "#a1a1aa",
            lineHeight: 1.3,
            letterSpacing: "-0.015em",
            maxWidth: "780px",
            display: "flex",
          }}
        >
          One score per US stock. Public scorecard. Public formula.
        </div>
      </div>
    ),
    { width: 1128, height: 191, fonts },
  );
}
