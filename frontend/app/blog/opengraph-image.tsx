/**
 * Brand OG card for the Blog index page.
 *
 * This public, indexable page uses pageMeta() (lib/seo.ts), which sets a
 * summary_large_image twitter card but attaches NO image unless the page
 * passes ogImage or co-locates an opengraph-image route. It had neither,
 * and Next does not cascade the root opengraph-image into child segments,
 * so the share card rendered blank (verified live 2026-06-01). Re-emit the
 * root brand card so this page ships a real card instead of a blank one.
 * (Individual posts at /blog/[slug] already have their own card; this is
 * the /blog index only.) The PNG inherits X-Robots-Tag: noindex from the
 * next.config.js per-path opengraph-image header rule.
 */
import RootOgImage from "../opengraph-image";

export const runtime = "edge";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";
export const alt = "Tapeline — Read the tape. Live.";

export default function Image() {
  return RootOgImage();
}
