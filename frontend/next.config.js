/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,

  // Self-hosted output for the Fly.io deployment — a Vercel-independent
  // host so the site is never hostage to one provider's billing again
  // (added 2026-06-13 after a Vercel Hobby pause took the whole site down
  // with HTTP 402). `standalone` emits a minimal node server + traced deps
  // that the Dockerfile copies into a slim runner image. No-op on Vercel.
  output: "standalone",

  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/api/:path*`,
      },
    ];
  },

  // Permanent redirects for two specific Search Console 404s:
  //
  // - /favicon.ico → /favicon.svg
  //   Browsers + Googlebot fetch /favicon.ico at the document root regardless
  //   of <link rel="icon"> hints. We only ship SVG, so the .ico fetch 404'd
  //   and surfaced in GSC. 308 redirect resolves to a 200 SVG that every
  //   modern browser + Googlebot accepts. Permanent so search engines learn
  //   the canonical and stop re-fetching the .ico.
  async redirects() {
    return [
      { source: "/favicon.ico", destination: "/favicon.svg", permanent: true },

      // Bare section roots → their real hub/index.
      //
      // Each of these is a programmatic cluster with only [param] children and
      // NO index route, so a type-in, a truncated deep URL, or a stray backlink
      // to the bare parent hard-404'd. None are advertised in sitemap.ts or
      // linked internally, so there's no link equity to preserve — this is
      // purely "don't dead-end the visitor / keep the GSC 404 bucket clean".
      // Mirrors the /t and /t/ → /signals redirect already in middleware.ts.
      // Exact-match sources: "/sector" never catches "/sector/{slug}".
      { source: "/sector", destination: "/sectors", permanent: true },
      { source: "/signal", destination: "/signals", permanent: true },
      { source: "/blog/ticker", destination: "/blog", permanent: true },
      { source: "/embed/score", destination: "/embed", permanent: true },

      // /badge is the bare parent of /badge/[symbol] — an SVG score-badge
      // asset route (route.ts, image/svg+xml), not a page. A developer who
      // strips the symbol off an embedded badge URL lands here; send them to
      // /embed, which documents the badge. Permanent: the embed hub is stable.
      // Exact-match: never catches /badge/{symbol}, so the SVG keeps serving.
      { source: "/badge", destination: "/embed", permanent: true },

      // Temporary (307) for these two: a proper /compare and /best-stocks-for
      // index hub is a plausible future build, so don't let browsers/Google
      // permanently cache the fallback target. /best-stock-scanners is the
      // existing scanner-comparison roundup; /signals is the live universe.
      { source: "/compare", destination: "/best-stock-scanners", permanent: false },
      { source: "/best-stocks-for", destination: "/signals", permanent: false },
    ];
  },

  // Production-grade security headers — same set Vercel + Linear ship.
  // CSP is intentionally NOT set yet because TradingView's embed + Cloudflare
  // Turnstile + the API rewrite all need an audit before we can pin hashes.
  // The headers below are safe to ship today and close the easy attack vectors.
  async headers() {
    const securityHeaders = [
      // Force HTTPS for 2 years; opt browsers in to the HSTS preload list.
      { key: "Strict-Transport-Security", value: "max-age=63072000; includeSubDomains; preload" },
      // Block clickjacking — no third party can iframe Tapeline.
      { key: "X-Frame-Options", value: "DENY" },
      // Stop browsers from MIME-sniffing responses into the wrong type.
      { key: "X-Content-Type-Options", value: "nosniff" },
      // Don't leak referrers to other origins.
      { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
      // Disallow access to powerful APIs we don't use.
      {
        key: "Permissions-Policy",
        value: "camera=(), microphone=(), geolocation=(), interest-cohort=()",
      },
      // Older XSS protection — modern browsers ignore but legacy ones still
      // honour it; cost is zero.
      { key: "X-XSS-Protection", value: "1; mode=block" },
    ];
    return [
      {
        source: "/:path*",
        headers: securityHeaders,
      },
      // Keep Next's auto-generated social-card image routes OUT of Google's
      // index without Disallow'ing them in robots.txt (a Disallow also blocks
      // facebookexternalhit / Twitterbot / LinkedInBot / Slackbot, which strips
      // the preview image from every shared link). `X-Robots-Tag: noindex`
      // lets scrapers fetch the PNG (cards render) while telling Google not to
      // index the route — and it actively drains the existing "Crawled - not
      // indexed" entries. `:path*` matches the dynamic routes at any depth
      // (/opengraph-image, /t/AAPL/opengraph-image, /blog/[slug]/..., etc.).
      // The query-string cache-buster Next appends doesn't affect path match.
      {
        source: "/opengraph-image",
        headers: [{ key: "X-Robots-Tag", value: "noindex" }],
      },
      {
        source: "/:path*/opengraph-image",
        headers: [{ key: "X-Robots-Tag", value: "noindex" }],
      },
      // No twitter-image routes exist today (Next reuses opengraph-image for
      // twitter:image), but cover the path defensively so any future
      // twitter-image route is noindexed automatically, matching the OG rule.
      {
        source: "/twitter-image",
        headers: [{ key: "X-Robots-Tag", value: "noindex" }],
      },
      {
        source: "/:path*/twitter-image",
        headers: [{ key: "X-Robots-Tag", value: "noindex" }],
      },
    ];
  },
};

module.exports = nextConfig;
