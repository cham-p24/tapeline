/**
 * Server-only headers for our own SSR -> API calls.
 *
 * Every server-rendered page in the site makes its upstream API calls from a
 * single Fly egress IP, so they all share the backend's per-IP limit_api
 * bucket (120/min). One ticker page fans out to ~3 upstream calls, so ~40 cold
 * renders a minute drains it, after which the backend 429s its own frontend
 * and the page throws -> HTTP 500. Any bulk crawl trips it: the weekly SEO
 * audit reported ~1,534 "broken" URLs it had itself broken, and Googlebot
 * walking the ~8,400-page ticker sitemap would see the same 500s.
 *
 * INTERNAL_SSR_TOKEN is deliberately NOT prefixed NEXT_PUBLIC_, so it is only
 * ever readable in the server runtime and never inlined into a browser bundle.
 * When it is unset we send nothing and the backend applies its normal per-IP
 * limit — i.e. a missing secret degrades to current behaviour, it does not
 * silently disable rate limiting.
 */
export function ssrInternalHeaders(): Record<string, string> {
  // `window` is undefined only in the server runtime; belt-and-braces so this
  // can never attach the token to a browser-side fetch even if imported there.
  if (typeof window !== "undefined") return {};
  const token = process.env.INTERNAL_SSR_TOKEN;
  return token ? { "x-tapeline-internal": token } : {};
}
