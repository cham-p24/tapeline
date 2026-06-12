/**
 * /badge/[symbol] — Shields.io-style flat SVG badge for GitHub READMEs.
 *
 * GitHub markdown sanitises iframes (security policy), so the
 * /embed/score/[symbol] widget can't render in READMEs. SVG images
 * DO render — that's what makes shields.io / github-readme-stats work.
 * This route serves the same Tapeline-Score-badge concept as a
 * cacheable static-ish SVG that any dev can drop into a project README:
 *
 *   ![Tapeline Score](https://tapeline.io/badge/NVDA)
 *
 * Why this matters for backlinks: every GitHub README that embeds the
 * badge produces a link to tapeline.io. GitHub's HTML for README image
 * tags wraps each image in a clickable <a> pointing at the image URL —
 * which means clicking the badge in a rendered README lands the
 * visitor at /badge/{TICKER}, which we 302-redirect... actually no, we
 * keep the image-only response so GitHub renders the SVG inline. The
 * link equity comes from the URL itself being on the README page
 * (Googlebot follows the src attribute when indexing the README).
 *
 * URL params:
 *   ?theme=dark — dark variant (matches site dark theme)
 *   ?label=X    — override the left-side label (default "tapeline")
 *
 * Cacheable: server caches the ticker fetch 60s; CDN caches the SVG
 * response 60s with 300s stale-while-revalidate. Even popular embeds
 * never hit the API more than once a minute.
 */
import { NextRequest } from "next/server";

const API_BASE =
  process.env.NEXT_PUBLIC_API_URL ||
  process.env.API_URL ||
  "https://api.tapeline.io";

type TickerData = {
  symbol: string;
  score: number | null;
  signal: string | null;
};

async function fetchTickerForBadge(symbol: string): Promise<TickerData | null> {
  try {
    const res = await fetch(`${API_BASE}/api/ticker/${symbol.toUpperCase()}`, {
      next: { revalidate: 1800 },
    });
    if (!res.ok) return null;
    return (await res.json()) as TickerData;
  } catch {
    return null;
  }
}

// Signal label → flat hex colour. Matches the iframe widget so a site
// using both /embed and /badge for the same ticker reads consistent.
function signalColor(signal: string | null): string {
  const s = (signal ?? "").toLowerCase();
  if (s.includes("high conviction")) return "#16a34a";
  if (s.includes("strong setup")) return "#22c55e";
  if (s.includes("constructive")) return "#3b82f6";
  if (s.includes("neutral")) return "#71717a";
  if (s.includes("caution")) return "#f59e0b";
  if (s.includes("weak")) return "#dc2626";
  return "#52525b";
}

// Short signal label used in the badge (full names like "HIGH CONVICTION"
// don't fit in a flat badge). Score number is the primary signal anyway.
function signalShort(signal: string | null): string {
  const s = (signal ?? "").toUpperCase();
  if (s.includes("HIGH CONVICTION")) return "HIGH";
  if (s.includes("STRONG SETUP")) return "STRONG";
  if (s.includes("CONSTRUCTIVE")) return "OK";
  if (s.includes("NEUTRAL")) return "NEUTRAL";
  if (s.includes("CAUTION")) return "CAUTION";
  if (s.includes("WEAK")) return "WEAK";
  return "—";
}

// Rough character-width estimator for the SVG layout. Shields.io uses
// per-glyph widths for a real font; this is the same approximation that
// works for the default sans-serif fallback browsers use to render
// shields.io badges in practice (Verdana metrics, scaled).
function textWidth(s: string, fontSize = 11): number {
  // Avg lowercase Verdana 11px ≈ 6.5px; uppercase ≈ 7.5px; digits 7px.
  // Mix is fine for the very short label + signal text we render.
  return Math.ceil(s.length * fontSize * 0.62);
}

