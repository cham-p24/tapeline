/**
 * Press asset generator — renders the /press logo PNGs and the directory
 * gallery banner from the canonical brand geometry, reproducibly.
 *
 * Source of truth: frontend/public/favicon.svg —
 *   a #0a0a0a rounded square (radius 6/32) with a centred #3b82f6 pill bar
 *   (20x4 of 32, radius 2/32 = fully rounded). Any change to the brand mark
 *   must be made there first and re-rendered here (same contract as
 *   extension/icons/make-icons.js, which renders the toolbar icons from the
 *   identical geometry).
 *
 * Rendering engine: `next/og` (satori + resvg) — the SAME engine that renders
 * every OG card, /banner-x and /profile-square, so the wordmark on the gallery
 * banner is real Inter, pixel-consistent with the rest of the brand, and no
 * native image dependency (sharp) is added to the tree. Element trees are
 * plain satori objects rather than JSX so this stays a runnable .mjs script.
 *
 * Fonts: Inter 500/700 fetched from the same @fontsource jsdelivr mirror as
 * lib/og-fonts.ts (~30 KB per weight, network needed at generation time
 * only — the rendered PNGs are committed). Unlike the OG routes, a font
 * failure here ABORTS instead of degrading: committing an off-brand asset
 * silently is worse than failing loudly.
 *
 * Outputs (into frontend/public/press/):
 *   tapeline-logo-512.png          512x512 logo tile
 *   tapeline-logo-1024.png         1024x1024 logo tile
 *   tapeline-gallery-1270x760.png  G2/Capterra-style gallery banner
 *                                  (logo + wordmark + one-line descriptor)
 *
 * Usage:  cd frontend && node scripts/make-press-assets.mjs
 */

// "next/og.js" rather than "next/og": next's package.json exports map only
// carries the extensioned specifier for plain-node ESM resolution.
import { ImageResponse } from "next/og.js";
import { writeFileSync, mkdirSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const OUT_DIR = join(dirname(fileURLToPath(import.meta.url)), "..", "public", "press");

/* ---------------------------------------------------------------- *
 * Brand constants — mirror favicon.svg exactly.
 * ---------------------------------------------------------------- */
const GROUND = "#0a0a0a"; // rounded-square ground
const BAR = "#3b82f6"; // pill bar accent (blue-500)
// 32-unit grid from favicon.svg: ground radius 6, bar 20x4 (radius 2).
const GRID = 32;
const GROUND_RADIUS = 6 / GRID;
const BAR_W = 20 / GRID;
const BAR_H = 4 / GRID;

// Same descriptor as the /banner-x tagline — one line, descriptive only.
const DESCRIPTOR = "One score per US stock. Public scorecard. Named factors.";

/** Minimal satori element helper (satori takes plain objects, not JSX). */
const el = (type, style, children = undefined) => ({
  type,
  props: children === undefined ? { style } : { style, children },
});

/** The brand mark at a given pixel size, geometry scaled off the 32-grid. */
function mark(size) {
  return el(
    "div",
    {
      width: `${size}px`,
      height: `${size}px`,
      background: GROUND,
      borderRadius: `${size * GROUND_RADIUS}px`,
      display: "flex",
      alignItems: "center",
      justifyContent: "center",
    },
    el("div", {
      width: `${size * BAR_W}px`,
      height: `${size * BAR_H}px`,
      background: BAR,
      borderRadius: "999px",
      display: "flex",
    }),
  );
}

/** Gallery banner: mark + wordmark centred, descriptor beneath. Palette and
 *  type treatment mirror app/banner-x/route.tsx so the cross-surface brand
 *  reads consistent. */
function banner(width, height) {
  return el(
    "div",
    {
      width: "100%",
      height: "100%",
      background: "linear-gradient(135deg, #07090c 0%, #0d1218 50%, #0a0f15 100%)",
      display: "flex",
      flexDirection: "column",
      alignItems: "center",
      justifyContent: "center",
      fontFamily: "Inter, system-ui, sans-serif",
      color: "#f4f4f5",
      position: "relative",
    },
    [
      // Accent glow, top-right — same device as /banner-x and the OG cards.
      el("div", {
        position: "absolute",
        top: "-260px",
        right: "-260px",
        width: "760px",
        height: "760px",
        background: "radial-gradient(circle, rgba(59, 130, 246, 0.20) 0%, rgba(59, 130, 246, 0) 70%)",
        display: "flex",
      }),
      // Mark + wordmark.
      el(
        "div",
        { display: "flex", alignItems: "center", gap: "44px", marginBottom: "40px" },
        [
          mark(150),
          el(
            "span",
            {
              fontSize: "132px",
              fontWeight: 700,
              letterSpacing: "-0.04em",
              lineHeight: 1,
            },
            "Tapeline",
          ),
        ],
      ),
      // One-line descriptor.
      el(
        "div",
        {
          fontSize: "38px",
          fontWeight: 500,
          color: "#a1a1aa",
          letterSpacing: "-0.02em",
          lineHeight: 1.2,
          display: "flex",
        },
        DESCRIPTOR,
      ),
    ],
  );
}

/* ---------------------------------------------------------------- *
 * Fonts — same mirror + weights as lib/og-fonts.ts, but hard-fail.
 * ---------------------------------------------------------------- */
const FONTSOURCE_BASE = "https://cdn.jsdelivr.net/npm/@fontsource/inter@5.0.16/files";

async function loadInterOrDie(weights) {
  return Promise.all(
    weights.map(async (weight) => {
      const url = `${FONTSOURCE_BASE}/inter-latin-${weight}-normal.woff`;
      const res = await fetch(url);
      if (!res.ok) throw new Error(`Inter ${weight} fetch failed (${res.status}) — refusing to render off-brand text`);
      return { name: "Inter", data: await res.arrayBuffer(), weight, style: "normal" };
    }),
  );
}

async function render(element, width, height, fonts, file) {
  const image = new ImageResponse(element, { width, height, fonts });
  const buf = Buffer.from(await image.arrayBuffer());
  writeFileSync(join(OUT_DIR, file), buf);
  console.log(`${file}  ${width}x${height}  ${buf.length} bytes`);
}

mkdirSync(OUT_DIR, { recursive: true });
const fonts = await loadInterOrDie([500, 700]);

// Logo tiles need no text, but passing fonts is harmless.
await render(mark(512), 512, 512, fonts, "tapeline-logo-512.png");
await render(mark(1024), 1024, 1024, fonts, "tapeline-logo-1024.png");
// 1270x760 is the native (1x) size of the G2/Capterra gallery slot — and of
// the four committed product screenshots (which are the same frame @2x).
await render(banner(1270, 760), 1270, 760, fonts, "tapeline-gallery-1270x760.png");
