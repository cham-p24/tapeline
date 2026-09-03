import { NextResponse, type NextRequest } from "next/server";
import { SECTOR_LEGACY_REDIRECTS } from "./app/sector/sectors";

/**
 * Tapeline edge middleware — two responsibilities:
 *
 * 1. Locale detection on every page request. Reads Vercel's edge geo
 *    data (request.geo.country — automatically populated, no API call)
 *    and sets a `tapeline_locale` cookie with the visitor's country-
 *    appropriate BCP 47 locale tag (e.g. "en-AU", "en-US", "de-DE").
 *    Override of the browser locale because Chrome's default install
 *    on AU/UK/EU often reports "en-US" via navigator.language even
 *    when the user is in Sydney — produces M/D/YYYY for an Australian,
 *    which is confusing. Reading request country fixes that.
 *
 * 2. Auth gate on /app/*. Redirects unauthenticated users to /signin.
 *    Cookie-level only (fast, no DB hit); backend enforces tier gates
 *    independently so this is defence-in-depth.
 *
 * IndexNow key serving: the key file lives at
 *   frontend/public/<KEY>.txt
 * and Vercel's static-asset path serves it directly. The previous
 * env-var-based dynamic handler was removed on 2026-05-12 because the
 * matcher was swallowing the static file before it could serve.
 */

// Country → BCP 47 locale. English-speaking countries get their own
// regional English; non-English countries get the dominant local
// language. Anything we don't recognise falls back to en-GB which
// uses unambiguous DD MMM YYYY format that everyone reads correctly.
const COUNTRY_LOCALE: Record<string, string> = {
  AU: "en-AU", US: "en-US", GB: "en-GB", CA: "en-CA", IE: "en-IE",
  NZ: "en-NZ", IN: "en-IN", ZA: "en-ZA", SG: "en-SG", HK: "en-HK",
  DE: "de-DE", AT: "de-AT", CH: "de-CH",
  FR: "fr-FR", BE: "fr-BE",
  ES: "es-ES", MX: "es-MX", AR: "es-AR",
  IT: "it-IT",
  NL: "nl-NL",
  PL: "pl-PL",
  PT: "pt-PT", BR: "pt-BR",
  SE: "sv-SE", NO: "no-NO", DK: "da-DK", FI: "fi-FI",
  JP: "ja-JP", KR: "ko-KR",
  CN: "zh-CN", TW: "zh-TW",
  RU: "ru-RU", UA: "uk-UA",
  TR: "tr-TR",
  AE: "ar-AE", SA: "ar-SA",
};

function localeForCountry(country: string | undefined): string {
  if (!country) return "en-GB";
  return COUNTRY_LOCALE[country.toUpperCase()] || "en-GB";
}

/**
 * The 18 competitor comparison pages, removed 2026-09-03 on the founder's
 * decision. Their URLs serve **410 Gone**, not 404.
 *
 * Why 410 and not a silent 404: these were in the sitemap and indexed. A 404
 * tells a crawler "maybe this is temporary, come back"; a 410 tells it "this is
 * intentionally gone, delist it". Google treats 410 as a slightly stronger
 * removal signal and stops retrying sooner. Neither leaks link equity anywhere,
 * which is correct — there is no successor page to send these to, and 301'ing
 * competitor-comparison traffic to /pricing or /compare would be a bait and
 * switch on the query intent.
 *
 * Why middleware rather than next.config: Next's `redirects()` cannot return a
 * status body, and these paths would otherwise fall through to the surviving
 * `/compare/[matchup]` dynamic route, which calls notFound() for a slug that
 * is not a ticker pair — a 404. This intercepts them first.
 *
 * Why they went: 0 of 10 instrumented signups came from the cluster while 4 of
 * 10 came from other programmatic content, and keeping claims about
 * competitors' pricing and terms accurate had already cost five separate
 * copy-correction sweeps across four months (#548, #686 and three others).
 * The stock-vs-stock cluster at /compare/[a]-vs-[b] is unaffected: it compares
 * two tickers on Tapeline's own score and makes no claim about a third party.
 */
