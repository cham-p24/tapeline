import type { MetadataRoute } from "next";

// Tickers that get explicit sitemap entries. Picks up search demand for
// "[TICKER] stock score" type queries on the most-Googled symbols.
// Google's sitemap limit is 50,000 URLs — could expand later by reading
// the live ticker universe, but this seeds the discovery loop without
// blowing up the sitemap file.
const SITEMAP_TICKERS = [
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

export default function sitemap(): MetadataRoute.Sitemap {
  const base = process.env.NEXT_PUBLIC_APP_URL || "https://tapeline.io";
  const now = new Date();

  const staticEntries: MetadataRoute.Sitemap = [
    { url: `${base}/`,                          lastModified: now, priority: 1.0 },
    { url: `${base}/pricing`,                   lastModified: now, priority: 0.9 },
    { url: `${base}/how-it-works`,              lastModified: now, priority: 0.9 },
    { url: `${base}/scorecard`,                 lastModified: now, priority: 0.9 },
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

  const tickerEntries: MetadataRoute.Sitemap = SITEMAP_TICKERS.map((sym) => ({
    url: `${base}/t/${sym}`,
    lastModified: now,
    changeFrequency: "daily" as const,
    priority: 0.7,
  }));

  return [...staticEntries, ...tickerEntries];
}
