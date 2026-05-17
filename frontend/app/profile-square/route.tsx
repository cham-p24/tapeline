/**
 * Square brand profile picture - 400x400 PNG.
 *
 * Served at /profile-square. Used as the profile picture / avatar on
 * tapeline.io's X account (@tapeline_io), LinkedIn personal + company
 * page, GitHub, and any other "round/square avatar" surface.
 *
 * Design: the canonical Tapeline brand mark is the blue pill stripe -
 * SAME mark used in the favicon (/icon.tsx), the email-logo, every OG
 * image, and both social banners. No letterform. The stripe alone is the
 * identity; an inserted "T" would split the brand into two competing
 * marks at different surfaces.
 *
 * Stripe is centered + sized so the inscribed circle (X / LinkedIn crop
 * the 400x400 to a circle of radius 200) shows the full pill. A subtle
 * top-right glow gives the dark square visual interest at the larger
 * sizes (profile page, "Edit profile" preview) without competing with
 * the stripe at small feed sizes.
 *
 * Edge-rendered + cached at the CDN so every avatar fetch is free.
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
          background: "#0a0a0a",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          position: "relative",
        }}
      >
        {/* Subtle accent glow top-right - matches the OG image + banner
            glow so the avatar feels visually consistent with the wider
            brand surface. Kept faint so it never competes with the
            stripe at small (~32px) feed render sizes. */}
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
        {/* The mark. 4:1 ratio matches /icon.tsx exactly - same brand
            stripe just scaled to the avatar canvas. Sized to fit
            comfortably inside the inscribed circle (radius 200) that
            X / LinkedIn / GitHub use for circle-cropped avatars. */}
        <div
          style={{
            width: "260px",
            height: "65px",
            background: "#3b82f6",
            borderRadius: "999px",
            display: "flex",
          }}
        />
      </div>
    ),
    { width: 400, height: 400 },
  );
}
