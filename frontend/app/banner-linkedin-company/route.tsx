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
 * validation upload failure.
 *
 * Layout - avatar safe area: LinkedIn overlays a LARGE square company
 * logo at bottom-left of the cover (NOT a small circle like personal
 * profiles). The avatar tile takes roughly x=44 to x=260, full height
 * on a 1128x191 banner. Anything in that zone gets chopped.
 *
 * So content is pushed RIGHT into the safe area (paddingLeft 296),
 * leaving the left ~26% empty for the company logo. The brand mark
 * shown on the banner is intentionally absent - the company logo IS
 * the brand mark and showing it twice (avatar tile + banner stripe)
 * reads as duplicate. The tagline becomes the hero of the cover.
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
          padding: "0 56px 0 296px",
          display: "flex",
          flexDirection: "column",
          justifyContent: "center",
          gap: "12px",
          fontFamily: "Inter, system-ui, sans-serif",
          color: "#f4f4f5",
          position: "relative",
        }}
      >
        {/* Stronger accent glow top-right - gives the dark canvas visual
            weight so it doesn't read empty next to busy company covers
            on the rest of LinkedIn. */}
        <div
          style={{
            position: "absolute",
            top: "-150px",
            right: "-150px",
            width: "440px",
            height: "440px",
            background:
              "radial-gradient(circle, rgba(59, 130, 246, 0.28) 0%, transparent 70%)",
            display: "flex",
          }}
        />
        {/* Hero tagline - the cover's job is to extend the company name
            (already shown by LinkedIn's chrome) with the value prop, not
            to repeat the brand mark. Two short sentences stacked. */}
        <div
          style={{
            fontSize: "36px",
            fontWeight: 700,
            color: "#f4f4f5",
            letterSpacing: "-0.025em",
            lineHeight: 1.05,
            display: "flex",
          }}
        >
          One score per US stock.
        </div>
        <div
          style={{
            fontSize: "22px",
            fontWeight: 500,
            color: "#a1a1aa",
            letterSpacing: "-0.015em",
            lineHeight: 1.3,
            display: "flex",
          }}
        >
          Public 6-factor formula. Public scorecard. tapeline.io
        </div>
      </div>
    ),
    { width: 1128, height: 191, fonts },
  );
}
