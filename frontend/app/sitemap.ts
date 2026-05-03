import type { MetadataRoute } from "next";

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

  const staticEntries: MetadataRoute.Sitemap = [
    { url: `${base}/`,                          lastModified: now, priority: 1.0 },
    { url: `${base}/pricing`,                   lastModified: now, priority: 0.9 },
    { url: `${base}/how-it-works`,              lastModified: now, priority: 0.9 },
    { url: `${base}/scorecard`,                 lastModified: now, priority: 0.9 },
    { url: `${base}/blog`,                      lastModified: now, priority: 0.7 },
    { url: `${base}/changelog`,                 lastModified: now, priority: 0.6 },
    { url: `${base}/roadmap`,                   lastModified: now, priority: 0.6 },
    { url: `${base}/status`,                    lastModified: now, priority: 0.4 },
    { url: `${base}/compare/finviz`,            lastModified: now, priority: 0.7 },
    { url: `${base}/compare/zacks`,             lastModified: now, priority: 0.7 },
    { url: `${base}/compare/wallstreetzen`,     lastModified: now, priority: 0.7 },
    { url: `${base}/signin`,                    lastModified: now, priority: 0.4 },
    { url: `${base}/signup`,                    lastModified: now, priority: 0.6 },
    { url: `${base}/legal/risk`,                lastModified: now, priority: 0.3 },
    { url: `${base}/legal/terms`,               lastModified: now, priority: 0.3 },
    { url: `${base}/legal/privacy`,             lastModified: now, priority: 0.3 },
  ];

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

  return [...staticEntries, ...tickerEntries, ...postEntries];
}
