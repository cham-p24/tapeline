import Link from "next/link";
import { MarketingNav } from "@/components/MarketingNav";
import { MarketingFooter } from "@/components/MarketingFooter";
import { TransparencyStrip } from "@/components/TransparencyStrip";
import { pageMeta } from "@/lib/seo";
import { PRICE_FRESHNESS_SENTENCE } from "@/lib/freshness";

export const metadata = pageMeta({
  title: "Tapeline Data Categories — What Powers Every Score",
  description:
    "The data categories Tapeline reads from: market data, fundamentals, macro indicators, SEC filings, news, analyst ratings. Composite score and labels are Tapeline's own derived output.",
  path: "/data-sources",
});

type Category = {
  name: string;
  usedFor: string[];
  surfaceArea: string;
  refreshCadence: string;
  publicRecord: boolean;
  /** A category we state as NOT available: rendered with no source badge. */
  unavailable?: boolean;
};

// Vendor-agnostic data category list. We deliberately do not name specific
// providers on the public marketing surface — license terms vary by tier and
// vendor and the named-attribution version of this page (live until 2026-05-19)
// risked over-disclosing how we source data. Where a downstream display surface
// (e.g. an Analyst Ratings widget) needs vendor attribution for legal reasons,
// it's attributed at the point of display, not aggregated here.
const CATEGORIES: Category[] = [
  {
    name: "Market data",
    usedFor: [
      "Equity + ETF prices, OHLC bars, volumes",
      "Trend and relative-strength calculations",
      "Heatmap tile sizing (dollar-volume weighted)",
      "Auto-discovery of the active US ticker universe",
    ],
    surfaceArea:
      "Every ticker price, every chart, every percentage change, the heatmap tiles, the scanner table.",
    // Measured 14 Sep 2026: the vendor snapshot was ~15 min behind and
    // worker passes landed 70-74 s apart. Daily bars are read once a day.
    refreshCadence: `${PRICE_FRESHNESS_SENTENCE} Daily OHLC bars (used for trend and relative strength) are read about once a day.`,
    publicRecord: false,
  },
  {
    name: "Fundamentals",
    usedFor: [
      "Per-ticker financial ratios (P/E, ROE, margins)",
      "Revenue and EPS growth",
      "Debt / equity, balance sheet health",
      "Company classification (sector backfill)",
    ],
    surfaceArea:
      "The Financials tab on every ticker page and the Fundamentals sub-factor in the score breakdown.",
    refreshCadence: "Refreshed on company filing cadence.",
    publicRecord: false,
  },
  {
    name: "Macro indicators",
    usedFor: [
      "10-year Treasury yield, DXY US Dollar Index, VIX",
      "Rate-direction classification (RISING / FALLING / SIDEWAYS)",
      "Inputs to the Macro sub-factor",
    ],
    surfaceArea:
      "The Regime tile on every dashboard page. The Macro sub-factor on every ticker. The Fear & Greed composite on /app/regime.",
    refreshCadence: "Daily readings: the VIX, 10-year yield and dollar index are end-of-day series, so the regime and Macro sub-factor usually change at most once a day.",
    publicRecord: true,
  },
  {
    name: "SEC filings",
    usedFor: [
      "Form 4 insider transactions (buys, sales, vesting)",
      "8-K material event filings (M&A, restatements, executive changes)",
      "CIK-to-ticker mapping",
    ],
    surfaceArea:
      "Recent insider buys feed at /app/holdings. Breaking-news bar 8-K alerts on dashboards.",
    // Form 4 cadence is the smart-money horizon in
    // backend/app/workers/signal_publisher.py (_EQUITY_FACTOR_DUE_AFTER, 36h,
    // on a 24h chain = re-read about every 48h; non-equities 30 days). It was
    // "daily" here while the real rotation was ~30 days (#822). The vendor's
    // own lag is larger: on 2026-09-14 its newest Form 4 for AAPL/NVDA/META
    // was 14/67/30 days behind SEC EDGAR's.
    refreshCadence:
      "Form 4 re-checked about every two days per stock (ETFs and other non-stocks about monthly), through a data vendor whose filings can run weeks behind SEC EDGAR. 8-Ks every 5 minutes.",
    publicRecord: true,
  },
  {
    // Integrity fix (founder-approved 2026-09-14). This entry used to say
    // congressional disclosures fed the Smart Money sub-factor and that
    // /app/congress showed "previously collected disclosures". Neither is
    // true today: every congress_trades row is mock output (filtered out by
    // backend/app/services/congress_integrity.py), there is no current source
    // of congressional disclosures, and the Smart Money factor reads SEC
    // Form 4 (see /how-it-works). Stated as unavailable rather
    // than silently dropped, so nobody reads the absence as an omission.
    // copy-compliance-allow unbacked-feature-claim -- the entry states the data is NOT available
    name: "Congressional disclosures (not available)",
    usedFor: ["Nothing today"],
    surfaceArea:
      "None. We don't currently have a real source of congressional trade disclosures, so we don't show any, and none feed the score.",
    refreshCadence: "Not applicable.",
    publicRecord: false,
    unavailable: true,
  },
  {
    name: "News wire",
    usedFor: [
      "Cashtag-tagged headlines per ticker",
      "Sentiment-tagged headlines for the breaking-news bar",
    ],
    surfaceArea:
      "News bar on every dashboard page. Per-ticker news section on the ticker detail page.",
    refreshCadence: "Every ~5 minutes.",
    publicRecord: false,
  },
  {
    // Truth check (2026-08-23): only the aggregate Buy/Hold/Sell tally is on
    // Tapeline's current data plan. Per-firm rating events and price targets
    // (including any "average price target") are a paid upstream endpoint we
    // do not subscribe to — the backend always returns avg_pt: null and
    // events: [] (backend/app/services/finnhub_feed.py,
    // fetch_analyst_recommendations), and the ticker key-stats endpoint
    // deliberately omits the 1-year price target for the same reason
    // (backend/app/routers/ticker.py). Cache TTL mirrors
    // CACHE_TTL_RECS_HOURS = 12.
    name: "Analyst ratings",
    usedFor: [
      "Consensus tally (Buy / Hold / Sell)",
    ],
    surfaceArea:
      "Analyst Ratings widget on Premium ticker pages. Not folded into the score — displayed as descriptive context only. Per-firm rating events and price targets are not on Tapeline's current data plan and are not shown.",
    refreshCadence: "Cached 12 hours per ticker.",
    publicRecord: false,
  },
];

