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

// Bound the upstream call. /api/public/signals does an ORDER BY score DESC
// over the full scored universe and can briefly stall (Neon scale-to-zero
// cold start or a heavy worker tick — observed >30s before recovering).
// Without a timeout the sitemap ISR regeneration inherits that stall, which
// can 5xx the /sitemap.xml route. That's a double miss: Google sees no
// sitemap, and the daily stale-link audit reads "sitemap_unavailable" so
// IndexNow submits nothing. An 8s cap lets a slow-but-fine call through while
// turning a true hang into a clean fallback. AbortSignal.timeout is not part
// of Next's fetch cache key, so the 1h ISR cache is preserved.
const UNIVERSE_TIMEOUT_MS = 8000;

// Full scored universe, symbols only. Deliberately the SAME source /stocks
// uses (app/stocks/page.tsx → fetchUniverse) so the sitemap and the HTML
// coverage directory can never drift: every /t/{symbol} we internally link
// from /stocks is also explicitly listed here for discovery + lastmod hints.
//
// 2026-06-01: switched from /api/public/top-tickers (hard-capped at 1,000 rows
// on the backend, ordered by score/$-volume) to /api/public/signals?limit=2000
// (the full universe). The old top-1,000 cut silently EXCLUDED real large-caps
// — e.g. SO (Southern Co), DUK (Duke Energy), AWK (American Water) — because
// they trade at lower dollar-volume than 1,000 higher-beta names, leaving
// their live, content-rich, index/follow /t/ pages stuck in GSC "Crawled -
// currently not indexed" with no sitemap reinforcement. Aligning the sitemap
// to the universe (itself the curated, actively-scored set, already fully
// linked from /stocks) is the logical completion of the 250→1000→"index
// everything" expansion. Both /api/public/* endpoints are no-auth and not
// tier-gated; /api/scanner would cap anonymous callers at the FREE-tier 20
// rows, defeating the SEO expansion entirely.
async function fetchUniverseSymbols(): Promise<string[]> {
  try {
    const res = await fetch(`${API_BASE}/api/public/signals?limit=2000`, {
      next: { revalidate: 3600 },
      signal: AbortSignal.timeout(UNIVERSE_TIMEOUT_MS),
    });
    if (!res.ok) return FALLBACK_TICKERS;
    const body = (await res.json()) as { items?: { symbol?: string }[] };
    const syms = (body.items ?? [])
      .map((i) => i.symbol)
      .filter((s): s is string => typeof s === "string" && s.length > 0);
    // De-dupe defensively — the feed is unique per symbol, but duplicate
    // <loc> entries are a sitemap-validity warning.
    const unique = Array.from(new Set(syms));
    return unique.length > 0 ? unique : FALLBACK_TICKERS;
  } catch {
    // Timeout / network error → fall back to the mega-cap list so the
    // sitemap still emits a valid (if smaller) document.
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
    // Daily-picks newsletter lead-magnet landing — preview of what
    // newsletter subscribers get. Refreshes every 30 min via ISR.
    { url: `${base}/daily-picks`,               lastModified: now, changeFrequency: "daily", priority: 0.9 },
    { url: `${base}/signals`,                   lastModified: now, changeFrequency: "daily", priority: 0.9 },
    // Stock coverage directory — the HTML-sitemap crawl path to EVERY scored
    // /t/{symbol} page (the /signals preview wall + top-20 sector hubs left the
    // long tail orphaned). Membership churns slowly via auto-discovery → daily.
    { url: `${base}/stocks`,                    lastModified: now, changeFrequency: "daily", priority: 0.8 },
    // Sector hub-of-hubs — shallow crawl entry point into the 11 /sector/{slug}
    // ranking pages (and onward to per-ticker pages). Aggregates change as
    // scores re-tick, so daily.
    { url: `${base}/sectors`,                   lastModified: now, changeFrequency: "daily", priority: 0.8 },
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
    { url: `${base}/compare/seeking-alpha`,     lastModified: STATIC_LAST_MODIFIED, priority: 0.8 },
    { url: `${base}/compare/stock-rover`,       lastModified: STATIC_LAST_MODIFIED, priority: 0.8 },
    { url: `${base}/compare/benzinga-pro`,      lastModified: STATIC_LAST_MODIFIED, priority: 0.8 },
    { url: `${base}/compare/stockcharts`,       lastModified: STATIC_LAST_MODIFIED, priority: 0.8 },
    // New competitor pages — 2026-05-20 expansion to cover the remaining
    // high-intent comparison clusters (free incumbent, broker-built scanners,
    // institutional pedigree, enterprise pricing anchor).
    { url: `${base}/compare/yahoo-finance`,     lastModified: STATIC_LAST_MODIFIED, priority: 0.8 },
    { url: `${base}/compare/webull`,            lastModified: STATIC_LAST_MODIFIED, priority: 0.8 },
    { url: `${base}/compare/robinhood`,         lastModified: STATIC_LAST_MODIFIED, priority: 0.8 },
    { url: `${base}/compare/marketsmith`,       lastModified: STATIC_LAST_MODIFIED, priority: 0.8 },
    { url: `${base}/compare/bloomberg-terminal`, lastModified: STATIC_LAST_MODIFIED, priority: 0.8 },
    // Listicle / best-of pages — top of the commercial-investigation funnel.
    { url: `${base}/best-finviz-alternatives`,  lastModified: STATIC_LAST_MODIFIED, priority: 0.8 },
    { url: `${base}/best-stock-scanners`,       lastModified: STATIC_LAST_MODIFIED, priority: 0.8 },
    // Feature landing pages — public surfaces for the gated /app/* tools.
    // High-intent keyword clusters: short squeeze, congress trades, insider
    // buying, market heatmap, market regime. Each ranks for the cluster +
    // converts to the matching tier via a tier-aware CTA.
    { url: `${base}/short-squeeze-scanner`,     lastModified: STATIC_LAST_MODIFIED, priority: 0.85 },
    { url: `${base}/congressional-trades`,      lastModified: STATIC_LAST_MODIFIED, priority: 0.85 },
    { url: `${base}/insider-buying`,            lastModified: STATIC_LAST_MODIFIED, priority: 0.85 },
    { url: `${base}/stock-market-heatmap`,      lastModified: STATIC_LAST_MODIFIED, priority: 0.85 },
    { url: `${base}/market-regime`,             lastModified: STATIC_LAST_MODIFIED, priority: 0.85 },
    // Free-tool / embed docs — backlink-acquisition asset. Every site that
    // pastes the iframe = one evergreen backlink to /t/{TICKER}. Indexed
    // intentionally (the embed views themselves are noindex; this docs
    // page IS the marketing landing page for the widget).
    { url: `${base}/embed`,                     lastModified: STATIC_LAST_MODIFIED, priority: 0.8 },
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

  // Per-ticker pages — the ENTIRE scored universe (~2,000), matching
  // /stocks and /api/public/signals exactly.
  //
  // 2026-05-24: reversed an earlier 250 cap after founder pushback ("i want
  // to be indexed for everything"), then capped at the top 1,000 by
  // $-volume. 2026-06-01: dropped the 1,000 cut entirely — it silently
  // excluded real large-caps (SO, DUK, AWK …) that happen to trade at lower
  // dollar-volume, stranding their /t/ pages in GSC "Crawled - not indexed."
  // Every page is already substantial enough for Google's quality classifier
  // to accept: /t/[symbol]/page.tsx → buildEditorialCommentary() auto-writes
  // a 200-400 word ticker-specific editorial paragraph from the live factor
  // sub-scores, alongside Related Tickers, the news-headlines feed, and FAQ.
  // The universe is the curated, actively-scored set (not a raw ticker dump),
  // and /stocks already internally links all of it, so listing it here just
  // reinforces discovery with per-URL lastmod hints.
  const tickers = await fetchUniverseSymbols();
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