const REMOVED_COMPARE_SLUGS = new Set([
  "benzinga-pro",
  "bloomberg-terminal",
  "finviz",
  "koyfin",
  "marketsmith",
  "robinhood",
  "seeking-alpha",
  "simply-wall-st",
  "stock-rover",
  "stockcharts",
  "tipranks",
  "trade-ideas",
  "tradingview",
  "trendspider",
  "wallstreetzen",
  "webull",
  "yahoo-finance",
  "zacks",
]);

export function handleRemovedComparePage(request: NextRequest) {
  const m = /^\/compare\/([^/]+)\/?$/.exec(request.nextUrl.pathname);
  if (!m) return null;
  if (!REMOVED_COMPARE_SLUGS.has(m[1].toLowerCase())) return null;
  return new NextResponse(
    "This comparison page has been removed. The public track record is at " +
      "https://tapeline.io/scorecard",
    {
      status: 410,
      headers: {
        "Content-Type": "text/plain; charset=utf-8",
        // Belt and braces: a crawler that ignores the 410 still must not index.
        "X-Robots-Tag": "noindex",
      },
    },
  );
}

export function middleware(request: NextRequest) {
  // Domain consolidation — legacy tapeline.app → canonical tapeline.io. Runs
  // first so nothing else fires on the redirect hop.
  const apexHandled = handleApexDomainRedirect(request);
  if (apexHandled) return apexHandled;

  // Ticker route handling — three responsibilities (see handleTickerRoute):
  //   - Redirect bare /t and /t/ (no symbol) → 308 → /signals so the
  //     symbol-less root resolves instead of hard-404'ing
  //   - Case-normalize lowercase backlinks like /t/aapl → 308 → /t/AAPL
  //   - Redirect non-ticker /t/* URLs (template placeholders, garbage)
  //     to /search?q=<raw> instead of letting them 404
  // Any of these returns early so auth+locale don't run on the redirect.
  const tickerHandled = handleTickerRoute(request);
  if (tickerHandled) return tickerHandled;

  // Removed competitor comparison pages → 410 Gone. Must run BEFORE the page
  // router, or these fall into /compare/[matchup] and 404 instead.
  const goneHandled = handleRemovedComparePage(request);
  if (goneHandled) return goneHandled;

  // Sector slug redirect — old Yahoo Finance slugs (technology,
  // healthcare, financial-services, consumer-cyclical, etc.) 308 to the
  // new GICS slugs. Returns early so locale/auth don't fire on the
  // redirect hop.
  const sectorHandled = handleSectorRedirect(request);
  if (sectorHandled) return sectorHandled;

  const response = handleAuth(request);

  // Set/refresh the locale cookie on every response. Vercel injects
  // request.geo automatically on its edge runtime.
  const country = (request as { geo?: { country?: string } }).geo?.country;
  const existing = request.cookies.get("tapeline_locale")?.value;
  if (country) {
    const locale = localeForCountry(country);
    if (existing !== locale) {
      response.cookies.set("tapeline_locale", locale, {
        maxAge: 60 * 60 * 24 * 30, // 30 days
        sameSite: "lax",
        path: "/",
      });
      // Also expose the country for any client code that wants to
      // do its own locale logic (analytics, currency display etc.).
      response.cookies.set("tapeline_country", country.toUpperCase(), {
        maxAge: 60 * 60 * 24 * 30,
        sameSite: "lax",
        path: "/",
      });
    }
  }
  return response;
}