const TRANSPARENCY_NOTE = `
Tapeline reads from several categories of market and reference data, transforms
it through a 6-factor scoring formula, and surfaces the result. The categories
above describe what each input is used for and where it appears in the product.

Where Tapeline displays a number that came directly from an upstream feed (a
price, a P/E ratio, an analyst rating), the displayed value is the upstream
value at the time of the most recent refresh. Where Tapeline displays its own
derived metric (the composite score, the sub-scores, the signal label, the
plain-English "why" sentence), that's Tapeline's own analytical output computed
via the published six-factor methodology at /how-it-works (the six factors are
named there, along with which carry the most weight).

Tapeline is not a registered investment adviser. Everything on the platform is
descriptive analytics — see /legal/risk for the full disclosure.
`.trim();

export default function DataSourcesPage() {
  return (
    <main id="main" className="min-h-screen">
      <MarketingNav />

      <section className="mx-auto max-w-4xl px-6 py-8">
        <p className="eyebrow">Data categories</p>
        <h1 className="mt-3 text-4xl sm:text-5xl font-bold tracking-tight">
          What powers Tapeline.
        </h1>
        <p className="mt-4 text-lg text-muted">
          The data categories Tapeline reads from, the surface area where each
          one appears, and the refresh cadence. No black boxes, no
          &ldquo;proprietary data&rdquo; vague-speak.
        </p>
        <p className="mt-3 text-sm text-subtle">
          The Tapeline composite score and the per-factor sub-scores are
          computed via the published six-factor methodology at{" "}
          <Link href="/how-it-works" className="link">/how-it-works</Link>. Those
          numbers are Tapeline&rsquo;s analytical output — derived through
          transformation, not redistributed from any single source. The list
          below covers the underlying input categories.
        </p>
      </section>

      <section className="mx-auto max-w-4xl px-6 pb-16">
        <ol className="divide-y divide-border/60 border-t border-border/60">
          {CATEGORIES.map((c) => (
            <li key={c.name} className="py-8">
              <div className="flex flex-wrap items-baseline justify-between gap-3">
                <h2 className="text-xl font-semibold">{c.name}</h2>
                {c.unavailable ? null : c.publicRecord ? (
                  <span className="rounded-full border border-up/30 bg-up/10 px-2 py-0.5 text-[10px] uppercase tracking-wider text-up">
                    Public record
                  </span>
                ) : (
                  <span className="rounded-full border border-muted/30 bg-muted/10 px-2 py-0.5 text-[10px] uppercase tracking-wider text-muted">
                    Market data
                  </span>
                )}
              </div>

              <div className="mt-4 grid gap-4 text-sm sm:grid-cols-2">
                <div>
                  <h3 className="text-[10px] uppercase tracking-wider text-subtle">What it&rsquo;s used for</h3>
                  <ul className="mt-1 space-y-1 text-muted">
                    {c.usedFor.map((u) => (
                      <li key={u} className="flex gap-2">
                        <span className="text-accent select-none">·</span>
                        <span>{u}</span>
                      </li>
                    ))}
                  </ul>
                </div>
                <div>
                  <h3 className="text-[10px] uppercase tracking-wider text-subtle">Where it appears</h3>
                  <p className="mt-1 text-muted leading-relaxed">{c.surfaceArea}</p>
                  <h3 className="mt-3 text-[10px] uppercase tracking-wider text-subtle">Refresh cadence</h3>
                  <p className="mt-1 text-muted">{c.refreshCadence}</p>
                </div>
              </div>
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
