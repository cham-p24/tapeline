import type { MetadataRoute } from "next";
import { SECTORS } from "./sector/sectors";
import { SIGNALS } from "./signal/signals";
import { STRATEGIES } from "./best-stocks-for/[strategy]/strategies";

// Sitemap revalidates hourly so newly-discovered tickers reach Google within
// the day, without paying a DB roundtrip on every crawler hit.
export const revalidate = 3600;

// Hardcoded fallback if the API is unreachable during a build/regeneration.
// These are the top mega-caps + sector ETFs; the dynamic API call below
// expands to the top-500 by $-volume in normal operation.
const FALLBACK_TICKERS = [
  "AAPL", "MSFT", "NVDA", "GOOGL", "META", "AMZN", "TSLA", "AVGO", "ORCL", "AMD",
  "JPM", "BAC", "V", "MA", "BRK.B",
  "JNJ", "UNH", "LLY", "PFE",
  "XOM", "CVX",
  "WMT", "COST", "PG", "KO", "PEP", "MCD", "NKE", "SBUX",
  "BA", "CAT", "GE", "LMT",
  "DIS", "NFLX", "CRM", "ADBE",
  "SPY", "QQQ", "IWM", "DIA", "VTI", "SMH", "XLK", "XLF", "XLE", "XLV",
  "GLD", "SLV", "USO", "TLT",
];

const API_BASE =
  process.env.NEXT_PUBLIC_API_URL ||
  process.env.API_URL ||
  "https://api.tapeline.io";