/**
 * Routes whose final path segment is a ticker symbol. Two jobs:
 *
 * 1. Case-normalize lowercase variants. /t/aapl → 308 → /t/AAPL.
 *    Next's dynamic segments are case-sensitive and our generated params +
 *    render path use uppercase; without this, every lowercase backlink
 *    404s and burns link equity.
 *
 * 2. Catch non-ticker garbage. /t/{search_term_string} (literal template
 *    placeholder from the Sitelinks SearchAction graph), /t/foo-bar,
 *    /t/$$$, etc. — these used to 404. Now they 308 to /search?q=<raw>
 *    so the searcher gets a sensible page AND GSC's "Not found (404)"
 *    report stops accumulating template-leak entries.
 *
 * Patterns covered (matched case-insensitively):
 *   /t/{SYMBOL}
 *   /scorecard/{SYMBOL}
 *   /blog/ticker/{SYMBOL}
 *
 * Valid ticker shape: 1-6 alpha + optional dot-suffix (BRK.B). Symbols
 * containing dots route via Next's static dispatch (matcher excludes
 * paths with dots), so this regex only sees no-dot paths in practice.
 *
 * SINGLE SEGMENT ONLY — the capture is ([^/]+), not (.+). A greedy (.+)
 * also swallowed nested metadata routes like /t/AAPL/opengraph-image
 * (raw = "AAPL/opengraph-image"), which fails VALID_TICKER_RE and got
 * 308'd to /search — silently breaking the og:image / twitter:image PNG
 * for EVERY per-ticker (and /blog/ticker) page (social-card previews on
 * X/LinkedIn/Slack/Facebook went imageless). Matching one segment lets
 * those image sub-routes fall through to Next so they render. Genuine
 * multi-segment garbage under /t/* now just 404s (negligibly rare) — a
 * fair trade for working social cards.
 */
export const TICKER_PREFIX_RE = /^\/(t|scorecard|blog\/ticker)\/([^/]+)$/;

/**
 * Ticker shape — MUST stay aligned with the backend's single source of truth,
 * `VALID_SYMBOL_RE = ^[A-Z][A-Z0-9.=/^-]{0,11}$` in
 * backend/app/services/symbols.py.
 *
 * This was `^[A-Z]{1,6}(\.[A-Z])?$`, far narrower than what the backend
 * actually serves. The backend deliberately admits class shares (BRK-B),
 * continuous futures (CL=F, ZC=F, RB=F) and index notation (^GSPC) —
 * ticker_freshness.py says these "must be kept", and there are backend tests
 * asserting BRK-B and CL=F are real servable symbols. /api/public/signals
 * returns them, so sitemap.ts emitted <loc>/t/CL=F</loc> and /stocks linked
 * to them, while THIS regex rejected them and 308'd to /search — which
 * robots.ts Disallows. Every such URL landed in GSC as "Page with redirect"
 * onto a target "Blocked by robots.txt": permanently unindexable, canonical
 * never served. Verified in production before the fix:
 *
 *   /t/BRK-B → 308 /search?q=BRK-B      (api /api/ticker/BRK-B → 200)
 *   /t/CL=F  → 308 /search?q=CL%3DF     (api /api/ticker/CL=F  → 200)
 *
 * `/` is omitted from the class: TICKER_PREFIX_RE captures a single segment
 * ([^/]+), so a symbol containing a slash can never reach here anyway.
 * Symbols containing a dot never reach the middleware at all — the matcher
 * excludes any path with a '.' — which is why the dot case was never noticed.
 */
export const VALID_TICKER_RE = /^[A-Z][A-Z0-9.=^-]{0,11}$/;

/**
 * Next.js metadata routes that sit DIRECTLY under a ticker-prefix segment
 * and are therefore indistinguishable from a one-segment ticker path.
 *
 * The single-segment capture above already protects NESTED metadata routes
 * (/t/AAPL/opengraph-image is two segments, so it never matches). It does
 * NOT protect a section's OWN card: /scorecard/opengraph-image is one
 * segment, fails VALID_TICKER_RE, and was 308'd to /search — so every share
 * of /scorecard on X, LinkedIn, Slack or Facebook rendered with no image at
 * all. That is the page the whole transparency pitch points people at.
 *
 * Matched case-insensitively, with an optional Next build hash suffix
 * (opengraph-image-1a2b3c4d). Falling through returns the real PNG.
 */
