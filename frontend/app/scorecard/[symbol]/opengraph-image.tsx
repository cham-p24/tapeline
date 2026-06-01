/**
 * Per-symbol scorecard share card — reuses the canonical /t/[symbol] OG
 * renderer.
 *
 * Why this file must exist: /scorecard/[symbol] ("{SYM} scorecard track
 * record") is an indexable (robots: index,follow) page and the product's
 * core trust artifact — every time {SYM} was a Tapeline top-10 pick, with
 * next-day return vs SPY. Its layout.tsx sets a summary_large_image twitter
 * card and its own openGraph object, but NEITHER carries an `images` field.
 * Next 14 does not deep-merge openGraph/twitter across segments (see
 * lib/seo.ts header), so those imageless objects REPLACE the inherited
 * defaults — and opengraph-image files do NOT cascade from the /scorecard
 * index into this nested [symbol] segment. Verified live: /scorecard/AAPL
 * emitted no og:image / twitter:image at all and /scorecard/AAPL/
 * opengraph-image 404'd, so every share rendered blank.
 *
 * Co-locating this route makes Next auto-inject og:image + twitter:image
 * pointing here AND serve the PNG. Mirrors the /blog/ticker/[symbol] fix:
 * re-emit the /t/[symbol] score card (zero JSX duplication, no drift). The
 * route-segment config is declared locally (Next analyses it in the route
 * file itself). The PNG inherits X-Robots-Tag: noindex from the existing
 * next.config.js /:path*/opengraph-image header rule. Card corner shows
 * tapeline.io/t/{SYM} — fine, the canonical page for the same symbol.
 *
 * (A bespoke track-record card — hit rate / median alpha — would be more
 * on-theme; deferred. A live score card beats a blank card today.)
 */
import TickerOgImage from "../../t/[symbol]/opengraph-image";

export const runtime = "edge";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";
export const alt = "Tapeline Score for this ticker";

export default function Image(props: { params: Promise<{ symbol: string }> }) {
  return TickerOgImage(props);
}
