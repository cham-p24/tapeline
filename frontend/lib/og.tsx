/**
 * Shared Open Graph image template for Tapeline.
 *
 * Edge-runtime `ImageResponse` from `next/og` renders TSX → PNG at the CDN
 * layer, so each call is cacheable + zero-cold-start. Every route-level
 * `opengraph-image.tsx` calls `ogResponse({...})` rather than reimplementing
 * the brand chrome.
 *
 * The shape mirrors the root `/opengraph-image.tsx` so the social-card
 * surface stays visually coherent across the site. Differentiation per page
 * comes from `eyebrow` (small uppercase context label), `title` (big hero),
 * and `subtitle` (one-line value prop).
 */
import { ImageResponse } from "next/og";
import { loadInter } from "@/lib/og-fonts";

export const ogSize = { width: 1200, height: 630 } as const;

type OgParams = {
  /** Small uppercase label, e.g. "COMPARE", "BLOG", "BEST STOCKS FOR". */
  eyebrow?: string;
  /** Hero headline, max ~80 chars to avoid wrap-clipping at 1200x630. */
  title: string;
  /** Sub-headline / value-prop, 1–2 lines. */
  subtitle?: string;
  /** Footer-left tagline. Defaults to the standard methodology line. */
  footerLeft?: string;
  /** Footer-right URL fragment. Defaults to "tapeline.io". */
  footerRight?: string;
  /** Accent color override (defaults to the brand blue #3b82f6). */
  accent?: string;
};

export async function ogResponse({
  eyebrow,
  title,
  subtitle,
  footerLeft = "Six-factor formula · Public scorecard · Live sub-60s refresh",
  footerRight = "tapeline.io",
  accent = "#3b82f6",
}: OgParams) {
  const fonts = await loadInter([400, 600, 700]);
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
          position: "relative",
          fontFamily: "Inter, system-ui, sans-serif",
          color: "#f4f4f5",
        }}
      >
        {/* Soft accent glow, top-right */}
        <div
          style={{
            position: "absolute",
            top: "-200px",
            right: "-200px",
            width: "600px",
            height: "600px",
            background: `radial-gradient(circle, ${accent}33 0%, transparent 70%)`,
            display: "flex",
          }}
        />

        {/* Brand row */}
        <div style={{ display: "flex", alignItems: "center", gap: "14px" }}>
          <div
            style={{
              width: "56px",
              height: "12px",
              background: accent,
              borderRadius: "999px",
              display: "flex",
            }}
          />
          <span style={{ fontSize: "30px", fontWeight: 600, letterSpacing: "-0.02em" }}>
            Tapeline
          </span>
          {eyebrow && (
            <span
              style={{
                fontSize: "20px",
                color: "#71717a",
                marginLeft: "auto",
                textTransform: "uppercase",
                letterSpacing: "0.18em",
                display: "flex",
              }}
            >
              {eyebrow}
            </span>
          )}
        </div>

        {/* Hero */}
        <div style={{ marginTop: "70px", display: "flex", flexDirection: "column", gap: "24px" }}>
          <div
            style={{
              fontSize: "68px",
              fontWeight: 700,
              lineHeight: 1.05,
              letterSpacing: "-0.03em",
              maxWidth: "1040px",
              display: "flex",
            }}
          >
            {title}
          </div>
          {subtitle && (
            <div
              style={{
                fontSize: "28px",
                color: "#a1a1aa",
                lineHeight: 1.4,
                maxWidth: "1000px",
                display: "flex",
              }}
            >
              {subtitle}
            </div>
          )}
        </div>

        {/* Footer */}
        <div
          style={{
            marginTop: "auto",
            display: "flex",
            justifyContent: "space-between",
            alignItems: "flex-end",
            fontSize: "20px",
            color: "#71717a",
            gap: "40px",
          }}
        >
          <span style={{ display: "flex" }}>{footerLeft}</span>
          <span style={{ display: "flex", color: "#a1a1aa" }}>{footerRight}</span>
        </div>
      </div>
    ),
    { ...ogSize, fonts },
  );
}
