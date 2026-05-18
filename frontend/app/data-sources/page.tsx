import Link from "next/link";
import { MarketingNav } from "@/components/MarketingNav";
import { MarketingFooter } from "@/components/MarketingFooter";
import { TransparencyStrip } from "@/components/TransparencyStrip";
import { pageMeta } from "@/lib/seo";

export const metadata = pageMeta({
  title: "Tapeline Data Sources — What Powers Every Score, Honestly",
  description:
    "Every data feed Tapeline reads from, what it's used for, and the license posture. Polygon/Massive for prices, Finnhub for fundamentals, SEC EDGAR for filings, FRED for macro, Benzinga for news. No hidden vendors, no embellishment.",
  path: "/data-sources",
});

type Source = {
  name: string;
  url: string;
  usedFor: string[];
  surfaceArea: string;          // where in the product this shows up
  refreshCadence: string;
  publicDomain: boolean;        // FRED + SEC = true; rest = no
  note?: string;                // optional flavour / caveat
};

const SOURCES: Source[] = [
  {
    name: "Massive (formerly Polygon.io)",
    url: "https://massive.com",
    usedFor: [
      "Live equity + ETF prices",
      "OHLC bars for trend / RS / momentum calculations",
      "Volume + dollar-volume for the heatmap tile sizing",
      "Auto-discovery of the active US ticker universe",
    ],
    surfaceArea: "Every ticker price you see, every chart, every percentage change, the heatmap tiles, the scanner table",
    refreshCadence: "Sub-60 seconds for live prices; weekly for the ticker universe walk",
    publicDomain: false,
    note: "Stocks Starter tier ($29/mo). Data is delayed ~15 minutes on this tier — the 'live' badge reflects scanner-tick freshness, not exchange real-time.",
  },
  {
    name: "Finnhub",
    url: "https://finnhub.io",
    usedFor: [
      "Per-ticker fundamentals (P/E, ROE, margins, growth rates)",
      "SEC Form 4 insider transactions",
      "Upcoming earnings + IPO calendar",
      "Company profile / sector classification (backfill)",
    ],
    surfaceArea: "The Financials tab on every ticker page, the Insider activity tab, the recent insider buys feed at /app/holdings, /app/earnings, /app/ipos, the sector label on the heatmap",
    refreshCadence: "Fundamentals refresh weekly. Form 4 transactions refresh daily for the top ~2,500 most-liquid tickers. Calendars refresh twice daily.",
    publicDomain: false,
    note: "Free tier (60 calls/min). Falls back to empty cards if the upstream key is unset.",
  },
  {
    name: "SEC EDGAR (direct)",
    url: "https://www.sec.gov/cgi-bin/browse-edgar",
    usedFor: [
      "Real-time 8-K material event filings",
      "CIK → ticker symbol mapping (for cross-referencing)",
    ],
    surfaceArea: "The breaking-news bar on every dashboard page tagged 'SEC EDGAR'. Material event filings (M&A announcements, earnings restatements, executive changes) appear here ~5-30 minutes before they're re-reported by the news wires.",
    refreshCadence: "Every 5 minutes alongside the news refresh",
    publicDomain: true,
    note: "US government public record. Free, no key, no licensing.",
  },
  {
    name: "FRED (Federal Reserve Economic Data)",
    url: "https://fred.stlouisfed.org",
    usedFor: [
      "10-year Treasury yield",
      "DXY US Dollar Index",
      "VIX volatility index",
      "Rate-direction inference (RISING / FALLING / SIDEWAYS)",
    ],
    surfaceArea: "The Regime tile on every dashboard page. The Macro sub-factor on every ticker score. The 'Fear & Greed' composite on /app/regime.",
    refreshCadence: "Cached 1 hour, refreshed on the next worker tick",
    publicDomain: true,
    note: "US Federal Reserve public data. Free, no licensing restrictions.",
  },
  {
    name: "Benzinga",
    url: "https://www.benzinga.com",
    usedFor: [
      "Live news wire with cashtag tagging",
      "Analyst consensus ratings (Buy/Hold/Sell tally, avg price target)",
    ],
    surfaceArea: "The breaking-news bar headlines tagged 'Benzinga'. The Analyst Ratings widget on Premium ticker pages.",
    refreshCadence: "News every 5 minutes. Analyst ratings cached 6 hours per ticker.",
    publicDomain: false,
    note: "Tapeline prefers Benzinga over Massive for news quality. Falls back to Massive cleanly if Benzinga is unreachable.",
  },
  {
    name: "Signal-system (the founder's research workbook)",
    url: "",
    usedFor: [
      "Composite ticker scoring (6-factor blend)",
      "Smart Money sub-score (Congressional + insider activity)",
      "Market regime label (BULL / NEUTRAL / CAUTIOUS / BEAR)",
      "ETF benchmark classifications",
    ],
    surfaceArea: "The composite 0-100 score on every ticker page, scanner row, and watchlist item. The signal label (HIGH CONVICTION / STRONG SETUP / etc.). The Regime tile.",
    refreshCadence: "Tapeline pulls the signal-system's published Google Sheet via CSV every 5 minutes",
    publicDomain: false,
    note: "Tapeline reads the founder's personal research workbook. The signal-system project is separate from Tapeline (lives at C:\\signal-system\\ on the founder's machine, not part of this repo).",
  },
];