export const METADATA_ROUTE_RE =
  /^(opengraph-image|twitter-image|icon|apple-icon)(-[a-z0-9]+)?$/i;

/**
 * Canonical-host consolidation. The canonical host is bare `tapeline.io`.
 * Non-canonical hosts must not serve a second indexable copy (that splits
 * SEO/link equity):
 *   - `www.tapeline.io` — resolves to the same Fly app and today returns a
 *     200 duplicate; a canonical tag softens it, but a 308 is the proper fix.
 *   - the legacy `tapeline.app` / `www.tapeline.app` domain.
 * Any request that reaches the app on one of these is 308'd (permanent) to the
 * same path on bare `tapeline.io`, query preserved. Returns null for the
 * canonical host and everything else, so there is no redirect loop. Pure +
 * exported so the decision is unit-tested without HTTP plumbing.
 */
export function apexRedirectTarget(
  host: string | null,
  pathname: string,
  search: string,
): string | null {
  const h = (host ?? "").toLowerCase();
  if (
    h === "www.tapeline.io" ||
    h === "tapeline.app" ||
    h === "www.tapeline.app"
  ) {
    return `https://tapeline.io${pathname}${search}`;
  }
  return null;
}

function handleApexDomainRedirect(request: NextRequest): NextResponse | null {
  const target = apexRedirectTarget(
    request.headers.get("host"),
    request.nextUrl.pathname,
    request.nextUrl.search,
  );
  return target ? NextResponse.redirect(new URL(target), 308) : null;
}

/**
 * What the middleware decides to do with a ticker-prefix path.
 *
 * Exported and PURE so the tests can exercise the real branch order. The test
 * suite previously kept its own `decide()` helper that "mirrors" this logic;
 * it imported the regexes but duplicated the branches, so when the branch
 * order changed here the copy silently kept testing the old shape. Anything
 * that matters about the ordering must live in this one function.
 */
export type TickerRouteDecision =
  | { kind: "fall-through" }
  | { kind: "signals-root" }
  | { kind: "search"; q: string }
  | { kind: "canonicalise"; to: string };

export function tickerRouteDecision(pathname: string): TickerRouteDecision {
  // Bare ticker-section root — /t and /t/ carry no symbol, so the [symbol]
  // dynamic route can't match and Next serves a hard 404. GSC logged /t in
  // its "Not found (404)" bucket. Redirect to the public signals universe so
  // the URL resolves (308 → 200) and the 404 clears on Validate Fix.
  // Exact-match ONLY: /scorecard and /blog/ticker are real index pages served
  // by their own route files and must never be caught here.
  if (pathname === "/t" || pathname === "/t/") return { kind: "signals-root" };

  const m = TICKER_PREFIX_RE.exec(pathname);
  if (!m) return { kind: "fall-through" };
  const [, prefix, raw] = m;

  const upper = raw.toUpperCase();

  // A section's OWN metadata route, checked BEFORE the ticker test — but only
  // for HYPHENATED names.
  //
  // Widening VALID_TICKER_RE to admit class shares (BRK-B) makes the hyphen a
  // legal ticker character, and `apple-icon` is 10 chars, so it now matches the
  // ticker shape. Left to the post-test check below it would be treated as the
  // ticker "APPLE-ICON" and 308'd to /scorecard/APPLE-ICON, breaking that PNG.
  // (`opengraph-image` at 15 and `twitter-image` at 13 exceed the 12-char
  // limit, so apple-icon is the only real collision today — but keying the
  // rule on the hyphen rather than one name keeps it true if the list grows.)
  //
  // Restricting this to hyphenated names preserves the original guarantee that
  // a real symbol is never shadowed: bare `ICON` has no hyphen, so it still
  // falls through to the ticker path and is handled as the ticker ICON.
  // Genuine hyphenated tickers (BRK-B, RDS-A) don't match METADATA_ROUTE_RE.
  if (raw.includes("-") && METADATA_ROUTE_RE.test(raw)) return { kind: "fall-through" };

  // Non-ticker symbol (template placeholder, garbage, or just gibberish).
  // Send to /search?q=<raw> so the visitor lands somewhere useful and
  // Google can crawl a 200 instead of a 404.
  if (!VALID_TICKER_RE.test(upper)) {
    // ...unless it's this section's OWN non-hyphenated metadata route (`icon`).
    // Checked here, after the ticker-shape test, so a real symbol is never
    // shadowed by a metadata name that happens to look like one.
    if (METADATA_ROUTE_RE.test(raw)) return { kind: "fall-through" };
    // Don't URL-encode the placeholder twice — pass through whatever the
    // crawler had. If raw is literally "{search_term_string}", that's what
    // /search shows back as the "didn't look like a ticker" hint.
    return { kind: "search", q: raw };
  }

  // Valid ticker but wrong case → canonicalise.
  const canonical = `/${prefix}/${upper}`;
  if (canonical === pathname) return { kind: "fall-through" };
  return { kind: "canonicalise", to: canonical };
}

