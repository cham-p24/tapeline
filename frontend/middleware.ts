import { NextResponse, type NextRequest } from "next/server";

/**
 * Tapeline edge middleware — three responsibilities:
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
 * 3. IndexNow key serving at /<INDEXNOW_KEY>.txt. The Bing/Yandex
 *    IndexNow protocol requires the key as plaintext at that exact
 *    URL. Serving it dynamically from env keeps the key out of git
 *    history.
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

function handleAuth(request: NextRequest) {
  const pathname = request.nextUrl.pathname;

  // IndexNow key verification. Spec requires the file at
  //   https://<host>/<KEY>.txt
  // with the key as plaintext content. The regex narrows to hex
  // strings 8-128 chars long so legitimate .txt files (robots.txt,
  // ads.txt, etc.) never collide here.
  const indexnowMatch = pathname.match(/^\/([a-f0-9]{8,128})\.txt$/i);
  if (indexnowMatch) {
    const key = process.env.INDEXNOW_KEY;
    if (key && indexnowMatch[1] === key) {
      return new NextResponse(key, {
        status: 200,
        headers: {
          "Content-Type": "text/plain; charset=utf-8",
          "Cache-Control": "public, max-age=3600",
        },
      });
    }
    // Anything matching the .txt key shape but NOT our key gets a
    // clean 404 rather than a generic Next.js page.
    return new NextResponse("Not Found", { status: 404 });
  }

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
  // Run on every non-static page (locale needs to refresh anywhere)
  // PLUS any single-segment hex .txt path (IndexNow). The first
  // matcher excludes _next assets + favicon; the second matcher is
  // more specific and overlaps cleanly because middleware is
  // de-duplicated per-request.
  matcher: [
    "/((?!_next/static|_next/image|favicon.ico|.*\\..*).*)",
    "/:key([a-fA-F0-9]{8,128}).txt",
  ],
};