const TRANSPARENCY_NOTE = `
Tapeline is built and run by one person. The product reads data from several
public and licensed feeds, transforms it through a 6-factor scoring formula,
and surfaces the result. The page above lists every feed honestly — what it's
used for, where it shows up, how often it refreshes. No hidden vendors, no
"proprietary data" hand-waving.

Where Tapeline displays a number that came directly from a vendor (a price, a
P/E ratio, an analyst rating), the vendor is named in the surface area
column above. Where Tapeline displays its own derived metric (the composite
score, the sub-scores, the signal label, the plain-English "why" sentence),
that's Tapeline's own analytical output computed via the published 6-factor
formula at /how-it-works.

If you're a vendor and you'd like Tapeline to credit you differently, drop a
line to support@tapeline.io. Page is editable on every release.
`.trim();

export default function DataSourcesPage() {
  return (
    <main className="min-h-screen">
      <MarketingNav />

      <section className="mx-auto max-w-4xl px-6 py-12">
        <p className="eyebrow">Data sources</p>
        <h1 className="mt-3 text-4xl sm:text-5xl font-bold tracking-tight">
          What powers Tapeline.
        </h1>
        <p className="mt-4 text-lg text-muted">
          Every data feed Tapeline reads from, the surface area where it appears,
          and the refresh cadence. No black boxes, no &ldquo;proprietary data&rdquo; vague-speak.
        </p>
        <p className="mt-3 text-sm text-subtle">
          The Tapeline composite score and the per-factor sub-scores are computed via the
          published 6-factor formula at{" "}
          <Link href="/how-it-works" className="link">/how-it-works</Link>. Those numbers are
          Tapeline&rsquo;s analytical output — derived through transformation, not redistributed
          from any single vendor. The list below covers the underlying inputs.
        </p>
      </section>

      <section className="mx-auto max-w-4xl px-6 pb-16">
        <ol className="space-y-8">
          {SOURCES.map((s) => (
            <li key={s.name} className="card p-6">
              <div className="flex flex-wrap items-baseline justify-between gap-3">
                <h2 className="text-xl font-semibold">{s.name}</h2>
                {s.publicDomain ? (
                  <span className="rounded-full border border-up/30 bg-up/10 px-2 py-0.5 text-[10px] uppercase tracking-wider text-up">
                    Public domain
                  </span>
                ) : (
                  <span className="rounded-full border border-muted/30 bg-muted/10 px-2 py-0.5 text-[10px] uppercase tracking-wider text-muted">
                    Licensed
                  </span>
                )}
              </div>
              {s.url && (
                <a
                  href={s.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="mt-1 inline-block text-xs text-accent hover:underline"
                >
                  {s.url.replace(/^https?:\/\//, "")} ↗
                </a>
              )}

              <div className="mt-4 grid gap-4 text-sm sm:grid-cols-2">
                <div>
                  <h3 className="text-[10px] uppercase tracking-wider text-subtle">What it's used for</h3>
                  <ul className="mt-1 space-y-1 text-muted">
                    {s.usedFor.map((u) => (
                      <li key={u} className="flex gap-2">
                        <span className="text-accent select-none">·</span>
                        <span>{u}</span>
                      </li>
                    ))}
                  </ul>
                </div>
                <div>
                  <h3 className="text-[10px] uppercase tracking-wider text-subtle">Where it appears</h3>
                  <p className="mt-1 text-muted leading-relaxed">{s.surfaceArea}</p>
                  <h3 className="mt-3 text-[10px] uppercase tracking-wider text-subtle">Refresh cadence</h3>
                  <p className="mt-1 text-muted">{s.refreshCadence}</p>
                </div>
              </div>

              {s.note && (
                <p className="mt-4 rounded-md bg-panel/60 p-3 text-xs text-muted leading-relaxed">
                  {s.note}
                </p>
              )}
            </li>
          ))}
        </ol>

        <div className="mt-12 rounded-xl bg-panel/60 p-6">
          <h2 className="text-lg font-semibold">Transparency note</h2>
          <p className="mt-3 text-sm text-muted whitespace-pre-line leading-relaxed">
            {TRANSPARENCY_NOTE}
          </p>
        </div>

        <div className="mt-8 flex flex-wrap gap-3 text-sm">
          <Link href="/how-it-works" className="link">← How the score is calculated</Link>
          <span className="text-subtle">·</span>
          <Link href="/scorecard" className="link">Public scorecard →</Link>
          <span className="text-subtle">·</span>
          <Link href="/changelog" className="link">Changelog →</Link>
        </div>
      </section>

      <TransparencyStrip current="/data-sources" />
      <MarketingFooter />
    </main>
  );
}
