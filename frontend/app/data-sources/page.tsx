import Link from "next/link";
import { MarketingNav } from "@/components/MarketingNav";
import { MarketingFooter } from "@/components/MarketingFooter";
import { TransparencyStrip } from "@/components/TransparencyStrip";
import { pageMeta } from "@/lib/seo";

export const metadata = pageMeta({
  title: "Tapeline Data Categories — What Powers Every Score",
  description:
    "The data categories Tapeline uses to compute every score: live market data, fundamentals, macro indicators, SEC filings, Congressional disclosures, news, analyst ratings. Composite score and labels are Tapeline's own derived output.",
  path: "/data-sources",
});

type Category = {
  name: string;
  usedFor: string[];
  surfaceArea: string;
  refreshCadence: string;
  publicRecord: boolean;
};

// Vendor-agnostic data category list. We deliberately do not name specific
// providers on the public marketing surface — license terms vary by tier and
// vendor and the named-attribution version of this page (live until 2026-05-19)
// risked over-disclosing how we source data. Where a downstream display surface
// (e.g. an Analyst Ratings widget) needs vendor attribution for legal reasons,
// it's attributed at the point of display, not aggregated here.
const CATEGORIES: Category[] = [
  {
    name: "Live market data",
    usedFor: [
      "Equity + ETF prices, OHLC bars, volumes",
      "Trend and relative-strength calculations",
      "Heatmap tile sizing (dollar-volume weighted)",
      "Auto-discovery of the active US ticker universe",
    ],
    surfaceArea:
      "Every ticker price, every chart, every percentage change, the heatmap tiles, the scanner table.",
    refreshCadence: "Sub-60 seconds during US market hours.",
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
    refreshCadence: "Hourly cache, refreshed on next worker tick.",
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
    refreshCadence:
      "Form 4 daily for the top-liquidity universe. 8-Ks every 5 minutes.",
    publicRecord: true,
  },
  {
    name: "Congressional disclosures",
    usedFor: [
      "House + Senate financial disclosure filings",
      "Inputs to the Smart Money sub-factor",
    ],
    surfaceArea:
      "Congressional trades feed at /app/congress (Premium tier).",
    refreshCadence: "Daily.",
    publicRecord: true,
  },
  {
    name: "News wire",
    usedFor: [
      "Live cashtag-tagged headlines per ticker",
      "Sentiment-tagged headlines for the breaking-news bar",
    ],
    surfaceArea:
      "News bar on every dashboard page. Per-ticker news section on the ticker detail page.",
    refreshCadence: "Every ~5 minutes.",
    publicRecord: false,
  },
  {
    name: "Analyst ratings",
    usedFor: [
      "Consensus tally (Buy / Hold / Sell)",
      "Average price target + recent rating events",
    ],
    surfaceArea:
      "Analyst Ratings widget on Premium ticker pages. Not folded into the score — displayed as descriptive context only.",
    refreshCadence: "Cached 6 hours per ticker.",
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
via the published 6-factor formula at /how-it-works.

Tapeline is not a registered investment adviser. Everything on the platform is
descriptive analytics — see /legal/risk for the full disclosure.
`.trim();

export default function DataSourcesPage() {
  return (
    <main className="min-h-screen">
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
          computed via the published 6-factor formula at{" "}
          <Link href="/how-it-works" className="link">/how-it-works</Link>. Those
          numbers are Tapeline&rsquo;s analytical output — derived through
          transformation, not redistributed from any single source. The list
          below covers the underlying input categories.
        </p>
      </section>

      <section className="mx-auto max-w-4xl px-6 pb-16">
        <ol className="space-y-8">
          {CATEGORIES.map((c) => (
            <li key={c.name} className="card p-6">
              <div className="flex flex-wrap items-baseline justify-between gap-3">
                <h2 className="text-xl font-semibold">{c.name}</h2>
                {c.publicRecord ? (
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
