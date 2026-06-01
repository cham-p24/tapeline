/**
 * Blog-ticker share card — reuses the canonical /t/[symbol] OG renderer.
 *
 * Why this file must exist: /blog/ticker/[symbol] ("Is {SYM} a Buy in
 * 2026?") is an indexable SEO content page that WANTS a 1200x630 score
 * card for share previews AND declares one in its Article JSON-LD
 *   imageUrl: https://tapeline.io/blog/ticker/{SYM}/opengraph-image
 * Next.js only auto-injects og:image / twitter:image meta (and serves that
 * PNG) when an opengraph-image route file is co-located in the segment.
 * There wasn't one here, so the page emitted NO image meta and the JSON-LD
 * image 404'd — every blog-ticker share rendered imageless and the Article
 * rich-result image variant never unlocked. (Before the middleware
 * single-segment fix it was worse: /blog/ticker/{SYM}/opengraph-image
 * 308'd to /search.)
 *
 * Rather than duplicate ~290 lines of card JSX — which would drift from the
 * /t/ card — import that component and re-emit it here. The route-segment
 * config (runtime/size/contentType/alt) is declared locally because Next
 * statically analyses these in the route file itself; they can't be
 * inherited from the imported module. The card's corner shows
 * tapeline.io/t/{SYM}, which is fine: it's the canonical page for the same
 * symbol, and both PNGs carry X-Robots-Tag: noindex via next.config.js.
 */
import TickerOgImage from "../../../t/[symbol]/opengraph-image";

export const runtime = "edge";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";
export const alt = "Tapeline Score for this ticker";

export default function Image(props: { params: Promise<{ symbol: string }> }) {
  return TickerOgImage(props);
}
