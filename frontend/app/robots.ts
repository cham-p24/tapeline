import type { MetadataRoute } from "next";

/**
 * robots.txt — tells crawlers what's indexable.
 *
 * Why this file exists (2026-05-24):
 *   GSC's "Page indexing > Crawled - currently not indexed" report showed
 *   474 pages stuck in the failure bucket. On inspection, many of those
 *   URLs were `/t/{TICKER}/opengraph-image?hash` — Next.js's automatically-
 *   generated OpenGraph image routes. Google was treating them as HTML
 *   candidates because the per-ticker page references them via
 *   `<meta property="og:image" content="...">`. The OG image routes return
 *   PNG bytes, not HTML, so Google's quality classifier rightly rejects
 *   them — but having 200+ junk URLs in the "Crawled not indexed" bucket
 *   was polluting the actual diagnostic signal for real /t/{TICKER} pages.
 *
 * Correction (2026-06-01):
 *   The original fix Disallow'd the opengraph-image / twitter-image route
 *   paths here, with a comment claiming social-card scrapers fetch og:image
 *   "regardless" of robots.txt. That premise is WRONG: facebookexternalhit,
 *   Twitterbot, LinkedInBot and Slackbot all honour robots.txt, so the
 *   `User-agent: *` Disallow stripped the preview image from every shared
 *   Tapeline link — and because Next points BOTH og:image and twitter:image
 *   at the opengraph-image route (there are no separate twitter-image
 *   routes), it broke both card types. Those Disallows are now removed and
 *   the same goal — keep the PNG routes out of Google's index — is achieved
 *   with `X-Robots-Tag: noindex` set on those routes in next.config.js
 *   headers(). noindex lets scrapers fetch the image (cards work) while
 *   telling Google not to index it, and actively drains the existing
 *   "Crawled - not indexed" entries (a Disallow only stops re-crawling).
 *
 * Also closes /api/* and /app/* (gated, auth-required) for completeness.
 */
export default function robots(): MetadataRoute.Robots {
  const base = process.env.NEXT_PUBLIC_APP_URL || "https://tapeline.io";

  return {
    rules: [
      {
        userAgent: "*",
        allow: "/",
        disallow: [
          // Backend API surface — not for crawlers.
          "/api/",
          // Authenticated app shell — already noindex via per-page meta, but
          // belt-and-suspenders for crawlers that don't render JS.
          "/app/",
          // Auth surfaces.
          "/signin",
          "/signup/welcome",
          // NOTE (2026-06-01): the opengraph-image / twitter-image routes are
          // deliberately NO LONGER Disallow'd — a crawl-block also blocks the
          // social-card scrapers (they honour robots.txt) and broke share-card
          // previews. They now carry `X-Robots-Tag: noindex` via
          // next.config.js headers() instead: fetchable by scrapers, ignored
          // by Google's index. See the file header for the full rationale.
          // Search-result-page surface — the /search?q= route is intentionally
          // present for the SearchAction sitelink (q matches a US ticker →
          // redirects). It shouldn't be a crawl target on its own.
          "/search",
        ],
      },
    ],
    sitemap: `${base}/sitemap.xml`,
    host: base,
  };
}