async function fetchTopTickers(limit = 500): Promise<string[]> {
  try {
    // /api/public/top-tickers is the no-auth, no-tier-gating endpoint built
    // specifically for sitemap use. The /api/scanner endpoint caps anonymous
    // callers to the FREE-tier 20-row limit, which would defeat the SEO
    // expansion entirely.
    const res = await fetch(`${API_BASE}/api/public/top-tickers?limit=${limit}`, {
      next: { revalidate: 3600 },
    });
    if (!res.ok) return FALLBACK_TICKERS;
    const body = (await res.json()) as { symbols?: string[] };
    const syms = body.symbols ?? [];
    return syms.length > 0 ? syms : FALLBACK_TICKERS;
  } catch {
    return FALLBACK_TICKERS;
  }
}

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const base = process.env.NEXT_PUBLIC_APP_URL || "https://tapeline.io";
  const now = new Date();

  // Per-URL stable lastModified dates. Previously every entry used `now`,
  // which Google heuristics treat as "the whole site changed" — a signal
  // they're known to downweight (and a likely contributor to the 496
  // "Discovered / crawled but not indexed" pages in GSC, since the
  // sitemap was telling Google to recrawl static content multiple times
  // a day with no real changes). Use the last known revision date per
  // page; the daily-changing surfaces (scanner-derived: scorecard,
  // signals, sector, signal, strategy, ticker) keep changeFrequency=daily
  // so Google still revisits them.
  const STATIC_LAST_MODIFIED = new Date("2026-05-18");
  const LEGAL_LAST_MODIFIED = new Date("2026-05-17");   // privacy rewrite in PR #35
  const HOWITWORKS_LAST_MODIFIED = new Date("2026-05-17");

  const staticEntries: MetadataRoute.Sitemap = [
    { url: `${base}/`,                          lastModified: STATIC_LAST_MODIFIED, priority: 1.0 },
    { url: `${base}/pricing`,                   lastModified: STATIC_LAST_MODIFIED, priority: 0.9 },
    { url: `${base}/how-it-works`,              lastModified: HOWITWORKS_LAST_MODIFIED, priority: 0.9 },
    { url: `${base}/data-sources`,              lastModified: STATIC_LAST_MODIFIED, priority: 0.85 },
    // Scorecard is daily-refreshing (new top-10 picks every market close).
    { url: `${base}/scorecard`,                 lastModified: now, changeFrequency: "daily", priority: 0.9 },
    { url: `${base}/signals`,                   lastModified: now, changeFrequency: "daily", priority: 0.9 },
    { url: `${base}/about`,                     lastModified: STATIC_LAST_MODIFIED, priority: 0.8 },
    { url: `${base}/press`,                     lastModified: STATIC_LAST_MODIFIED, priority: 0.7 },
    { url: `${base}/blog`,                      lastModified: STATIC_LAST_MODIFIED, priority: 0.7 },
    { url: `${base}/changelog`,                 lastModified: STATIC_LAST_MODIFIED, priority: 0.6 },
    { url: `${base}/roadmap`,                   lastModified: STATIC_LAST_MODIFIED, priority: 0.6 },
    { url: `${base}/status`,                    lastModified: now, changeFrequency: "hourly", priority: 0.4 },
    // Comparison pages — high commercial-investigation intent.
    { url: `${base}/compare/finviz`,            lastModified: STATIC_LAST_MODIFIED, priority: 0.8 },
    { url: `${base}/compare/zacks`,             lastModified: STATIC_LAST_MODIFIED, priority: 0.8 },
    { url: `${base}/compare/wallstreetzen`,     lastModified: STATIC_LAST_MODIFIED, priority: 0.8 },
    { url: `${base}/compare/tradingview`,       lastModified: STATIC_LAST_MODIFIED, priority: 0.8 },
    { url: `${base}/compare/trade-ideas`,       lastModified: STATIC_LAST_MODIFIED, priority: 0.8 },
    { url: `${base}/compare/koyfin`,            lastModified: STATIC_LAST_MODIFIED, priority: 0.8 },
    { url: `${base}/compare/tipranks`,          lastModified: STATIC_LAST_MODIFIED, priority: 0.8 },
    { url: `${base}/compare/simply-wall-st`,    lastModified: STATIC_LAST_MODIFIED, priority: 0.8 },
    // Listicle / best-of pages — top of the commercial-investigation funnel.
    { url: `${base}/best-finviz-alternatives`,  lastModified: STATIC_LAST_MODIFIED, priority: 0.8 },
    { url: `${base}/best-stock-scanners`,       lastModified: STATIC_LAST_MODIFIED, priority: 0.8 },
    { url: `${base}/signup`,                    lastModified: STATIC_LAST_MODIFIED, priority: 0.6 },
    { url: `${base}/contact`,                   lastModified: STATIC_LAST_MODIFIED, priority: 0.4 },
    // /signin removed from sitemap — auth pages shouldn't be in search
    // indices. Same posture as the noindex on /app/*.
    { url: `${base}/legal/risk`,                lastModified: LEGAL_LAST_MODIFIED, priority: 0.3 },
    { url: `${base}/legal/terms`,               lastModified: LEGAL_LAST_MODIFIED, priority: 0.3 },
    { url: `${base}/legal/privacy`,             lastModified: LEGAL_LAST_MODIFIED, priority: 0.3 },
    { url: `${base}/legal/refund`,              lastModified: LEGAL_LAST_MODIFIED, priority: 0.3 },
    { url: `${base}/security`,                  lastModified: STATIC_LAST_MODIFIED, priority: 0.4 },
    { url: `${base}/support`,                   lastModified: STATIC_LAST_MODIFIED, priority: 0.4 },
  ];

  // Programmatic surface: one URL per sector and per signal level. Each
  // page renders a live snapshot ranking + methodology + FAQ. Cached 5 min.
  const sectorEntries: MetadataRoute.Sitemap = SECTORS.map((s) => ({
    url: `${base}/sector/${s.slug}`,
    lastModified: now,
    changeFrequency: "daily" as const,
    priority: 0.7,
  }));
  const signalEntries: MetadataRoute.Sitemap = SIGNALS.map((s) => ({
    url: `${base}/signal/${s.slug}`,
    lastModified: now,
    changeFrequency: "daily" as const,
    priority: 0.7,
  }));
  // Strategy listicle pages — /best-stocks-for/{day-traders, swing-traders,
  // momentum, dividend, value}. Each page sorts/filters the live scanner
  // differently so the table content is unique per slug (no dup-content risk).
  const strategyEntries: MetadataRoute.Sitemap = STRATEGIES.map((s) => ({
    url: `${base}/best-stocks-for/${s.slug}`,
    lastModified: now,
    changeFrequency: "daily" as const,
    priority: 0.8,
  }));

  const tickers = await fetchTopTickers(500);
  const tickerEntries: MetadataRoute.Sitemap = tickers.map((sym) => ({
    url: `${base}/t/${sym}`,
    lastModified: now,
    changeFrequency: "daily" as const,
    priority: 0.7,
  }));

  // Blog posts — pulled from the same manifest the /blog routes use so
  // adding a post automatically lands in the sitemap.
  const { POSTS } = await import("./blog/posts");
  const postEntries: MetadataRoute.Sitemap = POSTS.map((p) => ({
    url: `${base}/blog/${p.slug}`,
    lastModified: new Date(p.publishedAt),
    priority: 0.6,
  }));

  // Per-ticker SEO landing pages at /blog/ticker/{symbol} — long-tail
  // commercial-investigation traffic ("is AAPL a buy", "NVDA stock score 2026").
  // 50 hand-picked tickers from scripts/generate-ticker-posts.mjs. The page
  // template fetches live data per request with revalidate caching, so a
  // changeFrequency of "daily" matches the underlying signal cadence.
  const { TICKERS } = await import("./blog/ticker/tickers");
  const tickerPostEntries: MetadataRoute.Sitemap = TICKERS.map((t) => ({
    url: `${base}/blog/ticker/${t.symbol}`,
    lastModified: now,
    changeFrequency: "daily" as const,
    priority: 0.7,
  }));

  return [
    ...staticEntries,
    ...sectorEntries,
    ...signalEntries,
    ...strategyEntries,
    ...tickerEntries,
    ...postEntries,
    ...tickerPostEntries,
  ];
}