function handleTickerRoute(request: NextRequest): NextResponse | null {
  const pathname = request.nextUrl.pathname;
  const decision = tickerRouteDecision(pathname);

  if (decision.kind === "fall-through") return null;
  if (decision.kind === "signals-root") {
    return NextResponse.redirect(new URL("/signals", request.url), 308);
  }
  if (decision.kind === "search") {
    const target = new URL("/search", request.url);
    target.searchParams.set("q", decision.q);
    return NextResponse.redirect(target, 308);
  }

  const canonical = decision.to;
  if (canonical === pathname) return null;
  const target = new URL(canonical, request.url);
  // Preserve query + hash so links like /t/aapl?ref=hn keep their UTM.
  target.search = request.nextUrl.search;
  target.hash = request.nextUrl.hash;
  return NextResponse.redirect(target, 308);
}

/**
 * Yahoo → GICS sector-slug 308 redirect. The frontend SECTORS list was
 * migrated to GICS on 2026-05-22 to match the backend's
 * canonical_sector() output. Old URLs (technology, healthcare, etc.)
 * already exist in Google's index and in external backlinks — 308 to
 * preserve link equity and stop those landings from 404'ing.
 */
function handleSectorRedirect(request: NextRequest): NextResponse | null {
  const pathname = request.nextUrl.pathname;
  // Match /sector/<slug> exactly (one segment after /sector/, no trailing path).
  const m = /^\/sector\/([^/]+)\/?$/.exec(pathname);
  if (!m) return null;
  const oldSlug = m[1].toLowerCase();
  const newSlug = SECTOR_LEGACY_REDIRECTS[oldSlug];
  if (!newSlug || newSlug === oldSlug) return null;
  const target = new URL(`/sector/${newSlug}`, request.url);
  target.search = request.nextUrl.search;
  target.hash = request.nextUrl.hash;
  return NextResponse.redirect(target, 308);
}

function handleAuth(request: NextRequest) {
  const pathname = request.nextUrl.pathname;

  // Auth redirect for /app/*.
  const isAppRoute = pathname.startsWith("/app");
  if (!isAppRoute) return NextResponse.next();

  const session = request.cookies.get("tapeline_session")?.value;
  if (!session) {
    const signinUrl = new URL("/signin", request.url);
    signinUrl.searchParams.set("next", pathname);
    return NextResponse.redirect(signinUrl);
  }
  return NextResponse.next();
}

export const config = {
  // Run on every non-static page (locale + auth need to apply to all
  // page requests). The exclusion list keeps Vercel's static-asset
  // path uninterrupted — including the IndexNow key file in /public.
  matcher: ["/((?!_next/static|_next/image|favicon.ico|.*\\..*).*)"],
};
