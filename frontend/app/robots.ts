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
 *   Disallowing the og-image route path keeps the og:image tag working
 *   (Google still fetches it for social cards via the OG protocol — that
 *   path uses a different user agent that respects og:image regardless)
 *   while removing it from the regular Googlebot crawl backlog.
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
          // Next.js OpenGraph image routes — they return PNG bytes, not HTML,
          // and Google was mis-indexing them as failed-to-index HTML pages.
          // Pattern covers every per-route `opengraph-image` Next emits.
          "/opengraph-image",
          "/*/opengraph-image",
          "/*/*/opengraph-image",
          "/*/*/*/opengraph-image",
          // Same for Twitter image routes (Next emits these alongside OG).
          "/twitter-image",
          "/*/twitter-image",
          "/*/*/twitter-image",
          "/*/*/*/twitter-image",
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
