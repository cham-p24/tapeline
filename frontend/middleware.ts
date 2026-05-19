import { NextResponse, type NextRequest } from "next/server";

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

export function middleware(request: NextRequest) {
  // Ticker route handling — two responsibilities (see handleTickerRoute):
  //   - Case-normalize lowercase backlinks like /t/aapl → 308 → /t/AAPL
  //   - Redirect non-ticker /t/* URLs (template placeholders, garbage)
  //     to /search?q=<raw> instead of letting them 404
  // Either of these returns early so auth+locale don't run on the redirect.
  const tickerHandled = handleTickerRoute(request);
  if (tickerHandled) return tickerHandled;

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
 */
const TICKER_PREFIX_RE = /^\/(t|scorecard|blog\/ticker)\/(.+)$/;
const VALID_TICKER_RE = /^[A-Z]{1,6}(\.[A-Z])?$/;

function handleTickerRoute(request: NextRequest): NextResponse | null {
  const pathname = request.nextUrl.pathname;
  const m = TICKER_PREFIX_RE.exec(pathname);
  if (!m) return null;
  const [, prefix, raw] = m;

  const upper = raw.toUpperCase();

  // Non-ticker symbol (template placeholder, garbage, or just gibberish).
  // Send to /search?q=<raw> so the visitor lands somewhere useful and
  // Google can crawl a 200 instead of a 404.
  if (!VALID_TICKER_RE.test(upper)) {
    const target = new URL("/search", request.url);
    // Don't URL-encode the placeholder twice — pass through whatever the
    // crawler had. If raw is literally "{search_term_string}", that's what
    // /search shows back as the "didn't look like a ticker" hint.
    target.searchParams.set("q", raw);
    return NextResponse.redirect(target, 308);
  }

  // Valid ticker but wrong case → canonicalise.
  const canonical = `/${prefix}/${upper}`;
  if (canonical === pathname) return null;
  const target = new URL(canonical, request.url);
  // Preserve query + hash so links like /t/aapl?ref=hn keep their UTM.
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