function buildBadgeSvg(
  symbol: string,
  data: TickerData | null,
  opts: { theme: string; label: string },
): string {
  const isDark = opts.theme === "dark";
  const leftBg = isDark ? "#0a0d14" : "#27272a"; // dark muted grey
  const leftFg = "#fafafa";
  const score = data?.score;
  const scoreStr = score != null ? score.toFixed(0) : "—";
  const sig = signalShort(data?.signal ?? null);
  const rightBg = data ? signalColor(data.signal) : "#52525b";
  const rightFg = "#fafafa";

  // Layout: [ symbol · label | score · signal ]
  // Left segment: "TAPELINE NVDA"
  // Right segment: "76 STRONG"
  const leftText = `${opts.label} ${symbol}`;
  const rightText = data ? `${scoreStr} ${sig}` : "—";
  const padX = 8;
  const leftW = textWidth(leftText) + padX * 2;
  const rightW = textWidth(rightText) + padX * 2;
  const totalW = leftW + rightW;
  const h = 20;
  const r = 3; // border radius (shields.io flat style)

  // Build SVG. Inline styles + Verdana fallback chain (matches shields.io,
  // ensures consistent rendering across GitHub / GitLab / Bitbucket /
  // generic markdown renderers).
  return `<svg xmlns="http://www.w3.org/2000/svg" width="${totalW}" height="${h}" role="img" aria-label="Tapeline Score for ${symbol}: ${scoreStr}">
  <title>Tapeline Score for ${symbol}: ${scoreStr} (${sig})</title>
  <linearGradient id="s" x2="0" y2="100%">
    <stop offset="0" stop-color="#fff" stop-opacity=".06"/>
    <stop offset="1" stop-opacity=".15"/>
  </linearGradient>
  <clipPath id="r"><rect width="${totalW}" height="${h}" rx="${r}" fill="#fff"/></clipPath>
  <g clip-path="url(#r)">
    <rect width="${leftW}" height="${h}" fill="${leftBg}"/>
    <rect x="${leftW}" width="${rightW}" height="${h}" fill="${rightBg}"/>
    <rect width="${totalW}" height="${h}" fill="url(#s)"/>
  </g>
  <g fill="${leftFg}" text-anchor="middle" font-family="Verdana,Geneva,DejaVu Sans,sans-serif" font-size="11">
    <text x="${leftW / 2}" y="15" fill="#000" fill-opacity=".3">${leftText}</text>
    <text x="${leftW / 2}" y="14" fill="${leftFg}">${leftText}</text>
    <text x="${leftW + rightW / 2}" y="15" fill="#000" fill-opacity=".3">${rightText}</text>
    <text x="${leftW + rightW / 2}" y="14" fill="${rightFg}">${rightText}</text>
  </g>
</svg>`;
}

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ symbol: string }> },
) {
  const { symbol } = await params;
  // Accept both /badge/NVDA and /badge/NVDA.svg (some markdown renderers
  // require the .svg extension to be confident the URL is an image).
  const sym = symbol.toUpperCase().replace(/\.SVG$/, "");
  const url = new URL(request.url);
  const theme = url.searchParams.get("theme") === "dark" ? "dark" : "light";
  const label = url.searchParams.get("label") || "tapeline";

  // Validate ticker — reject obvious junk early so we don't waste a
  // backend roundtrip.
  if (!/^[A-Z][A-Z0-9.-]{0,9}$/.test(sym)) {
    const errSvg = buildBadgeSvg(sym.slice(0, 10), null, { theme, label });
    return new Response(errSvg, {
      status: 200,
      headers: {
        "Content-Type": "image/svg+xml; charset=utf-8",
        "Cache-Control": "public, s-maxage=3600, stale-while-revalidate=86400",
      },
    });
  }

  const data = await fetchTickerForBadge(sym);
  const svg = buildBadgeSvg(sym, data, { theme, label });

  return new Response(svg, {
    status: 200,
    headers: {
      "Content-Type": "image/svg+xml; charset=utf-8",
      // 60s cache on CDN; 5min stale-while-revalidate so even hot tickers
      // never hammer the backend.
      "Cache-Control": "public, s-maxage=60, stale-while-revalidate=300",
      // Allow embedding from any origin (this is the point of the badge).
      "Access-Control-Allow-Origin": "*",
    },
  });
}
