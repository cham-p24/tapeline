/**
 * Embed-impression tracking for the two embeddable surfaces:
 *   - /badge/[symbol]        — shields.io-style SVG for GitHub READMEs
 *   - /embed/score/[symbol]  — iframe widget for blogs / Substacks
 *
 * Both exist to be rendered on OTHER people's sites, and both used to be
 * completely uninstrumented — every render was an invisible brand impression.
 * (/embed/score even carried a comment promising referrers would be
 * "aggregated later in analytics"; this is that.) Without it we cannot tell
 * whether the distribution loop works, which sites carry us, or which tickers
 * people actually embed.
 *
 * PRIVACY — hostname only, and the reduction happens HERE
 * ------------------------------------------------------
 * The browser's Referer on an embedded render is the full embedding page URL.
 * That URL's path and query can carry a search phrase, a document title, a
 * session token, or an account handle belonging to a third-party site. None of
 * that may leave this process, so `refererHost()` throws the whole URL away and
 * keeps the hostname — and the hostname is the ONLY field derived from the
 * request that we send. Same posture as the signup_referrer_host capture in
 * lib/utm.ts. (The backend re-normalises defensively; this is the first gate,
 * not the only one.)
 *
 * FAIL-OPEN — the render never waits on this
 * ------------------------------------------
 * `trackEmbedImpression` schedules the POST via `after()`, so the SVG / HTML is
 * already on the wire before the request is made. The POST has a short timeout,
 * swallows every error, and has no return value anybody acts on. If the backend
 * is down, slow, or 500ing, the badge still renders exactly as before. Even
 * `after()` itself is guarded: called outside a request scope it throws, and a
 * tracker must never be the reason a badge fails to render.
 *
 * COUNTS ARE DIRECTIONAL — do not "fix" the discrepancy
 * ----------------------------------------------------
 * The badge response is CDN-cached (s-maxage=60, stale-while-revalidate=300).
 * A render served from the CDN never reaches this code and is never counted, so
 * real impressions always exceed recorded ones. That trade is deliberate: cheap
 * cacheable embeds beat exact counts. Use the numbers for ranking and trend.
 * Do NOT add a cache-buster or a client-side beacon to reconcile them.
 */

import { after } from "next/server";

const API_BASE =
  process.env.NEXT_PUBLIC_API_URL ||
  process.env.API_URL ||
  "https://api.tapeline.io";

/** Our own hosts — an internal preview of the badge is not a distribution signal. */
const SELF_HOST_SUFFIX = "tapeline.io";

/** Loopback / dev hosts — a local render is not a distribution signal either. */
const LOCAL_HOSTS = new Set(["localhost", "127.0.0.1", "0.0.0.0", "::1", "[::1]"]);

/** Matches the backend column width (String(100)) and lib/utm.ts's cap. */
const MAX_HOST_LEN = 100;

/**
 * Reduce a Referer header to a storable host label, or null when the render
 * must not be counted (missing referer, our own site, localhost, junk).
 *
 * Only the hostname is ever returned — never the path, never the query.
 */
export function refererHost(referer: string | null | undefined): string | null {
  if (!referer) return null;
  const raw = referer.trim();
  if (!raw) return null;

  let host: string;
  try {
    // A Referer is always absolute, but tolerate a bare hostname too so the
    // same rules apply if a caller ever passes one.
    const url = new URL(raw.includes("://") ? raw : `https://${raw}`);
    host = url.hostname.toLowerCase().replace(/\.$/, "");
  } catch {
    return null;
  }
  if (!host) return null;

  // Treat www.example.com and example.com as one site.
  if (host.startsWith("www.")) host = host.slice(4);

  if (LOCAL_HOSTS.has(host)) return null;
  if (host.endsWith(".local") || host.endsWith(".localhost")) return null;
  if (host === SELF_HOST_SUFFIX || host.endsWith(`.${SELF_HOST_SUFFIX}`)) return null;
  // A dotless host is an intranet name or junk — never a site worth outreach.
  if (!host.includes(".")) return null;

  return host.slice(0, MAX_HOST_LEN);
}

/**
 * Fire-and-forget impression POST. Never throws, never returns anything the
 * caller acts on. Call it from `after()` so it runs AFTER the response is sent.
 *
 * `surface` is "badge" (the SVG route) or "iframe" (the widget page).
 */
export async function recordEmbedImpression(
  referer: string | null | undefined,
  symbol: string,
  surface: "badge" | "iframe",
): Promise<void> {
  try {
    const host = refererHost(referer);
    // No external embedding host → nothing to learn, don't spend the request.
    if (!host) return;

    await fetch(`${API_BASE}/api/embed/impression`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ host, symbol: symbol.toUpperCase(), surface }),
      // Never cache a write.
      cache: "no-store",
      // Short: this runs off the response path, but a wedged backend must not
      // hold a worker slot open indefinitely.
      signal: AbortSignal.timeout(2500),
    });
  } catch {
    // Analytics is never load-bearing. A failed count is invisible to the
    // visitor and strictly cheaper than a broken embed.
  }
}

/**
 * Schedule an impression to be counted AFTER the current response is sent.
 * This is what the embed surfaces call — it is synchronous, returns void, and
 * cannot throw.
 *
 * `after()` throws when there is no request scope (e.g. a unit test importing
 * the route handler directly, or a rendering mode that doesn't support it).
 * Swallowing that is the correct behaviour, not a test convenience: outside a
 * real request there is no impression to count, and a tracker must never be the
 * reason a badge fails to render.
 */
export function trackEmbedImpression(
  referer: string | null | undefined,
  symbol: string,
  surface: "badge" | "iframe",
): void {
  try {
    after(() => recordEmbedImpression(referer, symbol, surface));
  } catch {
    // No request scope → nothing to count. Render on.
  }
}
