/**
 * Square brand profile picture - 400x400 PNG.
 *
 * Served at /profile-square. Used as the profile picture / avatar on
 * tapeline.io's X account (@tapeline_io), LinkedIn personal + company
 * page, GitHub, and any other "round/square avatar" surface.
 *
 * Design: bold white "T" centered on the brand dark bg, with the
 * green->teal gradient stripe sitting as an underline accent. At small
 * profile sizes (~32px in feeds) the "T" reads cleanly; the stripe
 * adds the brand colour cue.
 *
 * Edge-rendered + cached at the CDN so every avatar fetch is free.
 */
import { ImageResponse } from "next/og";
import { loadInter } from "@/lib/og-fonts";

export const runtime = "edge";

export async function GET() {
  const fonts = await loadInter([700]);
  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          background: "#0a0a0a",
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          fontFamily: "Inter, system-ui, sans-serif",
          position: "relative",
        }}
      >
        {/* Subtle accent glow top-right - same as opengraph-image */}
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
        <span
          style={{
            color: "#f4f4f5",
            fontSize: "260px",
            fontWeight: 700,
            letterSpacing: "-0.05em",
            lineHeight: 0.85,
            marginBottom: "20px",
          }}
        >
          T
        </span>
        <div
          style={{
            width: "150px",
            height: "22px",
            background: "#3b82f6",
            borderRadius: "999px",
            display: "flex",
          }}
        />
      </div>
    ),
    { width: 400, height: 400, fonts },
  );
}
